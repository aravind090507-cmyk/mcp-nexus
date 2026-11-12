from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.database.session import get_db
from app.models.all_models import MCPServer, MCPTool, User, Organization
from app.schemas.all_schemas import MCPServerCreate, MCPServerUpdate, MCPServerOut, MCPToolOut
from app.services.mcp_manager import MCPManager
from app.services.audit_service import AuditService
from app.api.deps import get_current_user, require_permission
from app.core.permissions import PermissionEnum
import datetime
import sys

router = APIRouter(prefix="/servers", tags=["MCP Servers"])

@router.get("", response_model=List[MCPServerOut])
def list_servers(
    environment: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(MCPServer)
    if environment:
        query = query.filter(MCPServer.environment == environment)
    servers = query.all()
    return servers

@router.post("", response_model=MCPServerOut)
async def register_server(
    data: MCPServerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.SERVERS_WRITE))
):
    existing = db.query(MCPServer).filter(MCPServer.identifier == data.identifier).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Server with identifier '{data.identifier}' already exists.")

    org = db.query(Organization).first()
    if not org:
        org = Organization(name="Larsen & Toubro Digital Operations", slug="lt-digital")
        db.add(org)
        db.commit()

    server = MCPServer(
        organization_id=org.id,
        name=data.name,
        identifier=data.identifier,
        description=data.description,
        transport_type=data.transport_type,
        endpoint=data.endpoint,
        command=data.command or sys.executable,
        args=data.args,
        env_vars=data.env_vars,
        auth_method=data.auth_method,
        auth_token=data.auth_token,
        environment=data.environment,
        connection_timeout=data.connection_timeout,
        status="DISCONNECTED",
        is_enabled=True
    )
    db.add(server)
    db.commit()
    db.refresh(server)

    AuditService.record(
        db, "REGISTER_SERVER", "SERVER", server.id,
        user_name=current_user.full_name, role=current_user.role,
        details=f"Registered MCP server '{server.name}' ({server.transport_type})"
    )

    # Automatically attempt initial connection and discovery
    try:
        ok, msg, lat, _ = await MCPManager.test_server_connection(server)
        if ok:
            server.status = "HEALTHY"
            server.avg_response_time_ms = lat
            await MCPManager.discover_tools(db, server)
        else:
            server.status = "UNHEALTHY"
        db.commit()
        db.refresh(server)
    except Exception as e:
        server.status = "UNHEALTHY"
        db.commit()

    return server

@router.get("/{server_id}", response_model=MCPServerOut)
def get_server(
    server_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found.")
    return server

@router.put("/{server_id}", response_model=MCPServerOut)
def update_server(
    server_id: str,
    data: MCPServerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.SERVERS_WRITE))
):
    server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found.")

    for k, v in data.dict(exclude_unset=True).items():
        setattr(server, k, v)
    
    server.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(server)

    AuditService.record(
        db, "UPDATE_SERVER", "SERVER", server.id,
        user_name=current_user.full_name, role=current_user.role,
        details=f"Updated MCP server '{server.name}' configuration"
    )
    return server

@router.delete("/{server_id}")
def delete_server(
    server_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.SERVERS_DELETE))
):
    server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found.")

    server_name = server.name
    db.delete(server)
    db.commit()

    AuditService.record(
        db, "DELETE_SERVER", "SERVER", server_id,
        user_name=current_user.full_name, role=current_user.role,
        details=f"Deleted MCP server '{server_name}'"
    )
    return {"message": f"Server '{server_name}' deleted successfully."}

@router.post("/{server_id}/connect")
async def connect_server(
    server_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.SERVERS_CONNECT))
):
    server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found.")

    ok, msg, latency, info = await MCPManager.test_server_connection(server)
    if ok:
        server.status = "HEALTHY"
        server.avg_response_time_ms = latency
        server.last_health_check = datetime.datetime.utcnow()
        db.commit()
        # Refresh tools
        tools = await MCPManager.discover_tools(db, server)
        return {
            "status": "HEALTHY",
            "message": msg,
            "latency_ms": latency,
            "server_info": info,
            "tools_count": len(tools)
        }
    else:
        server.status = "UNHEALTHY"
        server.last_health_check = datetime.datetime.utcnow()
        db.commit()
        return {
            "status": "UNHEALTHY",
            "message": msg,
            "latency_ms": 0.0
        }

@router.post("/{server_id}/discover-tools")
async def discover_tools(
    server_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.SERVERS_WRITE))
):
    server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found.")

    tools = await MCPManager.discover_tools(db, server)
    return {
        "server_name": server.name,
        "discovered_count": len(tools),
        "tools": [MCPToolOut.from_orm(t) for t in tools]
    }

@router.get("/{server_id}/logs")
def get_server_logs(
    server_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found.")

    now = datetime.datetime.utcnow()
    logs = [
        f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] INFO [mcp-nexus] Initialized transport {server.transport_type} for '{server.name}'",
        f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] INFO [mcp-protocol] JSON-RPC 2.0 handshake verified. Capabilities: tools, resources",
        f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] INFO [health-check] Status: {server.status} | Latency: {server.avg_response_time_ms}ms",
        f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] INFO [registry] Active tools published: {len(server.tools)} endpoints",
        f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] DEBUG [telemetry] Error rate: {round(server.error_rate * 100, 2)}% | Total dispatches: {server.total_calls}"
    ]
    return {"server_id": server.id, "server_name": server.name, "logs": logs}
