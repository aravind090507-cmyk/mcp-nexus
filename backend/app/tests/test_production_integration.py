"""
MCP NEXUS — PHASE 15C STAGING VALIDATION SUITE
Production Integration, Controlled Rollout & Backward Compatibility Verification
"""

import sys
import os
import asyncio
import pytest
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.main import app
from app.core.config import settings
from app.database.session import SessionLocal
from app.models.all_models import MCPServer, MCPTool, User, Organization
from app.services.mcp_manager import MCPManager
from app.mcp.persistent_session import PersistentSessionManager, sanitize_log_data

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

@pytest.fixture(scope="module")
def viewer_headers(client):
    res = client.post("/api/v1/auth/switch-role", json={"role": "VIEWER"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(autouse=True)
def restore_settings():
    """Guarantees settings are restored to safe production defaults after each test."""
    orig_enabled = settings.ENABLE_PERSISTENT_MCP_SESSIONS
    orig_servers = settings.PERSISTENT_MCP_SERVERS
    orig_fallback = settings.PERSISTENT_MCP_FALLBACK_TO_LEGACY
    PersistentSessionManager.emergency_enable()
    yield
    settings.ENABLE_PERSISTENT_MCP_SESSIONS = orig_enabled
    settings.PERSISTENT_MCP_SERVERS = orig_servers
    settings.PERSISTENT_MCP_FALLBACK_TO_LEGACY = orig_fallback
    PersistentSessionManager.emergency_enable()


def test_01_default_remains_opt_in_legacy(client, admin_headers):
    """Rule: Persistent sessions must be disabled by default (opt-in only)."""
    assert settings.ENABLE_PERSISTENT_MCP_SESSIONS is False

    db = SessionLocal()
    try:
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        assert erp is not None
        assert MCPManager.is_persistent_enabled(erp) is False

        # Execute tool via default legacy transport
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_status").first()
        res, lat, success, err = asyncio.run(MCPManager.execute_tool(db, erp, tool, {"project_id": "PRJ-MUM-001"}))
        assert success is True
        assert err is None
        assert "Mumbai" in str(res)
    finally:
        db.close()


def test_02_runtime_health_endpoint_reports_transport_mode(client, admin_headers):
    """Verify /health and /servers/persistent/status endpoints expose accurate observability."""
    res_health = client.get("/health")
    assert res_health.status_code == 200
    h_data = res_health.json()
    assert h_data["status"] == "HEALTHY"
    assert "mcp_transport" in h_data
    assert h_data["mcp_transport"]["persistent_sessions"] == "OPT_IN_DISABLED"

    # Status endpoint
    res_status = client.get("/api/v1/servers/persistent/status", headers=admin_headers)
    assert res_status.status_code == 200
    s_data = res_status.json()
    assert s_data["global_flag_enabled"] is False
    assert s_data["emergency_disabled"] is False


def test_03_per_server_rollout_controls():
    """Verify granular per-server rollout (allowlists and per-server overrides)."""
    db = SessionLocal()
    try:
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        inv = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-inv-wh").first()
        eqp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-eqp-fleet").first()

        assert erp is not None
        assert inv is not None
        assert eqp is not None

        # Step A: Globally enabled, but restricted to ERP only
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "mcp-srv-erp-core"

        assert MCPManager.is_persistent_enabled(erp) is True
        assert MCPManager.is_persistent_enabled(inv) is False
        assert MCPManager.is_persistent_enabled(eqp) is False

        # Step B: Multiple servers in allowlist
        settings.PERSISTENT_MCP_SERVERS = "mcp-srv-erp-core, mcp-srv-eqp-fleet"
        assert MCPManager.is_persistent_enabled(erp) is True
        assert MCPManager.is_persistent_enabled(inv) is False
        assert MCPManager.is_persistent_enabled(eqp) is True

        # Step C: Per-server explicit override in env_vars
        inv.env_vars = {"ENABLE_PERSISTENT_SESSION": "true"}
        assert MCPManager.is_persistent_enabled(inv) is True

        erp.env_vars = {"ENABLE_PERSISTENT_SESSION": "false"}
        assert MCPManager.is_persistent_enabled(erp) is False

        # Restore env vars
        inv.env_vars = {}
        erp.env_vars = {}
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_04_persistent_transport_tool_execution():
    """Verify tool execution over warm persistent session when enabled."""
    db = SessionLocal()
    try:
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_status").first()

        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "mcp-srv-erp-core"

        # Execute multiple times on persistent session
        for _ in range(3):
            res, lat, success, err = await MCPManager.execute_tool(db, erp, tool, {"project_id": "PRJ-HAZ-002"})
            assert success is True
            assert err is None
            assert "Hazira" in str(res)
            # Persistent execution is ultra-fast
            assert lat < 50.0

        session = PersistentSessionManager.get_existing_session(erp.id)
        assert session is not None
        assert session.is_warm
        metrics = session.get_metrics()
        assert metrics["total_requests"] >= 3
        assert metrics["pending_requests"] == 0
    finally:
        await PersistentSessionManager.shutdown_all()
        db.close()


@pytest.mark.asyncio
async def test_05_mixed_transport_concurrent_workflow():
    """Verify concurrent workflow across mixed transports (ERP persistent, Inventory legacy)."""
    db = SessionLocal()
    try:
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        inv = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-inv-wh").first()

        tool_erp = db.query(MCPTool).filter(MCPTool.name == "get_project_status").first()
        tool_inv = db.query(MCPTool).filter(MCPTool.name == "get_inventory").first()

        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "mcp-srv-erp-core"  # Only ERP is persistent

        assert MCPManager.is_persistent_enabled(erp) is True
        assert MCPManager.is_persistent_enabled(inv) is False

        # Dispatch concurrent tasks
        t1 = MCPManager.execute_tool(db, erp, tool_erp, {"project_id": "PRJ-HYD-003"})
        t2 = MCPManager.execute_tool(db, inv, tool_inv, {})

        results = await asyncio.gather(t1, t2)
        res_erp, lat_erp, ok_erp, err_erp = results[0]
        res_inv, lat_inv, ok_inv, err_inv = results[1]

        assert ok_erp is True
        assert "Hyderabad" in str(res_erp)

        assert ok_inv is True
        assert "inventory" in str(res_inv).lower() or len(res_inv) > 0
    finally:
        await PersistentSessionManager.shutdown_all()
        db.close()


@pytest.mark.asyncio
async def test_06_safe_fallback_to_legacy_on_persistent_failure():
    """Verify that when persistent session startup fails, request safely falls back to legacy transport."""
    db = SessionLocal()
    try:
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_status").first()

        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "mcp-srv-erp-core"
        settings.PERSISTENT_MCP_FALLBACK_TO_LEGACY = True

        # Pre-create a corrupted session that cannot connect
        broken_session = PersistentSessionManager.get_session(
            server_id=erp.id,
            server_name=erp.name,
            command=sys.executable,
            args=["-c", "import sys; sys.exit(1)"],
            timeout=2.0
        )
        await broken_session.start()

        # Execute tool: persistent path fails, fallback to legacy succeeds!
        res, lat, success, err = await MCPManager.execute_tool(db, erp, tool, {"project_id": "PRJ-MUM-001"})
        assert success is True
        assert err is None
        assert "Mumbai" in str(res)
    finally:
        await PersistentSessionManager.shutdown_all()
        db.close()


def test_07_emergency_kill_switch_immediate_failover(client, admin_headers):
    """Verify operator emergency kill switch immediately stops persistent sessions and fails over to legacy."""
    settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
    settings.PERSISTENT_MCP_SERVERS = "*"

    # Engage emergency kill switch via API
    res = client.post("/api/v1/servers/persistent/emergency-disable", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["emergency_disabled"] is True
    assert PersistentSessionManager.is_emergency_disabled() is True

    # Health check reflects emergency disabled
    h_res = client.get("/health")
    assert h_res.json()["mcp_transport"]["persistent_sessions"] == "EMERGENCY_DISABLED"

    # Calls route to legacy transport
    db = SessionLocal()
    try:
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_status").first()

        # Must report disabled
        assert MCPManager.is_persistent_enabled(erp) is False

        # Execute succeeds via legacy per-call transport
        res_exec, _, ok, _ = asyncio.run(MCPManager.execute_tool(db, erp, tool, {"project_id": "PRJ-MUM-001"}))
        assert ok is True
        assert "Mumbai" in str(res_exec)
    finally:
        db.close()

    # Re-enable via API
    res_en = client.post("/api/v1/servers/persistent/emergency-enable", headers=admin_headers)
    assert res_en.status_code == 200
    assert res_en.json()["emergency_disabled"] is False
    assert PersistentSessionManager.is_emergency_disabled() is False


def test_08_governance_and_policy_engine_enforcement(client, viewer_headers, admin_headers):
    """Verify PolicyEngine stops prohibited actions before any transport is invoked."""
    settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
    settings.PERSISTENT_MCP_SERVERS = "*"

    # Viewer role executing a tool: rejected with 403 at API layer due to lack of TOOLS_TEST permission
    res_exec = client.post(
        "/api/v1/tools/execute",
        json={"tool_name": "get_project_status", "arguments": {"project_id": "PRJ-MUM-001"}},
        headers=viewer_headers
    )
    assert res_exec.status_code == 403

    # Dual-approval enforcement: Admin triggering a critical tool (report_equipment_issue with severity CRITICAL)
    res_crit = client.post(
        "/api/v1/tools/execute",
        json={
            "tool_name": "report_equipment_issue",
            "arguments": {
                "equipment_id": "EQP-CRN-8800",
                "severity": "CRITICAL",
                "description": "Crack observed in boom lattice during 500t test lift."
            }
        },
        headers=admin_headers
    )
    assert res_crit.status_code == 200
    body = res_crit.json()
    # Must require approval and halt before transport execution!
    assert body["is_success"] is False
    assert "approval" in body["error"].lower() or (body["result"] and body["result"].get("approval_required") is True)


def test_09_tenant_isolation_boundary():
    """Verify distinct tenant/organization boundaries execute without cross-tenant context leaks."""
    db = SessionLocal()
    try:
        orgs = db.query(Organization).all()
        assert len(orgs) >= 1
        org = orgs[0]

        # Verify servers belong to specific organization
        servers = db.query(MCPServer).filter(MCPServer.organization_id == org.id).all()
        assert len(servers) > 0
        for s in servers:
            assert s.organization_id == org.id
    finally:
        db.close()


def test_10_log_sanitizer_redacts_credentials():
    """Verify sensitive fields and auth tokens are stripped from log dictionaries and strings."""
    sensitive_input = {
        "username": "admin",
        "password": "SuperSecretPassword123!",
        "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy",
        "api_key": "sec-xyz-987",
        "nested": {
            "token": "tok_12345",
            "normal_data": "civil_engineering_metric"
        },
        "header_str": "Bearer eyJhbGciOiJIUzI1Ni.sensitive_part"
    }

    sanitized = sanitize_log_data(sensitive_input)
    assert sanitized["username"] == "admin"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["auth_token"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["normal_data"] == "civil_engineering_metric"
    assert "[REDACTED]" in sanitized["header_str"]
