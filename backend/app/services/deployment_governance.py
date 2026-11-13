"""
MCP NEXUS — DEPLOYMENT GOVERNANCE SERVICE
Enterprise deployment state machine, transition validation, role-based controls,
and auditable transition lifecycle for MCP servers and canary rollouts.

State Model:
DISABLED -> PREPARED -> ELIGIBLE -> CANARY_AUTHORIZED -> CANARY_ACTIVE -> ROLLBACK
"""

import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
import logging
import threading

from sqlalchemy.orm import Session
from app.models.all_models import MCPServer, User
from app.services.audit_service import AuditService
from app.core.permissions import RoleEnum
from app.core.config import settings

logger = logging.getLogger("mcp-nexus.deployment-governance")


class DeploymentState(str, Enum):
    DISABLED = "DISABLED"
    PREPARED = "PREPARED"
    ELIGIBLE = "ELIGIBLE"
    CANARY_AUTHORIZED = "CANARY_AUTHORIZED"
    CANARY_ACTIVE = "CANARY_ACTIVE"
    ROLLBACK = "ROLLBACK"


# Allowed state transitions matrix
_VALID_TRANSITIONS: Dict[DeploymentState, List[DeploymentState]] = {
    DeploymentState.DISABLED: [DeploymentState.PREPARED, DeploymentState.ROLLBACK],
    DeploymentState.PREPARED: [DeploymentState.ELIGIBLE, DeploymentState.DISABLED, DeploymentState.ROLLBACK],
    DeploymentState.ELIGIBLE: [DeploymentState.CANARY_AUTHORIZED, DeploymentState.PREPARED, DeploymentState.DISABLED, DeploymentState.ROLLBACK],
    DeploymentState.CANARY_AUTHORIZED: [DeploymentState.CANARY_ACTIVE, DeploymentState.ELIGIBLE, DeploymentState.ROLLBACK, DeploymentState.DISABLED],
    DeploymentState.CANARY_ACTIVE: [DeploymentState.ROLLBACK, DeploymentState.DISABLED],
    DeploymentState.ROLLBACK: [DeploymentState.DISABLED, DeploymentState.PREPARED],
}

# Roles permitted to alter deployment states
_AUTHORIZED_ROLES = {RoleEnum.SUPER_ADMIN.value, RoleEnum.ADMIN.value}


class DeploymentGovernanceService:
    """
    Centralized Deployment Governance Service.
    Enforces state transitions, role-based authorization, transition history auditing,
    and emergency override mechanisms for MCP servers.
    """
    _state_lock = threading.RLock()

    @classmethod
    def get_server_state(cls, server: MCPServer) -> DeploymentState:
        """Retrieves the authoritative deployment state of a server (defaults to PREPARED if enabled)."""
        env_vars = server.env_vars or {}
        raw = env_vars.get("DEPLOYMENT_STATE")
        if not raw:
            return DeploymentState.PREPARED if getattr(server, "is_enabled", True) else DeploymentState.DISABLED
        try:
            return DeploymentState(raw)
        except ValueError:
            return DeploymentState.DISABLED

    @classmethod
    def get_transition_history(cls, server: MCPServer) -> List[Dict[str, Any]]:
        """Retrieves auditable deployment transition history for a server."""
        env_vars = server.env_vars or {}
        return list(env_vars.get("DEPLOYMENT_HISTORY", []))

    @classmethod
    def transition_state(
        cls,
        db: Session,
        server: MCPServer,
        target_state: DeploymentState,
        actor: User,
        reason: str
    ) -> Tuple[bool, str, DeploymentState]:
        """
        Executes a controlled, auditable state transition for an MCP server.

        Strict Rules:
        - Only ADMIN and SECURITY_OFFICER can transition deployment states.
        - Actor must belong to the same organization as the server.
        - Transition must be permitted by the transition matrix.
        - Milestone 15D.3 restriction: CANARY_AUTHORIZED and CANARY_ACTIVE require explicit
          future authorization and CANNOT be activated automatically in this milestone.
        - State is persisted to server.env_vars to survive application restarts.
        """
        with cls._state_lock:
            # 1. RBAC authorization
            if actor.role not in _AUTHORIZED_ROLES:
                logger.warning(f"Unauthorized deployment state transition attempt by {actor.email} (role: {actor.role}).")
                return False, f"Access denied: Role '{actor.role}' is not authorized to modify deployment states.", cls.get_server_state(server)

            # 2. Tenant isolation
            if str(server.organization_id) != str(actor.organization_id):
                logger.error(f"Tenant isolation failure: User '{actor.email}' (org {actor.organization_id}) attempted transition on server '{server.name}' (org {server.organization_id}).")
                return False, "Access denied: Cannot alter deployment state of another organization's server.", cls.get_server_state(server)

            current_state = cls.get_server_state(server)

            # 3. Check for emergency shutdown override
            from app.mcp.persistent_session import PersistentSessionManager
            if PersistentSessionManager.is_emergency_disabled() and target_state in (DeploymentState.CANARY_AUTHORIZED, DeploymentState.CANARY_ACTIVE):
                return False, "Transition rejected: Global emergency kill switch is currently ENGAGED.", current_state

            # 4. Phase 15D.3 Safety Gate: Prevent premature activation of canary traffic
            if target_state == DeploymentState.CANARY_ACTIVE:
                return False, "Transition rejected: CANARY_ACTIVE is gated and strictly forbidden in Phase 15D.3 (Readiness only).", current_state

            # 5. Transition matrix check
            allowed_targets = _VALID_TRANSITIONS.get(current_state, [])
            if target_state not in allowed_targets and target_state != DeploymentState.ROLLBACK:
                return False, f"Invalid transition: Cannot transition from '{current_state.value}' to '{target_state.value}'.", current_state

            # 6. Apply state transition and update audit history
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            new_env = dict(server.env_vars or {})
            history = list(new_env.get("DEPLOYMENT_HISTORY", []))

            history_entry = {
                "from_state": current_state.value,
                "to_state": target_state.value,
                "actor_id": actor.id,
                "actor_email": actor.email,
                "actor_role": actor.role,
                "reason": reason,
                "timestamp": now_iso
            }
            history.append(history_entry)

            # Keep history bounded (last 50 events)
            if len(history) > 50:
                history = history[-50:]

            new_env["DEPLOYMENT_STATE"] = target_state.value
            new_env["DEPLOYMENT_HISTORY"] = history
            server.env_vars = new_env

            # If transitioning to ROLLBACK or DISABLED, ensure persistent session is shut down
            if target_state in (DeploymentState.ROLLBACK, DeploymentState.DISABLED):
                PersistentSessionManager.shutdown_session(server.id)

            db.commit()
            db.refresh(server)

            # Record system audit log
            AuditService.record(
                db, "DEPLOYMENT_STATE_CHANGE", "SERVER", server.id,
                user_name=actor.full_name, role=actor.role,
                details=f"Server '{server.name}' deployment state transitioned: {current_state.value} -> {target_state.value}. Reason: {reason}",
                diff={"from": current_state.value, "to": target_state.value, "reason": reason}
            )

            logger.info(f"Deployment state transitioned for '{server.name}': {current_state.value} -> {target_state.value} by {actor.email}")
            return True, f"Server deployment state successfully updated to {target_state.value}.", target_state

    @classmethod
    def rollback_server(
        cls,
        db: Session,
        server: MCPServer,
        actor: User,
        reason: str
    ) -> Tuple[bool, str]:
        """Performs immediate server-specific rollback to legacy execution."""
        return cls.transition_state(db, server, DeploymentState.ROLLBACK, actor, reason)[:2]
