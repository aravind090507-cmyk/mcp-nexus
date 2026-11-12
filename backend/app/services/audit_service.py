from sqlalchemy.orm import Session
from app.models.all_models import AuditLog
from typing import Optional, Dict, Any

class AuditService:
    @staticmethod
    def record(
        db: Session,
        action: str,
        entity_type: str,
        entity_id: str,
        user_name: str = "System",
        role: str = "ADMIN",
        details: Optional[str] = None,
        diff: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        log = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user_name=user_name,
            role=role,
            details=details,
            diff=diff or {}
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
