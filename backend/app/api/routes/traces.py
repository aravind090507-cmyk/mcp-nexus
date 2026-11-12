from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models.all_models import ExecutionTrace, User
from app.schemas.all_schemas import TraceOut, TraceDetailOut
from app.api.deps import get_current_user

router = APIRouter(prefix="/traces", tags=["Execution Traces"])

@router.get("", response_model=List[TraceOut])
def list_traces(
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ExecutionTrace)
    if status:
        query = query.filter(ExecutionTrace.status == status)
    if risk_level:
        query = query.filter(ExecutionTrace.risk_level == risk_level)
    return query.order_by(ExecutionTrace.created_at.desc()).limit(limit).all()

@router.get("/{trace_id}", response_model=TraceDetailOut)
def get_trace(
    trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    trace = db.query(ExecutionTrace).filter(ExecutionTrace.trace_id == trace_id).first()
    if not trace:
        # fallback to primary key id
        trace = db.query(ExecutionTrace).filter(ExecutionTrace.id == trace_id).first()
    if not trace:
        raise HTTPException(status_code=404, detail="Execution trace not found.")
    return trace
