import sys
import os
import pytest
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def admin_headers(client):
    res = client.post("/api/v1/auth/switch-role", json={"role": "SUPER_ADMIN"})
    assert res.status_code == 200, f"Failed to get admin token: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module")
def viewer_headers(client):
    res = client.post("/api/v1/auth/switch-role", json={"role": "VIEWER"})
    assert res.status_code == 200, f"Failed to get viewer token: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_root(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["platform"] == "MCP NEXUS"
    assert data["status"] == "OPERATIONAL"

def test_auth_rejection_without_token(client):
    """Verify backend-enforced authentication: Unauthenticated requests are rejected with 401."""
    res_servers = client.get("/api/v1/servers")
    assert res_servers.status_code == 401

    res_tools = client.get("/api/v1/tools")
    assert res_tools.status_code == 401

    res_agents = client.get("/api/v1/agents")
    assert res_agents.status_code == 401

    res_metrics = client.get("/api/v1/metrics/command-center")
    assert res_metrics.status_code == 401

def test_role_switcher_token_generation(client):
    """Verify /auth/switch-role returns valid signed JWT tokens for all valid personas."""
    roles = ["SUPER_ADMIN", "ADMIN", "DEVELOPER", "OPERATOR", "VIEWER"]
    for role in roles:
        res = client.post("/api/v1/auth/switch-role", json={"role": role})
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["role"] == role

    # Test invalid role rejection
    res_invalid = client.post("/api/v1/auth/switch-role", json={"role": "INVALID_ROLE"})
    assert res_invalid.status_code == 400

def test_unauthorized_role_execution_forbidden(client, viewer_headers):
    """Verify backend-enforced RBAC: VIEWER persona cannot execute tools, alter configs, or register servers."""
    # Attempt tool execution as VIEWER
    exec_res = client.post("/api/v1/tools/execute", json={
        "tool_name": "get_project_details",
        "arguments": {"project_id": "PRJ-MUM-001"}
    }, headers=viewer_headers)
    assert exec_res.status_code == 403
    assert "Forbidden" in exec_res.json()["detail"] or "permission" in exec_res.json()["detail"].lower()

    # Attempt tool configuration update as VIEWER
    tools_res = client.get("/api/v1/tools", headers=viewer_headers)
    assert tools_res.status_code == 200
    tool_id = tools_res.json()[0]["id"]

    cfg_res = client.put(f"/api/v1/tools/{tool_id}/config", json={
        "risk_level": "LOW",
        "requires_approval": False
    }, headers=viewer_headers)
    assert cfg_res.status_code == 403

    # Attempt server registration as VIEWER
    srv_res = client.post("/api/v1/servers", json={
        "name": "Unauthorized Server",
        "identifier": "mcp-srv-unauth",
        "transport_type": "STDIO"
    }, headers=viewer_headers)
    assert srv_res.status_code == 403

def test_servers_and_tools_discovery(client, admin_headers):
    res = client.get("/api/v1/servers", headers=admin_headers)
    assert res.status_code == 200
    servers = res.json()
    assert len(servers) >= 3
    server_names = [s["name"] for s in servers]
    assert "ERP MCP Server" in server_names
    assert "Inventory MCP Server" in server_names
    assert "Equipment MCP Server" in server_names

    # Check tools discovered
    tools_res = client.get("/api/v1/tools", headers=admin_headers)
    assert tools_res.status_code == 200
    tools = tools_res.json()
    assert len(tools) >= 9
    tool_names = [t["name"] for t in tools]
    assert "get_project_details" in tool_names
    assert "get_inventory" in tool_names
    assert "get_equipment_status" in tool_names

def test_command_center_metrics(client, admin_headers):
    res = client.get("/api/v1/metrics/command-center", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "top_metrics" in data
    assert data["top_metrics"]["registered_servers"] >= 3
    assert "server_distribution" in data
    assert "infra_health" in data
    assert "activity_chart" in data
    assert len(data["activity_chart"]) > 0

def test_playground_tool_execution(client, admin_headers):
    # Ensure get_project_details is in standard execution state
    tools_res = client.get("/api/v1/tools", headers=admin_headers)
    assert tools_res.status_code == 200
    for t in tools_res.json():
        if t["name"] == "get_project_details":
            client.put(f"/api/v1/tools/{t['id']}/config", json={"risk_level": "LOW", "requires_approval": False}, headers=admin_headers)
            break

    payload = {
        "tool_name": "get_project_details",
        "arguments": {"project_id": "PRJ-MUM-001"}
    }
    res = client.post("/api/v1/tools/execute", json=payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_success"] is True
    assert "result" in data
    assert "project" in data["result"]
    assert data["result"]["project"]["name"] == "Mumbai Coastal Road Tunnel & Sea Bridge Package 4"

def test_sensitive_tool_approval_enforcement(client, admin_headers):
    # Destructive tool with CRITICAL severity must be halted and trigger approval requirement
    payload = {
        "tool_name": "report_equipment_issue",
        "arguments": {
            "equipment_id": "EQP-CRN-8800",
            "severity": "CRITICAL",
            "description": "Crack observed in boom lattice during 500t test lift."
        }
    }
    res = client.post("/api/v1/tools/execute", json=payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    # Should require approval
    assert data["is_success"] is False
    assert "Approval request" in data["error"] or "approval_required" in str(data["result"])

def test_approval_workflow_review(client, admin_headers):
    # Fetch pending approvals
    approvals_res = client.get("/api/v1/governance/approvals?status_filter=PENDING", headers=admin_headers)
    assert approvals_res.status_code == 200
    approvals = approvals_res.json()
    assert len(approvals) >= 1
    target_approval = approvals[0]

    # Reject the approval request
    action_res = client.post(
        f"/api/v1/governance/approvals/{target_approval['id']}/action",
        json={"action": "REJECT", "notes": "Halted by Safety Auditor pending physical ultrasonic inspection."},
        headers=admin_headers
    )
    assert action_res.status_code == 200
    assert action_res.json()["status"] == "REJECTED"

def test_tool_config_update(client, admin_headers):
    tools_res = client.get("/api/v1/tools", headers=admin_headers)
    assert tools_res.status_code == 200
    tool = tools_res.json()[0]
    orig_risk = tool["risk_level"]
    orig_appr = tool["requires_approval"]
    orig_desc = tool["description"]

    update_payload = {
        "risk_level": "HIGH",
        "requires_approval": True,
        "description": "Updated tool description with strict policy."
    }
    res = client.put(f"/api/v1/tools/{tool['id']}/config", json=update_payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] == "HIGH"
    assert data["requires_approval"] is True
    assert data["description"] == update_payload["description"]

    # Restore original configuration so subsequent test runs remain idempotent
    client.put(f"/api/v1/tools/{tool['id']}/config", json={
        "risk_level": orig_risk,
        "requires_approval": orig_appr,
        "description": orig_desc
    }, headers=admin_headers)

def test_mcp_server_failure_handling(client, admin_headers):
    """Verify that registering an MCP server with an invalid or failing command is handled safely."""
    import uuid
    uid = uuid.uuid4().hex[:6]
    payload = {
        "name": f"Faulty Server {uid}",
        "identifier": f"faulty-srv-{uid}",
        "description": "Server pointing to nonexistent binary to test fault tolerance",
        "transport_type": "STDIO",
        "command": "nonexistent_executable_binary_xyz",
        "args": []
    }
    res = client.post("/api/v1/servers", json=payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UNHEALTHY"

def test_agent_cross_server_orchestration(client, admin_headers):
    # Retrieve agent
    agents_res = client.get("/api/v1/agents", headers=admin_headers)
    assert agents_res.status_code == 200
    agents = agents_res.json()
    assert len(agents) >= 1
    atlas = agents[0]

    orch_payload = {
        "agent_id": atlas["id"],
        "prompt": "Find all projects with delayed equipment maintenance and insufficient inventory."
    }
    res = client.post("/api/v1/agents/orchestrate", json=orch_payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["overall_status"] == "SUCCESS"
    assert len(data["tool_executions"]) >= 3
    assert len(data["spans"]) >= 5
    assert "Hazira" in data["synthesis"] or "PRJ-HAZ-002" in data["synthesis"]

def test_infrastructure_topology(client, admin_headers):
    res = client.get("/api/v1/topology", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "edges" in data
    node_types = {n["type"] for n in data["nodes"]}
    assert "gatewayNode" in node_types
    assert "serverNode" in node_types
    assert "agentNode" in node_types
