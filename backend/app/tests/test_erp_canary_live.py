"""
Phase 15D.2 Automated Pytest Suite: ERP Canary Live Verification & Telemetry.

Validates:
1. Pre-activation security gate (Tenant isolation & RBAC).
2. Controlled persistent canary execution for ERP server exclusively.
3. Isolation of non-canary servers (Inventory & Equipment remain on legacy).
4. Chaos recovery upon subprocess termination.
5. Emergency rollback (< 2000ms) and fallback execution preservation.
"""

import asyncio
import os
import sys
import psutil
import pytest
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.database.session import SessionLocal
from app.models.all_models import MCPServer, MCPTool, User, Organization
from app.core.config import settings
from app.mcp.persistent_session import PersistentSessionManager
from app.services.mcp_manager import MCPManager
from app.services.policy_engine import PolicyEngine, PolicyDecision


@pytest.fixture(autouse=True)
def reset_sessions_fixture():
    PersistentSessionManager.reset()
    yield
    PersistentSessionManager.reset()


@pytest.fixture(scope="module", autouse=True)
def isolated_test_database(tmp_path_factory):
    """
    Creates an isolated copy of the database in a temporary directory for canary live tests.
    Ensures zero mutation of real development or staging databases.
    """
    import shutil
    from app.database.session import reset_database_engine
    
    orig_db_url = settings.DATABASE_URL
    temp_dir = tmp_path_factory.mktemp("db_canary_live")
    temp_db_path = temp_dir / "isolated_canary_live_test.db"
    
    dev_db_path = settings.resolve_absolute_db_path()
    if os.path.exists(dev_db_path):
        shutil.copy2(dev_db_path, str(temp_db_path))
    
    isolated_db_url = f"sqlite:///{temp_db_path}"
    settings.DATABASE_URL = isolated_db_url
    reset_database_engine(isolated_db_url)
    
    yield isolated_db_url
    
    settings.DATABASE_URL = orig_db_url
    reset_database_engine(orig_db_url)


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    PersistentSessionManager.reset()
    db.close()


@pytest.mark.asyncio
async def test_canary_preactivation_security_gate(db_session):
    """Verify tenant isolation and RBAC before canary execution."""
    erp_server = db_session.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
    assert erp_server is not None, "ERP server must exist in database"

    dev_user = db_session.query(User).filter(User.role == "DEVELOPER").first()
    viewer_user = db_session.query(User).filter(User.role == "VIEWER").first()
    assert dev_user is not None
    assert viewer_user is not None

    fake_org = None
    unauth_user = None
    try:
        # Create temporary rogue tenant
        fake_org = Organization(name="Pytest Rogue Corp", slug=f"rogue-{int(time.time())}")
        db_session.add(fake_org)
        db_session.commit()

        unauth_user = User(
            organization_id=fake_org.id,
            email=f"spy-{int(time.time())}@{fake_org.slug}.com",
            full_name="External Infiltrator",
            hashed_password="dummy",
            role="DEVELOPER",
        )
        db_session.add(unauth_user)
        db_session.commit()

        tool_status = db_session.query(MCPTool).filter(MCPTool.server_id == erp_server.id, MCPTool.name == "get_project_status").first()
        tool_fin = db_session.query(MCPTool).filter(MCPTool.server_id == erp_server.id, MCPTool.name == "get_financial_summary").first()

        # 1. Tenant boundary enforcement
        dec_tenant, msg_tenant, _ = PolicyEngine.validate_execution(
            db_session, unauth_user, erp_server, tool_status, None, {"project_id": "PRJ-MUM-001"}
        )
        assert dec_tenant == PolicyDecision.BLOCKED
        assert "Tenant boundary mismatch" in msg_tenant or "tenant" in msg_tenant.lower()

        # 2. RBAC check on read-only financial tool
        dec_dev, _, _ = PolicyEngine.validate_execution(
            db_session, dev_user, erp_server, tool_fin, None, {"project_id": "PRJ-MUM-001"}
        )
        assert dec_dev == PolicyDecision.PERMITTED

        dec_viewer, _, _ = PolicyEngine.validate_execution(
            db_session, viewer_user, erp_server, tool_fin, None, {"project_id": "PRJ-MUM-001"}
        )
        assert dec_viewer == PolicyDecision.BLOCKED
    finally:
        if unauth_user:
            try:
                db_session.delete(unauth_user)
            except Exception:
                pass
        if fake_org:
            try:
                db_session.delete(fake_org)
            except Exception:
                pass
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()


@pytest.mark.asyncio
async def test_canary_activation_and_transport_scoping(db_session):
    """Verify persistent sessions activate ONLY for ERP server and legacy remains for inventory."""
    orig_flag = settings.ENABLE_PERSISTENT_MCP_SESSIONS
    orig_servers = settings.PERSISTENT_MCP_SERVERS
    try:
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "mcp-srv-erp-core"
        PersistentSessionManager.emergency_enable()

        erp_server = db_session.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        inv_server = db_session.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-inv-wh").first()
        eqp_server = db_session.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-eqp-fleet").first()

        assert erp_server is not None
        assert inv_server is not None
        assert eqp_server is not None

        # Check scoping logic
        assert MCPManager.is_persistent_enabled(erp_server) is True
        assert MCPManager.is_persistent_enabled(inv_server) is False
        assert MCPManager.is_persistent_enabled(eqp_server) is False

        # Execute tool on ERP server via persistent transport
        tool_status = db_session.query(MCPTool).filter(MCPTool.server_id == erp_server.id, MCPTool.name == "get_project_status").first()
        res, lat, ok, err = await MCPManager.execute_tool(
            db_session, erp_server, tool_status, {"project_id": "PRJ-MUM-001"}
        )
        assert ok is True
        assert err is None
        assert "PRJ-MUM-001" in str(res)

        # Confirm session is warm and registered
        session = PersistentSessionManager.get_existing_session(erp_server.id)
        assert session is not None
        assert session.is_warm is True
        assert session.pid is not None

        # Verify inventory session was NOT created in persistent manager
        inv_session = PersistentSessionManager.get_existing_session(inv_server.id)
        assert inv_session is None

    finally:
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = orig_flag
        settings.PERSISTENT_MCP_SERVERS = orig_servers


@pytest.mark.asyncio
async def test_canary_chaos_recovery(db_session):
    """Verify transparent recovery after persistent subprocess termination."""
    orig_flag = settings.ENABLE_PERSISTENT_MCP_SESSIONS
    orig_servers = settings.PERSISTENT_MCP_SERVERS
    orig_fallback = settings.PERSISTENT_MCP_FALLBACK_TO_LEGACY
    try:
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "mcp-srv-erp-core"
        settings.PERSISTENT_MCP_FALLBACK_TO_LEGACY = True
        PersistentSessionManager.emergency_enable()

        erp_server = db_session.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool_det = db_session.query(MCPTool).filter(MCPTool.server_id == erp_server.id, MCPTool.name == "get_project_details").first()

        # Ensure session is active via ping
        ping_ok, _, _ = await MCPManager.ping_server(erp_server)
        assert ping_ok is True
        session_before = PersistentSessionManager.get_existing_session(erp_server.id)
        assert session_before is not None
        old_pid = session_before.pid
        assert old_pid is not None

        # Terminate subprocess forcefully (chaos injection)
        proc = psutil.Process(old_pid)
        proc.kill()
        await asyncio.sleep(0.3)

        # Call tool immediately - should execute successfully via transparent reconnect or fallback
        res, lat, ok, err = await MCPManager.execute_tool(
            db_session, erp_server, tool_det, {"project_id": "PRJ-MUM-001"}
        )
        assert ok is True
        assert err is None
        assert "PRJ-MUM-001" in str(res)

        # Verify session is not stuck in dead process
        session_after = PersistentSessionManager.get_existing_session(erp_server.id)
        assert session_after is not None
        assert session_after.pid != old_pid or session_after.is_warm
    finally:
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = orig_flag
        settings.PERSISTENT_MCP_SERVERS = orig_servers
        settings.PERSISTENT_MCP_FALLBACK_TO_LEGACY = orig_fallback


@pytest.mark.asyncio
async def test_canary_emergency_rollback(db_session):
    """Verify emergency disable terminates persistent sessions and falls back cleanly in < 2s."""
    orig_flag = settings.ENABLE_PERSISTENT_MCP_SESSIONS
    orig_servers = settings.PERSISTENT_MCP_SERVERS
    try:
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "mcp-srv-erp-core"
        PersistentSessionManager.emergency_enable()

        erp_server = db_session.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool_status = db_session.query(MCPTool).filter(MCPTool.server_id == erp_server.id, MCPTool.name == "get_project_status").first()

        # Warm up session
        ping_ok, _, _ = await MCPManager.ping_server(erp_server)
        assert ping_ok is True
        session = PersistentSessionManager.get_existing_session(erp_server.id)
        assert session is not None
        old_pid = session.pid

        # Engage Emergency Kill Switch
        t0 = time.perf_counter()
        await PersistentSessionManager.emergency_disable("Pytest canary rollback test")
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = False
        rollback_duration_ms = (time.perf_counter() - t0) * 1000.0

        # Assert shutdown duration < 2000ms
        assert rollback_duration_ms < 2000.0, f"Rollback took too long: {rollback_duration_ms}ms"

        # Assert persistent session was removed and process terminated
        assert PersistentSessionManager.is_emergency_disabled() is True
        assert PersistentSessionManager.get_existing_session(erp_server.id) is None
        assert not psutil.pid_exists(old_pid)

        # Assert seamless execution via legacy fallback
        res, lat, ok, err = await MCPManager.execute_tool(
            db_session, erp_server, tool_status, {"project_id": "PRJ-MUM-001"}
        )
        assert ok is True
        assert err is None
        assert "PRJ-MUM-001" in str(res)
    finally:
        PersistentSessionManager.emergency_enable()
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = orig_flag
        settings.PERSISTENT_MCP_SERVERS = orig_servers
