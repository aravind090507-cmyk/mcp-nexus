from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database.session import get_db
from app.models.all_models import User, Organization
from app.schemas.all_schemas import UserLogin, UserCreate, UserOut, Token
from app.core.security import verify_password, create_access_token, get_password_hash
from app.api.deps import get_current_user
from app.core.permissions import RoleEnum
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])

class RoleSwitchRequest(BaseModel):
    role: str

@router.post("/login", response_model=Token)
def login(creds: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == creds.email).first()
    if not user or not verify_password(creds.password, user.hashed_password):
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
def switch_role(req: RoleSwitchRequest, db: Session = Depends(get_db)):
    """
    Issues an authentic signed JWT token for the requested enterprise role persona.
    Ensures that frontend role switching strictly changes the backend authenticated identity.
    """
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
