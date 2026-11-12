from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database.session import get_db
from app.models.all_models import User, Organization, SecurityEvent
from app.schemas.all_schemas import UserLogin, UserCreate, UserOut, Token
from app.core.security import verify_password, create_access_token, get_password_hash, decode_access_token
from app.api.deps import get_current_user
from app.core.permissions import RoleEnum
from app.core.config import settings
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])

class RoleSwitchRequest(BaseModel):
    role: str

@router.post("/login", response_model=Token)
def login(creds: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == creds.email).first()
    if not user or not verify_password(creds.password, user.hashed_password):
        # Record security event for authentication failure
        sec_evt = SecurityEvent(
            event_type="AUTH_FAILURE",
            severity="HIGH",
            actor=creds.email,
            target_resource="/auth/login",
            description=f"Failed authentication attempt for email '{creds.email}' from client {request.client.host if request.client else '127.0.0.1'}",
            metadata_json={"attempted_email": creds.email}
        )
        db.add(sec_evt)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User account is deactivated.")
    
    user.last_login = datetime.utcnow()
    db.commit()

    token = create_access_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/switch-role", response_model=Token)
def switch_role(req: RoleSwitchRequest, request: Request, db: Session = Depends(get_db)):
    """
    Issues an authentic signed JWT token for the requested enterprise role persona.
    Ensures that frontend role switching strictly changes the backend authenticated identity.
    Restricted in production environments to prevent privilege escalation.
    """
    # Guard against unauthorized privilege escalation in production
    if settings.ENVIRONMENT.lower() == "production":
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            sec_evt = SecurityEvent(
                event_type="PRIVILEGE_ESCALATION_ATTEMPT",
                severity="CRITICAL",
                actor="ANONYMOUS",
                target_resource="/auth/switch-role",
                description=f"Unauthenticated attempt to switch to role '{req.role}' in Production environment."
            )
            db.add(sec_evt)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Persona simulation is restricted in Production environments. Valid administrative Bearer token required."
            )
        token = auth_header[7:].strip()
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")
        caller = db.query(User).filter(User.id == payload.get("sub")).first()
        if not caller or caller.role != RoleEnum.SUPER_ADMIN.value:
            sec_evt = SecurityEvent(
                event_type="PRIVILEGE_ESCALATION_ATTEMPT",
                severity="CRITICAL",
                actor=caller.email if caller else "UNKNOWN",
                target_resource="/auth/switch-role",
                description=f"Non-SUPER_ADMIN user '{caller.email if caller else 'UNKNOWN'}' attempted to switch role in Production."
            )
            db.add(sec_evt)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only authenticated SUPER_ADMIN users may switch role personas in Production."
            )

    role_str = req.role.upper()
    try:
        valid_role = RoleEnum(role_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role '{req.role}'. Valid: {[r.value for r in RoleEnum]}")

    user = db.query(User).filter(User.role == valid_role.value).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"No provisioned user found for role '{valid_role.value}'")

    token = create_access_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
