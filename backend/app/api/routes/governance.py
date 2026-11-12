from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models.all_models import ApprovalRequest, SecurityEvent, AuditLog, User, MCPServer, MCPTool
from app.schemas.all_schemas import ApprovalOut, ApprovalActionRequest, SecurityEventOut, AuditLogOut
from app.services.mcp_manager import MCPManager
from app.services.audit_service import AuditService
from app.api.deps import get_current_user, require_permission
from app.core.permissions import PermissionEnum, RoleEnum
from app.services.policy_engine import PolicyEngine
import datetime

router = APIRouter(prefix="/governance", tags=["Governance, Security & Approvals"])

@router.get("/approvals", response_model=List[ApprovalOut])
def list_approvals(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ApprovalRequest)
    if status_filter:
        query = query.filter(ApprovalRequest.status == status_filter)
    reqs = query.order_by(ApprovalRequest.created_at.desc()).all()
    
    result = []
    for r in reqs:
        result.append(ApprovalOut(
            id=r.id,
            requesting_user=r.requesting_user.full_name if r.requesting_user else "System",
            agent_name=r.agent.name if r.agent else None,
            server_name=r.server.name if r.server else "Unknown Server",
            tool_name=r.tool.name if r.tool else "Unknown Tool",
            operation_description=r.operation_description,
            parameters=r.parameters or {},
            risk_level=r.risk_level,
            status=r.status,
            requires_dual_approval=r.requires_dual_approval or False,
            first_approver_name=r.first_approver.full_name if r.first_approver else None,
            first_approved_at=r.first_approved_at,
            second_approver_name=r.second_approver.full_name if r.second_approver else None,
            second_approved_at=r.second_approved_at,
            expires_at=r.expires_at,
            created_at=r.created_at,
            reviewed_at=r.reviewed_at
        ))
    return result

@router.post("/approvals/{approval_id}/action")
async def review_approval(
    approval_id: str,
    action_data: ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.GOVERNANCE_APPROVE))
):
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found.")

    # 1. Expiration Verification
    now = datetime.datetime.utcnow()
    if req.expires_at and now > req.expires_at and req.status in ("PENDING", "PARTIALLY_APPROVED"):
        req.status = "EXPIRED"
        db.commit()
        AuditService.record(
            db, "EXPIRE_APPROVAL", "APPROVAL", req.id,
            user_name="System", role="SYSTEM",
            details=f"Approval request #{req.id[:8]} expired after SLA window."
        )
        raise HTTPException(status_code=400, detail="Approval request has expired and can no longer be processed.")

    if req.status in ("APPROVED", "EXECUTED", "REJECTED", "EXPIRED"):
        raise HTTPException(status_code=400, detail=f"Request is already resolved as '{req.status}'.")

    # 2. Self-Approval Prevention Check
    if req.requesting_user_id == current_user.id:
        PolicyEngine._log_security_event(
            db, "UNAUTHORIZED_APPROVAL_ATTEMPT", "HIGH",
            current_user.email, req.tool.name if req.tool else "UNKNOWN_TOOL",
            f"User '{current_user.email}' attempted to self-approve operation #{req.id[:8]}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-approval is strictly forbidden by enterprise dual-control governance policy. A distinct authorized administrator must review this request."
        )

    action = action_data.action.upper()
    if action not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=400, detail="Action must be APPROVE or REJECT.")

    # 3. REJECT ACTION
    if action == "REJECT":
        req.status = "REJECTED"
        req.reviewed_by = current_user.id
        req.reviewed_at = now
        req.reason = action_data.reason or "Rejected by administrative reviewer"
        db.commit()

        AuditService.record(
            db, "REJECT_APPROVAL", "APPROVAL", req.id,
            user_name=current_user.full_name, role=current_user.role,
            details=f"Rejected approval request for tool '{req.tool.name if req.tool else req.tool_id}'. Reason: {req.reason}"
        )
        PolicyEngine._log_security_event(
            db, "APPROVAL_DECISION", "MEDIUM", current_user.email, req.tool.name if req.tool else req.tool_id,
            f"Approval request #{req.id[:8]} was REJECTED by {current_user.email}."
        )
        return {"status": "REJECTED", "message": "Approval request was rejected.", "details": req.reason}

    # 4. APPROVE ACTION (Dual-Control vs Single-Control)
    if req.requires_dual_approval:
        if req.first_approver_id is None:
            # First approval recorded
            req.first_approver_id = current_user.id
            req.first_approved_at = now
            req.status = "PARTIALLY_APPROVED"
            req.reason = action_data.reason
            db.commit()

            AuditService.record(
                db, "PARTIAL_APPROVAL", "APPROVAL", req.id,
                user_name=current_user.full_name, role=current_user.role,
                details=f"First approval granted by {current_user.full_name}. Awaiting second distinct administrator sign-off."
            )
            return {
                "status": "PARTIALLY_APPROVED",
                "message": "First approval recorded. Dual-control policy requires a second distinct authorized approver before execution can proceed.",
                "first_approver": current_user.full_name
            }
        else:
            # Second approval attempt: ensure not the same approver
            if req.first_approver_id == current_user.id:
                PolicyEngine._log_security_event(
                    db, "DUAL_APPROVAL_VIOLATION", "HIGH", current_user.email, req.tool.name if req.tool else req.tool_id,
                    f"User '{current_user.email}' attempted duplicate sign-off for dual-control request #{req.id[:8]}."
                )
                raise HTTPException(
                    status_code=400,
                    detail="Dual-control policy requires two distinct approvers. You have already provided the first approval."
                )

            req.second_approver_id = current_user.id
            req.second_approved_at = now
            req.reviewed_by = current_user.id
            req.reviewed_at = now
            req.status = "APPROVED"
            db.commit()
    else:
        # Standard Single Approval
        req.reviewed_by = current_user.id
        req.reviewed_at = now
        req.reason = action_data.reason
        req.status = "APPROVED"
        db.commit()

    # Once fully APPROVED -> Execute the deferred tool action
    exec_result, duration_ms, is_success, err = await MCPManager.execute_tool(
        db, req.server, req.tool, req.parameters or {}
    )

    req.status = "EXECUTED" if is_success else "EXECUTION_FAILED"
    db.commit()

    AuditService.record(
        db, "APPROVE_AND_EXECUTE", "APPROVAL", req.id,
        user_name=current_user.full_name, role=current_user.role,
        details=f"Approved and executed sensitive tool '{req.tool.name}' (Result: {'SUCCESS' if is_success else 'FAILED'}, Duration: {duration_ms}ms)"
    )
    PolicyEngine._log_security_event(
        db, "SENSITIVE_TOOL_EXEC", req.risk_level, current_user.email, req.tool.name,
        f"Sensitive tool '{req.tool.name}' executed following dual-control governance approval."
    )

    return {
        "status": req.status,
        "message": "Approved and executed successfully.",
        "execution_result": exec_result.get("parsed") or exec_result,
        "duration_ms": duration_ms,
        "error": err
    }

@router.get("/security-events", response_model=List[SecurityEventOut])
def list_security_events(
    severity: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(SecurityEvent)
    if severity:
        query = query.filter(SecurityEvent.severity == severity)
    return query.order_by(SecurityEvent.timestamp.desc()).limit(limit).all()

@router.get("/audit-logs", response_model=List[AuditLogOut])
def list_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()

@router.get("/policies")
def get_security_policies():
    """
    Returns the active enterprise governance policies and constraints.
    """
    return [
        {
            "id": "POL-001",
            "name": "Destructive Operation Sign-off",
            "scope": "ALL_SERVERS",
            "risk_trigger": "CRITICAL",
            "enforcement": "BLOCK_UNTIL_APPROVED",
            "description": "Any tool operation that modifies equipment state, logs fatal breakdowns, or deletes assets requires Admin approval."
        },
        {
            "id": "POL-002",
            "name": "Least-Privilege Role Authorization (RBAC)",
            "scope": "GLOBAL",
            "risk_trigger": "ANY",
            "enforcement": "REJECT_UNAUTHORIZED",
            "description": "Tool execution is restricted to DEVELOPER, OPERATOR, ADMIN, and SUPER_ADMIN roles only."
        },
        {
            "id": "POL-003",
            "name": "Automated Protocol Handshake Verification",
            "scope": "MCP_SERVERS",
            "risk_trigger": "CONNECTION",
            "enforcement": "DEGRADE_ON_FAILURE",
            "description": "MCP servers failing to complete JSON-RPC 2.0 initialize sequence are marked DEGRADED."
        },
        {
            "id": "POL-004",
            "name": "Cross-Server Boundary Guard",
            "scope": "AI_AGENTS",
            "risk_trigger": "HIGH",
            "enforcement": "AUDIT_AND_CONTAIN",
            "description": "AI agents may only execute tools on explicitly assigned MCP servers."
        }
    ]
