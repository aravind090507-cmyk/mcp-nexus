"""
MCP NEXUS — PHASE 15B SOAK & RESOURCE LEAK AUDIT
Continuous enterprise load testing across all 3 MCP servers (ERP, Inventory, Equipment).

Monitors:
- Python process count
- Child process count (via psutil.Process().children())
- Resident Set Size (RSS) memory in MB
- OS Handle count (Windows handles / file descriptors)
- OS Thread count
- Active event loop tasks
- Pending requests in MCP dispatcher
- Active sessions in PersistentSessionManager

Detects:
- Memory leaks (unbounded RSS growth)
- Handle / file descriptor leaks
- Subprocess leaks (orphaned children)
- Task leaks (uncollected coroutines)
- Stalled / uncollected pending requests
"""

import sys
import os
import asyncio
import time
import datetime
import json
import argparse
import psutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")))

from app.mcp.persistent_session import PersistentServerSession, PersistentSessionManager

ERP_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend", "app", "mcp", "demo_servers", "erp_server.py"))
INV_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend", "app", "mcp", "demo_servers", "inventory_server.py"))
EQ_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend", "app", "mcp", "demo_servers", "equipment_server.py"))


async def run_soak(duration_sec: float, batch_size: int = 10, batch_delay: float = 0.05, out_file: str = "soak_test_metrics.jsonl"):
    proc = psutil.Process()
    start_time = time.time()
    start_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    end_time = start_time + duration_sec

    # Start warm sessions for all 3 demo servers
    s_erp = PersistentSessionManager.get_session("soak-erp", "ERP", sys.executable, [ERP_SCRIPT])
    s_inv = PersistentSessionManager.get_session("soak-inv", "INV", sys.executable, [INV_SCRIPT])
    s_eq = PersistentSessionManager.get_session("soak-eq", "EQ", sys.executable, [EQ_SCRIPT])

    await asyncio.gather(s_erp.start(), s_inv.start(), s_eq.start())

    initial_rss = proc.memory_info().rss / (1024 * 1024)
    initial_handles = proc.num_handles()
    initial_children = len([c for c in proc.children(recursive=True) if "conhost" not in c.name().lower()])

    print(f"=== Starting Soak Test (Duration: {duration_sec}s, Batch Size: {batch_size}) ===")
    print(f"Baseline: RSS={initial_rss:.2f}MB | Handles={initial_handles} | Children={initial_children}")

    snapshots = []
    total_requests = 0
    total_failures = 0
    cycle = 0

    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), out_file))
    with open(out_path, "w") as f:
        f.write("") # truncate

    try:
        while time.time() < end_time:
            cycle += 1
            # Dispatch concurrent batch across all 3 servers
            tasks = []
            for i in range(batch_size):
                if i % 3 == 0:
                    tasks.append(s_erp.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"}))
                elif i % 3 == 1:
                    tasks.append(s_inv.call_tool("get_low_stock_items", {"threshold": 50}))
                else:
                    tasks.append(s_eq.call_tool("get_maintenance_schedule", {}))

            t0 = time.perf_counter()
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            batch_lat = (time.perf_counter() - t0) * 1000.0

            failures = sum(1 for r in batch_results if isinstance(r, Exception))
            total_requests += len(tasks)
            total_failures += failures

            # Sample metrics every 10 cycles or on last cycle
            if cycle % 10 == 0 or time.time() >= end_time:
                now_elapsed = time.time() - start_time
                current_rss = proc.memory_info().rss / (1024 * 1024)
                current_handles = proc.num_handles()
                current_threads = proc.num_threads()
                children = [c.pid for c in proc.children(recursive=True) if "conhost" not in c.name().lower()]
                current_tasks = len(asyncio.all_tasks())

                # Check dispatcher pending requests
                pending_count = 0
                for s in (s_erp, s_inv, s_eq):
                    if s._session and hasattr(s._session, "_dispatcher"):
                        pending_count += len(getattr(s._session._dispatcher, "_pending", {}))

                snapshot = {
                    "cycle": cycle,
                    "elapsed_sec": round(now_elapsed, 1),
                    "total_requests": total_requests,
                    "total_failures": total_failures,
                    "batch_latency_ms": round(batch_lat, 2),
                    "rss_memory_mb": round(current_rss, 2),
                    "rss_delta_mb": round(current_rss - initial_rss, 2),
                    "handle_count": current_handles,
                    "handle_delta": current_handles - initial_handles,
                    "thread_count": current_threads,
                    "child_process_count": len(children),
                    "child_pids": children,
                    "event_loop_task_count": current_tasks,
                    "pending_requests_count": pending_count,
                    "session_count": len(PersistentSessionManager._sessions)
                }
                snapshots.append(snapshot)
                with open(out_path, "a") as f:
                    f.write(json.dumps(snapshot) + "\n")

                print(
                    f"[{now_elapsed:6.1f}s] Req={total_requests:6d} | Fails={total_failures} | "
                    f"Lat={batch_lat:5.1f}ms | RSS={current_rss:5.1f}MB (d={snapshot['rss_delta_mb']:+4.1f}MB) | "
                    f"Handles={current_handles:4d} (d={snapshot['handle_delta']:+3d}) | "
                    f"Tasks={current_tasks} | Pending={pending_count} | Children={len(children)}"
                )

            await asyncio.sleep(batch_delay)

    finally:
        print("\nShutting down sessions...")
        await PersistentSessionManager.shutdown_all(timeout=3.0)
        await asyncio.sleep(0.5)

        final_children = len([c for c in proc.children(recursive=True) if "conhost" not in c.name().lower()])
        final_rss = proc.memory_info().rss / (1024 * 1024)
        final_handles = proc.num_handles()

        end_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        summary = {
            "start_timestamp_utc": start_iso,
            "end_timestamp_utc": end_iso,
            "target_duration_sec": duration_sec,
            "actual_duration_sec": round(time.time() - start_time, 2),
            "total_requests": total_requests,
            "total_failures": total_failures,
            "success_rate_pct": round(((total_requests - total_failures) / total_requests * 100.0) if total_requests > 0 else 0.0, 2),
            "initial_rss_mb": round(initial_rss, 2),
            "final_rss_mb": round(final_rss, 2),
            "net_memory_delta_mb": round(final_rss - initial_rss, 2),
            "initial_handles": initial_handles,
            "final_handles": final_handles,
            "net_handle_delta": final_handles - initial_handles,
            "final_child_count": final_children,
            "snapshots_recorded": len(snapshots)
        }

        sum_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "soak_test_summary.json"))
        with open(sum_path, "w") as f:
            json.dump(summary, f, indent=2)

        print("\n=== Soak Test Completed ===")
        print(f"Requests: {total_requests} | Success Rate: {summary['success_rate_pct']}%")
        print(f"Memory: Initial {initial_rss:.1f}MB -> Final {final_rss:.1f}MB (Delta: {summary['net_memory_delta_mb']:+.1f}MB)")
        print(f"Handles: Initial {initial_handles} -> Final {final_handles} (Delta: {summary['net_handle_delta']:+d})")
        print(f"Orphan Children: {final_children}")
        print(f"Summary saved to: {sum_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=60.0, help="Duration in seconds")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size per cycle")
    parser.add_argument("--batch-delay", type=float, default=0.02, help="Delay between batches")
    parser.add_argument("--out-file", type=str, default="soak_test_metrics.jsonl")
    args = parser.parse_args()

    asyncio.run(run_soak(
        duration_sec=args.duration,
        batch_size=args.batch_size,
        batch_delay=args.batch_delay,
        out_file=args.out_file
    ))
