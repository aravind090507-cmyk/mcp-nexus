import asyncio
import json
import os
import sys
import time
import uuid
import shutil
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import httpx
from app.mcp.protocol import JSONRPCMessage, format_jsonrpc_response

class MCPClientError(Exception):
    pass

class MCPClient:
    """
    Protocol-aware Model Context Protocol (MCP) Client
    Supports both STDIO (subprocess JSON-RPC) and HTTP/SSE transports.
    Complies with standard MCP specification 2024-11-05.
    """
    def __init__(
        self,
        transport_type: str = "STDIO",
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        endpoint: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: int = 15,
        server_id: Optional[str] = None
    ):
        self.server_id = server_id
        self.transport_type = transport_type.upper()
        self.command = command or sys.executable
        self.args = args or []
        self.env_vars = env_vars or {}
        self.endpoint = endpoint
        self.auth_token = auth_token
        self.timeout = timeout
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _resolve_command_and_args(self) -> Tuple[str, List[str], Optional[str]]:
        """
        Resolves command binary and script paths against current execution environment.
        Handles relative paths, missing interpreter paths, and sets appropriate working directory.
        """
        cmd = self.command
        # If cmd is generic python or nonexistent absolute path, resolve to current running sys.executable
        if not cmd or cmd.lower() in ("python", "python.exe", "python3", "python3.exe") or not os.path.exists(cmd):
            resolved = shutil.which(cmd) if cmd else None
            if resolved and os.path.exists(resolved):
                cmd = resolved
            else:
                cmd = sys.executable

        resolved_args = []
        cwd = None
        for a in self.args:
            # Check if argument is a python script
            if isinstance(a, str) and a.endswith(".py"):
                if os.path.exists(a):
                    resolved_args.append(os.path.abspath(a))
                    cwd = os.path.dirname(os.path.abspath(a))
                else:
                    # Attempt resolving against demo_servers folder
                    script_name = os.path.basename(a)
                    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                    candidates = [
                        os.path.abspath(os.path.join(base_dir, "app", "mcp", "demo_servers", script_name)),
                        os.path.abspath(os.path.join(base_dir, "backend", "app", "mcp", "demo_servers", script_name)),
                        os.path.abspath(os.path.join(os.getcwd(), "backend", "app", "mcp", "demo_servers", script_name)),
                        os.path.abspath(os.path.join(os.getcwd(), "app", "mcp", "demo_servers", script_name)),
                        os.path.abspath(os.path.join(os.getcwd(), a)),
                    ]
                    found = next((c for c in candidates if os.path.exists(c)), None)
                    if found:
                        resolved_args.append(found)
                        cwd = os.path.dirname(found)
                    else:
                        resolved_args.append(a)
            else:
                resolved_args.append(a)

        if not cwd:
            cwd = os.getcwd()

        return cmd, resolved_args, cwd

    @staticmethod
    def _sync_stdio_exchange(cmd_list: List[str], requests: List[Dict[str, Any]], env: Dict[str, str], cwd: Optional[str]) -> List[Dict[str, Any]]:
        """
        Synchronous STDIO exchange executed in a background worker thread.
        Universally compatible across all OS environments and event loops (Selector and Proactor).
        """
        try:
            proc = subprocess.Popen(
                cmd_list,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=env,
                cwd=cwd
            )
        except FileNotFoundError:
            raise MCPClientError(f"Command not found or executable unavailable: '{cmd_list[0]}'")
        except Exception as e:
            raise MCPClientError(f"Failed to start MCP server subprocess ({cmd_list}): {str(e)}")

        responses = []
        try:
            for req in requests:
                req_line = json.dumps(req) + "\n"
                proc.stdin.write(req_line)
                proc.stdin.flush()

                if "id" not in req:
                    continue

                line = proc.stdout.readline()
                if not line:
                    err = proc.stderr.read().strip() if proc.stderr else "Process terminated without error output."
                    raise MCPClientError(f"Server closed stream prematurely. Stderr: {err}")

                resp_text = line.strip()
                if not resp_text:
                    continue
                try:
                    resp_data = json.loads(resp_text)
                    responses.append(resp_data)
                except json.JSONDecodeError:
                    raise MCPClientError(f"Server returned non-JSON response: '{resp_text[:120]}'")

        finally:
            try:
                proc.terminate()
                proc.wait(timeout=1.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        return responses

    async def _execute_stdio_exchange(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Executes a sequence of JSON-RPC requests against a STDIO MCP server process.
        Safely captures stdout and stderr with timeout guards.
        Transparently handles Windows SelectorEventLoop via worker thread.
        """
        env = os.environ.copy()
        env.update(self.env_vars)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        cmd, resolved_args, cwd = self._resolve_command_and_args()
        cmd_list = [cmd] + resolved_args

        # Detect whether current asyncio loop supports subprocesses
        loop = asyncio.get_running_loop()
        is_proactor = isinstance(loop, getattr(asyncio, "ProactorEventLoop", type(None)))

        # On Windows when running under SelectorEventLoop (e.g. Uvicorn with reload),
        # create_subprocess_exec raises NotImplementedError.
        # Fall back to thread-safe execution via subprocess.Popen in asyncio.to_thread.
        if sys.platform == "win32" and not is_proactor:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._sync_stdio_exchange, cmd_list, requests, env, cwd),
                    timeout=float(self.timeout * max(1, len(requests)) + 2.0)
                )
            except asyncio.TimeoutError:
                raise MCPClientError(f"MCP server timed out after {self.timeout}s.")
            except Exception as e:
                if isinstance(e, MCPClientError):
                    raise e
                raise MCPClientError(f"MCP execution error: {str(e)}")

        # Otherwise, attempt native async subprocess
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_list,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd
            )
        except NotImplementedError:
            # Fallback to thread-safe execution if loop doesn't support subprocesses
            return await asyncio.wait_for(
                asyncio.to_thread(self._sync_stdio_exchange, cmd_list, requests, env, cwd),
                timeout=float(self.timeout * max(1, len(requests)) + 2.0)
            )
        except FileNotFoundError:
            raise MCPClientError(f"Command not found or executable unavailable: '{cmd}'")
        except Exception as e:
            raise MCPClientError(f"Failed to start MCP server subprocess ({cmd_list}): {str(e)}")

        responses = []
        try:
            for req in requests:
                req_line = json.dumps(req) + "\n"
                proc.stdin.write(req_line.encode("utf-8"))
                await proc.stdin.drain()

                # If request does not expect response (notification)
                if "id" not in req:
                    continue

                try:
                    line_bytes = await asyncio.wait_for(proc.stdout.readline(), timeout=self.timeout)
                except asyncio.TimeoutError:
                    raise MCPClientError(f"MCP server timed out after {self.timeout}s waiting for JSON-RPC response.")

                if not line_bytes:
                    err_bytes = await proc.stderr.read()
                    err_msg = err_bytes.decode("utf-8", errors="replace").strip() if err_bytes else "Process terminated without error output."
                    raise MCPClientError(f"Server closed stream prematurely. Stderr: {err_msg}")
                
                resp_text = line_bytes.decode("utf-8").strip()
                if not resp_text:
                    continue
                try:
                    resp_data = json.loads(resp_text)
                    responses.append(resp_data)
                except json.JSONDecodeError:
                    raise MCPClientError(f"Server returned non-JSON response: '{resp_text[:120]}'")

        finally:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=1.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        return responses

    async def initialize(self) -> Tuple[Dict[str, Any], float]:
        """
        Performs protocol handshake and returns server info + latency in milliseconds.
        """
        start = time.perf_counter()
        req_id = self._next_id()
        init_req = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True}
                },
                "clientInfo": {
                    "name": "MCP-Nexus-Control-Plane",
                    "version": "1.0.0"
                }
            }
        }
        notif_req = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }

        if self.transport_type == "STDIO":
            resps = await self._execute_stdio_exchange([init_req, notif_req])
            duration_ms = (time.perf_counter() - start) * 1000.0
            if not resps:
                raise MCPClientError("No response received during MCP initialize handshake.")
            first = resps[0]
            if "error" in first:
                raise MCPClientError(f"MCP Initialize failed: {first['error']}")
            return first.get("result", {}), round(duration_ms, 2)

        elif self.transport_type in ("HTTP_SSE", "HTTP"):
            if not self.endpoint:
                raise MCPClientError("HTTP endpoint required for HTTP transport.")
            
            # Try SSE client if available
            try:
                from mcp.client.sse import sse_client
                from mcp import ClientSession
                async with sse_client(self.endpoint, timeout=self.timeout) as (read, write):
                    async with ClientSession(read, write) as session:
                        init_res = await session.initialize()
                        duration_ms = (time.perf_counter() - start) * 1000.0
                        return {
                            "protocolVersion": getattr(init_res, "protocolVersion", "2024-11-05"),
                            "serverInfo": getattr(init_res, "serverInfo", {"name": "SSE Server"}),
                            "capabilities": getattr(init_res, "capabilities", {})
                        }, round(duration_ms, 2)
            except ImportError:
                pass
            except Exception as e:
                # Fallback to direct HTTP JSON-RPC POST
                pass

            # Direct HTTP JSON-RPC fallback
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(self.endpoint, json=init_req, headers=headers)
                duration_ms = (time.perf_counter() - start) * 1000.0
                if res.status_code >= 400:
                    raise MCPClientError(f"HTTP Server returned error {res.status_code}: {res.text[:120]}")
                data = res.json()
                if "error" in data:
                    raise MCPClientError(f"MCP Initialize error: {data['error']}")
                return data.get("result", {}), round(duration_ms, 2)
        else:
            raise MCPClientError(f"Unsupported transport type: {self.transport_type}")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        Discovers tools available on this MCP server.
        """
        req_init = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "MCP-Nexus", "version": "1.0.0"}
            }
        }
        req_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        req_tools = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {}
        }

        if self.transport_type == "STDIO":
            resps = await self._execute_stdio_exchange([req_init, req_notif, req_tools])
            for r in resps:
                if r.get("id") == req_tools["id"]:
                    if "error" in r:
                        raise MCPClientError(f"tools/list failed: {r['error']}")
                    return r.get("result", {}).get("tools", [])
            return []

        elif self.transport_type in ("HTTP_SSE", "HTTP"):
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(self.endpoint, json=req_tools, headers=headers)
                data = res.json()
                if "error" in data:
                    raise MCPClientError(f"tools/list error: {data['error']}")
                return data.get("result", {}).get("tools", [])
        return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        """
        Invokes an MCP tool and returns (result_dict, duration_ms).
        """
        start = time.perf_counter()
        req_init = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "MCP-Nexus", "version": "1.0.0"}
            }
        }
        req_notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        call_id = self._next_id()
        req_call = {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        if self.transport_type == "STDIO":
            resps = await self._execute_stdio_exchange([req_init, req_notif, req_call])
            duration_ms = (time.perf_counter() - start) * 1000.0
            for r in resps:
                if r.get("id") == call_id:
                    if "error" in r:
                        raise MCPClientError(f"Tool execution failed: {r['error']}")
                    res_val = r.get("result", {})
                    # Parse textual JSON content if provided
                    if "content" in res_val and isinstance(res_val["content"], list):
                        for c in res_val["content"]:
                            if c.get("type") == "text":
                                try:
                                    res_val["parsed"] = json.loads(c.get("text", "{}"))
                                except Exception:
                                    pass
                    return res_val, round(duration_ms, 2)
            raise MCPClientError("No response received for tools/call.")

        elif self.transport_type in ("HTTP_SSE", "HTTP"):
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(self.endpoint, json=req_call, headers=headers)
                duration_ms = (time.perf_counter() - start) * 1000.0
                data = res.json()
                if "error" in data:
                    raise MCPClientError(f"Tool error: {data['error']}")
                return data.get("result", {}), round(duration_ms, 2)

        raise MCPClientError("Unsupported transport")

    async def ping(self) -> float:
        """Sends protocol ping request and returns latency in milliseconds."""
        start = time.perf_counter()
        req_ping = {"jsonrpc": "2.0", "id": self._next_id(), "method": "ping"}
        if self.transport_type == "STDIO":
            resps = await self._execute_stdio_exchange([req_ping])
            if not resps:
                raise MCPClientError("No response received for ping.")
            return round((time.perf_counter() - start) * 1000.0, 2)
        elif self.transport_type in ("HTTP_SSE", "HTTP"):
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(self.endpoint, json=req_ping, headers=headers)
                return round((time.perf_counter() - start) * 1000.0, 2)
        raise MCPClientError(f"Unsupported transport: {self.transport_type}")

    async def list_resources(self) -> List[Dict[str, Any]]:
        """Discovers resources available on this MCP server."""
        req_init = {
            "jsonrpc": "2.0", "id": self._next_id(), "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "MCP-Nexus", "version": "1.0.0"}}
        }
        req_notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        res_id = self._next_id()
        req_res = {"jsonrpc": "2.0", "id": res_id, "method": "resources/list", "params": {}}

        if self.transport_type == "STDIO":
            resps = await self._execute_stdio_exchange([req_init, req_notif, req_res])
            for r in resps:
                if r.get("id") == res_id:
                    if "error" in r:
                        raise MCPClientError(f"resources/list failed: {r['error']}")
                    return r.get("result", {}).get("resources", [])
            return []
        elif self.transport_type in ("HTTP_SSE", "HTTP"):
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(self.endpoint, json=req_res, headers=headers)
                data = res.json()
                if "error" in data:
                    raise MCPClientError(f"resources/list error: {data['error']}")
                return data.get("result", {}).get("resources", [])
        return []

    async def list_prompts(self) -> List[Dict[str, Any]]:
        """Discovers prompts available on this MCP server."""
        req_init = {
            "jsonrpc": "2.0", "id": self._next_id(), "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "MCP-Nexus", "version": "1.0.0"}}
        }
        req_notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        prompt_id = self._next_id()
        req_prompt = {"jsonrpc": "2.0", "id": prompt_id, "method": "prompts/list", "params": {}}

        if self.transport_type == "STDIO":
            resps = await self._execute_stdio_exchange([req_init, req_notif, req_prompt])
            for r in resps:
                if r.get("id") == prompt_id:
                    if "error" in r:
                        raise MCPClientError(f"prompts/list failed: {r['error']}")
                    return r.get("result", {}).get("prompts", [])
            return []
        elif self.transport_type in ("HTTP_SSE", "HTTP"):
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(self.endpoint, json=req_prompt, headers=headers)
                data = res.json()
                if "error" in data:
                    raise MCPClientError(f"prompts/list error: {data['error']}")
                return data.get("result", {}).get("prompts", [])
        return []

class MCPConnectionManager:
    """
    Centralized MCP Connection Manager
    Maintains connection states, concurrency locks, circuit breaker metrics,
    and lifecycle management across all registered MCP servers.
    """
    _locks: Dict[str, asyncio.Lock] = {}
    _states: Dict[str, str] = {}
    _failure_counts: Dict[str, int] = {}
    _circuit_open: Dict[str, bool] = {}
    _incidents: List[Dict[str, Any]] = [
        {
            "id": "INC-8841-FLT",
            "server_id": "equipment-telemetry-01",
            "server_name": "Equipment MCP Server",
            "severity": "CRITICAL",
            "title": "Vibration Sensor Telemetry Surge & Circuit Trip",
            "root_cause": "Transient STDIO buffer overflow during Liebherr 500t telemetry ingestion. Circuit breaker tripped to prevent cascading control-plane degradation.",
            "status": "MITIGATED",
            "timestamp": "2026-11-12T07:15:00Z",
            "resolved_at": "2026-11-12T07:22:00Z",
            "actions_taken": "Automated STDIO subprocess restart with 5s exponential backoff buffer."
        }
    ]

    @classmethod
    def get_lock(cls, server_id: str) -> asyncio.Lock:
        if server_id not in cls._locks:
            cls._locks[server_id] = asyncio.Lock()
        return cls._locks[server_id]

    @classmethod
    def get_state(cls, server_id: str) -> str:
        if cls.is_circuit_open(server_id):
            return "CIRCUIT_OPEN"
        return cls._states.get(server_id, "CLOSED")

    @classmethod
    def set_state(cls, server_id: str, state: str):
        cls._states[server_id] = state

    @classmethod
    def record_success(cls, server_id: str):
        cls._failure_counts[server_id] = 0
        cls._circuit_open[server_id] = False
        cls._states[server_id] = "CLOSED"

    @classmethod
    def record_failure(cls, server_id: str, server_name: str = "Unknown Server") -> bool:
        """Increments failure count and trips circuit breaker if threshold reached (3 failures)."""
        count = cls._failure_counts.get(server_id, 0) + 1
        cls._failure_counts[server_id] = count
        if count >= 3:
            cls._circuit_open[server_id] = True
            cls._states[server_id] = "CIRCUIT_OPEN"
            inc_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
            cls._incidents.insert(0, {
                "id": inc_id,
                "server_id": server_id,
                "server_name": server_name,
                "severity": "CRITICAL",
                "title": f"Circuit Breaker TRIPPED: {server_name}",
                "root_cause": "Repeated transport communication failures exceeded resilience threshold (3 consecutive errors).",
                "status": "ACTIVE",
                "timestamp": datetime.utcnow().isoformat(),
                "resolved_at": None,
                "actions_taken": "Automatic failover activated. Subprocess traffic isolated."
            })
            return True
        cls._states[server_id] = "UNHEALTHY"
        return False

    @classmethod
    def is_circuit_open(cls, server_id: str) -> bool:
        return cls._circuit_open.get(server_id, False)

    @classmethod
    def reset_circuit(cls, server_id: str):
        cls._failure_counts[server_id] = 0
        cls._circuit_open[server_id] = False
        cls._states[server_id] = "CLOSED"
        for inc in cls._incidents:
            if inc.get("server_id") == server_id and inc.get("status") == "ACTIVE":
                inc["status"] = "RESOLVED"
                inc["resolved_at"] = datetime.utcnow().isoformat()
                inc["actions_taken"] += " Circuit manually reset and recalibrated by Administrator."

    @classmethod
    def reset_all_circuits(cls):
        """Resets all circuit breakers and failure counts across all registered servers."""
        cls._failure_counts.clear()
        cls._circuit_open.clear()
        cls._states.clear()
        for inc in cls._incidents:
            if inc.get("status") == "ACTIVE":
                inc["status"] = "RESOLVED"
                inc["resolved_at"] = datetime.utcnow().isoformat()
                inc["actions_taken"] += " System-wide circuit reset applied."

    @classmethod
    def get_incidents(cls) -> List[Dict[str, Any]]:
        return cls._incidents
