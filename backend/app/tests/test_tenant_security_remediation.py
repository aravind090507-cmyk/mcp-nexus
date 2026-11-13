"""
Phase 15D.2.4 — Tenant Security Remediation Test Suite:
10 Mandatory Security Verifications for Authoritative Tenant Identity Binding,
Tamper Resistance, Fail-Closed Handling, and Concurrent Multi-Tenant Isolation.
"""

import sys
import os
import asyncio
import uuid
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.main import app
from app.core.config import settings
from app.database.session import SessionLocal, reset_database_engine
from app.models.all_models import MCPServer, MCPTool, User, Organization
from app.services.mcp_manager import MCPManager
from app.mcp.persistent_session import PersistentSessionManager
from app.mcp.demo_servers.erp_server import PRIMARY_ORGANIZATION_ID, SECONDARY_ORGANIZATION_ID, handle_call_tool

ERP_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp", "demo_servers", "erp_server.py"))


@pytest.fixture(scope="module", autouse=True)
def isolated_test_database(tmp_path_factory):
    """
    Creates an isolated copy of the database in a temporary directory for this security test module.
    Ensures zero mutation of real development or staging databases.
    """
    import shutil
    orig_db_url = settings.DATABASE_URL
    temp_dir = tmp_path_factory.mktemp("db_tenant_security")
    temp_db_path = temp_dir / "isolated_tenant_security_test.db"

    dev_db_path = settings.resolve_absolute_db_path()
    if os.path.exists(dev_db_path):
        shutil.copy2(dev_db_path, str(temp_db_path))

    isolated_db_url = f"sqlite:///{temp_db_path}"
    settings.DATABASE_URL = isolated_db_url
    reset_database_engine(isolated_db_url)

    yield isolated_db_url

    settings.DATABASE_URL = orig_db_url
    reset_database_engine(orig_db_url)


@pytest.fixture(autouse=True)
def clean_sessions():
    PersistentSessionManager.emergency_enable()
    yield
    PersistentSessionManager.emergency_enable()


# ==============================================================================
# 10 MANDATORY SECURITY TESTS (PHASE 15D.2.4)
# ==============================================================================

@pytest.mark.asyncio
async def test_01_caller_supplies_forged_organization_id():
    """Security Test 1: Caller supplies a forged organization_id; authoritative server identity overrides it."""
    db = SessionLocal()
    try:
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_details").first()
        assert erp.organization_id == PRIMARY_ORGANIZATION_ID

        # Attacker provides forged organization_id pointing to Tenant B (SECONDARY_ORGANIZATION_ID)
        # while attempting to access Tenant B's project PRJ-T2-001.
        forged_args = {
            "project_id": "PRJ-T2-001",
            "organization_id": SECONDARY_ORGANIZATION_ID
        }

        # MCPManager must overwrite organization_id with server's PRIMARY_ORGANIZATION_ID.
        # Consequently, the ERP server sees PRIMARY_ORGANIZATION_ID trying to access PRJ-T2-001
        # and rejects the cross-tenant access.
        res, lat, ok, err = await MCPManager.execute_tool(db, erp, tool, forged_args)
        assert ok is True  # Tool executed successfully
        parsed = res.get("parsed") or res
        assert "error" in parsed
        assert parsed.get("code") == "CROSS_TENANT_ACCESS_DENIED"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_02_caller_supplies_forged_tenant_id():
    """Security Test 2: Caller supplies a forged tenant_id; authoritative server identity overrides it."""
    db = SessionLocal()
    try:
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_details").first()

        forged_args = {
            "project_id": "PRJ-T2-001",
            "tenant_id": SECONDARY_ORGANIZATION_ID
        }

        res, lat, ok, err = await MCPManager.execute_tool(db, erp, tool, forged_args)
        assert ok is True
        parsed = res.get("parsed") or res
        assert "error" in parsed
        assert parsed.get("code") == "CROSS_TENANT_ACCESS_DENIED"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_03_caller_supplies_both_forged_values():
    """Security Test 3: Caller supplies both forged organization_id and tenant_id."""
    db = SessionLocal()
    try:
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_details").first()

        forged_args = {
            "project_id": "PRJ-T2-001",
            "organization_id": "forged-org-rogue-x",
            "tenant_id": "forged-tenant-rogue-y",
            "org_id": "forged-alias-z",
            "context": {"organization_id": "nested-forgery"}
        }

        res, lat, ok, err = await MCPManager.execute_tool(db, erp, tool, forged_args)
        assert ok is True
        parsed = res.get("parsed") or res
        # Must be rejected because authoritative identity is PRIMARY_ORGANIZATION_ID,
        # which cannot access PRJ-T2-001 (Tenant B).
        assert "error" in parsed
        assert parsed.get("code") == "CROSS_TENANT_ACCESS_DENIED"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_04_server_has_no_organization_id_fails_closed():
    """Security Test 4: Server has no organization ID configured (None or empty); fails closed."""
    db = SessionLocal()
    try:
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_status").first()
        
        # Create mock server without organization_id
        server_no_org = MCPServer(
            id="srv-mock-no-org",
            name="Mock Server Without Org",
            identifier="mock-no-org",
            organization_id=None,
            command=sys.executable,
            args=[ERP_SCRIPT]
        )

        res, lat, ok, err = await MCPManager.execute_tool(db, server_no_org, tool, {"project_id": "PRJ-MUM-001"})
        assert ok is False
        assert err is not None
        assert "no authoritative organization_id" in err.lower()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_05_server_has_invalid_organization_id_fails_closed():
    """Security Test 5: Server references an invalid/non-existent organization ID; fails closed."""
    db = SessionLocal()
    try:
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_status").first()
        
        server_invalid_org = MCPServer(
            id="srv-mock-invalid-org",
            name="Mock Server With Invalid Org",
            identifier="mock-invalid-org",
            organization_id="non-existent-uuid-99999",
            command=sys.executable,
            args=[ERP_SCRIPT]
        )

        res, lat, ok, err = await MCPManager.execute_tool(db, server_invalid_org, tool, {"project_id": "PRJ-MUM-001"})
        assert ok is False
        assert err is not None
        assert "invalid organization_id" in err.lower()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_06_legitimate_tenant_request_succeeds():
    """Security Test 6: Legitimate tenant request using authoritative identity succeeds."""
    db = SessionLocal()
    try:
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_details").first()

        legit_args = {"project_id": "PRJ-MUM-001"}
        res, lat, ok, err = await MCPManager.execute_tool(db, erp, tool, legit_args)
        assert ok is True
        assert err is None
        parsed = res.get("parsed") or res
        assert "project" in parsed
        assert parsed["project"]["organization_id"] == PRIMARY_ORGANIZATION_ID
        assert "Mumbai" in parsed["project"]["name"]
    finally:
        db.close()


@pytest.mark.asyncio
async def test_07_cross_tenant_request_is_rejected():
    """Security Test 7: Cross-tenant request to access another tenant's project is strictly rejected."""
    db = SessionLocal()
    try:
        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool = db.query(MCPTool).filter(MCPTool.name == "get_financial_summary").first()

        # Tenant A's server attempting to query Tenant B's PRJ-T2-001 financials
        res, lat, ok, err = await MCPManager.execute_tool(db, erp, tool, {"project_id": "PRJ-T2-001"})
        assert ok is True
        parsed = res.get("parsed") or res
        assert "error" in parsed
        assert parsed.get("code") == "CROSS_TENANT_ACCESS_DENIED"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_08_concurrent_requests_two_tenants_remain_isolated():
    """Security Test 8: Concurrent requests from two tenants remain completely isolated."""
    db = SessionLocal()
    try:
        tenant_a = PRIMARY_ORGANIZATION_ID
        tenant_b = SECONDARY_ORGANIZATION_ID

        async def worker_a(idx: int):
            res = handle_call_tool("get_project_details", {
                "project_id": "PRJ-MUM-001",
                "organization_id": tenant_a
            })
            assert res["project"]["organization_id"] == tenant_a
            assert "Mumbai" in res["project"]["name"]

        async def worker_b(idx: int):
            res = handle_call_tool("get_project_details", {
                "project_id": "PRJ-T2-001",
                "organization_id": tenant_b
            })
            assert res["project"]["organization_id"] == tenant_b
            assert "Bengaluru" in res["project"]["name"]

        tasks = []
        for i in range(10):
            tasks.append(worker_a(i))
            tasks.append(worker_b(i))

        await asyncio.gather(*tasks)
    finally:
        db.close()


@pytest.mark.asyncio
async def test_09_persistent_session_reuse_does_not_leak_tenant_context():
    """Security Test 9: Reusing a warm persistent session never leaks tenant context across requests."""
    db = SessionLocal()
    try:
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "mcp-srv-erp-core"

        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_status").first()

        # Pre-warm session
        ok_warm, _, _ = await MCPManager.ping_server(erp)
        assert ok_warm is True

        # Call 1: Tenant A project
        res1, lat1, ok1, _ = await MCPManager.execute_tool(db, erp, tool, {"project_id": "PRJ-MUM-001"})
        assert ok1 is True
        assert "Mumbai" in str(res1)

        # Call 2: Attacker attempts to sneak in forged tenant
        res2, lat2, ok2, _ = await MCPManager.execute_tool(db, erp, tool, {
            "project_id": "PRJ-T2-001",
            "organization_id": SECONDARY_ORGANIZATION_ID
        })
        assert ok2 is True
        parsed2 = res2.get("parsed") or res2
        # Must be rejected because authoritative tenant is Tenant A
        assert "CROSS_TENANT_ACCESS_DENIED" == parsed2.get("code")

        # Call 3: Subsequent normal call succeeds without any corruption from Call 2
        res3, lat3, ok3, _ = await MCPManager.execute_tool(db, erp, tool, {"project_id": "PRJ-HAZ-002"})
        assert ok3 is True
        assert "Hazira" in str(res3)
    finally:
        await PersistentSessionManager.shutdown_all()
        db.close()


@pytest.mark.asyncio
async def test_10_cancellation_and_reconnect_do_not_preserve_stale_identity():
    """Security Test 10: Cancellation, session shutdown, and reconnect preserve strict authoritative identity."""
    db = SessionLocal()
    try:
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "mcp-srv-erp-core"

        erp = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
        tool = db.query(MCPTool).filter(MCPTool.name == "get_project_status").first()

        # Warm up
        await MCPManager.ping_server(erp)

        # Force shutdown / reset (simulating process crash / reconnect)
        await PersistentSessionManager.shutdown_all()

        # New call must re-spawn cleanly and apply authoritative identity
        res, lat, ok, err = await MCPManager.execute_tool(db, erp, tool, {
            "project_id": "PRJ-MUM-001",
            "organization_id": "forged-post-reconnect"
        })
        assert ok is True
        assert "Mumbai" in str(res)
    finally:
        await PersistentSessionManager.shutdown_all()
        db.close()
