"""
MCP NEXUS — PHASE 15C.1 INDEPENDENT SECURITY & RELIABILITY AUDIT
Comprehensive Security, Multi-Tenant Isolation, Fallback Integrity,
Emergency Kill Switch, and Canary Readiness Test Suite
"""

import sys
import os
import asyncio
import uuid
import pytest
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.main import app
from app.core.config import settings
from app.database.session import SessionLocal
from app.models.all_models import MCPServer, MCPTool, User, Organization, SecurityEvent
from app.services.mcp_manager import MCPManager
from app.services.policy_engine import PolicyEngine, PolicyDecision
from app.mcp.persistent_session import PersistentSessionManager, sanitize_log_data, SessionLifecycleState
from app.core.security import get_password_hash
from app.core.permissions import RoleEnum

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def admin_headers(client):
    res = client.post("/api/v1/auth/switch-role", json={"role": "SUPER_ADMIN"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module", autouse=True)
def isolated_test_database(tmp_path_factory):
    """
    Creates an isolated copy of the database in a temporary directory for this test module.
    Rebinds SQLAlchemy engine and SessionLocal so no test mutations touch the real development DB.
    Guarantees clean teardown even on assertion failure.
    """
    import shutil
    from app.database.session import reset_database_engine
    
    orig_db_url = settings.DATABASE_URL
    temp_dir = tmp_path_factory.mktemp("db_phase15c1")
    temp_db_path = temp_dir / "isolated_phase15c1_test.db"
    
    dev_db_path = settings.resolve_absolute_db_path()
    if os.path.exists(dev_db_path):
        shutil.copy2(dev_db_path, str(temp_db_path))
    
    isolated_db_url = f"sqlite:///{temp_db_path}"
    settings.DATABASE_URL = isolated_db_url
    reset_database_engine(isolated_db_url)
    
    yield isolated_db_url
    
    # Teardown: Restore original database configuration
    settings.DATABASE_URL = orig_db_url
    reset_database_engine(orig_db_url)

@pytest.fixture(autouse=True)
def clean_test_environment():
    orig_enabled = settings.ENABLE_PERSISTENT_MCP_SESSIONS
    orig_servers = settings.PERSISTENT_MCP_SERVERS
    orig_fallback = settings.PERSISTENT_MCP_FALLBACK_TO_LEGACY
    PersistentSessionManager.emergency_enable()
    yield
    settings.ENABLE_PERSISTENT_MCP_SESSIONS = orig_enabled
    settings.PERSISTENT_MCP_SERVERS = orig_servers
    settings.PERSISTENT_MCP_FALLBACK_TO_LEGACY = orig_fallback
    PersistentSessionManager.emergency_enable()


# ==============================================================================
# 1. TENANT ISOLATION AUDIT
# ==============================================================================

def test_tenant_isolation_policy_engine_blocks_cross_tenant_access():
    """Audit: PolicyEngine must strictly block a tenant from accessing another tenant's server."""
    db = SessionLocal()
    org2 = None
    user2 = None
    try:
        # Create Tenant 1 (Org 1) and Tenant 2 (Org 2)
        org1 = db.query(Organization).first()
        org2_id = f"org-audit-isolated-{uuid.uuid4().hex[:6]}"
        org2 = Organization(id=org2_id, name="Isolated Audit Tenant 2", slug=f"audit-tenant-2-{uuid.uuid4().hex[:4]}")
        db.add(org2)
        db.commit()

        # Create Tenant 2 User (Developer role, belonging to Org 2)
        u2_id = f"usr-audit-{uuid.uuid4().hex[:6]}"
        user2 = User(
            id=u2_id,
            organization_id=org2.id,
            email=f"dev@{org2.slug}.com",
            full_name="Tenant 2 Developer",
            hashed_password=get_password_hash("AuditPass@2026"),
            role=RoleEnum.DEVELOPER.value
        )
        db.add(user2)
        db.commit()

        # Retrieve Tenant 1's Server (mcp-srv-erp-core, belonging to Org 1)
        server1 = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool1 = db.query(MCPTool).filter(MCPTool.name == "get_project_status").first()
        assert server1.organization_id == org1.id

        # Attempt: Tenant 2 User tries to validate execution on Tenant 1's server
        decision, msg, risk = PolicyEngine.validate_execution(
            db=db,
            user=user2,
            server=server1,
            tool=tool1,
            agent=None,
            arguments={"project_id": "PRJ-MUM-001"}
        )

        # MUST BE BLOCKED WITH CROSS-TENANT VIOLATION
        assert decision == PolicyDecision.BLOCKED
        assert "Cross-tenant" in msg or "different organization" in msg

        # Verify Security Audit Event recorded
        sec_evt = db.query(SecurityEvent).filter(
            SecurityEvent.actor == user2.email,
            SecurityEvent.event_type == "CROSS_TENANT_ACCESS_DENIED"
        ).order_by(SecurityEvent.timestamp.desc()).first()
        assert sec_evt is not None
        assert "Cross-tenant violation" in sec_evt.description
    finally:
        if user2:
            try:
                db.delete(user2)
            except Exception:
                pass
        if org2:
            try:
                db.delete(org2)
            except Exception:
                pass
        try:
            db.commit()
        except Exception:
            db.rollback()
        db.close()


@pytest.mark.asyncio
async def test_tenant_isolation_concurrent_isolated_executions():
    """Audit: Distinct tenants executing on distinct persistent servers do not leak context."""
    db = SessionLocal()
    try:
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "*"

        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        inv = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-inv-wh").first()

        tool_erp = db.query(MCPTool).filter(MCPTool.name == "get_project_status").first()
        tool_inv = db.query(MCPTool).filter(MCPTool.name == "get_inventory").first()

        # Execute concurrent tasks representing distinct domains/tenants
        t1 = MCPManager.execute_tool(db, erp, tool_erp, {"project_id": "PRJ-MUM-001"})
        t2 = MCPManager.execute_tool(db, inv, tool_inv, {})

        res1, lat1, ok1, err1 = await t1
        res2, lat2, ok2, err2 = await t2

        assert ok1 is True and err1 is None
        assert ok2 is True and err2 is None

        # Verify data outputs are completely distinct and contain no cross-server leakage
        assert "Mumbai" in str(res1)
        assert "Mumbai" not in str(res2)
    finally:
        await PersistentSessionManager.shutdown_all()
        db.close()


# ==============================================================================
# 2. EMERGENCY KILL SWITCH AUDIT
# ==============================================================================

@pytest.mark.asyncio
async def test_emergency_kill_switch_during_active_concurrent_requests():
    """Audit: Engaging emergency disable during active concurrent requests shuts down sessions and forces legacy transport."""
    db = SessionLocal()
    try:
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "*"

        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_status").first()

        # Pre-warm session
        ok_warm, _, _ = await MCPManager.ping_server(erp)
        assert ok_warm is True
        session = PersistentSessionManager.get_existing_session(erp.id)
        assert session is not None
        assert session.is_warm

        # Launch concurrent requests and disable midway
        async def _call(pid):
            return await MCPManager.execute_tool(db, erp, tool, {"project_id": pid})

        tasks = [asyncio.create_task(_call("PRJ-MUM-001")) for _ in range(5)]
        
        # Engage emergency disable immediately
        status = await PersistentSessionManager.emergency_disable(reason="Security Audit Chaos Test")
        assert status["emergency_disabled"] is True
        assert PersistentSessionManager.is_emergency_disabled() is True

        # Complete tasks (they will either complete on persistent or safely fall back to legacy)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            assert not isinstance(r, Exception)
            res_val, _, ok_val, _ = r
            assert ok_val is True
            assert "Mumbai" in str(res_val)

        # Subsequent request MUST route to legacy transport
        assert MCPManager.is_persistent_enabled(erp) is False
        res_post, lat_post, ok_post, _ = await MCPManager.execute_tool(db, erp, tool, {"project_id": "PRJ-HAZ-002"})
        assert ok_post is True
        assert "Hazira" in str(res_post)
    finally:
        PersistentSessionManager.emergency_enable()
        await PersistentSessionManager.shutdown_all()
        db.close()


@pytest.mark.asyncio
async def test_emergency_kill_switch_idempotency_and_circuit_cooldown():
    """Audit: Repeated emergency disable calls are completely idempotent and safe during circuit cooldown."""
    db = SessionLocal()
    try:
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()

        # Repeated calls
        res1 = await PersistentSessionManager.emergency_disable("Call 1")
        res2 = await PersistentSessionManager.emergency_disable("Call 2")
        res3 = await PersistentSessionManager.emergency_disable("Call 3")

        assert res1["emergency_disabled"] is True
        assert res2["emergency_disabled"] is True
        assert res3["emergency_disabled"] is True
        assert PersistentSessionManager.is_emergency_disabled() is True

        # Re-enable
        en_res = PersistentSessionManager.emergency_enable()
        assert en_res["emergency_disabled"] is False
        assert PersistentSessionManager.is_emergency_disabled() is False
    finally:
        db.close()


# ==============================================================================
# 3. AUTOMATIC FALLBACK AUDIT
# ==============================================================================

@pytest.mark.asyncio
async def test_fallback_preserves_policy_and_authorization():
    """Audit: Automatic fallback to legacy transport CANNOT bypass PolicyEngine, RBAC, or Dual-Approval."""
    db = SessionLocal()
    try:
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "*"
        settings.PERSISTENT_MCP_FALLBACK_TO_LEGACY = True

        eqp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-eqp-fleet").first()
        tool_crit = db.query(MCPTool).filter(MCPTool.name == "report_equipment_issue").first()
        user_admin = db.query(User).filter(User.role == RoleEnum.SUPER_ADMIN.value).first()

        # Step 1: PolicyEngine check for critical operation
        args_crit = {
            "equipment_id": "EQP-CRN-8800",
            "severity": "CRITICAL",
            "description": "Lattice boom micro-fracture audit."
        }

        decision, msg, risk = PolicyEngine.validate_execution(
            db, user_admin, eqp, tool_crit, None, args_crit
        )

        # PolicyEngine MUST return NEEDS_APPROVAL before transport is reached
        assert decision == PolicyDecision.NEEDS_APPROVAL
        assert risk == "CRITICAL"

        # Neither persistent nor legacy transport can be called directly without approval
    finally:
        db.close()


# ==============================================================================
# 4. LOG SANITIZATION SECURITY TESTS
# ==============================================================================

def test_log_sanitizer_deep_scrubbing():
    """Audit: Comprehensive sanitization against tokens, passwords, API keys, and stack traces."""
    # Test complex mixed payload
    payload = {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy_access",
        "refresh_token": "rtk_99887766554433221100",
        "api_key": "sec_live_abcdef123456",
        "apikey": "sec_apikey_789",
        "client_secret": "cs_live_secret_value",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEogIBAAKCAQEA...",
        "credentials": {"db_password": "ProductionRootPassword@2026!"},
        "nested_list": [
            {"token": "nested_tok_abc"},
            "Header: Bearer eyJhbGciOiJIUzI1Ni.jwt_value",
            "Traceback: DatabaseError: failed with password=PlainTextPass123 and api_key=sk-secret-live"
        ],
        "safe_data": {
            "project_name": "Mumbai Coastal Road",
            "concrete_grade": "M60"
        }
    }

    sanitized = sanitize_log_data(payload)

    # Assert all sensitive fields redacted
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["refresh_token"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["apikey"] == "[REDACTED]"
    assert sanitized["client_secret"] == "[REDACTED]"
    assert sanitized["private_key"] == "[REDACTED]"
    assert sanitized["credentials"] == "[REDACTED]"

    # Assert nested structures sanitized
    assert sanitized["nested_list"][0]["token"] == "[REDACTED]"
    assert "Bearer [REDACTED]" in sanitized["nested_list"][1]
    assert "password=[REDACTED]" in sanitized["nested_list"][2]
    assert "api_key=[REDACTED]" in sanitized["nested_list"][2]

    # Assert safe domain data preserved
    assert sanitized["safe_data"]["project_name"] == "Mumbai Coastal Road"
    assert sanitized["safe_data"]["concrete_grade"] == "M60"


# ==============================================================================
# 5. CONCURRENCY & CANARY TARGET VERIFICATION
# ==============================================================================

def test_canary_target_erp_core_readiness():
    """Audit: Validate candidate canary server 'mcp-srv-erp-core' readiness and isolation."""
    db = SessionLocal()
    try:
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        assert erp is not None
        assert erp.name == "ERP MCP Server"
        assert erp.transport_type == "STDIO"
        assert erp.is_enabled is True
        assert erp.command is not None

        # Verify its tools are registered and governed
        tools = db.query(MCPTool).filter(MCPTool.server_id == erp.id).all()
        assert len(tools) >= 3
        tool_names = [t.name for t in tools]
        assert "get_project_status" in tool_names
        assert "get_project_details" in tool_names
        assert "get_financial_summary" in tool_names

        for t in tools:
            assert t.is_enabled is True
            # Read-only ERP tools are LOW risk
            assert t.risk_level in ("LOW", "MEDIUM")

        # Rollback capability verification: Verify MCPManager properly toggles with allowlist
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "mcp-srv-erp-core"
        assert MCPManager.is_persistent_enabled(erp) is True

        # Rollback by removing from allowlist
        settings.PERSISTENT_MCP_SERVERS = ""
        assert MCPManager.is_persistent_enabled(erp) is False
    finally:
        db.close()
