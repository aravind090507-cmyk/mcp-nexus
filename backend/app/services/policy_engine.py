import fnmatch
from typing import Tuple, Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.models.all_models import MCPServer, MCPTool, AIAgent, AgentToolPermission, User, SecurityEvent, SecurityPolicy
from app.core.permissions import RoleEnum, has_permission, PermissionEnum
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class PolicyDecision:
    PERMITTED = "PERMITTED"
    BLOCKED = "BLOCKED"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"

class PolicyEngine:
    """
    Enterprise Security & Governance Policy Intelligence Engine
    Enforces RBAC, dynamic database policies, tool risk classification, 
    environment overrides (Production vs Staging), argument-level checks, 
    and dual-person approval triggers.
    """
    
    @staticmethod
    def classify_risk(tool_name: str, arguments: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Determines default risk level (LOW, MEDIUM, HIGH, CRITICAL) and approval requirement.
        Destructive operations or critical equipment changes require administrative approval.
        """
        name_lower = tool_name.lower()
        
        # High-risk / Destructive operations
        if "report_equipment_issue" in name_lower:
            sev = str(arguments.get("severity", "")).upper()
            if sev in ("CRITICAL", "HIGH"):
                return "CRITICAL", True
            return "MEDIUM", False
        
        if any(term in name_lower for term in ["delete", "drop", "terminate", "reboot", "halt", "shutdown"]):
            return "CRITICAL", True
        
        if any(term in name_lower for term in ["update", "modify", "allocate", "order", "dispatch", "transfer"]):
            return "HIGH", True
        
        if any(term in name_lower for term in ["status", "details", "summary", "schedule", "inventory", "availability"]):
            return "LOW", False
        
        return "MEDIUM", False

    @staticmethod
    def _evaluate_argument_conditions(conditions: Dict[str, Any], arguments: Dict[str, Any]) -> bool:
        """
        Validates argument-level policy conditions (e.g., severity in ['CRITICAL', 'HIGH']).
        Returns True if all conditions match.
        """
        if not conditions:
            return True
        for key, expected_val in conditions.items():
            actual_val = arguments.get(key)
            if actual_val is None:
                return False
            if isinstance(expected_val, list):
                if str(actual_val).upper() not in [str(v).upper() for v in expected_val]:
                    return False
            else:
                if str(actual_val).upper() != str(expected_val).upper():
                    return False
        return True

    @staticmethod
    def validate_execution(
        db: Session,
        user: User,
        server: MCPServer,
        tool: MCPTool,
        agent: Optional[AIAgent],
        arguments: Dict[str, Any]
    ) -> Tuple[str, str, Optional[str]]:
        """
        Validates authorization to execute a tool.
        Returns (decision, message, risk_level).
        """
        # 1. Server must be active and enabled
        if not server.is_enabled:
            PolicyEngine._log_security_event(
                db, "BLOCKED_TOOL", "MEDIUM", user.email, server.name,
                f"Attempted execution on disabled MCP Server '{server.name}'"
            )
            return PolicyDecision.BLOCKED, f"Server '{server.name}' is currently disabled by administrator.", "LOW"

        # 1b. Tenant Isolation Boundary Enforcement
        if user.organization_id and server.organization_id and user.organization_id != server.organization_id:
            if user.role != RoleEnum.SUPER_ADMIN.value:
                PolicyEngine._log_security_event(
                    db, "CROSS_TENANT_ACCESS_DENIED", "CRITICAL", user.email, server.name,
                    f"Cross-tenant violation: User '{user.email}' (Tenant: {user.organization_id}) attempted to access Server '{server.name}' (Tenant: {server.organization_id})"
                )
                return PolicyDecision.BLOCKED, f"Access denied: Cross-tenant access forbidden. Server '{server.name}' belongs to a different organization.", "HIGH"

        # 2. Tool must be enabled
        if not tool.is_enabled:
            PolicyEngine._log_security_event(
                db, "BLOCKED_TOOL", "MEDIUM", user.email, tool.name,
                f"Attempted execution of disabled tool '{tool.name}'"
            )
            return PolicyDecision.BLOCKED, f"Tool '{tool.name}' is disabled in the Tool Registry.", "LOW"

        # 3. User RBAC validation
        user_role = RoleEnum(user.role)
        if not has_permission(user_role, PermissionEnum.TOOLS_EXECUTE):
            PolicyEngine._log_security_event(
                db, "UNAUTHORIZED_ACCESS", "HIGH", user.email, tool.name,
                f"User '{user.email}' with role '{user.role}' lacks TOOLS_EXECUTE permission"
            )
            return PolicyDecision.BLOCKED, f"Role '{user.role}' is not authorized to execute tools.", "MEDIUM"

        # 4. Agent tool permission validation (if called via Agent)
        if agent:
            perm = db.query(AgentToolPermission).filter(
                AgentToolPermission.agent_id == agent.id,
                AgentToolPermission.tool_id == tool.id
            ).first()
            if perm and not perm.is_permitted:
                PolicyEngine._log_security_event(
                    db, "POLICY_VIOLATION", "HIGH", f"Agent:{agent.name}", tool.name,
                    f"Agent '{agent.name}' attempted to invoke forbidden tool '{tool.name}'"
                )
                return PolicyDecision.BLOCKED, f"Tool '{tool.name}' is explicitly forbidden for agent '{agent.name}'.", "HIGH"

        # 5. Dynamic Database Policy Evaluation (Server-level, Tool-level, Argument-level, Environment rules)
        current_env = (settings.ENVIRONMENT or "DEVELOPMENT").upper()
        active_policies = db.query(SecurityPolicy).filter(
            SecurityPolicy.is_enabled == True,
            SecurityPolicy.environment.in_(["ALL", current_env])
        ).all()

        # Collect and rank all matching policies
        # Specificity ranking: Exact tool match (100) > Pattern match (50) > Server scope (30) > Global (10)
        # Action weight: DENY (3) > REQUIRE_APPROVAL (2) > ALLOW (1)
        matched_policies = []
        for policy in active_policies:
            matched = False
            specificity = 0
            if policy.scope == "TOOL":
                pattern = (policy.tool_pattern or "*").lower()
                if tool.name.lower() == pattern:
                    matched = True
                    specificity = 100
                elif fnmatch.fnmatch(tool.name.lower(), pattern):
                    matched = True
                    specificity = 50
            elif policy.scope == "SERVER":
                if policy.server_id == server.id or policy.server_id == server.identifier:
                    matched = True
                    specificity = 30
            elif policy.scope == "GLOBAL":
                matched = True
                specificity = 10

            if matched:
                if policy.argument_conditions and not PolicyEngine._evaluate_argument_conditions(policy.argument_conditions, arguments):
                    continue
                action_weight = 3 if policy.action == "DENY" else (2 if policy.action == "REQUIRE_APPROVAL" else 1)
                matched_policies.append((specificity, action_weight, policy))

        if matched_policies:
            # Sort by specificity desc, then action_weight desc
            matched_policies.sort(key=lambda x: (x[0], x[1]), reverse=True)
            _, _, top_policy = matched_policies[0]

            p_action = top_policy.action.upper()
            p_risk = top_policy.risk_level.upper() if top_policy.risk_level != "ANY" else "HIGH"

            if p_action == "DENY":
                PolicyEngine._log_security_event(
                    db, "POLICY_VIOLATION", "HIGH", user.email, tool.name,
                    f"Execution rejected by Security Policy '{top_policy.name}' (Action: DENY, Env: {current_env})"
                )
                return PolicyDecision.BLOCKED, f"Execution denied by Policy '{top_policy.name}'.", p_risk

            elif p_action == "REQUIRE_APPROVAL":
                PolicyEngine._log_security_event(
                    db, "APPROVAL_REQUESTED", "HIGH", user.email, tool.name,
                    f"Sensitive execution gated by Policy '{top_policy.name}' (Requires Dual-Control Approval)"
                )
                return PolicyDecision.NEEDS_APPROVAL, f"Policy '{top_policy.name}' mandates administrative approval for tool '{tool.name}'.", p_risk

            elif p_action == "ALLOW":
                return PolicyDecision.PERMITTED, f"Execution explicitly permitted by Policy '{top_policy.name}'.", p_risk

        # 6. Default Fallback Risk Classification & Approval check
        risk_level, requires_approval = PolicyEngine.classify_risk(tool.name, arguments)
        if tool.requires_approval or requires_approval:
            PolicyEngine._log_security_event(
                db, "APPROVAL_REQUESTED", "HIGH", user.email, tool.name,
                f"Sensitive tool '{tool.name}' execution flagged for approval (Risk: {risk_level})"
            )
            return PolicyDecision.NEEDS_APPROVAL, f"Tool '{tool.name}' is classified as {risk_level} risk and requires administrative approval.", risk_level

        return PolicyDecision.PERMITTED, "Execution permitted under active governance policy.", risk_level

    @staticmethod
    def _log_security_event(db: Session, event_type: str, severity: str, actor: str, target: str, description: str):
        evt = SecurityEvent(
            event_type=event_type,
            severity=severity,
            actor=actor,
            target_resource=target,
            description=description
        )
        db.add(evt)
        db.commit()
