from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.all_models import User
from app.core.security import decode_access_token
from app.core.permissions import RoleEnum, PermissionEnum, has_permission
from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    token = None
    if credentials:
        token = credentials.credentials
    elif "authorization" in request.headers:
        auth_header = request.headers["authorization"]
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if token:
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )
        return user

    # Development simulation header (only valid when DEBUG is True)
    if settings.DEBUG and "x-nexus-role" in request.headers:
        role_val = request.headers["x-nexus-role"].upper()
        user = db.query(User).filter(User.role == role_val).first()
        if user:
            return user

    # No valid authentication provided -> Strict 401 Unauthorized
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials not provided. Bearer token required.",
        headers={"WWW-Authenticate": "Bearer"},
    )

def require_permission(perm: PermissionEnum):
    def dependency(user: User = Depends(get_current_user)):
        user_role = RoleEnum(user.role)
        if not has_permission(user_role, perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires permission '{perm.value}' which is not granted to role '{user.role}'."
            )
        return user
    return dependency
