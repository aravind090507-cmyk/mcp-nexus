from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.services.monitoring import MonitoringService
from app.api.deps import get_current_user
from app.models.all_models import User, MCPServer
import psutil
import datetime
import os

router = APIRouter(prefix="/metrics", tags=["System Observability & Metrics"])

@router.get("/command-center")
def get_command_center_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return MonitoringService.get_command_center_metrics(db)

@router.get("/system-health")
def get_system_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Real dynamic process telemetry via psutil
    proc = psutil.Process(os.getpid())
    mem_info = proc.memory_info()
    cpu_pct = psutil.cpu_percent(interval=None)
    active_servers = db.query(MCPServer).filter(MCPServer.status == "HEALTHY").count()

    return {
        "status": "OPERATIONAL",
        "cpu_usage_pct": round(cpu_pct, 1),
        "memory_usage_mb": round(mem_info.rss / (1024 * 1024), 1),
        "active_threads": proc.num_threads(),
        "open_mcp_connections": active_servers,
        "governance_engine": "ACTIVE_ENFORCING",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
