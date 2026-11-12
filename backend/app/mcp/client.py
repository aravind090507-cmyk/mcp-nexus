import asyncio
import json
import os
import sys
import time
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
        timeout: int = 15
    ):
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

    async def _execute_stdio_exchange(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Executes a sequence of JSON-RPC requests against a STDIO MCP server process.
        Safely captures stdout and stderr with timeout guards.
        """
        env = os.environ.copy()
        env.update(self.env_vars)
        env["PYTHONUNBUFFERED"] = "1"

        cmd_list = [self.command] + self.args
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_list,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
        except FileNotFoundError:
            raise MCPClientError(f"Command not found or executable unavailable: '{self.command}'")
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
                except json.JSONDecodeError as jde:
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

    @classmethod
    def get_lock(cls, server_id: str) -> asyncio.Lock:
        if server_id not in cls._locks:
            cls._locks[server_id] = asyncio.Lock()
        return cls._locks[server_id]

    @classmethod
    def get_state(cls, server_id: str) -> str:
        return cls._states.get(server_id, "DISCONNECTED")

    @classmethod
    def set_state(cls, server_id: str, state: str):
        cls._states[server_id] = state

    @classmethod
    def record_success(cls, server_id: str):
        cls._failure_counts[server_id] = 0
        cls._circuit_open[server_id] = False
        cls._states[server_id] = "HEALTHY"

    @classmethod
    def record_failure(cls, server_id: str) -> bool:
        """Increments failure count and trips circuit breaker if threshold reached (3 failures)."""
        count = cls._failure_counts.get(server_id, 0) + 1
        cls._failure_counts[server_id] = count
        if count >= 3:
            cls._circuit_open[server_id] = True
            cls._states[server_id] = "CIRCUIT_OPEN"
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
        cls._states[server_id] = "READY"
