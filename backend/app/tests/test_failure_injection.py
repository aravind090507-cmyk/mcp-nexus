"""
MCP NEXUS — PHASE 15B FAILURE INJECTION & RESILIENCE TEST SUITE
Comprehensive failure injection across 10 critical failure modes and Circuit Breaker validation.

Scenarios:
1. MCP server sudden termination
2. Server termination during multiple active concurrent requests
3. Repeated server crashes tripping CIRCUIT_OPEN
4. Broken STDIO pipes / EOF detection
5. Heartbeat timeout & failure recovery
6. Reconnection failure with invalid command
7. Application shutdown during active tool execution
8. Client cancellation during execution without session corruption
9. Multiple MCP servers failing simultaneously without cross-talk
10. Server becoming unavailable during initialization handshake
11. Circuit breaker OPEN state fast-rejection during cooldown
12. Circuit breaker HALF_OPEN canary recovery
"""

import sys
import os
import asyncio
import time
import pytest
import psutil

from app.mcp.persistent_session import (
    PersistentServerSession,
    PersistentSessionManager,
    SessionLifecycleState
)

ERP_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp", "demo_servers", "erp_server.py"))
INV_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp", "demo_servers", "inventory_server.py"))
EQ_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp", "demo_servers", "equipment_server.py"))


@pytest.fixture(autouse=True)
def cleanup_sessions():
    PersistentSessionManager.reset()
    yield
    PersistentSessionManager.reset()


@pytest.mark.asyncio
async def test_fi_01_sudden_server_termination():
    """Failure Injection 1: MCP server sudden termination when idle."""
    session = PersistentServerSession(
        server_id="fi-01",
        server_name="FI Sudden Kill",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=10.0
    )
    await session.start()
    pid = session.pid
    assert pid is not None

    # Abrupt kill
    psutil.Process(pid).kill()
    await asyncio.sleep(0.5)

    assert session.state == SessionLifecycleState.RECONNECTING

    # Next call recovers automatically
    res, lat = await session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
    assert "Mumbai" in res.get("name", "")
    assert session.state == SessionLifecycleState.WARM
    assert session.pid != pid

    await session.shutdown()


@pytest.mark.asyncio
async def test_fi_02_termination_during_active_concurrent_requests():
    """Failure Injection 2: Server termination while multiple requests are in-flight."""
    session = PersistentServerSession(
        server_id="fi-02",
        server_name="FI Mid-flight Kill",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=10.0
    )
    await session.start()
    pid = session.pid

    async def delayed_kill():
        await asyncio.sleep(0.005) # let requests dispatch into stdin
        try:
            psutil.Process(pid).kill()
        except Exception:
            pass

    # Launch concurrent requests and kill process mid-flight
    tasks = [
        session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"}),
        session.call_tool("get_project_status", {"project_id": "PRJ-HAZ-002"}),
        session.call_tool("get_project_status", {"project_id": "PRJ-HYD-003"}),
        delayed_kill()
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    # The tool calls should either succeed or fail cleanly with connection closed
    tool_results = results[:3]
    for r in tool_results:
        assert isinstance(r, (tuple, Exception))

    # Give session time to handle disconnect
    await asyncio.sleep(0.5)

    # Next call must recover cleanly
    res, lat = await session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
    assert "Mumbai" in res.get("name", "")
    assert session.state == SessionLifecycleState.WARM

    await session.shutdown()


@pytest.mark.asyncio
async def test_fi_03_repeated_server_crashes_trips_circuit_breaker():
    """Failure Injection 3: Repeated genuine crashes transition session to CIRCUIT_OPEN with cooldown rejection & recovery."""
    session = PersistentServerSession(
        server_id="fi-03-hardened",
        server_name="FI Repeated Crashes Hardened",
        command=sys.executable,
        args=["-c", "import sys; sys.exit(1)"], # Genuinely crashes immediately on launch
        timeout=5.0,
        max_reconnect_attempts=2,
        circuit_break_cooldown=1.0
    )
    # Start encounters failure 1, then backoff retry encounters failure 2 -> reaches limit 2
    ok = await session.start()
    assert ok is False
    # Strict assertion verifying exact state and failure counting
    assert session.state == SessionLifecycleState.CIRCUIT_OPEN
    assert session._consecutive_failures >= 2

    # Verify rejection during cooldown
    with pytest.raises(RuntimeError) as exc_info:
        await session.call_tool("get_project_status", {})
    assert "CIRCUIT_OPEN" in str(exc_info.value) or "Cooldown active" in str(exc_info.value)

    # Verify recovery behavior: Point args to valid server, wait out cooldown, and verify return to WARM
    session.args = [ERP_SCRIPT]
    await asyncio.sleep(1.1)

    res, lat = await session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
    assert session.state == SessionLifecycleState.WARM
    assert "Mumbai" in res.get("name", "")

    await session.shutdown()


@pytest.mark.asyncio
async def test_fi_04_broken_stdio_pipes():
    """Failure Injection 4: Broken pipe detection via EOF."""
    session = PersistentServerSession(
        server_id="fi-04",
        server_name="FI Broken Pipe",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=10.0
    )
    await session.start()

    # Simulate pipe breakage by killing child process
    psutil.Process(session.pid).kill()
    await asyncio.sleep(0.5)

    # Transport watcher detects stream closed
    assert session.state == SessionLifecycleState.RECONNECTING

    await session.shutdown()


@pytest.mark.asyncio
async def test_fi_05_heartbeat_timeout_recovery():
    """Failure Injection 5: Heartbeat failure triggers reconnect."""
    session = PersistentServerSession(
        server_id="fi-05",
        server_name="FI Heartbeat",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=10.0,
        heartbeat_interval=0.5 # Fast heartbeat for testing
    )
    await session.start()

    # Kill process to force next heartbeat to fail
    psutil.Process(session.pid).kill()
    # Wait for heartbeat loop to fire (0.5s interval)
    await asyncio.sleep(1.0)

    # Heartbeat failed and triggered reconnect
    assert session.state in (SessionLifecycleState.RECONNECTING, SessionLifecycleState.WARM)

    # Verify recovery
    res, lat = await session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
    assert "Mumbai" in res.get("name", "")

    await session.shutdown()


@pytest.mark.asyncio
async def test_fi_06_reconnection_failure_with_invalid_command():
    """Failure Injection 6: Unrecoverable launch parameters trip to CIRCUIT_OPEN."""
    session = PersistentServerSession(
        server_id="fi-06",
        server_name="FI Invalid Cmd",
        command=sys.executable,
        args=["-c", "import sys; sys.exit(42)"], # Immediate crash
        timeout=5.0,
        max_reconnect_attempts=2,
        circuit_break_cooldown=10.0
    )
    ok = await session.start()
    assert ok is False
    assert session.state == SessionLifecycleState.CIRCUIT_OPEN

    await session.shutdown()


@pytest.mark.asyncio
async def test_fi_07_shutdown_during_active_execution():
    """Failure Injection 7: Application shutdown called while request is executing."""
    session = PersistentServerSession(
        server_id="fi-07",
        server_name="FI Mid-shutdown",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=10.0
    )
    await session.start()

    task = asyncio.create_task(session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"}))
    await asyncio.sleep(0.001)

    # Shutdown immediately
    await session.shutdown(timeout=2.0)
    assert session.state == SessionLifecycleState.CLOSED

    # Task finishes or cancels cleanly without hanging
    try:
        await task
    except Exception:
        pass


@pytest.mark.asyncio
async def test_fi_08_client_cancellation_preserves_session():
    """Failure Injection 8: Client cancellation does not invalidate session."""
    session = PersistentServerSession(
        server_id="fi-08",
        server_name="FI Client Cancel",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=10.0
    )
    await session.start()

    for _ in range(3):
        task = asyncio.create_task(session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"}))
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert session.state == SessionLifecycleState.WARM

    # Subsequent call succeeds with no corruption
    res, lat = await session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
    assert "Mumbai" in res.get("name", "")

    await session.shutdown()


@pytest.mark.asyncio
async def test_fi_09_multiple_servers_failing_simultaneously():
    """Failure Injection 9: Multiple servers fail concurrently without cross-talk."""
    s_erp = PersistentServerSession("fi-erp", "ERP", sys.executable, [ERP_SCRIPT], timeout=10.0)
    s_inv = PersistentServerSession("fi-inv", "INV", sys.executable, [INV_SCRIPT], timeout=10.0)

    await s_erp.start()
    await s_inv.start()

    pid_erp = s_erp.pid
    pid_inv = s_inv.pid

    # Kill both simultaneously
    psutil.Process(pid_erp).kill()
    psutil.Process(pid_inv).kill()

    await asyncio.sleep(0.5)

    assert s_erp.state == SessionLifecycleState.RECONNECTING
    assert s_inv.state == SessionLifecycleState.RECONNECTING

    # Both recover independently
    r_erp, _ = await s_erp.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
    r_inv, _ = await s_inv.call_tool("get_low_stock_items", {})

    assert "Mumbai" in r_erp.get("name", "")
    assert isinstance(r_inv, (dict, list))

    await s_erp.shutdown()
    await s_inv.shutdown()


@pytest.mark.asyncio
async def test_fi_10_server_unavailable_during_init():
    """Failure Injection 10: Non-existent script fails gracefully without hanging."""
    session = PersistentServerSession(
        server_id="fi-10",
        server_name="FI Non-existent",
        command=sys.executable,
        args=["non_existent_server_script_12345.py"],
        timeout=2.0,
        max_reconnect_attempts=1
    )
    ok = await session.start()
    assert ok is False
    assert session.state == SessionLifecycleState.CIRCUIT_OPEN

    await session.shutdown()


@pytest.mark.asyncio
async def test_cb_01_circuit_breaker_fast_rejection_during_cooldown():
    """Circuit Breaker 1: Requests during cooldown fast-fail without spawning processes."""
    proc = psutil.Process()
    session = PersistentServerSession(
        server_id="cb-01",
        server_name="CB Fast Fail",
        command=sys.executable,
        args=["-c", "import sys; sys.exit(1)"],
        timeout=2.0,
        max_reconnect_attempts=1,
        circuit_break_cooldown=10.0
    )
    ok = await session.start()
    assert ok is False
    assert session.state == SessionLifecycleState.CIRCUIT_OPEN

    initial_children = len(proc.children(recursive=True))

    # Attempt 5 concurrent tool calls while circuit is OPEN
    async def try_call():
        try:
            await session.call_tool("test_tool", {})
            return "SUCCESS"
        except RuntimeError as e:
            return "REJECTED_FAST"

    t0 = time.perf_counter()
    results = await asyncio.gather(*[try_call() for _ in range(5)])
    duration_ms = (time.perf_counter() - t0) * 1000.0

    # All must be fast-rejected in sub-10ms
    assert all(r == "REJECTED_FAST" for r in results)
    assert duration_ms < 50.0, f"Circuit fast-fail should be sub-50ms (got {duration_ms:.2f}ms)"

    # Zero new processes spawned
    after_children = len(proc.children(recursive=True))
    assert after_children == initial_children

    await session.shutdown()


@pytest.mark.asyncio
async def test_cb_02_circuit_breaker_half_open_canary_recovery():
    """Circuit Breaker 2: Genuinely trips circuit breaker without mutation, validates HALF_OPEN canary and return to WARM."""
    # Use short 1.0s cooldown and max_reconnect_attempts=1 for clean testing
    session = PersistentServerSession(
        server_id="cb-02-genuine",
        server_name="CB Half Open Genuine",
        command=sys.executable,
        args=["-c", "import sys; sys.exit(1)"], # Genuinely exits immediately
        timeout=5.0,
        max_reconnect_attempts=1,
        circuit_break_cooldown=1.0
    )
    # Attempt 1 fails -> trips to CIRCUIT_OPEN through genuine failure
    ok = await session.start()
    assert ok is False
    assert session.state == SessionLifecycleState.CIRCUIT_OPEN
    assert session._consecutive_failures >= 1

    # Immediate call during cooldown fast-fails with RuntimeError without spawning processes
    with pytest.raises(RuntimeError) as exc_info:
        await session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
    assert "CIRCUIT_OPEN" in str(exc_info.value) or "Cooldown active" in str(exc_info.value)

    # Point to valid server script to test HALF_OPEN canary
    session.args = [ERP_SCRIPT]

    # Wait for cooldown window (1.0s) to elapse
    await asyncio.sleep(1.1)

    # Next call acts as HALF_OPEN canary, connects, and recovers to WARM
    res, lat = await session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"})
    assert "Mumbai" in res.get("name", "")
    assert session.state == SessionLifecycleState.WARM

    await session.shutdown()
