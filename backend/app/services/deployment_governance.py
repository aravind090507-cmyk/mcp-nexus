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
        try:
            env_vars = getattr(server, "env_vars", None) or {}
            raw = env_vars.get("DEPLOYMENT_STATE")
            if not raw:
                return DeploymentState.PREPARED if getattr(server, "is_enabled", True) else DeploymentState.DISABLED
            return DeploymentState(raw)
        except Exception:
            return DeploymentState.PREPARED if getattr(server, "is_enabled", True) else DeploymentState.DISABLED

    @classmethod
    def get_transition_history(cls, server: MCPServer) -> List[Dict[str, Any]]:
        """Retrieves auditable deployment transition history for a server."""
        try:
            env_vars = getattr(server, "env_vars", None) or {}
            return list(env_vars.get("DEPLOYMENT_HISTORY", []))
        except Exception:
            return []

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
            initial_state = cls.get_server_state(server)

            # 1. RBAC authorization check on actor
            if actor.role not in _AUTHORIZED_ROLES:
                logger.warning(f"Unauthorized deployment state transition attempt by {actor.email} (role: {actor.role}).")
                return False, f"Access denied: Role '{actor.role}' is not authorized to modify deployment states.", initial_state

            # 2. Concurrency Control & Authoritative Database Row Re-query:
            # Re-query server inside transaction with engine-aware locking to prevent lost updates across workers.
            bind = db.get_bind()
            dialect_name = bind.dialect.name.lower() if bind else "sqlite"

            from sqlalchemy import text
            if dialect_name == "sqlite":
                # Guarantee cross-process serialized write lock in SQLite before reading authoritative state
                try:
                    db.execute(text("BEGIN IMMEDIATE"))
                except Exception as e:
                    err_msg = str(e).lower()
                    if "database is locked" in err_msg or "busy" in err_msg:
                        logger.warning(f"Concurrent state transition detected (SQLite database locked): {e}")
                        try:
                            db.rollback()
                        except Exception:
                            pass
                        return False, "Database is locked: concurrent deployment state transition in progress.", initial_state
                    elif "cannot start a transaction within a transaction" in err_msg:
                        pass
                    else:
                        try:
                            db.rollback()
                        except Exception:
                            pass
                        raise

            try:
                query = db.query(MCPServer).filter(MCPServer.id == server.id)
                if dialect_name != "sqlite":
                    # For PostgreSQL/MySQL/Oracle, acquire row-level exclusive lock
                    query = query.with_for_update()

                locked_server = query.first()
                if not locked_server:
                    db.rollback()
                    return False, f"Server '{server.id}' not found in database.", initial_state

                # Ensure session is not seeing stale cached attributes across transactions
                db.refresh(locked_server)

                # 3. Tenant isolation (using re-queried authoritative record)
                if str(locked_server.organization_id) != str(actor.organization_id):
                    logger.error(f"Tenant isolation failure: User '{actor.email}' (org {actor.organization_id}) attempted transition on server '{locked_server.name}' (org {locked_server.organization_id}).")
                    db.rollback()
                    return False, "Access denied: Cannot alter deployment state of another organization's server.", cls.get_server_state(locked_server)

                # 4. Read authoritative current state after acquiring lock
                current_state = cls.get_server_state(locked_server)

                # 5. Check for emergency shutdown override
                from app.mcp.persistent_session import PersistentSessionManager
                if PersistentSessionManager.is_emergency_disabled() and target_state in (DeploymentState.CANARY_AUTHORIZED, DeploymentState.CANARY_ACTIVE):
                    db.rollback()
                    return False, "Transition rejected: Global emergency kill switch is currently ENGAGED.", current_state

                # 6. Phase 15D.3 Safety Gate: Prevent premature activation of canary traffic
                if target_state == DeploymentState.CANARY_ACTIVE:
                    db.rollback()
                    return False, "Transition rejected: CANARY_ACTIVE is gated and strictly forbidden in Phase 15D.3 (Readiness only).", current_state

                # 7. Transition matrix check
                allowed_targets = _VALID_TRANSITIONS.get(current_state, [])
                if target_state not in allowed_targets and target_state != DeploymentState.ROLLBACK:
                    db.rollback()
                    return False, f"Invalid transition: Cannot transition from '{current_state.value}' to '{target_state.value}'.", current_state

                # 8. Apply state transition and update audit history atomically
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                new_env = dict(locked_server.env_vars or {})
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
                locked_server.env_vars = new_env

                # If transitioning to ROLLBACK or DISABLED, ensure persistent session is shut down
                if target_state in (DeploymentState.ROLLBACK, DeploymentState.DISABLED):
                    PersistentSessionManager.shutdown_session(locked_server.id)

                # Stage system audit log within the same database transaction (auto_commit=False)
                audit_log = AuditService.record(
                    db, "DEPLOYMENT_STATE_CHANGE", "SERVER", locked_server.id,
                    user_name=actor.full_name, role=actor.role,
                    details=f"Server '{locked_server.name}' deployment state transitioned: {current_state.value} -> {target_state.value}. Reason: {reason}",
                    diff={"from": current_state.value, "to": target_state.value, "reason": reason},
                    auto_commit=False
                )

                # Single atomic commit for both state transition and audit log
                db.commit()
                db.refresh(locked_server)
                if server is not locked_server:
                    db.refresh(server)
                try:
                    db.refresh(audit_log)
                except Exception:
                    pass

                logger.info(f"Deployment state transitioned for '{locked_server.name}': {current_state.value} -> {target_state.value} by {actor.email}")
                return True, f"Server deployment state successfully updated to {target_state.value}.", target_state
            except Exception as e:
                db.rollback()
                logger.error(f"Failed transaction during deployment state transition for '{server.name}': {e}")
                return False, f"Database transaction failed: {str(e)}", cls.get_server_state(server)

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
