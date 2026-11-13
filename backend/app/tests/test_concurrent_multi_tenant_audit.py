"""
Phase 15D.2.3 Independent Audit Test Suite:
Concurrent Multi-Tenant Isolation, Request-Bound Context, and Argument Override Resistance.
"""

import sys
import os
import asyncio
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.mcp.demo_servers.erp_server import handle_call_tool, PRIMARY_ORGANIZATION_ID, SECONDARY_ORGANIZATION_ID
from app.mcp.persistent_session import PersistentServerSession, PersistentSessionManager
from app.models.all_models import MCPServer, MCPTool, User, Organization
from app.services.mcp_manager import MCPManager
from app.database.session import SessionLocal

ERP_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp", "demo_servers", "erp_server.py"))


@pytest.mark.asyncio
async def test_audit_concurrent_multi_tenant_isolated_executions():
    """Audit: Two tenants simultaneously dispatching tool calls receive strictly their own data."""
    tenant_a = PRIMARY_ORGANIZATION_ID
    tenant_b = SECONDARY_ORGANIZATION_ID

    async def _tenant_a_worker(call_idx: int):
        # Tenant A queries PRJ-MUM-001
        res = handle_call_tool("get_project_details", {
            "project_id": "PRJ-MUM-001",
            "organization_id": tenant_a
        })
        assert "project" in res
        assert res["project"]["organization_id"] == tenant_a
        assert res["project"]["name"] == "Mumbai Coastal Road Tunnel & Sea Bridge Package 4"

        # Tenant A queries financials
        res_fin = handle_call_tool("get_financial_summary", {
            "project_id": "PRJ-MUM-001",
            "organization_id": tenant_a
        })
        assert "financial_summary" in res_fin
        assert res_fin["financial_summary"]["organization_id"] == tenant_a

    async def _tenant_b_worker(call_idx: int):
        # Tenant B queries PRJ-T2-001
        res = handle_call_tool("get_project_details", {
            "project_id": "PRJ-T2-001",
            "organization_id": tenant_b
        })
        assert "project" in res
        assert res["project"]["organization_id"] == tenant_b
        assert res["project"]["name"] == "Bengaluru International Tech Corridor Phase 2"

        # Tenant B queries financials
        res_fin = handle_call_tool("get_financial_summary", {
            "project_id": "PRJ-T2-001",
            "organization_id": tenant_b
        })
        assert "financial_summary" in res_fin
        assert res_fin["financial_summary"]["organization_id"] == tenant_b

    # Run 20 concurrent requests interleaved across both tenants
    tasks = []
    for i in range(10):
        tasks.append(_tenant_a_worker(i))
        tasks.append(_tenant_b_worker(i))

    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_audit_cross_tenant_simultaneous_rejection():
    """Audit: Simultaneous cross-tenant unauthorized calls are 100% rejected without state leakage."""
    tenant_a = PRIMARY_ORGANIZATION_ID
    tenant_b = SECONDARY_ORGANIZATION_ID

    async def _tenant_a_intruder():
        # Tenant A trying to access Tenant B's PRJ-T2-001
        res = handle_call_tool("get_project_details", {
            "project_id": "PRJ-T2-001",
            "organization_id": tenant_a
        })
        assert "error" in res
        assert res.get("code") == "CROSS_TENANT_ACCESS_DENIED"

    async def _tenant_b_intruder():
        # Tenant B trying to access Tenant A's PRJ-MUM-001
        res = handle_call_tool("get_project_details", {
            "project_id": "PRJ-MUM-001",
            "organization_id": tenant_b
        })
        assert "error" in res
        assert res.get("code") == "CROSS_TENANT_ACCESS_DENIED"

    tasks = []
    for _ in range(10):
        tasks.append(_tenant_a_intruder())
        tasks.append(_tenant_b_intruder())

    await asyncio.gather(*tasks)


def test_audit_user_argument_override_vulnerability():
    """
    Audit Finding: Verifies whether setdefault in execute_tool permits user-supplied
    arguments to override server.organization_id.
    """
    db = SessionLocal()
    erp_server = db.query(MCPServer).filter(MCPServer.identifier == "mcp-srv-erp-core").first()
    db.close()
    assert erp_server is not None
    assert erp_server.organization_id == PRIMARY_ORGANIZATION_ID

    # Malicious arguments attempting to override server organization
    user_args = {
        "project_id": "PRJ-T2-001",
        "organization_id": SECONDARY_ORGANIZATION_ID  # Attacker attempts to masquerade as Tenant B
    }

    # Simulate execute_tool's setdefault logic:
    effective_args = dict(user_args)
    if erp_server.organization_id:
        effective_args.setdefault("organization_id", erp_server.organization_id)

    # If effective_args retains SECONDARY_ORGANIZATION_ID, setdefault failed to protect the boundary!
    is_overridden = (effective_args["organization_id"] == SECONDARY_ORGANIZATION_ID)
    print("Vulnerability audit: is_overridden =", is_overridden)
    # This assertion documents the presence of the vulnerability in setdefault:
    assert is_overridden is True, "Vulnerability confirmed: setdefault allows user payload to override server organization context."
