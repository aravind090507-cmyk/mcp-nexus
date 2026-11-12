from typing import Tuple, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.all_models import MCPServer, MCPTool, AIAgent, AgentToolPermission, User, SecurityEvent
from app.core.permissions import RoleEnum, has_permission, PermissionEnum
import logging

logger = logging.getLogger(__name__)

class PolicyDecision:
    PERMITTED = "PERMITTED"
    BLOCKED = "BLOCKED"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"

class PolicyEngine:
    """
    Enterprise Security & Governance Policy Engine
    Enforces RBAC, tool permissions, risk classification, and sensitive operation gating.
    """
    
    @staticmethod
    def classify_risk(tool_name: str, arguments: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Determines risk level (LOW, MEDIUM, HIGH, CRITICAL) and approval requirement.
        Destructive operations or critical equipment changes require administrative approval.
        """
        name_lower = tool_name.lower()
        
        # High-risk / Destructive keywords
        if "report_equipment_issue" in name_lower:
            sev = arguments.get("severity", "").upper()
            if sev in ("CRITICAL", "HIGH"):
                return "CRITICAL", True
            return "MEDIUM", False
        
        if any(term in name_lower for term in ["delete", "drop", "terminate", "reboot", "halt", "shutdown"]):
            return "CRITICAL", True
        
        if any(term in name_lower for term in ["update", "modify", "allocate", "order", "dispatch"]):
            return "HIGH", True
        
        if any(term in name_lower for term in ["status", "details", "summary", "schedule", "inventory", "availability"]):
            return "LOW", False
        
        return "MEDIUM", False

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

        # 5. Risk classification & approval check
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
