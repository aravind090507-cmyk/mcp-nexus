import sys
import os
import asyncio
from contextlib import asynccontextmanager

if sys.platform == "win32" and sys.version_info < (3, 14):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.database.session import Base, engine, SessionLocal
from app.api.routes import (
    auth, servers, tools, agents, workflows, governance, traces, metrics, topology, integrations, settings as settings_route
)
from app.models.all_models import (
    Organization, User, MCPServer, MCPTool, AIAgent, IntegrationConfig, ExecutionTrace, SecurityEvent, AuditLog
)
from app.core.security import get_password_hash
from app.core.permissions import RoleEnum
from app.services.mcp_manager import MCPManager
import logging
import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mcp-nexus")

# Database schema management:
# Base.metadata.create_all(bind=engine) removed to prevent DDL on module import (Phase 15D.4.4).
# Production schema migrations must be applied explicitly via Alembic ('alembic upgrade head').

def check_database_readiness():
    """
    Verifies that required database schema prerequisites exist before application startup.
    Fails fast in Production if migrations have not been applied.
    """
    from sqlalchemy import inspect
    try:
        with engine.connect() as conn:
            insp = inspect(conn)
            existing_tables = set(insp.get_table_names())
        required_tables = {"organizations", "users", "mcp_servers", "mcp_tools"}
        missing = required_tables - existing_tables
        if missing:
            if settings.ENVIRONMENT.upper() == "PRODUCTION":
                raise RuntimeError(
                    f"CRITICAL STARTUP ERROR: Database schema prerequisites are missing: {sorted(missing)}. "
                    "In Production, database schema must be initialized via explicit migrations: 'alembic upgrade head'."
                )
            else:
                logger.info(f"Non-production environment: initializing missing tables {sorted(missing)} for local development/testing.")
                Base.metadata.create_all(bind=engine)
    except Exception as e:
        if settings.ENVIRONMENT.upper() == "PRODUCTION":
            raise
        logger.warning(f"Database readiness check encountered warning: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Strict fail-closed enterprise startup validation (Task B2)
    settings.validate_startup_configuration()
    check_database_readiness()
    await startup_seed()
    if getattr(settings, "ENABLE_PERSISTENT_MCP_SESSIONS", False) and getattr(settings, "PERSISTENT_MCP_PREWARM_ON_STARTUP", False):
        try:
            from app.services.mcp_manager import MCPManager
            db = SessionLocal()
            try:
                servers = db.query(MCPServer).filter(MCPServer.is_enabled == True, MCPServer.transport_type == "STDIO").all()
                for s in servers:
                    if MCPManager.is_persistent_enabled(s):
                        asyncio.create_task(MCPManager.ping_server(s))
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Error pre-warming persistent MCP sessions: {e}")
    yield
    try:
        from app.mcp.persistent_session import PersistentSessionManager
        await PersistentSessionManager.shutdown_all()
    except Exception as e:
        logger.warning(f"Error shutting down persistent MCP sessions: {e}")

app = FastAPI(
    title=f"{settings.PROJECT_NAME} Control Plane",
    description="Enterprise AI Integration, Orchestration & Governance Platform for Model Context Protocol (MCP)",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(servers.router, prefix=settings.API_V1_PREFIX)
app.include_router(tools.router, prefix=settings.API_V1_PREFIX)
app.include_router(agents.router, prefix=settings.API_V1_PREFIX)
app.include_router(workflows.router, prefix=settings.API_V1_PREFIX)
app.include_router(governance.router, prefix=settings.API_V1_PREFIX)
app.include_router(traces.router, prefix=settings.API_V1_PREFIX)
app.include_router(metrics.router, prefix=settings.API_V1_PREFIX)
app.include_router(topology.router, prefix=settings.API_V1_PREFIX)
app.include_router(integrations.router, prefix=settings.API_V1_PREFIX)
app.include_router(settings_route.router, prefix=settings.API_V1_PREFIX)

@app.get("/")
def root():
    return {
        "platform": settings.PROJECT_NAME,
        "tagline": settings.TAGLINE,
        "status": "OPERATIONAL",
        "version": settings.VERSION,
        "docs": "/docs",
        "api_v1": settings.API_V1_PREFIX
    }

@app.get("/health")
def health():
    from app.mcp.persistent_session import PersistentSessionManager
    persistent_status = "OPT_IN_DISABLED"
    if getattr(settings, "ENABLE_PERSISTENT_MCP_SESSIONS", False):
        persistent_status = "EMERGENCY_DISABLED" if PersistentSessionManager.is_emergency_disabled() else "ACTIVE"
    return {
        "status": "HEALTHY",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "database": "CONNECTED",
        "governance_engine": "ACTIVE",
        "mcp_transport": {
            "persistent_sessions": persistent_status,
            "fallback_enabled": getattr(settings, "PERSISTENT_MCP_FALLBACK_TO_LEGACY", True)
        }
    }

# Seed realistic enterprise data on first run
async def startup_seed():
    from app.mcp.client import MCPConnectionManager
    MCPConnectionManager.reset_all_circuits()
    db = SessionLocal()
    try:
        # Production administrator credential security & idempotent bootstrap
        if settings.ENVIRONMENT.upper() == "PRODUCTION":
            existing_admin = db.query(User).filter(User.role == RoleEnum.SUPER_ADMIN.value).first()
            if existing_admin:
                logger.info("Production Super Admin account verified; existing credentials preserved.")
                return

            bootstrap_password = settings.BOOTSTRAP_ADMIN_PASSWORD
            if not bootstrap_password:
                logger.error("Production startup halted: BOOTSTRAP_ADMIN_PASSWORD is required for initial production setup.")
                raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD is required for initial production setup.")

            org = db.query(Organization).first()
            if not org:
                org = Organization(
                    name="Enterprise Production",
                    slug="enterprise-prod",
                    description="MCP Nexus Production Control Plane",
                    tier="ENTERPRISE_MISSION_CRITICAL"
                )
                db.add(org)
                db.commit()
                db.refresh(org)

            admin_user = User(
                organization_id=org.id,
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
                full_name="Production Administrator",
                hashed_password=get_password_hash(bootstrap_password),
                role=RoleEnum.SUPER_ADMIN.value,
                department="Platform Operations"
            )
            db.add(admin_user)
            db.commit()
            logger.info(f"Production Super Admin successfully bootstrapped ({settings.BOOTSTRAP_ADMIN_EMAIL}); credentials secured.")
            return

        # Check if already seeded (Development / Staging / Test)
        if db.query(Organization).first():
            logger.info("Database already seeded.")
            return

        logger.info("Initializing enterprise seed data for MCP NEXUS...")

        # 1. Organization
        org = Organization(
            name="Larsen & Toubro Heavy Civil & Digital IC",
            slug="lt-heavy-civil",
            description="L&T Infrastructure Control Center & AI Operations Plane",
            tier="ENTERPRISE_MISSION_CRITICAL"
        )
        db.add(org)
        db.commit()
        db.refresh(org)

        # 2. Users (Super Admin, Admin, Developer, Operator, Viewer)
        users = [
            User(
                organization_id=org.id,
                email="admin@mcp-nexus.enterprise",
                full_name="Vikramaditya Sharma",
                hashed_password=get_password_hash("NexusAdmin@2026"),
                role=RoleEnum.SUPER_ADMIN.value,
                department="AI & Platform Infrastructure"
            ),
            User(
                organization_id=org.id,
                email="ops.lead@mcp-nexus.enterprise",
                full_name="Priya Sengupta",
                hashed_password=get_password_hash("NexusOps@2026"),
                role=RoleEnum.ADMIN.value,
                department="Industrial Operations Control"
            ),
            User(
                organization_id=org.id,
                email="dev.arch@mcp-nexus.enterprise",
                full_name="Karthik Narayan",
                hashed_password=get_password_hash("NexusDev@2026"),
                role=RoleEnum.DEVELOPER.value,
                department="Smart Infrastructure Solutions"
            ),
            User(
                organization_id=org.id,
                email="operator.site@mcp-nexus.enterprise",
                full_name="Rajesh Patel",
                hashed_password=get_password_hash("NexusOp@2026"),
                role=RoleEnum.OPERATOR.value,
                department="Site Execution Wing"
            ),
            User(
                organization_id=org.id,
                email="audit.viewer@mcp-nexus.enterprise",
                full_name="Ananya Roy",
                hashed_password=get_password_hash("NexusView@2026"),
                role=RoleEnum.VIEWER.value,
                department="Quality & Safety Compliance"
            )
        ]
        for u in users:
            db.add(u)
        db.commit()

        # 3. Register the 3 Working MCP Demo Servers with absolute paths
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        erp_script = os.path.join(base_dir, "app", "mcp", "demo_servers", "erp_server.py")
        inv_script = os.path.join(base_dir, "app", "mcp", "demo_servers", "inventory_server.py")
        eqp_script = os.path.join(base_dir, "app", "mcp", "demo_servers", "equipment_server.py")

        s_erp = MCPServer(
            organization_id=org.id,
            name="ERP MCP Server",
            identifier="mcp-srv-erp-core",
            description="Enterprise resource planning integration for project contracts, milestones, and financials.",
            transport_type="STDIO",
            command=sys.executable,
            args=[erp_script],
            environment="Production",
            status="HEALTHY",
            avg_response_time_ms=32.4,
            is_enabled=True,
            total_calls=1240
        )
        s_inv = MCPServer(
            organization_id=org.id,
            name="Inventory MCP Server",
            identifier="mcp-srv-inv-wh",
            description="Centralized multi-site warehouse inventory and high-tensile material tracking.",
            transport_type="STDIO",
            command=sys.executable,
            args=[inv_script],
            environment="Production",
            status="HEALTHY",
            avg_response_time_ms=28.1,
            is_enabled=True,
            total_calls=2150
        )
        s_eqp = MCPServer(
            organization_id=org.id,
            name="Equipment MCP Server",
            identifier="mcp-srv-eqp-fleet",
            description="Heavy machinery telemetry, crane load monitors, and preventative maintenance logs.",
            transport_type="STDIO",
            command=sys.executable,
            args=[eqp_script],
            environment="Production",
            status="HEALTHY",
            avg_response_time_ms=41.8,
            is_enabled=True,
            total_calls=980
        )
        db.add_all([s_erp, s_inv, s_eqp])
        db.commit()

        # Discover tools automatically on all 3 servers
        for s in [s_erp, s_inv, s_eqp]:
            try:
                await MCPManager.discover_tools(db, s)
                logger.info(f"Discovered tools for {s.name}")
            except Exception as e:
                logger.error(f"Failed initial tool discovery on {s.name}: {e}")

        # 4. Connected AI Agents
        agent_infra = AIAgent(
            organization_id=org.id,
            name="Atlas Infrastructure Orchestrator",
            identifier="agent-atlas-infra",
            description="Autonomous multi-server agent coordinating EPC projects, equipment fleet telemetry, and supply chains.",
            llm_provider="GEMINI",
            model="gemini-1.5-pro",
            status="ACTIVE",
            max_execution_steps=6,
            execution_policy="STRICT",
            total_orchestrations=84,
            system_prompt="You are Atlas, the principal industrial AI orchestrator for L&T operations."
        )
        agent_safety = AIAgent(
            organization_id=org.id,
            name="Aegis Safety & Compliance Agent",
            identifier="agent-aegis-safety",
            description="Specialized agent auditing machinery vibration alarms, overdue services, and workplace incidents.",
            llm_provider="GEMINI",
            model="gemini-1.5-flash",
            status="ACTIVE",
            max_execution_steps=4,
            execution_policy="STRICT",
            total_orchestrations=42,
            system_prompt="You are Aegis, dedicated to zero-incident safety governance across all construction packages."
        )
        db.add_all([agent_infra, agent_safety])
        db.commit()

        # 5. Enterprise Integrations (ERP, Inventory, Equipment, HR, Procurement)
        integs = [
            IntegrationConfig(
                name="SAP S/4HANA Enterprise ERP",
                system_type="ERP",
                vendor="SAP SE",
                status="CONNECTED",
                endpoint="https://erp-gateway.internal.lt.corp/v2",
                linked_mcp_server="ERP MCP Server",
                stats={"active_modules": ["PS", "CO", "FI", "MM"], "sync_records": 18204}
            ),
            IntegrationConfig(
                name="Maximo Asset Management",
                system_type="EQUIPMENT",
                vendor="IBM Maximo",
                status="CONNECTED",
                endpoint="https://maximo.plant-machinery.lt.corp/api",
                linked_mcp_server="Equipment MCP Server",
                stats={"tracked_units": 412, "telemetry_refresh_sec": 5}
            ),
            IntegrationConfig(
                name="WMS Warehouse Inventory Grid",
                system_type="INVENTORY",
                vendor="Oracle WMS Cloud",
                status="CONNECTED",
                endpoint="https://wms-hubs.supply.lt.corp/rest",
                linked_mcp_server="Inventory MCP Server",
                stats={"active_yards": 14, "sku_count": 8420}
            ),
            IntegrationConfig(
                name="Workday Global Workforce & HR",
                system_type="HR",
                vendor="Workday",
                status="CONNECTED",
                endpoint="https://workday.lt.corp/api/v4",
                linked_mcp_server=None,
                stats={"certified_riggers": 128, "active_engineers": 940}
            ),
            IntegrationConfig(
                name="Ariba E-Procurement Network",
                system_type="PROCUREMENT",
                vendor="SAP Ariba",
                status="CONNECTED",
                endpoint="https://ariba-b2b.procure.lt.corp/contracts",
                linked_mcp_server=None,
                stats={"rfq_in_flight": 32, "approved_vendors": 415}
            )
        ]
        db.add_all(integs)

        # 6. Seed Realistic Security Events
        sec_events = [
            SecurityEvent(
                event_type="UNAUTHORIZED_ACCESS",
                severity="HIGH",
                actor="user:contractor_temp@partner.com",
                target_resource="report_equipment_issue",
                description="Contractor role attempted destructive machinery report without role elevation.",
                ip_address="192.168.14.88"
            ),
            SecurityEvent(
                event_type="POLICY_VIOLATION",
                severity="MEDIUM",
                actor="agent:agent-aegis-safety",
                target_resource="get_financial_summary",
                description="Safety agent attempted unassigned financial record retrieval; blocked by Cross-Server Boundary Guard.",
                ip_address="10.20.10.4"
            ),
            SecurityEvent(
                event_type="BLOCKED_TOOL",
                severity="LOW",
                actor="user:operator.site@mcp-nexus.enterprise",
                target_resource="report_equipment_issue",
                description="Execution blocked: required administrative approval queue submission.",
                ip_address="192.168.1.42"
            )
        ]
        db.add_all(sec_events)

        # 7. Seed Initial Audit Logs
        audits = [
            AuditLog(
                action="SYSTEM_INIT",
                entity_type="PLATFORM",
                entity_id="core",
                user_name="Vikramaditya Sharma",
                role="SUPER_ADMIN",
                details="Initialized MCP NEXUS enterprise governance control plane."
            ),
            AuditLog(
                action="REGISTER_SERVER",
                entity_type="SERVER",
                entity_id="mcp-srv-erp-core",
                user_name="Vikramaditya Sharma",
                role="SUPER_ADMIN",
                details="Registered ERP MCP Server with STDIO transport."
            ),
            AuditLog(
                action="REGISTER_SERVER",
                entity_type="SERVER",
                entity_id="mcp-srv-inv-wh",
                user_name="Vikramaditya Sharma",
                role="SUPER_ADMIN",
                details="Registered Inventory MCP Server with STDIO transport."
            ),
            AuditLog(
                action="REGISTER_SERVER",
                entity_type="SERVER",
                entity_id="mcp-srv-eqp-fleet",
                user_name="Vikramaditya Sharma",
                role="SUPER_ADMIN",
                details="Registered Equipment MCP Server with STDIO transport."
            )
        ]
        db.add_all(audits)
        db.commit()
        logger.info("Enterprise seed data populated successfully.")
    except Exception as e:
        logger.error(f"Error during startup seed: {e}")
        db.rollback()
        if settings.ENVIRONMENT.upper() == "PRODUCTION":
            raise
    finally:
        db.close()
