from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.models.all_models import AIAgent, AgentServerAssignment, MCPServer, User, Organization
from app.schemas.all_schemas import AIAgentCreate, AIAgentOut, OrchestrationRequest, OrchestrationResponse
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.audit_service import AuditService
from app.api.deps import get_current_user, require_permission
from app.core.permissions import PermissionEnum
import datetime

router = APIRouter(prefix="/agents", tags=["AI Agents & Orchestration"])

@router.get("", response_model=List[AIAgentOut])
def list_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(AIAgent).all()

@router.post("", response_model=AIAgentOut)
def create_agent(
    data: AIAgentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.AGENTS_WRITE))
):
    existing = db.query(AIAgent).filter(AIAgent.identifier == data.identifier).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Agent '{data.identifier}' already exists.")

    org = db.query(Organization).first()
    if not org:
        org = Organization(name="Larsen & Toubro Digital Operations", slug="lt-digital")
        db.add(org)
        db.commit()

    agent = AIAgent(
        organization_id=org.id,
        name=data.name,
        identifier=data.identifier,
        description=data.description,
        llm_provider=data.llm_provider,
        model=data.model,
        system_prompt=data.system_prompt,
        max_execution_steps=data.max_execution_steps,
        execution_policy=data.execution_policy,
        status="ACTIVE"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    # Assign servers
    for s_id in data.assigned_server_ids:
        assign = AgentServerAssignment(agent_id=agent.id, server_id=s_id)
        db.add(assign)
    db.commit()

    AuditService.record(
        db, "CREATE_AGENT", "AGENT", agent.id,
        user_name=current_user.full_name, role=current_user.role,
        details=f"Created AI agent '{agent.name}' assigned to {len(data.assigned_server_ids)} MCP servers"
    )

    return agent

@router.get("/{agent_id}", response_model=AIAgentOut)
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="AI Agent not found.")
    return agent

@router.post("/orchestrate", response_model=OrchestrationResponse)
async def orchestrate(
    req: OrchestrationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.AGENTS_ORCHESTRATE))
):
    agent = db.query(AIAgent).filter(AIAgent.id == req.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="AI Agent not found.")

    if agent.status != "ACTIVE":
        raise HTTPException(status_code=400, detail=f"Agent '{agent.name}' is currently {agent.status}.")

    res = await AgentOrchestrator.orchestrate_request(
        db=db,
        agent=agent,
        user=current_user,
        user_prompt=req.prompt
    )

    AuditService.record(
        db, "AGENT_ORCHESTRATION", "AGENT", agent.id,
        user_name=current_user.full_name, role=current_user.role,
        details=f"Orchestrated query: '{req.prompt[:60]}...' Result: {res['overall_status']}"
    )

    return res
