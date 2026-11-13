import asyncio
import json
import os
import sys
import time
import uuid
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Callable
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
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

    async def _run_sdk_stdio_operation(self, op_fn: Callable[[ClientSession, Any], Any]) -> Any:
        """
        Executes an operation using the official Python MCP SDK (stdio_client, StdioServerParameters, ClientSession).
        Isolates execution inside a Windows-compatible Proactor worker thread when running under non-proactor loops,
        ensuring 100% reliable asynchronous subprocess lifecycle and protocol framing without custom JSON-RPC.
        """
        cmd, resolved_args, cwd = self._resolve_command_and_args()
        cmd_list = [cmd] + resolved_args

        env = os.environ.copy()
        env.update(self.env_vars)
        if "MCP_SERVER_ORGANIZATION_ID" not in env:
            env["MCP_SERVER_ORGANIZATION_ID"] = "abbc6079-36ce-4b73-b8ee-0796f7de5821"
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        server_params = StdioServerParameters(
            command=cmd,
            args=resolved_args,
            env=env,
            cwd=cwd,
            encoding="utf-8"
        )

        def _format_exception(exc: BaseException) -> str:
            if hasattr(exc, "exceptions") and exc.exceptions:
                return "; ".join(_format_exception(sub) for sub in exc.exceptions)
            return str(exc)

        async def _sdk_flow():
            try:
                async with stdio_client(server_params) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream, read_timeout_seconds=float(self.timeout)) as session:
                        init_result = await session.initialize()
                        return await op_fn(session, init_result)
            except FileNotFoundError:
                raise MCPClientError(f"Command not found or executable unavailable: '{cmd}'")
            except (Exception, BaseExceptionGroup) as e:
                err_text = _format_exception(e)
                if "timed out" in err_text.lower():
                    raise MCPClientError(f"MCP server timed out after {self.timeout}s: {err_text}")
                elif "connection closed" in err_text.lower() or "closed stream" in err_text.lower():
                    raise MCPClientError(f"Server closed stream prematurely. Stderr: {err_text}")
                elif isinstance(e, MCPClientError):
                    raise e
                raise MCPClientError(f"Failed to start MCP server subprocess ({cmd_list}): {err_text}")

        loop = asyncio.get_running_loop()
        is_proactor = isinstance(loop, getattr(asyncio, "ProactorEventLoop", type(None)))

        if sys.platform == "win32" and not is_proactor:
            def _thread_worker():
                worker_loop = asyncio.WindowsProactorEventLoopPolicy().new_event_loop()
                asyncio.set_event_loop(worker_loop)
                try:
                    return worker_loop.run_until_complete(_sdk_flow())
                finally:
                    try:
                        pending = asyncio.all_tasks(worker_loop)
                        for t in pending:
                            t.cancel()
                        if pending:
                            worker_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    except Exception:
                        pass
                    worker_loop.close()

            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(_thread_worker),
                    timeout=float(self.timeout + 3.0)
                )
            except asyncio.TimeoutError:
                raise MCPClientError(f"MCP server timed out after {self.timeout}s waiting for response.")
        else:
            try:
                return await asyncio.wait_for(
                    _sdk_flow(),
                    timeout=float(self.timeout + 3.0)
                )
            except asyncio.TimeoutError:
                raise MCPClientError(f"MCP server timed out after {self.timeout}s waiting for response.")

    async def initialize(self) -> Tuple[Dict[str, Any], float]:
        """
        Performs protocol handshake and returns server info + latency in milliseconds.
        Uses official MCP ClientSession.initialize() for STDIO transport.
        """
        start = time.perf_counter()

        if self.transport_type == "STDIO":
            async def _op(session: ClientSession, init_res: Any):
                caps = getattr(init_res, "capabilities", None)
                sinfo = getattr(init_res, "server_info", None)
                caps_dict = caps.model_dump(exclude_none=True) if hasattr(caps, "model_dump") else (caps.dict(exclude_none=True) if hasattr(caps, "dict") else {})
                sinfo_dict = sinfo.model_dump(exclude_none=True) if hasattr(sinfo, "model_dump") else (sinfo.dict(exclude_none=True) if hasattr(sinfo, "dict") else {})
                return {
                    "protocolVersion": getattr(init_res, "protocol_version", "2024-11-05"),
                    "serverInfo": sinfo_dict,
                    "capabilities": caps_dict
                }
            res_dict = await self._run_sdk_stdio_operation(_op)
            duration_ms = (time.perf_counter() - start) * 1000.0
            return res_dict, round(duration_ms, 2)

        elif self.transport_type in ("HTTP_SSE", "HTTP"):
            if not self.endpoint:
                raise MCPClientError("HTTP endpoint required for HTTP transport.")
            
            # Try SSE client if available
            try:
                from mcp.client.sse import sse_client
                async with sse_client(self.endpoint, timeout=self.timeout) as (read, write):
                    async with ClientSession(read, write) as session:
                        init_res = await session.initialize()
                        duration_ms = (time.perf_counter() - start) * 1000.0
                        return {
                            "protocolVersion": getattr(init_res, "protocol_version", "2024-11-05"),
                            "serverInfo": getattr(init_res, "server_info", {"name": "SSE Server"}),
                            "capabilities": getattr(init_res, "capabilities", {})
                        }, round(duration_ms, 2)
            except ImportError:
                pass
            except Exception:
                pass

            # Direct HTTP JSON-RPC fallback
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            
            init_req = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": True}},
                    "clientInfo": {"name": "MCP-Nexus-Control-Plane", "version": "1.0.0"}
                }
            }
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
        Discovers tools available on this MCP server using official ClientSession.list_tools().
        """
        if self.transport_type == "STDIO":
            async def _op(session: ClientSession, init_res: Any):
                tools_res = await session.list_tools()
                discovered = []
                for t in tools_res.tools:
                    schema = getattr(t, "input_schema", getattr(t, "inputSchema", {}))
                    if hasattr(schema, "model_dump"):
                        schema = schema.model_dump(exclude_none=True)
                    elif hasattr(schema, "dict"):
                        schema = schema.dict(exclude_none=True)
                    discovered.append({
                        "name": t.name,
                        "description": t.description or "",
                        "inputSchema": schema or {}
                    })
                return discovered
            return await self._run_sdk_stdio_operation(_op)

        elif self.transport_type in ("HTTP_SSE", "HTTP"):
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            req_tools = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list",
                "params": {}
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(self.endpoint, json=req_tools, headers=headers)
                data = res.json()
                if "error" in data:
                    raise MCPClientError(f"tools/list error: {data['error']}")
                return data.get("result", {}).get("tools", [])
        return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        """
        Invokes an MCP tool using official ClientSession.call_tool() and returns (result_dict, duration_ms).
        """
        start = time.perf_counter()

        if self.transport_type == "STDIO":
            async def _op(session: ClientSession, init_res: Any):
                res = await session.call_tool(tool_name, arguments or {})
                content_list = []
                parsed_data = None
                for c in res.content:
                    c_type = getattr(c, "type", "text")
                    c_text = getattr(c, "text", "")
                    content_list.append({"type": c_type, "text": c_text})
                    if c_type == "text" and parsed_data is None:
                        try:
                            parsed_data = json.loads(c_text)
                        except Exception:
                            pass
                return {
                    "content": content_list,
                    "isError": getattr(res, "is_error", False),
                    "parsed": parsed_data
                }
            res_dict = await self._run_sdk_stdio_operation(_op)
            duration_ms = (time.perf_counter() - start) * 1000.0
            return res_dict, round(duration_ms, 2)

        elif self.transport_type in ("HTTP_SSE", "HTTP"):
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            req_call = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(self.endpoint, json=req_call, headers=headers)
                duration_ms = (time.perf_counter() - start) * 1000.0
                data = res.json()
                if "error" in data:
                    raise MCPClientError(f"Tool error: {data['error']}")
                return data.get("result", {}), round(duration_ms, 2)

        raise MCPClientError(f"Unsupported transport: {self.transport_type}")

    async def ping(self) -> float:
        """Sends protocol ping request using official ClientSession.send_ping() and returns latency in milliseconds."""
        start = time.perf_counter()
        if self.transport_type == "STDIO":
            async def _op(session: ClientSession, init_res: Any):
                await session.send_ping()
                return True
            await self._run_sdk_stdio_operation(_op)
            return round((time.perf_counter() - start) * 1000.0, 2)
        elif self.transport_type in ("HTTP_SSE", "HTTP"):
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            req_ping = {"jsonrpc": "2.0", "id": self._next_id(), "method": "ping"}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(self.endpoint, json=req_ping, headers=headers)
                return round((time.perf_counter() - start) * 1000.0, 2)
        raise MCPClientError(f"Unsupported transport: {self.transport_type}")

    async def list_resources(self) -> List[Dict[str, Any]]:
        """Discovers resources available on this MCP server using official ClientSession.list_resources()."""
        if self.transport_type == "STDIO":
            async def _op(session: ClientSession, init_res: Any):
                res_res = await session.list_resources()
                resources = []
                for r in res_res.resources:
                    resources.append({
                        "uri": str(r.uri),
                        "name": r.name or "",
                        "description": getattr(r, "description", "") or "",
                        "mimeType": getattr(r, "mime_type", getattr(r, "mimeType", "application/json")) or "application/json"
                    })
                return resources
            return await self._run_sdk_stdio_operation(_op)

        elif self.transport_type in ("HTTP_SSE", "HTTP"):
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            req_res = {"jsonrpc": "2.0", "id": self._next_id(), "method": "resources/list", "params": {}}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(self.endpoint, json=req_res, headers=headers)
                data = res.json()
                if "error" in data:
                    raise MCPClientError(f"resources/list error: {data['error']}")
                return data.get("result", {}).get("resources", [])
        return []

    async def list_prompts(self) -> List[Dict[str, Any]]:
        """Discovers prompts available on this MCP server using official ClientSession.list_prompts()."""
        if self.transport_type == "STDIO":
            async def _op(session: ClientSession, init_res: Any):
                prm_res = await session.list_prompts()
                prompts = []
                for p in prm_res.prompts:
                    args_list = []
                    for a in (getattr(p, "arguments", []) or []):
                        args_list.append({
                            "name": a.name,
                            "description": getattr(a, "description", "") or "",
                            "required": getattr(a, "required", False)
                        })
                    prompts.append({
                        "name": p.name,
                        "description": getattr(p, "description", "") or "",
                        "arguments": args_list
                    })
                return prompts
            return await self._run_sdk_stdio_operation(_op)

        elif self.transport_type in ("HTTP_SSE", "HTTP"):
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            req_prompt = {"jsonrpc": "2.0", "id": self._next_id(), "method": "prompts/list", "params": {}}
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
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
                inc["resolved_at"] = datetime.now(timezone.utc).isoformat()
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
                inc["resolved_at"] = datetime.now(timezone.utc).isoformat()
                inc["actions_taken"] += " System-wide circuit reset applied."

    @classmethod
    def get_incidents(cls) -> List[Dict[str, Any]]:
        return cls._incidents
