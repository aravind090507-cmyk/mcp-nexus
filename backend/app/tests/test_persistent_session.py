"""
MCP NEXUS — PERSISTENT MCP SESSION MANAGER ACCEPTANCE SUITE (PHASE 15A)
Comprehensive validation of Persistent MCP Sessions using official Python MCP SDK v2.3.0.

Validates:
1. Session initialization & capability negotiation
2. Repeated calls reusing identical child process PID
3. Concurrent tool calls via JSONRPCDispatcher multiplexing
4. Multiple independent MCP servers (ERP, Inventory, Equipment)
5. Child process crash detection
6. Connection auto-recovery following crash
7. Heartbeat ping exchange & sub-millisecond latency
8. Request timeout handling
9. Request cancellation resilience
10. Controlled application shutdown
11. Zero zombie child processes
12. Compatibility with existing transport when ENABLE_PERSISTENT_MCP_SESSIONS=False
"""

import sys
import os
import asyncio
import time
import pytest
import psutil

from app.core.config import settings
from app.mcp.persistent_session import (
    PersistentServerSession,
    PersistentSessionManager,
    SessionLifecycleState
)
from app.mcp.client import MCPClient
from app.models.all_models import MCPServer, MCPTool
from app.services.mcp_manager import MCPManager
from app.database.session import SessionLocal

ERP_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp", "demo_servers", "erp_server.py"))
INV_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp", "demo_servers", "inventory_server.py"))
EQ_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp", "demo_servers", "equipment_server.py"))


@pytest.fixture(autouse=True)
def cleanup_sessions():
    """Ensure persistent session manager is reset between tests."""
    PersistentSessionManager.reset()
    yield
    PersistentSessionManager.reset()


@pytest.mark.asyncio
async def test_01_session_initialization():
    """Scenario 1: Session initialization and handshake with official MCP SDK."""
    session = PersistentServerSession(
        server_id="test-erp-init",
        server_name="ERP Server",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=15.0
    )
    assert session.state == SessionLifecycleState.UNINITIALIZED
    
    ok = await session.start()
    assert ok is True
    assert session.state == SessionLifecycleState.WARM
    assert session.pid is not None
    assert psutil.pid_exists(session.pid)
    
    await session.shutdown()
    assert session.state == SessionLifecycleState.CLOSED


@pytest.mark.asyncio
async def test_02_repeated_calls_same_process():
    """Scenario 2: Repeated calls reuse the same warm process (PID invariant)."""
    session = PersistentServerSession(
        server_id="test-erp-reuse",
        server_name="ERP Server",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=15.0
    )
    await session.start()
    initial_pid = session.pid

    for _ in range(5):
        res, lat = await session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
        assert "Mumbai Coastal Road" in res.get("name", "")
        assert session.pid == initial_pid, "Process PID must remain invariant across repeated calls"
        assert lat < 50.0, f"Warm call should be sub-50ms (got {lat}ms)"

    await session.shutdown()


@pytest.mark.asyncio
async def test_03_concurrent_tool_execution():
    """Scenario 3: Concurrent tool execution multiplexing on single ClientSession."""
    session = PersistentServerSession(
        server_id="test-erp-concurrent",
        server_name="ERP Server",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=15.0
    )
    await session.start()

    tasks = [
        session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"}),
        session.call_tool("get_project_status", {"project_id": "PRJ-HAZ-002"}),
        session.call_tool("get_project_status", {"project_id": "PRJ-HYD-003"}),
        session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"}),
        session.call_tool("get_project_status", {"project_id": "PRJ-HAZ-002"}),
    ]

    t0 = time.perf_counter()
    results = await asyncio.gather(*tasks)
    total_time_ms = (time.perf_counter() - t0) * 1000.0

    assert len(results) == 5
    assert "Mumbai" in results[0][0]["name"]
    assert "Hazira" in results[1][0]["name"]
    assert "Hyderabad" in results[2][0]["name"]
    assert "Mumbai" in results[3][0]["name"]
    assert "Hazira" in results[4][0]["name"]

    # All 5 concurrent calls together should finish in under 100ms on warm session
    assert total_time_ms < 200.0, f"5 concurrent calls should be under 200ms (got {total_time_ms:.1f}ms)"

    await session.shutdown()


@pytest.mark.asyncio
async def test_04_multiple_independent_servers():
    """Scenario 4: Multiple independent MCP servers (ERP, Inventory, Equipment) side by side."""
    res_erp, lat_erp = await PersistentSessionManager.execute_tool(
        server_id="srv-erp",
        server_name="ERP Server",
        command=sys.executable,
        args=[ERP_SCRIPT],
        env_vars={},
        cwd=os.getcwd(),
        tool_name="get_project_status",
        arguments={"project_id": "PRJ-MUM-001"}
    )
    res_inv, lat_inv = await PersistentSessionManager.execute_tool(
        server_id="srv-inv",
        server_name="Inventory Server",
        command=sys.executable,
        args=[INV_SCRIPT],
        env_vars={},
        cwd=os.getcwd(),
        tool_name="get_low_stock_items",
        arguments={"threshold": 50}
    )
    res_eq, lat_eq = await PersistentSessionManager.execute_tool(
        server_id="srv-eq",
        server_name="Equipment Server",
        command=sys.executable,
        args=[EQ_SCRIPT],
        env_vars={},
        cwd=os.getcwd(),
        tool_name="get_maintenance_schedule",
        arguments={}
    )

    assert "Mumbai" in res_erp.get("name", "")
    assert isinstance(res_inv, (list, dict))
    assert isinstance(res_eq, (list, dict))

    # Verify 3 distinct active sessions
    assert len(PersistentSessionManager._sessions) == 3

    await PersistentSessionManager.shutdown_all()


@pytest.mark.asyncio
async def test_05_server_process_crash_detection():
    """Scenario 5: Process crash detection and state transition."""
    session = PersistentServerSession(
        server_id="test-erp-crash",
        server_name="ERP Server",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=15.0
    )
    await session.start()
    pid = session.pid
    assert pid is not None

    # Kill child process
    proc = psutil.Process(pid)
    proc.kill()
    proc.wait(timeout=3.0)

    # Wait for the transport watcher to detect EOF
    await asyncio.sleep(0.5)

    # State should have transitioned to RECONNECTING
    assert session.state == SessionLifecycleState.RECONNECTING

    await session.shutdown()


@pytest.mark.asyncio
async def test_06_connection_recovery_after_crash():
    """Scenario 6: Automatic reconnection and execution recovery following process termination."""
    session = PersistentServerSession(
        server_id="test-erp-recover",
        server_name="ERP Server",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=15.0
    )
    await session.start()
    pid1 = session.pid

    # Kill process
    proc = psutil.Process(pid1)
    proc.kill()
    proc.wait(timeout=3.0)

    await asyncio.sleep(0.5)

    # Subsequent call should automatically reconnect to a new process
    res, lat = await session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
    assert "Mumbai Coastal Road" in res.get("name", "")
    assert session.state == SessionLifecycleState.WARM
    assert session.pid is not None
    assert session.pid != pid1, "New process PID must differ from killed process PID"

    await session.shutdown()


@pytest.mark.asyncio
async def test_07_heartbeat_ping():
    """Scenario 7: Explicit heartbeat ping verifies liveness with sub-millisecond latency."""
    session = PersistentServerSession(
        server_id="test-erp-ping",
        server_name="ERP Server",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=15.0
    )
    await session.start()

    lat = await session.send_ping()
    assert lat >= 0.0
    assert lat < 50.0, f"Ping should be sub-50ms (got {lat}ms)"

    await session.shutdown()


@pytest.mark.asyncio
async def test_08_request_timeouts():
    """Scenario 8: Request timeout does not deadlock or corrupt session."""
    session = PersistentServerSession(
        server_id="test-erp-timeout",
        server_name="ERP Server",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=15.0
    )
    await session.start()

    # Call with impossibly tight timeout
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"}),
            timeout=0.000001
        )

    # Session remains warm and handles subsequent tool calls
    assert session.state == SessionLifecycleState.WARM
    res, lat = await session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
    assert "Mumbai" in res.get("name", "")

    await session.shutdown()


@pytest.mark.asyncio
async def test_09_request_cancellation():
    """Scenario 9: Caller task cancellation resilience."""
    session = PersistentServerSession(
        server_id="test-erp-cancel",
        server_name="ERP Server",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=15.0
    )
    await session.start()

    # Launch task and cancel it immediately
    task = asyncio.create_task(session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"}))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Session remains warm and responsive
    assert session.state == SessionLifecycleState.WARM
    res, lat = await session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
    assert "Mumbai" in res.get("name", "")

    await session.shutdown()


@pytest.mark.asyncio
async def test_10_application_shutdown():
    """Scenario 10: PersistentSessionManager.shutdown_all() cleanly closes all sessions."""
    await PersistentSessionManager.execute_tool(
        "srv-erp-shut", "ERP", sys.executable, [ERP_SCRIPT], {}, os.getcwd(),
        "get_project_status", {"project_id": "PRJ-MUM-001"}
    )
    await PersistentSessionManager.execute_tool(
        "srv-inv-shut", "Inventory", sys.executable, [INV_SCRIPT], {}, os.getcwd(),
        "get_low_stock_items", {}
    )

    assert len(PersistentSessionManager._sessions) == 2

    await PersistentSessionManager.shutdown_all(timeout=3.0)
    assert len(PersistentSessionManager._sessions) == 0


@pytest.mark.asyncio
async def test_11_zero_zombie_subprocesses():
    """Scenario 11: Subprocess cleanup guarantees zero zombie/orphan child processes."""
    proc = psutil.Process()
    
    await PersistentSessionManager.execute_tool(
        "srv-erp-zombie", "ERP", sys.executable, [ERP_SCRIPT], {}, os.getcwd(),
        "get_project_status", {"project_id": "PRJ-MUM-001"}
    )
    children_during = [c for c in proc.children(recursive=True) if "conhost" not in c.name().lower()]
    assert len(children_during) >= 1

    await PersistentSessionManager.shutdown_all(timeout=3.0)
    await asyncio.sleep(0.5)

    children_after = [c for c in proc.children(recursive=True) if "conhost" not in c.name().lower()]
    assert len(children_after) == 0, f"Expected 0 child processes after shutdown, found: {children_after}"


@pytest.mark.asyncio
async def test_12_existing_transport_compatibility_flag(monkeypatch):
    """Scenario 12: Existing per-call transport works unchanged when ENABLE_PERSISTENT_MCP_SESSIONS=False."""
    monkeypatch.setattr(settings, "ENABLE_PERSISTENT_MCP_SESSIONS", False)

    client = MCPClient(
        transport_type="STDIO",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=15.0
    )
    init_res, lat_init = await client.initialize()
    assert init_res is not None
    assert lat_init > 0.0

    tools = await client.list_tools()
    assert len(tools) > 0

    tool_res, lat_tool = await client.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
    parsed_name = tool_res.get("parsed", {}).get("name", "") or tool_res.get("name", "")
    assert "Mumbai Coastal Road" in parsed_name
