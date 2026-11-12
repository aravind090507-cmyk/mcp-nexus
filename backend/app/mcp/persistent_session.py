"""
MCP NEXUS — PERSISTENT MCP SESSION MANAGER
Enterprise Persistent Session Manager using the Official Python MCP SDK v2.3.0.

Provides warm, reusable, multiplexed ClientSessions for Model Context Protocol servers.
Complies strictly with official MCP SDK lifecycle, AnyIO streams, and Windows Proactor isolation.
"""

import sys
import os
import asyncio
import threading
import time
import logging
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List, Callable
from contextlib import asynccontextmanager

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

from app.core.config import settings

logger = logging.getLogger("mcp-nexus.persistent-session")


class SessionLifecycleState(str, Enum):
    """Explicit Lifecycle States for Persistent MCP Server Sessions."""
    UNINITIALIZED = "UNINITIALIZED"
    CONNECTING = "CONNECTING"
    WARM = "WARM"
    RECONNECTING = "RECONNECTING"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    SHUTTING_DOWN = "SHUTTING_DOWN"
    CLOSED = "CLOSED"


class PersistentServerSession:
    """
    Manages the persistent lifecycle of a single Model Context Protocol (MCP) server.
    
    Architecture:
    - Owns an OS subprocess via official stdio_client.
    - Manages an official ClientSession with protocol version negotiation (2024-11-05).
    - Guarantees strict event loop ownership: ClientSession is only accessed on its owning loop.
    - Supports concurrent request multiplexing across multiple coroutines on the owning loop.
    - Provides connection barriers, background health check pings, and auto-reconnection.
    """

    def __init__(
        self,
        server_id: str,
        server_name: str,
        command: str,
        args: Optional[List[str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: float = 30.0,
        heartbeat_interval: float = 30.0,
        max_reconnect_attempts: int = 3,
    ):
        self.server_id = server_id
        self.server_name = server_name
        self.command = command
        self.args = args or []
        self.env_vars = env_vars or {}
        self.cwd = cwd or os.getcwd()
        self.timeout = float(timeout)
        self.heartbeat_interval = float(heartbeat_interval)
        self.max_reconnect_attempts = int(max_reconnect_attempts)

        self._state = SessionLifecycleState.UNINITIALIZED
        self._session: Optional[ClientSession] = None
        self._init_result: Any = None
        self._consecutive_failures = 0
        self._pid: Optional[int] = None

        # Thread and Event Loop ownership
        self._owning_loop: Optional[asyncio.AbstractEventLoop] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._thread_ready_evt = threading.Event()
        self._stop_event: Optional[asyncio.Event] = None
        self._connection_barrier: Optional[asyncio.Event] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._runner_task: Optional[asyncio.Task] = None

        # Mutex for state transitions
        self._state_lock = asyncio.Lock()

    @property
    def state(self) -> SessionLifecycleState:
        return self._state

    @property
    def pid(self) -> Optional[int]:
        return self._pid

    @property
    def is_warm(self) -> bool:
        return self._state == SessionLifecycleState.WARM and self._session is not None

    def _build_server_params(self) -> StdioServerParameters:
        env = os.environ.copy()
        env.update(self.env_vars)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        if sys.platform == "win32" and "SystemRoot" not in env:
            env["SystemRoot"] = os.environ.get("SystemRoot", "C:\\Windows")

        return StdioServerParameters(
            command=self.command,
            args=self.args,
            env=env,
            cwd=self.cwd,
            encoding="utf-8"
        )

    def _ensure_worker_thread(self):
        """
        On Windows with non-proactor parent loop, or when dedicated thread ownership is needed,
        creates a dedicated background thread running a ProactorEventLoop.
        """
        if self._worker_thread and self._worker_thread.is_alive():
            return

        self._thread_ready_evt.clear()

        def _worker_entry():
            if sys.platform == "win32":
                loop = asyncio.WindowsProactorEventLoopPolicy().new_event_loop()
            else:
                loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._owning_loop = loop
            self._stop_event = asyncio.Event()
            self._connection_barrier = asyncio.Event()
            self._thread_ready_evt.set()
            try:
                loop.run_forever()
            finally:
                loop.close()

        self._worker_thread = threading.Thread(
            target=_worker_entry,
            name=f"MCP-SessionThread-{self.server_name[:12]}",
            daemon=True
        )
        self._worker_thread.start()
        self._thread_ready_evt.wait(timeout=5.0)

    async def start(self) -> bool:
        """Starts the persistent session and awaits initialization barrier."""
        if self._state == SessionLifecycleState.WARM:
            return True

        # Ensure dedicated loop exists
        is_windows = sys.platform == "win32"
        current_loop = asyncio.get_running_loop()
        is_proactor = isinstance(current_loop, getattr(asyncio, "ProactorEventLoop", ()))

        if is_windows and not is_proactor:
            self._ensure_worker_thread()
            fut = asyncio.run_coroutine_threadsafe(self._async_start(), self._owning_loop)
            return await asyncio.wrap_future(fut)
        else:
            self._owning_loop = current_loop
            if self._stop_event is None:
                self._stop_event = asyncio.Event()
            if self._connection_barrier is None:
                self._connection_barrier = asyncio.Event()
            return await self._async_start()

    async def _async_start(self) -> bool:
        """Internal connection logic running directly on owning loop."""
        async with self._state_lock:
            if self._state == SessionLifecycleState.WARM:
                return True
            if self._state == SessionLifecycleState.CONNECTING:
                # Another coroutine is already connecting; wait on connection barrier
                pass

        if self._state == SessionLifecycleState.CONNECTING:
            await self._connection_barrier.wait()
            return self._state == SessionLifecycleState.WARM

        self._state = SessionLifecycleState.CONNECTING
        self._connection_barrier.clear()

        # Launch session runner task
        self._runner_task = self._owning_loop.create_task(self._run_session_loop())
        
        # Await connection barrier
        try:
            await asyncio.wait_for(self._connection_barrier.wait(), timeout=self.timeout)
            return self._state == SessionLifecycleState.WARM
        except asyncio.TimeoutError:
            logger.error(f"[{self.server_name}] Connection barrier timed out after {self.timeout}s.")
            self._state = SessionLifecycleState.CIRCUIT_OPEN
            return False

    async def _run_session_loop(self):
        """
        Long-running task holding the stdio_client context and ClientSession.
        Runs until shutdown or unrecoverable circuit failure.
        """
        reconnect_attempts = 0
        server_params = self._build_server_params()

        while not self._stop_event.is_set():
            try:
                try:
                    import psutil
                    pre_pids = {c.pid for c in psutil.Process().children(recursive=True)}
                except Exception:
                    pre_pids = set()

                logger.info(f"[{self.server_name}] Launching subprocess: {server_params.command} {server_params.args}")
                async with stdio_client(server_params) as (read_stream, write_stream):
                    try:
                        import psutil
                        post_pids = [
                            c.pid for c in psutil.Process().children(recursive=True)
                            if c.pid not in pre_pids and "conhost" not in c.name().lower()
                        ]
                        if post_pids:
                            self._pid = post_pids[0]
                    except Exception:
                        pass

                    async with ClientSession(read_stream, write_stream, read_timeout_seconds=self.timeout) as session:
                        self._session = session
                        # Capability handshake
                        self._init_result = await session.initialize()
                        self._state = SessionLifecycleState.WARM
                        self._consecutive_failures = 0
                        reconnect_attempts = 0
                        self._connection_barrier.set()
                        logger.info(f"[{self.server_name}] Persistent session established & WARM (PID: {self._pid}).")

                        # Start heartbeat ping task
                        self._heartbeat_task = self._owning_loop.create_task(self._heartbeat_loop())

                        # Monitor session loop until stop signal or transport disconnection
                        while not self._stop_event.is_set():
                            if getattr(session._dispatcher, "_closed", False) or not getattr(session._dispatcher, "_running", True):
                                raise ConnectionError("MCP server transport closed unexpectedly (EOF / process terminated).")
                            try:
                                await asyncio.wait_for(self._stop_event.wait(), timeout=0.25)
                                break
                            except asyncio.TimeoutError:
                                pass
                        break

            except anyio.get_cancelled_exc_class():
                logger.info(f"[{self.server_name}] Session task cancelled.")
                break
            except Exception as exc:
                self._pid = None
                reconnect_attempts += 1
                self._consecutive_failures += 1
                self._session = None
                self._connection_barrier.clear()
                logger.warning(f"[{self.server_name}] Session disconnected ({type(exc).__name__}: {exc}). Attempt #{reconnect_attempts}")

                if self._heartbeat_task and not self._heartbeat_task.done():
                    self._heartbeat_task.cancel()

                if self._stop_event.is_set() or self._state == SessionLifecycleState.SHUTTING_DOWN:
                    break

                if self._consecutive_failures >= self.max_reconnect_attempts:
                    logger.error(f"[{self.server_name}] Reconnect limit ({self.max_reconnect_attempts}) reached. Tripping CIRCUIT_OPEN.")
                    self._state = SessionLifecycleState.CIRCUIT_OPEN
                    self._connection_barrier.set() # Unblock waiters with failure
                    break

                self._state = SessionLifecycleState.RECONNECTING
                # Exponential backoff (1s, 2s, 4s...)
                backoff = min(8.0, 1.0 * (2 ** (reconnect_attempts - 1)))
                logger.info(f"[{self.server_name}] Backing off for {backoff:.1f}s before reconnect...")
                await asyncio.sleep(backoff)

        # Cleanup on exit
        if self._state != SessionLifecycleState.CIRCUIT_OPEN:
            self._state = SessionLifecycleState.CLOSED
        self._session = None
        self._connection_barrier.set()
        logger.info(f"[{self.server_name}] Persistent session loop terminated ({self._state.value}).")

    async def _heartbeat_loop(self):
        """Periodic background probe using official MCP send_ping()."""
        while not self._stop_event.is_set() and self._state == SessionLifecycleState.WARM:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                if self._session and self._state == SessionLifecycleState.WARM:
                    t0 = time.perf_counter()
                    await self._session.send_ping()
                    latency_ms = (time.perf_counter() - t0) * 1000.0
                    logger.debug(f"[{self.server_name}] Heartbeat ping OK ({latency_ms:.2f}ms)")
            except (asyncio.CancelledError, anyio.get_cancelled_exc_class()):
                break
            except Exception as e:
                logger.warning(f"[{self.server_name}] Heartbeat ping failed ({e}). Triggering reconnect.")
                # Closing read/write streams or cancelling runner triggers reconnect
                if self._runner_task and not self._runner_task.done():
                    self._runner_task.cancel()
                break

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        """
        Executes a tool on the warm persistent session.
        Safe for concurrent invocation from multiple callers.
        """
        # Ensure session is active
        if self._state != SessionLifecycleState.WARM:
            ok = await self.start()
            if not ok:
                raise RuntimeError(f"Cannot execute tool '{tool_name}': server '{self.server_name}' state is {self._state}.")

        # If running on dedicated worker thread, dispatch to that loop
        current_loop = asyncio.get_running_loop()
        if self._owning_loop and current_loop != self._owning_loop:
            fut = asyncio.run_coroutine_threadsafe(self._async_call_tool(tool_name, arguments), self._owning_loop)
            return await asyncio.wrap_future(fut)
        else:
            return await self._async_call_tool(tool_name, arguments)

    async def _async_call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        """Runs call_tool on the session's owning event loop."""
        if not self._session or self._state != SessionLifecycleState.WARM:
            raise RuntimeError(f"Session '{self.server_name}' is not WARM (current: {self._state})")

        t0 = time.perf_counter()
        try:
            res = await self._session.call_tool(tool_name, arguments)
            duration_ms = (time.perf_counter() - t0) * 1000.0

            # Extract structured result payload
            parsed = {}
            for block in getattr(res, "content", []):
                text_val = getattr(block, "text", None)
                if text_val:
                    try:
                        import json
                        parsed = json.loads(text_val)
                        break
                    except Exception:
                        parsed = {"text": text_val}
            if not parsed and hasattr(res, "model_dump"):
                parsed = res.model_dump()

            return parsed, round(duration_ms, 2)
        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            logger.error(f"[{self.server_name}] call_tool '{tool_name}' failed after {duration_ms:.1f}ms: {e}")
            raise e

    async def send_ping(self) -> float:
        """Explicit ping verifying connection latency."""
        if self._state != SessionLifecycleState.WARM:
            ok = await self.start()
            if not ok:
                raise RuntimeError(f"Cannot ping '{self.server_name}': session state is {self._state}")

        current_loop = asyncio.get_running_loop()
        if self._owning_loop and current_loop != self._owning_loop:
            fut = asyncio.run_coroutine_threadsafe(self._async_ping(), self._owning_loop)
            return await asyncio.wrap_future(fut)
        else:
            return await self._async_ping()

    async def _async_ping(self) -> float:
        if not self._session or self._state != SessionLifecycleState.WARM:
            raise RuntimeError(f"Session '{self.server_name}' is not WARM.")
        t0 = time.perf_counter()
        await self._session.send_ping()
        return round((time.perf_counter() - t0) * 1000.0, 2)

    async def shutdown(self, timeout: float = 3.0):
        """Gracefully terminates session, stops background loop, and reclaims resources."""
        if self._state in (SessionLifecycleState.SHUTTING_DOWN, SessionLifecycleState.CLOSED):
            return

        self._state = SessionLifecycleState.SHUTTING_DOWN
        logger.info(f"[{self.server_name}] Shutting down persistent session...")

        if self._owning_loop and self._owning_loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(self._async_shutdown(timeout), self._owning_loop)
            try:
                await asyncio.wrap_future(fut)
            except Exception as e:
                logger.warning(f"[{self.server_name}] Error during async shutdown: {e}")
        else:
            await self._async_shutdown(timeout)

        # Stop worker thread if any
        if self._worker_thread and self._worker_thread.is_alive():
            if self._owning_loop:
                self._owning_loop.call_soon_threadsafe(self._owning_loop.stop)
            self._worker_thread.join(timeout=2.0)
            self._worker_thread = None

        self._state = SessionLifecycleState.CLOSED
        logger.info(f"[{self.server_name}] Shutdown complete.")

    async def _async_shutdown(self, timeout: float):
        if self._stop_event:
            self._stop_event.set()
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        if self._runner_task and not self._runner_task.done():
            self._runner_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(self._runner_task), timeout=timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass


class PersistentSessionManager:
    """
    Centralized Registry & Lifecycle Supervisor for Persistent MCP Sessions.
    
    Provides thread-safe singleton access, lazy initialization, multi-server isolation,
    and graceful shutdown coordination across all enterprise MCP servers.
    """
    _sessions: Dict[str, PersistentServerSession] = {}
    _lock = threading.Lock()

    @classmethod
    def get_session(
        cls,
        server_id: str,
        server_name: str,
        command: str,
        args: Optional[List[str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: float = 30.0,
    ) -> PersistentServerSession:
        """Retrieves or lazily instantiates a persistent session for the given server ID."""
        with cls._lock:
            if server_id not in cls._sessions:
                heartbeat = getattr(settings, "MCP_HEARTBEAT_INTERVAL_SECONDS", 30.0)
                cls._sessions[server_id] = PersistentServerSession(
                    server_id=server_id,
                    server_name=server_name,
                    command=command,
                    args=args,
                    env_vars=env_vars,
                    cwd=cwd,
                    timeout=timeout,
                    heartbeat_interval=heartbeat
                )
            return cls._sessions[server_id]

    @classmethod
    def get_existing_session(cls, server_id: str) -> Optional[PersistentServerSession]:
        with cls._lock:
            return cls._sessions.get(server_id)

    @classmethod
    async def execute_tool(
        cls,
        server_id: str,
        server_name: str,
        command: str,
        args: Optional[List[str]],
        env_vars: Optional[Dict[str, str]],
        cwd: Optional[str],
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: float = 30.0
    ) -> Tuple[Dict[str, Any], float]:
        """High-level entry point to execute a tool on a persistent session."""
        session = cls.get_session(
            server_id=server_id,
            server_name=server_name,
            command=command,
            args=args,
            env_vars=env_vars,
            cwd=cwd,
            timeout=timeout
        )
        return await session.call_tool(tool_name, arguments)

    @classmethod
    async def shutdown_all(cls, timeout: float = 3.0):
        """Gracefully stops all active persistent sessions across all registered servers."""
        with cls._lock:
            sessions = list(cls._sessions.values())
            cls._sessions.clear()

        if not sessions:
            return

        logger.info(f"Shutting down {len(sessions)} persistent MCP server session(s)...")
        tasks = [s.shutdown(timeout=timeout) for s in sessions]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All persistent MCP server sessions cleanly shutdown.")

    @classmethod
    def reset(cls):
        """Synchronous reset for test harness isolation."""
        with cls._lock:
            for s in list(cls._sessions.values()):
                if s._owning_loop and s._owning_loop.is_running():
                    asyncio.run_coroutine_threadsafe(s.shutdown(timeout=1.0), s._owning_loop)
            cls._sessions.clear()
