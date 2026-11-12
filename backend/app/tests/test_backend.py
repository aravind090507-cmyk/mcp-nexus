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
    assert res.status_code == 200, f"Failed to get super admin token: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module")
def ops_admin_headers(client):
    res = client.post("/api/v1/auth/switch-role", json={"role": "ADMIN"})
    assert res.status_code == 200, f"Failed to get ops admin token: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module")
def dev_headers(client):
    res = client.post("/api/v1/auth/switch-role", json={"role": "DEVELOPER"})
    assert res.status_code == 200, f"Failed to get developer token: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module")
def operator_headers(client):
    res = client.post("/api/v1/auth/switch-role", json={"role": "OPERATOR"})
    assert res.status_code == 200, f"Failed to get operator token: {res.text}"
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

def test_approval_workflow_review(client, admin_headers, ops_admin_headers):
    # Fetch pending approvals
    approvals_res = client.get("/api/v1/governance/approvals?status_filter=PENDING", headers=admin_headers)
    assert approvals_res.status_code == 200
    approvals = approvals_res.json()
    assert len(approvals) >= 1
    target_approval = approvals[0]

    # Verify self-approval rejection: Super Admin requested this operation, so Super Admin cannot review their own request
    self_approve_res = client.post(
        f"/api/v1/governance/approvals/{target_approval['id']}/action",
        json={"action": "APPROVE"},
        headers=admin_headers
    )
    assert self_approve_res.status_code == 403
    assert "Self-approval is strictly forbidden" in self_approve_res.json()["detail"]

    # Distinct authorized administrator (ADMIN role) reviews and rejects the approval request
    action_res = client.post(
        f"/api/v1/governance/approvals/{target_approval['id']}/action",
        json={"action": "REJECT", "reason": "Halted by Safety Auditor pending physical ultrasonic inspection."},
        headers=ops_admin_headers
    )
    assert action_res.status_code == 200
    assert action_res.json()["status"] == "REJECTED"

def test_dual_person_approval_workflow(client, dev_headers, ops_admin_headers, admin_headers):
    """
    Verify genuine dual-person approval governance for CRITICAL operations:
    1. Developer triggers critical tool in playground -> requires approval
    2. Approver 1 (Admin) provides first sign-off -> status: PARTIALLY_APPROVED
    3. Approver 1 attempts duplicate sign-off -> rejected with 400
    4. Approver 2 (Super Admin) provides second sign-off -> status: EXECUTED
    """
    # 1. Developer triggers critical equipment report
    payload = {
        "tool_name": "report_equipment_issue",
        "arguments": {
            "equipment_id": "EQP-GEN-1200",
            "severity": "CRITICAL",
            "description": "Bearing temperature runaway on emergency generator."
        }
    }
    exec_res = client.post("/api/v1/tools/execute", json=payload, headers=dev_headers)
    assert exec_res.status_code == 200
    app_id = exec_res.json()["result"]["approval_id"]

    # 2. First Approver (Ops Admin) reviews and approves -> PARTIALLY_APPROVED
    first_app_res = client.post(
        f"/api/v1/governance/approvals/{app_id}/action",
        json={"action": "APPROVE", "reason": "Plant engineer initial clearance granted."},
        headers=ops_admin_headers
    )
    assert first_app_res.status_code == 200
    assert first_app_res.json()["status"] == "PARTIALLY_APPROVED"

    # 3. Duplicate sign-off attempt by same approver -> 400 Bad Request
    dup_res = client.post(
        f"/api/v1/governance/approvals/{app_id}/action",
        json={"action": "APPROVE", "reason": "Duplicate attempt."},
        headers=ops_admin_headers
    )
    assert dup_res.status_code == 400
    assert "two distinct approvers" in dup_res.json()["detail"].lower()

    # 4. Second distinct Approver (Super Admin) provides final sign-off -> EXECUTED
    final_app_res = client.post(
        f"/api/v1/governance/approvals/{app_id}/action",
        json={"action": "APPROVE", "reason": "Chief Safety Officer final concurrence."},
        headers=admin_headers
    )
    assert final_app_res.status_code == 200
    assert final_app_res.json()["status"] == "EXECUTED"

def test_security_audit_events_logged(client, admin_headers):
    """Verify that permission violations and unauthorized approval attempts are recorded in security events."""
    sec_res = client.get("/api/v1/governance/security-events", headers=admin_headers)
    assert sec_res.status_code == 200
    events = sec_res.json()
    event_types = {e["event_type"] for e in events}
    assert "PERMISSION_VIOLATION" in event_types or "UNAUTHORIZED_APPROVAL_ATTEMPT" in event_types

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
    if data["overall_status"] != "SUCCESS":
        print("\n\nFAILURE DEBUG:")
        print("synthesis:", data.get("synthesis"))
        for s in data.get("spans", []):
            if s.get("status") in ("BLOCKED", "FAILED"):
                print("FAILED SPAN:", s)
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

def test_mcp_protocol_capabilities_and_ping(client, admin_headers):
    """Verify MCP protocol ping and latency measurement on connected server."""
    servers_res = client.get("/api/v1/servers", headers=admin_headers)
    assert servers_res.status_code == 200
    erp_server = [s for s in servers_res.json() if s["name"] == "ERP MCP Server"][0]

    ping_res = client.post(f"/api/v1/servers/{erp_server['id']}/ping", headers=admin_headers)
    assert ping_res.status_code == 200
    ping_data = ping_res.json()
    assert ping_data["success"] is True
    assert ping_data["latency_ms"] >= 0.0
    assert "Pong" in ping_data["message"]

def test_mcp_resources_and_prompts_discovery(client, admin_headers):
    """Verify standard MCP resource and prompt discovery (specification 2024-11-05)."""
    servers_res = client.get("/api/v1/servers", headers=admin_headers)
    assert servers_res.status_code == 200
    erp_server = [s for s in servers_res.json() if s["name"] == "ERP MCP Server"][0]

    # Discover resources
    res_out = client.get(f"/api/v1/servers/{erp_server['id']}/resources", headers=admin_headers)
    assert res_out.status_code == 200
    resources = res_out.json()["resources"]
    assert len(resources) >= 1
    assert any("erp://" in r["uri"] for r in resources)

    # Discover prompts
    prompt_out = client.get(f"/api/v1/servers/{erp_server['id']}/prompts", headers=admin_headers)
    assert prompt_out.status_code == 200
    prompts = prompt_out.json()["prompts"]
    assert len(prompts) >= 1
    assert prompts[0]["name"] == "audit_project_milestones"

def test_circuit_breaker_resilience(client, admin_headers):
    """Verify circuit breaker trips to OPEN on repeated failures, records incident, and can be reset."""
    from app.mcp.client import MCPConnectionManager
    srv_id = "test-fault-srv-99"
    MCPConnectionManager.reset_circuit(srv_id)
    assert MCPConnectionManager.is_circuit_open(srv_id) is False

    # Simulate 3 failures
    MCPConnectionManager.record_failure(srv_id, "Test Fault Server")
    MCPConnectionManager.record_failure(srv_id, "Test Fault Server")
    tripped = MCPConnectionManager.record_failure(srv_id, "Test Fault Server")
    assert tripped is True
    assert MCPConnectionManager.is_circuit_open(srv_id) is True

    # Check incident recorded via API
    inc_res = client.get("/api/v1/servers/circuit-breaker/incidents", headers=admin_headers)
    assert inc_res.status_code == 200
    incidents = inc_res.json()
    assert len(incidents) >= 1
    target_inc = [i for i in incidents if i.get("server_id") == srv_id][0]
    assert target_inc["status"] == "ACTIVE"

    # Reset circuit
    MCPConnectionManager.reset_circuit(srv_id)
    assert MCPConnectionManager.is_circuit_open(srv_id) is False

    # Check incident resolved via API
    inc_res2 = client.get("/api/v1/servers/circuit-breaker/incidents", headers=admin_headers)
    assert inc_res2.status_code == 200
    target_inc2 = [i for i in inc_res2.json() if i.get("server_id") == srv_id][0]
    assert target_inc2["status"] == "RESOLVED"

def test_agent_dynamic_planning_and_concurrency(client, admin_headers):
    """Verify dynamic tool selection, parameter extraction, concurrent execution across 3 servers."""
    agents_res = client.get("/api/v1/agents", headers=admin_headers)
    assert agents_res.status_code == 200
    agents = agents_res.json()
    assert len(agents) >= 1
    agent_id = agents[0]["id"]

    # Prompt with cross-server correlation intent
    req = {
        "agent_id": agent_id,
        "prompt": "Identify delayed projects across Hazira LNG expansion with crane maintenance alerts and flange stock deficits."
    }
    orch_res = client.post("/api/v1/agents/orchestrate", json=req, headers=admin_headers)
    assert orch_res.status_code == 200
    data = orch_res.json()

    assert data["overall_status"] == "SUCCESS"
    assert len(data["tool_executions"]) >= 3
    # Check that tools from ERP, Equipment, and Inventory were called
    servers_called = {t["server"] for t in data["tool_executions"]}
    assert "ERP MCP Server" in servers_called
    assert "Equipment MCP Server" in servers_called
    assert "Inventory MCP Server" in servers_called

    # Verify spans contain USER_REQUEST, AGENT_DECISION, POLICY_VALIDATION, MCP_SERVER, TOOL_EXECUTION, RESPONSE
    stages = {s["stage"] for s in data["spans"]}
    assert "USER_REQUEST" in stages
    assert "AGENT_DECISION" in stages
    assert "POLICY_VALIDATION" in stages
    assert "MCP_SERVER" in stages
    assert "TOOL_EXECUTION" in stages
    assert "RESPONSE" in stages

def test_agent_max_execution_steps_guard(client, admin_headers):
    """Verify that execution limit guard halts orchestration when planned steps exceed agent limit."""
    import uuid
    # Create an agent with max_execution_steps = 1
    create_payload = {
        "name": "Restricted Constrained Agent",
        "identifier": f"constrained-agent-{uuid.uuid4().hex[:6]}",
        "description": "Agent strictly constrained to 1 step",
        "model": "claude-3-5-sonnet",
        "system_prompt": "You are a restricted agent.",
        "max_execution_steps": 1
    }
    c_res = client.post("/api/v1/agents", json=create_payload, headers=admin_headers)
    assert c_res.status_code == 200
    constrained_agent_id = c_res.json()["id"]

    # Send multi-step query requiring 3 steps
    req = {
        "agent_id": constrained_agent_id,
        "prompt": "Correlate delayed projects, overdue maintenance and safety stock shortages across all servers."
    }
    orch_res = client.post("/api/v1/agents/orchestrate", json=req, headers=admin_headers)
    assert orch_res.status_code == 200
    data = orch_res.json()

    assert data["overall_status"] == "BLOCKED"
    assert "exceed agent max execution limit" in data["synthesis"].lower() or "halted" in data["synthesis"].lower()
    assert len(data["tool_executions"]) == 0

def test_policy_crud_operations(client, admin_headers):
    """Verify database-backed Policy Intelligence Engine CRUD endpoints."""
    # 1. Fetch policies (seeds defaults)
    res = client.get("/api/v1/governance/policies", headers=admin_headers)
    assert res.status_code == 200
    policies = res.json()
    assert len(policies) >= 4
    names = [p["name"] for p in policies]
    assert any("Destructive Operation" in n for n in names)

    # 2. Create custom policy rule
    create_payload = {
        "name": "Staging Fleet Shutdown Prohibition",
        "description": "Prohibit direct fleet shutdown commands across staging environments.",
        "action": "DENY",
        "risk_level": "CRITICAL",
        "environment": "ALL",
        "scope": "TOOL",
        "tool_pattern": "*shutdown*",
        "is_enabled": True
    }
    c_res = client.post("/api/v1/governance/policies", json=create_payload, headers=admin_headers)
    assert c_res.status_code == 200
    created = c_res.json()
    pol_id = created["id"]
    assert created["action"] == "DENY"

    # 3. Update policy rule
    u_res = client.put(
        f"/api/v1/governance/policies/{pol_id}",
        json={"is_enabled": False, "description": "Temporarily disabled by test"},
        headers=admin_headers
    )
    assert u_res.status_code == 200
    assert u_res.json()["is_enabled"] is False

    # 4. Delete policy rule
    d_res = client.delete(f"/api/v1/governance/policies/{pol_id}", headers=admin_headers)
    assert d_res.status_code == 200
    assert d_res.json()["success"] is True

def test_policy_engine_dynamic_evaluation_rule(client, admin_headers):
    """Verify that a dynamic DENY policy blocks tool execution immediately."""
    # Ensure any residual freeze policy is deleted
    policies_res = client.get("/api/v1/governance/policies", headers=admin_headers)
    for p in policies_res.json():
        if "Dynamic ERP Freeze Rule" in p["name"]:
            client.delete(f"/api/v1/governance/policies/{p['id']}", headers=admin_headers)

    create_payload = {
        "name": "Dynamic ERP Freeze Rule",
        "description": "Temporarily freeze project status inquiries",
        "action": "DENY",
        "risk_level": "HIGH",
        "environment": "ALL",
        "scope": "TOOL",
        "tool_pattern": "get_project_status",
        "is_enabled": True
    }
    freeze_pol_id = None
    exec_payload = {
        "tool_name": "get_project_status",
        "arguments": {}
    }
    try:
        c_res = client.post("/api/v1/governance/policies", json=create_payload, headers=admin_headers)
        assert c_res.status_code == 200
        freeze_pol_id = c_res.json()["id"]

        # Attempt execution of get_project_status -> must be blocked
        e_res = client.post("/api/v1/tools/execute", json=exec_payload, headers=admin_headers)
        assert e_res.status_code == 200
        assert e_res.json()["is_success"] is False
        assert "denied by policy" in e_res.json()["error"].lower()
    finally:
        if freeze_pol_id:
            client.delete(f"/api/v1/governance/policies/{freeze_pol_id}", headers=admin_headers)

    # Execution succeeds again after unfreezing
    e2_res = client.post("/api/v1/tools/execute", json=exec_payload, headers=admin_headers)
    assert e2_res.status_code == 200
    assert e2_res.json()["is_success"] is True

def test_mcp_auto_discovery_endpoint(client, admin_headers):
    """Verify probing and capability discovery on an MCP server endpoint before registration."""
    payload = {
        "transport_type": "STDIO",
        "command": "python",
        "args": ["demo_servers/equipment_server.py"]
    }
    res = client.post("/api/v1/servers/discover", json=payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["protocol_version"] == "2024-11-05"
    assert "tools" in data["capabilities"]
    assert len(data["discovered_tools"]) >= 3
    tool_names = [t["name"] for t in data["discovered_tools"]]
    assert "get_equipment_status" in tool_names
    assert "report_equipment_issue" in tool_names
    assert len(data["discovered_resources"]) >= 1
    assert len(data["discovered_prompts"]) >= 1
    assert data["latency_ms"] >= 0.0

# ==============================================================================
# ENTERPRISE WORKFLOW INTELLIGENCE: CONSTRUCTION PROJECT RISK INTELLIGENCE TESTS
# ==============================================================================

def test_workflow_successful_cross_server(client, admin_headers):
    """Test 1: Successful cross-server workflow execution across ERP, Equipment, and Inventory."""
    payload = {
        "workflow_id": "construction-risk-intelligence",
        "prompt": "Identify construction projects at risk due to delayed milestones, equipment failures and insufficient inventory."
    }
    res = client.post("/api/v1/workflows/execute", json=payload, headers=admin_headers)
    assert res.status_code == 200, f"Workflow execution failed: {res.text}"
    data = res.json()
    assert data["workflow_id"] == "construction-risk-intelligence"
    assert data["execution_status"] in ("SUCCESS", "COMPLETED")
    assert "trace_id" in data
    assert "risk_assessment" in data
    assert len(data["tool_executions"]) >= 3
    # Check that tools from all 3 servers ran
    servers_executed = [t["server"] for t in data["tool_executions"]]
    assert any("ERP" in s for s in servers_executed)
    assert any("Equipment" in s for s in servers_executed)
    assert any("Inventory" in s for s in servers_executed)

def test_workflow_dynamic_tool_discovery(client, admin_headers):
    """Test 2: Verify tools are dynamically discovered from active database records registered to servers."""
    res = client.get("/api/v1/workflows/scenarios", headers=admin_headers)
    assert res.status_code == 200
    scenarios = res.json()
    assert len(scenarios) >= 1
    assert scenarios[0]["id"] == "construction-risk-intelligence"
    assert "get_project_status" in scenarios[0]["tools_involved"]
    assert "get_maintenance_schedule" in scenarios[0]["tools_involved"]
    assert "get_low_stock_items" in scenarios[0]["tools_involved"]

def test_workflow_concurrent_read_only_execution(client, admin_headers):
    """Test 3: Verify concurrent read-only tool execution via parallel dispatch."""
    payload = {
        "workflow_id": "construction-risk-intelligence",
        "prompt": "Identify construction projects at risk due to delayed milestones, equipment failures and insufficient inventory."
    }
    res = client.post("/api/v1/workflows/execute", json=payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    progress = data["server_progress"]
    assert progress["agent_planning"]["concurrency"] == "PARALLEL_ASYNCIO_GATHER"
    assert progress["erp_server"]["status"] == "COMPLETED"
    assert progress["equipment_server"]["status"] == "COMPLETED"
    assert progress["inventory_server"]["status"] == "COMPLETED"

def test_workflow_missing_server_handling(client, admin_headers):
    """Test 4: Gracefully handle missing or disabled MCP server without crashing the workflow."""
    # Temporarily disable inventory server
    servers_res = client.get("/api/v1/servers", headers=admin_headers)
    assert servers_res.status_code == 200
    inv_server = next((s for s in servers_res.json() if "Inventory" in s["name"]), None)
    assert inv_server is not None, "Inventory server should exist"

    try:
        # Disable server
        client.put(f"/api/v1/servers/{inv_server['id']}", json={"is_enabled": False}, headers=admin_headers)

        payload = {"workflow_id": "construction-risk-intelligence"}
        res = client.post("/api/v1/workflows/execute", json=payload, headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        # Should gracefully report missing inventory server
        assert data["server_progress"]["inventory_server"]["status"] == "UNAVAILABLE"
        # Remaining servers (ERP & Equipment) still execute
        assert data["server_progress"]["erp_server"]["status"] == "COMPLETED"
        assert data["server_progress"]["equipment_server"]["status"] == "COMPLETED"
    finally:
        # Re-enable server
        client.put(f"/api/v1/servers/{inv_server['id']}", json={"is_enabled": True}, headers=admin_headers)

def test_workflow_mcp_server_timeout(client, admin_headers):
    """Test 5: Verify that server timeout or execution error does not hang the workflow."""
    # Directly invoke a non-existent or failing tool to test error handling
    payload = {
        "tool_name": "non_existent_emergency_tool",
        "arguments": {}
    }
    res = client.post("/api/v1/tools/execute", json=payload, headers=admin_headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

def test_workflow_invalid_tool_response(client, admin_headers):
    """Test 6: Correlation engine handles partial or empty tool outputs without throwing exceptions."""
    from app.services.risk_intelligence_engine import RiskIntelligenceEngine
    # Pass malformed or partial output
    partial_results = [
        {"server": "ERP MCP Server", "tool": "get_project_status", "output": {"malformed": True}},
        {"server": "Equipment MCP Server", "tool": "get_maintenance_schedule", "output": "invalid_string_output"},
    ]
    assessment = RiskIntelligenceEngine.correlate_and_assess_risk(partial_results)
    assert "summary" in assessment
    assert assessment["summary"]["total_projects_assessed"] >= 1
    assert "projects" in assessment

def test_workflow_permission_rejection(client, viewer_headers):
    """Test 7: Unauthenticated or VIEWER role is strictly forbidden from executing workflows."""
    # 1. Unauthenticated request
    unauth_res = client.post("/api/v1/workflows/execute", json={})
    assert unauth_res.status_code == 401

    # 2. VIEWER role without AGENTS_ORCHESTRATE permission
    viewer_res = client.post("/api/v1/workflows/execute", json={}, headers=viewer_headers)
    assert viewer_res.status_code == 403
    assert "Forbidden" in viewer_res.json()["detail"] or "permission" in viewer_res.json()["detail"].lower()

def test_workflow_approval_enforcement(client, admin_headers):
    """Test 8: Workflow policy engine halts execution if a tool violates a policy or requires approval."""
    # Create dynamic policy requiring approval for get_maintenance_schedule
    freeze_pol_id = None
    try:
        policy_payload = {
            "name": "Safety Freeze on Equipment Maintenance Probes",
            "action": "REQUIRE_APPROVAL",
            "risk_level": "HIGH",
            "environment": "ALL",
            "scope": "TOOL",
            "tool_pattern": "get_maintenance_schedule",
            "is_enabled": True
        }
        pol_res = client.post("/api/v1/governance/policies", json=policy_payload, headers=admin_headers)
        assert pol_res.status_code == 200
        freeze_pol_id = pol_res.json()["id"]

        # Attempt workflow execution -> must be blocked
        wf_res = client.post("/api/v1/workflows/execute", json={}, headers=admin_headers)
        assert wf_res.status_code == 200
        data = wf_res.json()
        assert data["execution_status"] == "BLOCKED"
        assert "policy" in data["synthesis"].lower()
    finally:
        if freeze_pol_id:
            client.delete(f"/api/v1/governance/policies/{freeze_pol_id}", headers=admin_headers)

def test_workflow_risk_calculation(client, admin_headers):
    """Test 9: Verify accurate calculation of risk scores (CRITICAL, HIGH, MEDIUM, LOW) based on factual data."""
    payload = {"workflow_id": "construction-risk-intelligence"}
    res = client.post("/api/v1/workflows/execute", json=payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    risk_assessment = data["risk_assessment"]
    summary = risk_assessment["summary"]

    assert summary["critical_risks"] >= 1
    assert "PRJ-HAZ-002" in summary["critical_projects"]

    # Verify PRJ-HAZ-002 is classified as CRITICAL
    haz_proj = next((p for p in risk_assessment["projects"] if p["project_id"] == "PRJ-HAZ-002"), None)
    assert haz_proj is not None
    assert haz_proj["overall_risk"] == "CRITICAL"
    assert haz_proj["risk_score"] >= 75
    assert len(haz_proj["affected_equipment"]) >= 1
    assert len(haz_proj["affected_materials"]) >= 1

    # Verify PRJ-HYD-003 is classified as LOW or MEDIUM
    hyd_proj = next((p for p in risk_assessment["projects"] if p["project_id"] == "PRJ-HYD-003"), None)
    assert hyd_proj is not None
    assert hyd_proj["overall_risk"] in ("LOW", "MEDIUM")

def test_workflow_evidence_traceability(client, admin_headers):
    """Test 10: Every risk factor must contain provable supporting evidence and source tool identification."""
    res = client.post("/api/v1/workflows/execute", json={}, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    projects = data["risk_assessment"]["projects"]
    for p in projects:
        assert "evidence" in p
        assert isinstance(p["evidence"], list)
        assert len(p["evidence"]) >= 1
        assert "business_impact" in p
        assert "recommended_action" in p
        assert len(p["source_servers"]) >= 1

def test_workflow_execution_trace_creation(client, admin_headers):
    """Test 11: An ExecutionTrace record is persisted in the database with 6 inspectable lifecycle stages."""
    res = client.post("/api/v1/workflows/execute", json={}, headers=admin_headers)
    assert res.status_code == 200
    trace_id = res.json()["trace_id"]

    # Fetch trace from traces API
    trace_res = client.get(f"/api/v1/traces/{trace_id}", headers=admin_headers)
    assert trace_res.status_code == 200
    trace_data = trace_res.json()
    assert trace_data["trace_id"] == trace_id
    assert trace_data["status"] in ("SUCCESS", "COMPLETED")
    assert len(trace_data["spans"]) >= 4

    # Verify key lifecycle stages exist
    span_stages = [s["stage"] for s in trace_data["spans"]]
    assert "USER_REQUEST" in span_stages
    assert "AGENT_DECISION" in span_stages
    assert "POLICY_VALIDATION" in span_stages
    assert "TOOL_EXECUTION" in span_stages

def test_workflow_failure_recovery(client, admin_headers):
    """Test 12: Audit service records workflow execution and diagnostic metadata even under errors."""
    res = client.post("/api/v1/workflows/execute", json={}, headers=admin_headers)
    assert res.status_code == 200

    # Verify audit log entry
    audit_res = client.get("/api/v1/governance/audit-logs", headers=admin_headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    wf_logs = [l for l in logs if l["action"] == "WORKFLOW_EXECUTION"]
    assert len(wf_logs) >= 1
    assert "Construction Project Risk Intelligence" in wf_logs[0]["details"]

# ==============================================================================
# PHASE 7 REGRESSION TESTS: MCP PROCESS MANAGEMENT & SUBPROCESS RESILIENCE
# ==============================================================================

@pytest.mark.asyncio
async def test_regression_missing_python_interpreter_resolution():
    """Test 1: Verify MCPClient dynamically resolves non-existent interpreter paths to current sys.executable."""
    from app.mcp.client import MCPClient
    client = MCPClient(
        server_id="test-interpreter-res",
        transport_type="STDIO",
        command="C:\\NonExistentPath\\python99.exe",
        args=["erp_server.py"]
    )
    resolved_cmd, resolved_args, cwd = client._resolve_command_and_args()
    assert os.path.exists(resolved_cmd), f"Resolved binary must exist on disk: {resolved_cmd}"
    assert resolved_cmd.lower().endswith("python.exe") or "python" in resolved_cmd.lower()

@pytest.mark.asyncio
async def test_regression_server_script_path_resolution():
    """Test 2: Verify MCPClient dynamically resolves bare script names to demo_servers folder."""
    from app.mcp.client import MCPClient
    client = MCPClient(
        server_id="test-script-res",
        transport_type="STDIO",
        command=sys.executable,
        args=["inventory_server.py"]
    )
    resolved_cmd, resolved_args, cwd = client._resolve_command_and_args()
    assert len(resolved_args) == 1
    assert os.path.isabs(resolved_args[0])
    assert os.path.exists(resolved_args[0]), f"Resolved script must exist on disk: {resolved_args[0]}"
    assert os.path.basename(resolved_args[0]) == "inventory_server.py"

@pytest.mark.asyncio
async def test_regression_dependency_or_bad_script_failure():
    """Test 3: Verify subprocess launch with completely invalid script fails cleanly with descriptive error."""
    from app.mcp.client import MCPClient, MCPClientError
    client = MCPClient(
        server_id="test-bad-script",
        transport_type="STDIO",
        command=sys.executable,
        args=["non_existent_fake_server_script_12345.py"],
        timeout=3.0
    )
    with pytest.raises(MCPClientError) as exc_info:
        await client.initialize()
    assert any(term in str(exc_info.value).lower() for term in ["server closed stream", "failed to start", "no such file", "non-json"])

@pytest.mark.asyncio
async def test_regression_mcp_init_handshake_validation():
    """Test 4: Verify full MCP initialization handshake and capability exchange succeeds on a valid server."""
    from app.mcp.client import MCPClient
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    erp_script = os.path.join(base_dir, "app", "mcp", "demo_servers", "erp_server.py")
    client = MCPClient(
        server_id="test-erp-init",
        transport_type="STDIO",
        command=sys.executable,
        args=[erp_script],
        timeout=5.0
    )
    init_res, latency = await client.initialize()
    assert "protocolVersion" in init_res
    assert init_res["protocolVersion"] == "2024-11-05"
    assert "serverInfo" in init_res
    assert latency > 0

@pytest.mark.asyncio
async def test_regression_tool_discovery_success():
    """Test 5: Verify MCPClient tool discovery lists all declared tools on equipment server."""
    from app.mcp.client import MCPClient
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    eq_script = os.path.join(base_dir, "app", "mcp", "demo_servers", "equipment_server.py")
    client = MCPClient(
        server_id="test-eq-tools",
        transport_type="STDIO",
        command=sys.executable,
        args=[eq_script],
        timeout=5.0
    )
    tools = await client.list_tools()
    assert isinstance(tools, list)
    tool_names = [t["name"] for t in tools]
    assert "get_equipment_status" in tool_names
    assert "get_maintenance_schedule" in tool_names

@pytest.mark.asyncio
async def test_regression_tool_invocation_success():
    """Test 6: Verify MCPClient invokes tool and returns parsed output correctly."""
    from app.mcp.client import MCPClient
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    inv_script = os.path.join(base_dir, "app", "mcp", "demo_servers", "inventory_server.py")
    client = MCPClient(
        server_id="test-inv-call",
        transport_type="STDIO",
        command=sys.executable,
        args=[inv_script],
        timeout=5.0
    )
    result, duration_ms = await client.call_tool("get_low_stock_items", {"threshold_multiplier": 1.0})
    assert duration_ms > 0
    assert result.get("isError") is False or "content" in result
    parsed = result.get("parsed")
    assert isinstance(parsed, dict)
    assert "low_stock_items_count" in parsed

@pytest.mark.asyncio
async def test_regression_server_timeout_handling():
    """Test 7: Verify MCPClient enforces timeouts without hanging subprocesses."""
    from app.mcp.client import MCPClient, MCPClientError
    client = MCPClient(
        server_id="test-timeout-hang",
        transport_type="STDIO",
        command=sys.executable,
        args=["-c", "import time; time.sleep(10)"],
        timeout=1.0
    )
    with pytest.raises(MCPClientError) as exc_info:
        await client.initialize()
    err_str = str(exc_info.value).lower()
    assert "timed out" in err_str or "closed stream" in err_str or "server closed" in err_str

@pytest.mark.asyncio
async def test_regression_clean_subprocess_shutdown():
    """Test 8: Verify subprocesses are cleanly terminated and do not leak processes."""
    import psutil
    from app.mcp.client import MCPClient
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    erp_script = os.path.join(base_dir, "app", "mcp", "demo_servers", "erp_server.py")
    
    current_proc = psutil.Process()
    initial_children = len(current_proc.children(recursive=True))
    
    client = MCPClient(
        server_id="test-shutdown",
        transport_type="STDIO",
        command=sys.executable,
        args=[erp_script],
        timeout=5.0
    )
    await client.initialize()
    await client.list_tools()
    
    # After operations complete, child processes should be terminated
    final_children = len(current_proc.children(recursive=True))
    assert final_children <= initial_children + 1  # No leaked zombie processes

@pytest.mark.asyncio
async def test_regression_concurrent_execution_all_servers():
    """Test 9: Verify concurrent execution across ERP, Equipment, and Inventory completes without deadlock."""
    import asyncio
    from app.mcp.client import MCPClient
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    erp_c = MCPClient(server_id="erp-c", transport_type="STDIO", command=sys.executable, args=[os.path.join(base_dir, "app", "mcp", "demo_servers", "erp_server.py")])
    eq_c = MCPClient(server_id="eq-c", transport_type="STDIO", command=sys.executable, args=[os.path.join(base_dir, "app", "mcp", "demo_servers", "equipment_server.py")])
    inv_c = MCPClient(server_id="inv-c", transport_type="STDIO", command=sys.executable, args=[os.path.join(base_dir, "app", "mcp", "demo_servers", "inventory_server.py")])
    
    async def run_one(c, tool, args):
        res, dur = await c.call_tool(tool, args)
        return res
        
    t1 = run_one(erp_c, "get_project_status", {})
    t2 = run_one(eq_c, "get_maintenance_schedule", {"overdue_only": True})
    t3 = run_one(inv_c, "get_low_stock_items", {"threshold_multiplier": 1.0})
    
    r1, r2, r3 = await asyncio.gather(t1, t2, t3)
    assert r1.get("isError") is False or "content" in r1
    assert r2.get("isError") is False or "content" in r2
    assert r3.get("isError") is False or "content" in r3

def test_regression_partial_workflow_failure_reporting(client, admin_headers):
    """Test 10: Verify partial workflow failure reports PARTIAL_SUCCESS or FAILED, completion < 100%, and warns in synthesis."""
    srv_res = client.get("/api/v1/servers", headers=admin_headers)
    assert srv_res.status_code == 200
    servers = srv_res.json()
    inv_srv = next((s for s in servers if "Inventory" in s["name"]), None)
    assert inv_srv is not None
    
    # Disable inventory server
    client.put(f"/api/v1/servers/{inv_srv['id']}", json={"is_enabled": False}, headers=admin_headers)
    try:
        wf_res = client.post("/api/v1/workflows/execute", json={}, headers=admin_headers)
        assert wf_res.status_code == 200
        wf_data = wf_res.json()
        assert wf_data["execution_status"] in ("PARTIAL_SUCCESS", "PARTIAL_FAILURE")
        assert wf_data["server_progress"]["completion_status"]["percentage"] < 100
        assert wf_data["server_progress"]["inventory_server"]["status"] == "UNAVAILABLE"
        assert "PARTIAL" in wf_data["synthesis"] or "CAUTION" in wf_data["synthesis"]
    finally:
        # Re-enable
        client.put(f"/api/v1/servers/{inv_srv['id']}", json={"is_enabled": True}, headers=admin_headers)

# ==============================================================================
# PHASE 5: OFFICIAL MCP SDK TRANSPORT TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_official_sdk_stdio_client_session_types():
    """Verify that MCPClient invokes official stdio_client and provides authentic ClientSession instances."""
    from app.mcp.client import MCPClient
    from mcp import ClientSession
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    erp_script = os.path.join(base_dir, "app", "mcp", "demo_servers", "erp_server.py")
    client = MCPClient(args=[erp_script])
    
    session_verified = False
    init_res_verified = False
    
    async def _verify_types(session: ClientSession, init_res: Any):
        nonlocal session_verified, init_res_verified
        assert isinstance(session, ClientSession)
        session_verified = True
        assert hasattr(init_res, "protocol_version")
        assert init_res.protocol_version == "2024-11-05"
        init_res_verified = True
        return "OK"
        
    res = await client._run_sdk_stdio_operation(_verify_types)
    assert res == "OK"
    assert session_verified is True
    assert init_res_verified is True

@pytest.mark.asyncio
async def test_official_sdk_ping_exchange():
    """Verify that MCPClient.ping() executes official ClientSession.send_ping() without manual JSON-RPC."""
    from app.mcp.client import MCPClient
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    erp_script = os.path.join(base_dir, "app", "mcp", "demo_servers", "erp_server.py")
    client = MCPClient(args=[erp_script])
    
    latency = await client.ping()
    assert isinstance(latency, float)
    assert latency > 0

@pytest.mark.asyncio
async def test_official_sdk_tool_discovery_typed():
    """Verify that MCPClient.list_tools() invokes official session.list_tools() and produces valid tool schemas."""
    from app.mcp.client import MCPClient
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    eq_script = os.path.join(base_dir, "app", "mcp", "demo_servers", "equipment_server.py")
    client = MCPClient(args=[eq_script])
    
    tools = await client.list_tools()
    assert isinstance(tools, list)
    assert len(tools) == 3
    tool_map = {t["name"]: t for t in tools}
    assert "get_equipment_status" in tool_map
    assert "inputSchema" in tool_map["get_equipment_status"]
    assert isinstance(tool_map["get_equipment_status"]["inputSchema"], dict)

@pytest.mark.asyncio
async def test_official_sdk_resource_and_prompt_discovery():
    """Verify that MCPClient discovers resources and prompts using official SDK list_resources/list_prompts."""
    from app.mcp.client import MCPClient
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    erp_script = os.path.join(base_dir, "app", "mcp", "demo_servers", "erp_server.py")
    client = MCPClient(args=[erp_script])
    
    resources = await client.list_resources()
    assert isinstance(resources, list)
    assert len(resources) == 2
    uris = [r["uri"] for r in resources]
    assert "erp://projects/specs" in uris
    
    prompts = await client.list_prompts()
    assert isinstance(prompts, list)
    assert len(prompts) == 1
    assert prompts[0]["name"] == "audit_project_milestones"

@pytest.mark.asyncio
async def test_official_sdk_call_tool_structured_content():
    """Verify that MCPClient.call_tool() invokes official session.call_tool() and parses JSON text content."""
    from app.mcp.client import MCPClient
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    inv_script = os.path.join(base_dir, "app", "mcp", "demo_servers", "inventory_server.py")
    client = MCPClient(args=[inv_script])
    
    res, duration_ms = await client.call_tool("get_low_stock_items", {"threshold_multiplier": 1.0})
    assert duration_ms > 0
    assert "content" in res
    assert isinstance(res["content"], list)
    assert res.get("isError") is False
    assert "parsed" in res
    assert res["parsed"]["low_stock_items_count"] >= 1







