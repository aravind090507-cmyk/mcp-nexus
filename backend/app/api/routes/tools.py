from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.database.session import get_db
from app.models.all_models import MCPTool, MCPServer, User, ExecutionTrace, ApprovalRequest
from app.schemas.all_schemas import MCPToolOut, MCPToolUpdate, ToolExecuteRequest, ToolExecuteResponse
from app.services.mcp_manager import MCPManager
from app.services.policy_engine import PolicyEngine, PolicyDecision
from app.services.audit_service import AuditService
from app.api.deps import get_current_user, require_permission
from app.core.permissions import PermissionEnum, RoleEnum
import uuid
import datetime

router = APIRouter(prefix="/tools", tags=["Tool Registry & Playground"])

@router.get("", response_model=List[MCPToolOut])
def list_tools(
    server_id: Optional[str] = None,
    risk_level: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(MCPTool)
    if server_id:
        query = query.filter(MCPTool.server_id == server_id)
    if risk_level:
        query = query.filter(MCPTool.risk_level == risk_level)
    return query.all()

@router.get("/{tool_id}", response_model=MCPToolOut)
def get_tool(
    tool_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tool = db.query(MCPTool).filter(MCPTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found.")
    return tool

@router.patch("/{tool_id}/toggle")
def toggle_tool(
    tool_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.TOOLS_CONFIG))
):
    tool = db.query(MCPTool).filter(MCPTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found.")

    tool.is_enabled = not tool.is_enabled
    db.commit()

    AuditService.record(
        db, "TOGGLE_TOOL", "TOOL", tool.id,
        user_name=current_user.full_name, role=current_user.role,
        details=f"Set tool '{tool.name}' enabled status to {tool.is_enabled}"
    )
    return {"id": tool.id, "name": tool.name, "is_enabled": tool.is_enabled}

@router.put("/{tool_id}/config", response_model=MCPToolOut)
def update_tool_config(
    tool_id: str,
    data: MCPToolUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.TOOLS_CONFIG))
):
    tool = db.query(MCPTool).filter(MCPTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found.")

    if data.risk_level is not None:
        if data.risk_level not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            raise HTTPException(status_code=400, detail="Invalid risk level.")
        tool.risk_level = data.risk_level

    if data.requires_approval is not None:
        tool.requires_approval = data.requires_approval

    if data.is_enabled is not None:
        tool.is_enabled = data.is_enabled

    if data.description is not None:
        tool.description = data.description

    tool.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(tool)

    AuditService.record(
        db, "CONFIGURE_TOOL", "TOOL", tool.id,
        user_name=current_user.full_name, role=current_user.role,
        details=f"Configured tool '{tool.name}': risk={tool.risk_level}, requires_approval={tool.requires_approval}"
    )
    return tool

@router.post("/execute", response_model=ToolExecuteResponse)
async def execute_playground_tool(
    req: ToolExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.TOOLS_TEST))
):
    tool = db.query(MCPTool).filter(MCPTool.name == req.tool_name).first()
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{req.tool_name}' not found in registry.")

    server = db.query(MCPServer).filter(MCPServer.id == tool.server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Associated MCP Server not found.")

    # Governance check via PolicyEngine
    decision, msg, risk_level = PolicyEngine.validate_execution(
        db, current_user, server, tool, None, req.arguments
    )

    trace_id = f"trc-{uuid.uuid4().hex[:12]}"
    req_id = f"req-{uuid.uuid4().hex[:10]}"

    if decision == PolicyDecision.NEEDS_APPROVAL:
        # Enqueue in approval queue
        app_req = ApprovalRequest(
            requesting_user_id=current_user.id,
            server_id=server.id,
            tool_id=tool.id,
            operation_description=f"Playground execution of {tool.name} with params: {req.arguments}",
            parameters=req.arguments,
            risk_level=risk_level,
            status="PENDING",
            reason="Playground execution flagged for administrative sign-off"
        )
        db.add(app_req)
        db.commit()

        trace = ExecutionTrace(
            trace_id=trace_id,
            request_id=req_id,
            user_id=current_user.id,
            server_id=server.id,
            server_name=server.name,
            tool_name=tool.name,
            user_query="Playground execution",
            input_parameters=req.arguments,
            output_response={"approval_request_id": app_req.id, "message": msg},
            status="PENDING_APPROVAL",
            duration_ms=5.0,
            risk_level=risk_level,
            authorization_decision="NEEDS_APPROVAL",
            policy_evaluated="Destructive Action Approval Rule"
        )
        db.add(trace)
        db.commit()

        return ToolExecuteResponse(
            tool_name=tool.name,
            server_name=server.name,
            is_success=False,
            duration_ms=5.0,
            result={"approval_required": True, "approval_id": app_req.id},
            error=f"Operation halted: {msg}. Approval request #{app_req.id[:8]} created.",
            trace_id=trace_id
        )

    if decision == PolicyDecision.BLOCKED:
        trace = ExecutionTrace(
            trace_id=trace_id,
            request_id=req_id,
            user_id=current_user.id,
            server_id=server.id,
            server_name=server.name,
            tool_name=tool.name,
            user_query="Playground execution",
            input_parameters=req.arguments,
            error_details=msg,
            status="BLOCKED",
            duration_ms=2.0,
            risk_level=risk_level,
            authorization_decision="BLOCKED",
            policy_evaluated="RBAC Access Rule"
        )
        db.add(trace)
        db.commit()

        return ToolExecuteResponse(
            tool_name=tool.name,
            server_name=server.name,
            is_success=False,
            duration_ms=2.0,
            result=None,
            error=msg,
            trace_id=trace_id
        )

    # Permitted: Run real MCP tool call
    res, duration_ms, is_success, err_msg = await MCPManager.execute_tool(db, server, tool, req.arguments)

    parsed_result = res.get("parsed") or res

    # Record trace
    trace = ExecutionTrace(
        trace_id=trace_id,
        request_id=req_id,
        user_id=current_user.id,
        server_id=server.id,
        server_name=server.name,
        tool_name=tool.name,
        user_query="Playground execution",
        input_parameters=req.arguments,
        output_response=parsed_result,
        error_details=err_msg,
        status="SUCCESS" if is_success else "FAILED",
        duration_ms=duration_ms,
        risk_level=risk_level,
        authorization_decision="PERMITTED",
        policy_evaluated="Default Permission Policy",
        spans=[
            {"stage": "USER_REQUEST", "name": "Playground Call", "status": "COMPLETED", "duration_ms": 1.0, "timestamp": datetime.datetime.utcnow().isoformat()},
            {"stage": "POLICY_VALIDATION", "name": "Policy Engine Check", "status": "COMPLETED", "duration_ms": 2.0, "timestamp": datetime.datetime.utcnow().isoformat()},
            {"stage": "MCP_SERVER", "name": f"STDIO Handshake: {server.name}", "status": "COMPLETED", "duration_ms": 3.0, "timestamp": datetime.datetime.utcnow().isoformat()},
            {"stage": "TOOL_EXECUTION", "name": f"Call {tool.name}", "status": "COMPLETED" if is_success else "FAILED", "duration_ms": duration_ms, "timestamp": datetime.datetime.utcnow().isoformat()},
            {"stage": "RESPONSE", "name": "Payload Serialization", "status": "COMPLETED", "duration_ms": 1.5, "timestamp": datetime.datetime.utcnow().isoformat()}
        ]
    )
    db.add(trace)
    db.commit()

    return ToolExecuteResponse(
        tool_name=tool.name,
        server_name=server.name,
        is_success=is_success,
        duration_ms=duration_ms,
        result=parsed_result,
        error=err_msg,
        trace_id=trace_id
    )
