from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.models.all_models import IntegrationConfig, User
from app.api.deps import get_current_user

router = APIRouter(prefix="/integrations", tags=["Enterprise Integrations"])

@router.get("")
def list_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(IntegrationConfig).all()
