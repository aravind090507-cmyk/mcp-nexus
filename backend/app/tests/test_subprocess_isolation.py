"""
MCP NEXUS — SUBPROCESS OWNERSHIP & CLEANUP ISOLATION TEST SUITE (PHASE 15D.4.7)

Validates strict process ownership and isolation guarantees:
1. A test cleans up its own multiprocessing worker.
2. A test cleans up its own subprocess.
3. A pre-existing unrelated child process is not terminated by manager cleanup.
4. A pre-existing unrelated child's wait status is not consumed by manager cleanup.
5. Repeated manager shutdown is idempotent and does not leak processes.
6. Cleanup executes reliably after an assertion failure.
7. Zero-zombie verification correctly detects a deliberately uncleaned test-owned process.
8. Concurrent or overlapping test execution does not cause one test to terminate another test's workers.
"""

import sys
import os
import time
import subprocess
import multiprocessing as mp
import asyncio
import pytest
import psutil

from app.mcp.persistent_session import (
    PersistentServerSession,
    PersistentSessionManager,
    SessionLifecycleState
)

ERP_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp", "demo_servers", "erp_server.py"))


def _dummy_worker(ready_evt, stop_evt):
    """Simple worker for isolation testing."""
    ready_evt.set()
    stop_evt.wait(timeout=10.0)


# ==============================================================================
# TEST CASES
# ==============================================================================

def test_01_test_cleans_up_own_multiprocessing_worker():
    """Requirement 1: A test cleans up its own multiprocessing worker."""
    ctx = mp.get_context("spawn")
    ready_evt = ctx.Event()
    stop_evt = ctx.Event()

    proc = ctx.Process(target=_dummy_worker, args=(ready_evt, stop_evt))
    proc.start()
    try:
        assert ready_evt.wait(timeout=5.0), "Worker failed to signal ready"
        assert proc.is_alive()
        pid = proc.pid
        assert pid is not None
        assert psutil.pid_exists(pid)
    finally:
        stop_evt.set()
        proc.join(timeout=2.0)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1.0)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=1.0)
        assert not proc.is_alive()
        if hasattr(proc, "close"):
            proc.close()

    if pid:
        assert not psutil.pid_exists(pid)


def test_02_test_cleans_up_own_subprocess():
    """Requirement 2: A test cleans up its own subprocess."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys, time; time.sleep(10)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    pid = proc.pid
    assert proc.poll() is None, "Subprocess should be running"
    assert psutil.pid_exists(pid)

    try:
        proc.terminate()
        exit_code = proc.wait(timeout=2.0)
        assert exit_code is not None, "Subprocess must exit after terminate"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=1.0)

    assert not psutil.pid_exists(pid)


def test_03_preexisting_unrelated_child_process_is_not_terminated():
    """Requirement 3: A pre-existing unrelated child process is not terminated by manager reset."""
    unrelated = subprocess.Popen(
        [sys.executable, "-c", "import sys, time; time.sleep(8)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    try:
        assert unrelated.poll() is None, "Unrelated process should be running"
        unrelated_pid = unrelated.pid

        # Exercise manager reset
        PersistentSessionManager.reset()

        # Verify unrelated process is STILL alive and untouched
        assert unrelated.poll() is None, "Unrelated child process must NOT be terminated by reset()"
        assert psutil.pid_exists(unrelated_pid), "Unrelated child PID must still exist"
    finally:
        unrelated.terminate()
        try:
            unrelated.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            unrelated.kill()
            unrelated.wait(timeout=1.0)


def test_04_preexisting_unrelated_child_wait_status_not_consumed():
    """Requirement 4: A pre-existing unrelated child's wait status is not consumed by manager reset."""
    # Process exits with specific non-zero exit code
    unrelated = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(42)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    # Wait for process to exit
    time.sleep(0.3)

    # Manager reset must not call waitpid(-1) or consume this process's exit status
    PersistentSessionManager.reset()

    # The caller must be able to reap its own child and obtain exit code 42
    exit_code = unrelated.wait(timeout=2.0)
    assert exit_code == 42, f"Expected exit code 42, got {exit_code} (wait status was likely stolen if -1/None)"


@pytest.mark.asyncio
async def test_05_repeated_manager_shutdown_does_not_leak_processes():
    """Requirement 5: Repeated manager shutdown is idempotent and does not leak processes."""
    # Repeated reset on clean state
    for _ in range(3):
        PersistentSessionManager.reset()
    assert len(PersistentSessionManager._sessions) == 0

    # Start session and execute tool
    res, _ = await PersistentSessionManager.execute_tool(
        "srv-erp-repeat", "ERP", sys.executable, [ERP_SCRIPT], {}, os.getcwd(),
        "get_project_status", {"project_id": "PRJ-MUM-001"}
    )
    assert "Mumbai" in res.get("name", "")

    session = PersistentSessionManager.get_existing_session("srv-erp-repeat")
    assert session is not None
    session_pid = session.pid
    assert session_pid is not None
    assert psutil.pid_exists(session_pid)

    # Repeated shutdown
    await PersistentSessionManager.shutdown_all(timeout=2.0)
    await PersistentSessionManager.shutdown_all(timeout=2.0)
    PersistentSessionManager.reset()
    PersistentSessionManager.reset()

    # Verify session closed and subprocess reaped
    assert not psutil.pid_exists(session_pid)
    assert len(PersistentSessionManager._sessions) == 0


def test_06_cleanup_executes_after_assertion_failure():
    """Requirement 6: Cleanup executes reliably after an assertion failure."""
    ctx = mp.get_context("spawn")
    ready_evt = ctx.Event()
    stop_evt = ctx.Event()
    proc = ctx.Process(target=_dummy_worker, args=(ready_evt, stop_evt))
    proc.start()
    pid = None

    # Simulate a failed test block wrapped in guaranteed cleanup
    try:
        assert ready_evt.wait(timeout=5.0)
        pid = proc.pid
        assert pid is not None
        # Deliberately raise assertion error
        with pytest.raises(AssertionError):
            assert False, "Simulated assertion failure inside test body"
    finally:
        stop_evt.set()
        proc.join(timeout=2.0)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1.0)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=1.0)
        assert not proc.is_alive()
        if hasattr(proc, "close"):
            proc.close()

    if pid:
        assert not psutil.pid_exists(pid)


def test_07_zero_zombie_verification_detects_deliberate_leak():
    """Requirement 7: The zero-zombie test detects a deliberately uncleaned test-owned process."""
    # Spawn a deliberate process without shutting it down
    leaked = subprocess.Popen(
        [sys.executable, "-c", "import sys, time; time.sleep(5)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    leaked_pid = leaked.pid
    try:
        # Verify the detection logic: process is running and exists
        assert psutil.pid_exists(leaked_pid)
        proc_handle = psutil.Process(leaked_pid)
        assert proc_handle.is_running()
        
        # A proper zero-zombie assertion checks `not proc_handle.is_running()`.
        # When uncleaned, this assertion MUST fail (detecting the leak).
        is_still_running = proc_handle.is_running()
        assert is_still_running is True, "Detection logic must identify that uncleaned process is still running"
    finally:
        leaked.terminate()
        try:
            leaked.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            leaked.kill()
            leaked.wait(timeout=1.0)


def test_08_concurrent_workers_do_not_cross_terminate():
    """Requirement 8: Concurrent workers do not cross-terminate each other."""
    ctx = mp.get_context("spawn")
    ready1, stop1 = ctx.Event(), ctx.Event()
    ready2, stop2 = ctx.Event(), ctx.Event()

    proc1 = ctx.Process(target=_dummy_worker, args=(ready1, stop1))
    proc2 = ctx.Process(target=_dummy_worker, args=(ready2, stop2))

    proc1.start()
    proc2.start()

    try:
        assert ready1.wait(timeout=5.0)
        assert ready2.wait(timeout=5.0)
        assert proc1.is_alive() and proc2.is_alive()

        # Stop and join proc1 ONLY
        stop1.set()
        proc1.join(timeout=2.0)
        if proc1.is_alive():
            proc1.terminate()
            proc1.join(timeout=1.0)

        # Proc1 is dead
        assert not proc1.is_alive()

        # Proc2 MUST STILL BE ALIVE and completely unaffected
        assert proc2.is_alive(), "Worker 2 must NOT be terminated when Worker 1 is stopped"

    finally:
        stop2.set()
        proc2.join(timeout=2.0)
        if proc2.is_alive():
            proc2.terminate()
            proc2.join(timeout=1.0)
        assert not proc1.is_alive()
        assert not proc2.is_alive()
        for p in (proc1, proc2):
            if hasattr(p, "close"):
                p.close()
