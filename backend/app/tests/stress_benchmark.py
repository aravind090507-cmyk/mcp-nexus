"""
MCP NEXUS — PHASE 15B BENCHMARK SUITE
Fair empirical comparison between Per-Call and Persistent MCP Session architectures.
Measures 1, 5, 10, 25, 50, and 100 concurrent requests across:
- Success rate (%)
- Throughput (req/s)
- Average latency (ms)
- P50, P95, P99 latencies (ms)
- Timeouts & Error counts
- Peak memory & CPU consumption
"""

import sys
import os
import asyncio
import time
import statistics
import json
import psutil

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")))

from app.mcp.client import MCPClient
from app.mcp.persistent_session import PersistentServerSession, PersistentSessionManager

ERP_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend", "app", "mcp", "demo_servers", "erp_server.py"))


async def run_per_call_single(request_id: int, timeout: float = 30.0):
    t0 = time.perf_counter()
    try:
        client = MCPClient(
            transport_type="STDIO",
            command=sys.executable,
            args=[ERP_SCRIPT],
            timeout=timeout
        )
        # In per-call mode, execute tool launches subprocess, initializes, calls tool, and tears down
        res, lat = await asyncio.wait_for(
            client.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"}),
            timeout=timeout
        )
        total_lat = (time.perf_counter() - t0) * 1000.0
        success = "Mumbai Coastal Road" in (res.get("parsed", {}).get("name", "") or res.get("name", ""))
        return {"success": success, "latency_ms": total_lat, "error": None}
    except asyncio.TimeoutError:
        return {"success": False, "latency_ms": (time.perf_counter() - t0) * 1000.0, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "latency_ms": (time.perf_counter() - t0) * 1000.0, "error": str(e)}


async def run_persistent_single(session: PersistentServerSession, request_id: int, timeout: float = 30.0):
    t0 = time.perf_counter()
    try:
        res, tool_lat = await asyncio.wait_for(
            session.call_tool("get_project_status", {"project_id": "PRJ-MUM-001"}),
            timeout=timeout
        )
        total_lat = (time.perf_counter() - t0) * 1000.0
        success = "Mumbai Coastal Road" in res.get("name", "")
        return {"success": success, "latency_ms": total_lat, "error": None}
    except asyncio.TimeoutError:
        return {"success": False, "latency_ms": (time.perf_counter() - t0) * 1000.0, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "latency_ms": (time.perf_counter() - t0) * 1000.0, "error": str(e)}


def calculate_metrics(results, total_duration_s, initial_mem_mb, peak_mem_mb, cpu_pct):
    latencies = [r["latency_ms"] for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    timeouts = [r for r in failures if r["error"] == "Timeout"]
    errors = [r for r in failures if r["error"] != "Timeout"]

    count = len(results)
    success_count = len(latencies)
    success_rate = (success_count / count * 100.0) if count > 0 else 0.0
    throughput = (success_count / total_duration_s) if total_duration_s > 0 else 0.0

    if latencies:
        avg_lat = statistics.mean(latencies)
        p50 = statistics.median(latencies)
        # Quantiles require at least 2 data points
        if len(latencies) >= 2:
            p95 = statistics.quantiles(latencies, n=100)[94] if len(latencies) >= 100 else sorted(latencies)[int(len(latencies) * 0.95)]
            p99 = statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else sorted(latencies)[int(len(latencies) * 0.99)]
        else:
            p95 = latencies[0]
            p99 = latencies[0]
    else:
        avg_lat = p50 = p95 = p99 = 0.0

    return {
        "concurrency": count,
        "success_rate_pct": round(success_rate, 2),
        "throughput_req_per_sec": round(throughput, 2),
        "total_time_sec": round(total_duration_s, 3),
        "avg_latency_ms": round(avg_lat, 2),
        "p50_latency_ms": round(p50, 2),
        "p95_latency_ms": round(p95, 2),
        "p99_latency_ms": round(p99, 2),
        "timeout_count": len(timeouts),
        "error_count": len(errors),
        "initial_memory_mb": round(initial_mem_mb, 2),
        "peak_memory_mb": round(peak_mem_mb, 2),
        "memory_delta_mb": round(peak_mem_mb - initial_mem_mb, 2),
        "cpu_percent": round(cpu_pct, 1)
    }


async def benchmark_concurrency_level(mode: str, concurrency: int, session=None):
    process = psutil.Process()
    process.cpu_percent(interval=None) # reset counter
    initial_mem = process.memory_info().rss / (1024 * 1024)

    t0 = time.perf_counter()
    if mode == "persistent":
        tasks = [run_persistent_single(session, i) for i in range(concurrency)]
        results = await asyncio.gather(*tasks)
    else:
        tasks = [run_per_call_single(i) for i in range(concurrency)]
        results = await asyncio.gather(*tasks)

    duration = time.perf_counter() - t0
    peak_mem = process.memory_info().rss / (1024 * 1024)
    cpu = process.cpu_percent(interval=None)

    return calculate_metrics(results, duration, initial_mem, peak_mem, cpu)


async def main():
    concurrency_levels = [1, 5, 10, 25, 50, 100]
    report = {"persistent": {}, "per_call": {}}

    print("================================================================================")
    print("MCP NEXUS — STRESS & CONCURRENCY BENCHMARK (PHASE 15B)")
    print("Testing levels: 1, 5, 10, 25, 50, 100 concurrent requests")
    print("================================================================================")

    # 1. Persistent Architecture Benchmark
    print("\n--- [1] BENCHMARKING PERSISTENT MCP SESSION ARCHITECTURE ---")
    session = PersistentServerSession(
        server_id="stress-erp",
        server_name="ERP Stress Server",
        command=sys.executable,
        args=[ERP_SCRIPT],
        timeout=30.0
    )
    await session.start()
    print(f"Warm session established (PID: {session.pid})")

    for c in concurrency_levels:
        print(f"Running Persistent Concurrency = {c}...")
        metrics = await benchmark_concurrency_level("persistent", c, session=session)
        report["persistent"][c] = metrics
        print(f"  Level {c:3d}: Success={metrics['success_rate_pct']}% | Throughput={metrics['throughput_req_per_sec']:8.1f} req/s | Avg={metrics['avg_latency_ms']:6.2f}ms | P95={metrics['p95_latency_ms']:6.2f}ms | P99={metrics['p99_latency_ms']:6.2f}ms | MemPeak={metrics['peak_memory_mb']:5.1f}MB")
        await asyncio.sleep(0.5)

    await session.shutdown()

    # 2. Per-Call Architecture Benchmark
    # Note: On Windows, spawning 50-100 simultaneous OS processes can exhaust OS handles/pipes;
    # we test all levels up to 100 to capture true baseline behavior.
    print("\n--- [2] BENCHMARKING PER-CALL MCP SUBPROCESS ARCHITECTURE ---")
    for c in concurrency_levels:
        print(f"Running Per-Call Concurrency = {c}...")
        metrics = await benchmark_concurrency_level("per_call", c)
        report["per_call"][c] = metrics
        print(f"  Level {c:3d}: Success={metrics['success_rate_pct']}% | Throughput={metrics['throughput_req_per_sec']:8.1f} req/s | Avg={metrics['avg_latency_ms']:6.2f}ms | P95={metrics['p95_latency_ms']:6.2f}ms | P99={metrics['p99_latency_ms']:6.2f}ms | MemPeak={metrics['peak_memory_mb']:5.1f}MB")
        await asyncio.sleep(1.0)

    # Save output json
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "stress_benchmark_results.json"))
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nBenchmark results saved to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
