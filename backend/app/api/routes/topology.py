from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.all_models import MCPServer, AIAgent, IntegrationConfig, User
from app.api.deps import get_current_user

router = APIRouter(prefix="/topology", tags=["Infrastructure Map Topology"])

@router.get("")
def get_topology(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    servers = db.query(MCPServer).all()
    agents = db.query(AIAgent).all()
    integrations = db.query(IntegrationConfig).all()

    nodes = []
    edges = []

    # 1. Central MCP NEXUS Orchestrator Control Plane Node
    nodes.append({
        "id": "nexus-gateway",
        "type": "gatewayNode",
        "position": {"x": 480, "y": 240},
        "data": {
            "label": "MCP NEXUS Control Plane",
            "subtitle": "Central Protocol Gateway & Policy Engine",
            "type": "GATEWAY",
            "status": "OPERATIONAL",
            "active_rules": 4,
            "badge": "Active Core"
        }
    })

    # 2. AI Agent Nodes (Left Column)
    y_agent = 100
    for a in agents:
        node_id = f"agent-{a.id}"
        nodes.append({
            "id": node_id,
            "type": "agentNode",
            "position": {"x": 60, "y": y_agent},
            "data": {
                "label": a.name,
                "subtitle": f"{a.llm_provider} • {a.model}",
                "type": "AI_AGENT",
                "status": a.status,
                "policy": a.execution_policy,
                "orchestrations": a.total_orchestrations
            }
        })
        edges.append({
            "id": f"edge-{node_id}-nexus",
            "source": node_id,
            "target": "nexus-gateway",
            "animated": True,
            "style": {"stroke": "#F0A43A", "strokeWidth": 2}
        })
        y_agent += 140

    # 3. MCP Server Nodes (Middle Right Column)
    y_server = 80
    for s in servers:
        node_id = f"server-{s.id}"
        nodes.append({
            "id": node_id,
            "type": "serverNode",
            "position": {"x": 880, "y": y_server},
            "data": {
                "label": s.name,
                "subtitle": f"{s.transport_type} • {len(s.tools)} Tools",
                "type": "MCP_SERVER",
                "status": s.status,
                "latency_ms": s.avg_response_time_ms,
                "serverId": s.id
            }
        })
        edges.append({
            "id": f"edge-nexus-{node_id}",
            "source": "nexus-gateway",
            "target": node_id,
            "animated": s.status == "HEALTHY",
            "style": {"stroke": "#48B9D0" if s.status == "HEALTHY" else "#EBB346", "strokeWidth": 2}
        })
        y_server += 140

    # 4. Enterprise Integrations (Far Right Column)
    y_integ = 80
    for i in integrations:
        node_id = f"integ-{i.id}"
        nodes.append({
            "id": node_id,
            "type": "integrationNode",
            "position": {"x": 1280, "y": y_integ},
            "data": {
                "label": i.name,
                "subtitle": f"{i.vendor} • {i.system_type}",
                "type": "ENTERPRISE_SYSTEM",
                "status": i.status
            }
        })
        # Find matching server to draw edge
        matching_server = next((s for s in servers if i.system_type.lower() in s.name.lower()), None)
        if matching_server:
            edges.append({
                "id": f"edge-server-{matching_server.id}-{node_id}",
                "source": f"server-{matching_server.id}",
                "target": node_id,
                "style": {"stroke": "#43B581", "strokeWidth": 1.5, "strokeDasharray": "4"}
            })
        y_integ += 140

    # 5. Core PostgreSQL Database Node
    nodes.append({
        "id": "nexus-db",
        "type": "databaseNode",
        "position": {"x": 480, "y": 480},
        "data": {
            "label": "Audit & Trace Vault",
            "subtitle": "PostgreSQL Normalized Schema",
            "type": "DATABASE",
            "status": "HEALTHY"
        }
    })
    edges.append({
        "id": "edge-nexus-db",
        "source": "nexus-gateway",
        "target": "nexus-db",
        "style": {"stroke": "#303640", "strokeWidth": 2}
    })

    return {"nodes": nodes, "edges": edges}
