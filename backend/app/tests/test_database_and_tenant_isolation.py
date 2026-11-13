"""
Phase 15D.2.2 Automated Security & Reliability Test Suite:
1. Staging vs Development Database Isolation and Fail-Fast Enforcement.
2. ERP Server Tenant Defense-in-Depth (Cross-tenant rejection, missing context fail-closed).
3. Monitoring Endpoint (/servers/persistent/status) RBAC and Audit Logging.
"""

import os
import sys
import pytest
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.main import app
from app.core.config import Settings, _resolve_and_load_environment
from app.database.session import SessionLocal, reset_database_engine
from app.models.all_models import MCPServer, MCPTool, User, Organization, AuditLog
from app.services.mcp_manager import MCPManager
from app.core.security import create_access_token
from app.core.permissions import RoleEnum
from app.mcp.demo_servers.erp_server import handle_call_tool, PRIMARY_ORGANIZATION_ID, SECONDARY_ORGANIZATION_ID


# ==============================================================================
# 1. DATABASE & ENVIRONMENT ISOLATION TESTS
# ==============================================================================

def test_database_isolation_staging_vs_development():
    """Verify Staging and Development resolve to distinct databases and never collide."""
    # Dev settings
    s_dev = Settings.reload_for_environment("Development")
    dev_path = s_dev.resolve_absolute_db_path()

    # Staging settings
    s_stage = Settings.reload_for_environment("Staging")
    stage_path = s_stage.resolve_absolute_db_path()

    assert "mcp_nexus.db" in dev_path
    assert "mcp_nexus_staging.db" in stage_path
    assert dev_path != stage_path, "Staging and Development MUST NOT share the same physical database file."


def test_staging_missing_env_file_fails_fast():
    """Verify that if .env.staging is absent in Staging mode, startup fails fast."""
    orig_env = os.environ.get("ENVIRONMENT", "Development")
    os.environ["ENVIRONMENT"] = "Staging"
    
    # Temporarily move .env.staging if present
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    staging_file = os.path.join(repo_root, ".env.staging")
    tmp_file = os.path.join(repo_root, ".env.staging.test_bak")

    try:
        if os.path.isfile(staging_file):
            os.rename(staging_file, tmp_file)

        with pytest.raises(RuntimeError) as exc_info:
            _resolve_and_load_environment()
        assert "CRITICAL CONFIGURATION ERROR" in str(exc_info.value)
        assert ".env.staging" in str(exc_info.value)
    finally:
        if os.path.isfile(tmp_file):
            os.rename(tmp_file, staging_file)
        os.environ["ENVIRONMENT"] = orig_env
        Settings.reload_for_environment("Development")


def test_staging_with_dev_database_url_fails_fast():
    """Verify that configuring Staging with the development database URL triggers a hard failure."""
    orig_env = os.environ.get("ENVIRONMENT", "Development")
    orig_db = os.environ.get("DATABASE_URL", "")
    try:
        os.environ["ENVIRONMENT"] = "Staging"
        os.environ["DATABASE_URL"] = "sqlite:///./mcp_nexus.db"  # Erroneous dev DB in staging

        with pytest.raises(RuntimeError) as exc_info:
            _resolve_and_load_environment()
        assert "CRITICAL CONFIGURATION ERROR" in str(exc_info.value)
        assert "mcp_nexus_staging.db" in str(exc_info.value)
    finally:
        os.environ["ENVIRONMENT"] = orig_env
        if orig_db:
            os.environ["DATABASE_URL"] = orig_db
        else:
            os.environ.pop("DATABASE_URL", None)
        Settings.reload_for_environment("Development")


# ==============================================================================
# 2. ERP TENANT DEFENSE-IN-DEPTH TESTS
# ==============================================================================

def test_erp_missing_tenant_context_fails_closed(monkeypatch):
    """Verify tool calls without any tenant organization context fail closed."""
    monkeypatch.delenv("MCP_SERVER_ORGANIZATION_ID", raising=False)
    res = handle_call_tool("get_project_details", {"project_id": "PRJ-MUM-001", "organization_id": ""})
    assert "error" in res
    assert res.get("code") == "MISSING_TENANT_CONTEXT"
    assert "Missing tenant context" in res["error"]


def test_erp_cross_tenant_access_rejected_in_tool():
    """Verify Tenant B cannot retrieve Tenant A's project details or financial summary."""
    tenant_a = PRIMARY_ORGANIZATION_ID
    tenant_b = SECONDARY_ORGANIZATION_ID

    # 1. Project details cross-tenant rejection
    res_details = handle_call_tool("get_project_details", {
        "project_id": "PRJ-MUM-001",  # Belongs to Tenant A
        "organization_id": tenant_b   # Tenant B attempting access
    })
    assert "error" in res_details
    assert res_details.get("code") == "CROSS_TENANT_ACCESS_DENIED"

    # 2. Financial summary cross-tenant rejection
    res_fin = handle_call_tool("get_financial_summary", {
        "project_id": "PRJ-MUM-001",
        "organization_id": tenant_b
    })
    assert "error" in res_fin
    assert res_fin.get("code") == "CROSS_TENANT_ACCESS_DENIED"

    # 3. Legitimate tenant access succeeds
    res_valid = handle_call_tool("get_project_details", {
        "project_id": "PRJ-MUM-001",
        "organization_id": tenant_a
    })
    assert "project" in res_valid
    assert res_valid["project"]["project_id"] == "PRJ-MUM-001"


def test_erp_project_status_tenant_filtering():
    """Verify get_project_status filters results to strictly return caller's projects."""
    tenant_a = PRIMARY_ORGANIZATION_ID
    tenant_b = SECONDARY_ORGANIZATION_ID

    # Tenant A summary
    res_a = handle_call_tool("get_project_status", {"organization_id": tenant_a})
    assert "projects" in res_a
    for p in res_a["projects"]:
        assert p["project_id"] in ["PRJ-MUM-001", "PRJ-HAZ-002", "PRJ-HYD-003"]
        assert p["project_id"] != "PRJ-T2-001"

    # Tenant B summary
    res_b = handle_call_tool("get_project_status", {"organization_id": tenant_b})
    assert "projects" in res_b
    assert res_b["total_projects"] == 1
    assert res_b["projects"][0]["project_id"] == "PRJ-T2-001"


# ==============================================================================
# 3. MONITORING ENDPOINT SECURITY & AUDIT TESTS
# ==============================================================================

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_monitoring_status_endpoint_viewer_forbidden(client):
    """Verify that VIEWER users are forbidden from accessing operational telemetry."""
    db = SessionLocal()
    viewer_user = db.query(User).filter(User.role == "VIEWER").first()
    db.close()
    assert viewer_user is not None

    token = create_access_token(viewer_user.id)
    response = client.get(
        "/api/v1/servers/persistent/status",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert "restricted to authorized operators" in response.json()["detail"]


def test_monitoring_status_endpoint_operator_authorized_with_audit(client):
    """Verify that OPERATOR / ADMIN users can access telemetry and audit records are created."""
    db = SessionLocal()
    operator_user = db.query(User).filter(User.role == "OPERATOR").first()
    assert operator_user is not None

    token = create_access_token(operator_user.id)
    response = client.get(
        "/api/v1/servers/persistent/status",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "warm_sessions" in data
    assert "total_subprocess_rss_mb" in data

    # Verify audit log record
    log_entry = db.query(AuditLog).filter(
        AuditLog.action == "PERSISTENT_POOL_STATUS_READ",
        AuditLog.user_name == operator_user.full_name
    ).order_by(AuditLog.id.desc()).first()
    assert log_entry is not None
    assert "inspected persistent MCP session pool metrics" in log_entry.details
    db.close()
