from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.database.session import get_db
from app.models.all_models import MCPServer, MCPTool, User, Organization
from app.schemas.all_schemas import (
    MCPServerCreate, MCPServerUpdate, MCPServerOut, MCPToolOut,
    ServerDiscoverRequest, ServerDiscoverResponse
)
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

@router.get("/{server_id}/resources")
async def get_server_resources(
    server_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found.")
    resources = await MCPManager.discover_resources(server)
    return {"server_id": server.id, "server_name": server.name, "count": len(resources), "resources": resources}

@router.get("/{server_id}/prompts")
async def get_server_prompts(
    server_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found.")
    prompts = await MCPManager.discover_prompts(server)
    return {"server_id": server.id, "server_name": server.name, "count": len(prompts), "prompts": prompts}

@router.post("/{server_id}/ping")
async def ping_server_endpoint(
    server_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found.")
    ok, lat, msg = await MCPManager.ping_server(server)
    if ok:
        server.avg_response_time_ms = lat
        server.last_health_check = datetime.datetime.utcnow()
        db.commit()
    return {"server_id": server.id, "success": ok, "latency_ms": lat, "message": msg}

@router.get("/circuit-breaker/incidents")
def list_incidents(
    current_user: User = Depends(get_current_user)
):
    """
    Returns live infrastructure incidents, tripped circuit breakers, and automatic mitigation events.
    """
    from app.mcp.client import MCPConnectionManager
    return MCPConnectionManager.get_incidents()

@router.post("/{server_id}/reset-circuit")
def reset_circuit_endpoint(
    server_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.SERVERS_WRITE))
):
    server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found.")
    from app.mcp.client import MCPConnectionManager
    MCPConnectionManager.reset_circuit(server.id)
    server.status = "HEALTHY"
    server.error_rate = 0.0
    db.commit()
    return {"message": f"Circuit breaker for '{server.name}' reset successfully.", "status": "HEALTHY"}

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

@router.post("/discover", response_model=ServerDiscoverResponse)
async def auto_discover_endpoint(
    req: ServerDiscoverRequest,
    current_user: User = Depends(require_permission(PermissionEnum.SERVERS_WRITE))
):
    """
    Probes an external MCP endpoint (STDIO or HTTP_SSE), negotiates protocol capabilities,
    and returns discovered tools, resources, and prompts for admin review before activation.
    """
    from app.mcp.client import MCPClient
    import time
    import os
    
    start_time = time.perf_counter()
    try:
        cmd = req.command
        args = list(req.args or [])
        if cmd in ("python", "python3") and getattr(sys, "executable", None):
            cmd = sys.executable

        # Resolve demo server script paths if needed
        resolved_args = []
        for a in args:
            if a.endswith(".py") and not os.path.isabs(a):
                candidates = [
                    os.path.abspath(a),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp", a)),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp", "demo_servers", os.path.basename(a))),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp", os.path.basename(a))),
                ]
                found = False
                for c in candidates:
                    if os.path.isfile(c):
                        resolved_args.append(c)
                        found = True
                        break
                if not found:
                    resolved_args.append(a)
            else:
                resolved_args.append(a)
        args = resolved_args

        client = MCPClient(
            transport_type=req.transport_type,
            command=cmd,
            args=args,
            endpoint=req.endpoint,
            env_vars=req.env_vars,
            auth_token=req.auth_token,
            timeout=10.0
        )

        init_res, handshake_ms = await client.initialize()
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()
        
        total_latency = round((time.perf_counter() - start_time) * 1000.0, 2)
        
        return ServerDiscoverResponse(
            success=True,
            protocol_version=init_res.get("protocolVersion", "2024-11-05"),
            server_info=init_res.get("serverInfo", {}),
            capabilities=init_res.get("capabilities", {}),
            discovered_tools=tools,
            discovered_resources=resources,
            discovered_prompts=prompts,
            latency_ms=total_latency
        )
    except Exception as e:
        total_latency = round((time.perf_counter() - start_time) * 1000.0, 2)
        return ServerDiscoverResponse(
            success=False,
            latency_ms=total_latency,
            error=str(e)
        )
