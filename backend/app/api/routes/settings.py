from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.database.session import get_db
from app.models.all_models import Organization, User
from app.schemas.all_schemas import UserOut, UserCreate
from app.core.config import settings
from app.core.security import get_password_hash
from app.api.deps import get_current_user, require_permission
from app.core.permissions import PermissionEnum, RoleEnum

router = APIRouter(prefix="/settings", tags=["Enterprise Settings"])

@router.get("/organization")
def get_organization(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org = db.query(Organization).first()
    if not org:
        org = Organization(name="Larsen & Toubro Digital Operations", slug="lt-digital")
        db.add(org)
        db.commit()
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "tier": org.tier,
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
        "tagline": settings.TAGLINE
    }

@router.get("/api-configuration")
def get_api_config(
    current_user: User = Depends(require_permission(PermissionEnum.SETTINGS_READ))
):
    return {
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "has_api_key": bool(settings.LLM_API_KEY),
        "api_key_masked": f"{settings.LLM_API_KEY[:4]}...{settings.LLM_API_KEY[-4:]}" if settings.LLM_API_KEY else "NOT_CONFIGURED (Running in Deterministic Enterprise Mode)",
        "mcp_protocol_version": "2024-11-05",
        "supported_transports": ["STDIO", "HTTP_SSE"],
        "default_timeout_seconds": 15
    }

@router.get("/users", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(User).all()

@router.post("/users", response_model=UserOut)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionEnum.SETTINGS_WRITE))
):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists.")
    
    org = db.query(Organization).first()
    user = User(
        organization_id=org.id,
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        role=data.role,
        department=data.department,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
