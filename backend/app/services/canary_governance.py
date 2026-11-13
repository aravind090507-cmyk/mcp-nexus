"""
MCP NEXUS — CANARY GOVERNANCE & READINESS SERVICE
Centralized evaluation of server canary eligibility, policy alignment,
operational readiness thresholds, and enterprise deployment compliance.
"""

import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session
from app.models.all_models import MCPServer, User
from app.core.config import settings
from app.services.deployment_governance import DeploymentGovernanceService, DeploymentState
from app.mcp.persistent_session import PersistentSessionManager
from app.mcp.client import MCPConnectionManager
from app.services.policy_engine import PolicyEngine


class CanaryEligibilityDecision(BaseModel):
    is_eligible: bool
    reason: str
    server_id: str
    server_name: str
    environment: str
    evaluated_at: str
    deployment_state: str
    policy_allowed: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class CanaryGovernanceService:
    """
    Centralized Canary Governance & Eligibility Evaluation Service.
    Evaluates multi-vector enterprise readiness conditions before admitting any
    MCP server to persistent session canary execution.
    """

    @classmethod
    def evaluate_server_canary_eligibility(
        cls,
        db: Session,
        server: MCPServer,
        user: Optional[User] = None
    ) -> CanaryEligibilityDecision:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        current_env = getattr(settings, "ENVIRONMENT", "Development").capitalize()
        state = DeploymentGovernanceService.get_server_state(server)

        # 1. Global activation check
        if not getattr(settings, "ENABLE_PERSISTENT_MCP_SESSIONS", False):
            return CanaryEligibilityDecision(
                is_eligible=False,
                reason="Global feature flag ENABLE_PERSISTENT_MCP_SESSIONS is disabled.",
                server_id=server.id,
                server_name=server.name,
                environment=current_env,
                evaluated_at=now_iso,
                deployment_state=state.value,
                policy_allowed=False,
                details={"gate": "GLOBAL_FLAG_DISABLED"}
            )

        # 2. Emergency kill switch check
        if PersistentSessionManager.is_emergency_disabled():
            return CanaryEligibilityDecision(
                is_eligible=False,
                reason="Global emergency kill switch is currently ENGAGED.",
                server_id=server.id,
                server_name=server.name,
                environment=current_env,
                evaluated_at=now_iso,
                deployment_state=state.value,
                policy_allowed=False,
                details={"gate": "EMERGENCY_KILL_SWITCH_ACTIVE"}
            )

        # 3. Tenant isolation check (Defense-in-depth: Tenant authorization first)
        if user is not None and str(server.organization_id) != str(user.organization_id):
            return CanaryEligibilityDecision(
                is_eligible=False,
                reason="Tenant isolation boundary: Server does not belong to user's organization.",
                server_id=server.id,
                server_name=server.name,
                environment=current_env,
                evaluated_at=now_iso,
                deployment_state=state.value,
                policy_allowed=False,
                details={"gate": "CROSS_TENANT_REJECTED"}
            )

        # 4. Server allowlist check (no wildcard in Staging or Production)
        allowed_servers = getattr(settings, "PERSISTENT_MCP_SERVERS", "")
        if not allowed_servers or not allowed_servers.strip() or allowed_servers.strip().lower() == "none":
            return CanaryEligibilityDecision(
                is_eligible=False,
                reason="Server is not in PERSISTENT_MCP_SERVERS allowlist (allowlist is empty).",
                server_id=server.id,
                server_name=server.name,
                environment=current_env,
                evaluated_at=now_iso,
                deployment_state=state.value,
                policy_allowed=False,
                details={"gate": "ALLOWLIST_EMPTY"}
            )

        if allowed_servers.strip() == "*":
            if current_env in ("Staging", "Production"):
                return CanaryEligibilityDecision(
                    is_eligible=False,
                    reason=f"Wildcard PERSISTENT_MCP_SERVERS='*' is strictly forbidden in {current_env}.",
                    server_id=server.id,
                    server_name=server.name,
                    environment=current_env,
                    evaluated_at=now_iso,
                    deployment_state=state.value,
                    policy_allowed=False,
                    details={"gate": "WILDCARD_ALLOWLIST_FORBIDDEN"}
                )

        items = [x.strip().lower() for x in allowed_servers.split(",") if x.strip()]
        identifier = (server.identifier or "").lower()
        s_id = (server.id or "").lower()
        s_name = (server.name or "").lower()
        if not any(x in (identifier, s_id, s_name) for x in items):
            return CanaryEligibilityDecision(
                is_eligible=False,
                reason=f"Server '{server.name}' ({server.identifier}) is not in PERSISTENT_MCP_SERVERS allowlist.",
                server_id=server.id,
                server_name=server.name,
                environment=current_env,
                evaluated_at=now_iso,
                deployment_state=state.value,
                policy_allowed=False,
                details={"gate": "NOT_IN_ALLOWLIST"}
            )

        # 5. Server enablement and status
        if not server.is_enabled:
            return CanaryEligibilityDecision(
                is_eligible=False,
                reason=f"Server '{server.name}' is administratively disabled.",
                server_id=server.id,
                server_name=server.name,
                environment=current_env,
                evaluated_at=now_iso,
                deployment_state=state.value,
                policy_allowed=False,
                details={"gate": "SERVER_DISABLED"}
            )

        if server.status == "UNHEALTHY":
            return CanaryEligibilityDecision(
                is_eligible=False,
                reason=f"Server '{server.name}' is in UNHEALTHY status.",
                server_id=server.id,
                server_name=server.name,
                environment=current_env,
                evaluated_at=now_iso,
                deployment_state=state.value,
                policy_allowed=False,
                details={"gate": "SERVER_UNHEALTHY"}
            )

        # 6. Circuit breaker check
        if MCPConnectionManager.is_circuit_open(server.id):
            return CanaryEligibilityDecision(
                is_eligible=False,
                reason=f"Circuit breaker is OPEN for server '{server.name}'.",
                server_id=server.id,
                server_name=server.name,
                environment=current_env,
                evaluated_at=now_iso,
                deployment_state=state.value,
                policy_allowed=False,
                details={"gate": "CIRCUIT_BREAKER_OPEN"}
            )

        # 7. Deployment state check
        if state in (DeploymentState.DISABLED, DeploymentState.ROLLBACK):
            return CanaryEligibilityDecision(
                is_eligible=False,
                reason=f"Server deployment state '{state.value}' is ineligible for persistent canary sessions.",
                server_id=server.id,
                server_name=server.name,
                environment=current_env,
                evaluated_at=now_iso,
                deployment_state=state.value,
                policy_allowed=False,
                details={"gate": "DEPLOYMENT_STATE_INELIGIBLE"}
            )

        # 8. All checks passed: eligible
        return CanaryEligibilityDecision(
            is_eligible=True,
            reason=f"Server '{server.name}' fulfills all canary eligibility criteria.",
            server_id=server.id,
            server_name=server.name,
            environment=current_env,
            evaluated_at=now_iso,
            deployment_state=state.value,
            policy_allowed=True,
            details={"gate": "ELIGIBLE"}
        )

    @classmethod
    def evaluate_readiness_thresholds(cls, observed_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluates operational performance and reliability against configurable enterprise
        acceptance criteria (Task H). Reports PASS, FAIL, or NOT_MEASURED.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        obs = observed_metrics or {}

        # Configured thresholds from settings
        min_success_rate = getattr(settings, "CANARY_MIN_SUCCESS_RATE_PCT", 99.0)
        max_p95_latency = getattr(settings, "CANARY_MAX_P95_LATENCY_MS", 150.0)
        max_p99_latency = getattr(settings, "CANARY_MAX_P99_LATENCY_MS", 350.0)
        max_init_failures = getattr(settings, "CANARY_MAX_INIT_FAILURES", 0)
        max_hb_failures = getattr(settings, "CANARY_MAX_HEARTBEAT_FAILURES", 0)
        max_mem_growth = getattr(settings, "CANARY_MAX_MEMORY_GROWTH_MB", 50.0)
        target_rollback_ms = getattr(settings, "CANARY_ROLLBACK_TARGET_MS", 2000.0)

        # Check observed metrics
        criteria = {}

        # 1. Success rate
        if "success_rate_pct" in obs:
            val = float(obs["success_rate_pct"])
            criteria["execution_success_rate"] = {
                "threshold": f">= {min_success_rate}%",
                "measured": f"{val}%",
                "status": "PASS" if val >= min_success_rate else "FAIL"
            }
        else:
            criteria["execution_success_rate"] = {
                "threshold": f">= {min_success_rate}%",
                "measured": "None (No canary traffic active)",
                "status": "NOT_MEASURED"
            }

        # 2. P95 latency
        if "p95_latency_ms" in obs:
            val = float(obs["p95_latency_ms"])
            criteria["p95_latency"] = {
                "threshold": f"<= {max_p95_latency}ms",
                "measured": f"{val}ms",
                "status": "PASS" if val <= max_p95_latency else "FAIL"
            }
        else:
            criteria["p95_latency"] = {
                "threshold": f"<= {max_p95_latency}ms",
                "measured": "None",
                "status": "NOT_MEASURED"
            }

        # 3. P99 latency
        if "p99_latency_ms" in obs:
            val = float(obs["p99_latency_ms"])
            criteria["p99_latency"] = {
                "threshold": f"<= {max_p99_latency}ms",
                "measured": f"{val}ms",
                "status": "PASS" if val <= max_p99_latency else "FAIL"
            }
        else:
            criteria["p99_latency"] = {
                "threshold": f"<= {max_p99_latency}ms",
                "measured": "None",
                "status": "NOT_MEASURED"
            }

        # 4. Session init failures
        init_fails = obs.get("init_failures", 0)
        criteria["session_initialization_failures"] = {
            "threshold": f"<= {max_init_failures}",
            "measured": str(init_fails),
            "status": "PASS" if init_fails <= max_init_failures else "FAIL"
        }

        # 5. Heartbeat failures
        hb_fails = obs.get("heartbeat_failures", 0)
        criteria["heartbeat_failures"] = {
            "threshold": f"<= {max_hb_failures}",
            "measured": str(hb_fails),
            "status": "PASS" if hb_fails <= max_hb_failures else "FAIL"
        }

        # 6. Memory growth
        mem_growth = obs.get("memory_growth_mb", 0.0)
        criteria["memory_growth"] = {
            "threshold": f"<= {max_mem_growth}MB",
            "measured": f"{mem_growth}MB",
            "status": "PASS" if mem_growth <= max_mem_growth else "FAIL"
        }

        # 7. Orphan subprocesses
        orphans = obs.get("orphan_subprocesses", 0)
        criteria["orphan_subprocesses"] = {
            "threshold": "== 0",
            "measured": str(orphans),
            "status": "PASS" if orphans == 0 else "FAIL"
        }

        # 8. Unauthorized activations
        unauth = obs.get("unauthorized_activations", 0)
        criteria["unauthorized_activations"] = {
            "threshold": "== 0",
            "measured": str(unauth),
            "status": "PASS" if unauth == 0 else "FAIL"
        }

        # 9. Cross-tenant access attempts
        cross_tenant = obs.get("cross_tenant_access", 0)
        criteria["cross_tenant_access"] = {
            "threshold": "== 0",
            "measured": str(cross_tenant),
            "status": "PASS" if cross_tenant == 0 else "FAIL"
        }

        # 10. Emergency rollback duration
        rollback_ms = obs.get("emergency_rollback_ms", 0.0)
        if rollback_ms > 0:
            criteria["emergency_rollback_duration"] = {
                "threshold": f"<= {target_rollback_ms}ms",
                "measured": f"{rollback_ms}ms",
                "status": "PASS" if rollback_ms <= target_rollback_ms else "FAIL"
            }
        else:
            criteria["emergency_rollback_duration"] = {
                "threshold": f"<= {target_rollback_ms}ms",
                "measured": "Simulated/Not invoked",
                "status": "NOT_MEASURED"
            }

        # Overall Readiness Verdict
        all_non_measured_or_pass = all(c["status"] in ("PASS", "NOT_MEASURED") for c in criteria.values())
        any_fail = any(c["status"] == "FAIL" for c in criteria.values())

        overall_verdict = "FAIL" if any_fail else ("READY_FOR_CANARY" if all_non_measured_or_pass else "NOT_READY")

        return {
            "overall_status": overall_verdict,
            "canary_traffic_active": False,
            "evaluated_at": now_iso,
            "criteria": criteria
        }
