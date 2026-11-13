"""
MCP NEXUS — OPERATIONAL OBSERVABILITY & TELEMETRY SERVICE
Comprehensive, bounded, real-time monitoring of session lifecycles, execution latencies
(with exact P95/P99 percentile calculation), resource metrics, and security events.
"""

import threading
import time
import os
import math
from collections import deque
from typing import Dict, Any, List, Optional
import datetime

logger = logging = __import__("logging").getLogger("mcp-nexus.observability")


class ObservabilityService:
    """
    Centralized Operational Observability Service.
    Thread-safe, bounded telemetry recorder for MCP Nexus enterprise operations.
    """
    _lock = threading.RLock()

    # Latency sliding window for exact P95 / P99 calculation (bounded to last 1000 observations)
    _latencies: deque = deque(maxlen=1000)

    # Execution counters
    _total_executions: int = 0
    _successful_executions: int = 0
    _failed_executions: int = 0
    _fallback_executions: int = 0
    _timeout_executions: int = 0

    # Session counters
    _session_creation_failures: int = 0
    _session_reconnect_attempts: int = 0
    _heartbeat_failures: int = 0

    # Security counters
    _unauthorized_activation_attempts: int = 0
    _cross_tenant_access_attempts: int = 0
    _policy_denials: int = 0
    _approval_failures: int = 0
    _emergency_shutdown_events: int = 0

    @classmethod
    def record_execution(cls, duration_ms: float, success: bool, is_fallback: bool = False, is_timeout: bool = False):
        with cls._lock:
            cls._total_executions += 1
            if success:
                cls._successful_executions += 1
            else:
                cls._failed_executions += 1
            if is_fallback:
                cls._fallback_executions += 1
            if is_timeout:
                cls._timeout_executions += 1
            if duration_ms > 0:
                cls._latencies.append(duration_ms)

    @classmethod
    def record_session_event(cls, event_type: str):
        with cls._lock:
            if event_type == "INIT_FAILURE":
                cls._session_creation_failures += 1
            elif event_type == "RECONNECT_ATTEMPT":
                cls._session_reconnect_attempts += 1
            elif event_type == "HEARTBEAT_FAILURE":
                cls._heartbeat_failures += 1

    @classmethod
    def record_security_event(cls, event_type: str):
        with cls._lock:
            if event_type == "UNAUTHORIZED_ACTIVATION":
                cls._unauthorized_activation_attempts += 1
            elif event_type == "CROSS_TENANT_ACCESS":
                cls._cross_tenant_access_attempts += 1
            elif event_type == "POLICY_DENIAL":
                cls._policy_denials += 1
            elif event_type == "APPROVAL_FAILURE":
                cls._approval_failures += 1
            elif event_type == "EMERGENCY_SHUTDOWN":
                cls._emergency_shutdown_events += 1

    @classmethod
    def calculate_percentiles(cls) -> Dict[str, float]:
        with cls._lock:
            if not cls._latencies:
                return {"avg_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}
            sorted_lat = sorted(cls._latencies)
            n = len(sorted_lat)
            avg = round(sum(sorted_lat) / n, 2)
            idx95 = min(int(math.ceil(0.95 * n)) - 1, n - 1)
            idx99 = min(int(math.ceil(0.99 * n)) - 1, n - 1)
            return {
                "avg_ms": avg,
                "p95_ms": round(sorted_lat[max(0, idx95)], 2),
                "p99_ms": round(sorted_lat[max(0, idx99)], 2)
            }

    @classmethod
    def get_resource_metrics(cls) -> Dict[str, Any]:
        """Calculates real process and thread resource measurements."""
        active_threads = threading.active_count()
        rss_mb = 0.0
        try:
            import psutil
            process = psutil.Process(os.getpid())
            rss_mb = round(process.memory_info().rss / (1024 * 1024), 2)
        except Exception:
            # Fallback if psutil is not available
            rss_mb = 0.0

        from app.database.session import get_current_managed_context
        ctx = get_current_managed_context()

        return {
            "active_worker_threads": active_threads,
            "process_rss_mb": rss_mb,
            "database_engine": {
                "url": str(ctx.url),
                "active_leases": ctx.active_leases,
                "is_retired": ctx.is_retired,
                "is_disposed": ctx.is_disposed
            }
        }

    @classmethod
    def get_telemetry_snapshot(cls) -> Dict[str, Any]:
        """Returns complete, sanitized operational telemetry snapshot."""
        from app.mcp.persistent_session import PersistentSessionManager
        from app.mcp.client import MCPConnectionManager

        pool_status = PersistentSessionManager.get_pool_status()
        percentiles = cls.calculate_percentiles()
        resources = cls.get_resource_metrics()

        with cls._lock:
            total_execs = cls._total_executions
            success_execs = cls._successful_executions
            fail_execs = cls._failed_executions
            fallback_execs = cls._fallback_executions
            timeout_execs = cls._timeout_executions

            success_rate = round((success_execs / total_execs * 100.0), 2) if total_execs > 0 else 100.0

            return {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "session_metrics": {
                    "active_persistent_sessions": pool_status.get("warm_sessions", 0),
                    "total_sessions": pool_status.get("total_sessions", 0),
                    "total_pending_requests": pool_status.get("total_pending_requests", 0),
                    "total_subprocess_rss_mb": pool_status.get("total_subprocess_rss_mb", 0.0),
                    "session_creation_failures": cls._session_creation_failures,
                    "session_reconnect_attempts": cls._session_reconnect_attempts,
                    "heartbeat_failures": cls._heartbeat_failures,
                    "emergency_disabled": pool_status.get("emergency_disabled", False)
                },
                "execution_metrics": {
                    "total_executions": total_execs,
                    "successful_executions": success_execs,
                    "failed_executions": fail_execs,
                    "fallback_executions": fallback_execs,
                    "timeout_executions": timeout_execs,
                    "success_rate_pct": success_rate,
                    "latency": percentiles
                },
                "resource_metrics": resources,
                "security_metrics": {
                    "unauthorized_activation_attempts": cls._unauthorized_activation_attempts,
                    "cross_tenant_access_attempts": cls._cross_tenant_access_attempts,
                    "policy_denials": cls._policy_denials,
                    "approval_failures": cls._approval_failures,
                    "emergency_shutdown_events": cls._emergency_shutdown_events
                }
            }

    @classmethod
    def reset(cls):
        """Resets telemetry counters for test harness isolation."""
        with cls._lock:
            cls._latencies.clear()
            cls._total_executions = 0
            cls._successful_executions = 0
            cls._failed_executions = 0
            cls._fallback_executions = 0
            cls._timeout_executions = 0
            cls._session_creation_failures = 0
            cls._session_reconnect_attempts = 0
            cls._heartbeat_failures = 0
            cls._unauthorized_activation_attempts = 0
            cls._cross_tenant_access_attempts = 0
            cls._policy_denials = 0
            cls._approval_failures = 0
            cls._emergency_shutdown_events = 0
