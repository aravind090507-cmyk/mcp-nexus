# MCP NEXUS
### Enterprise AI Integration, Orchestration & Governance Platform
**Tagline:** CONNECT. ORCHESTRATE. GOVERN.  
**Audience:** Technical Architecture Showcase for Larsen & Toubro (L&T Heavy Civil IC & Enterprise AI)  
**System Version:** 2.0.0-Enterprise  

---

## Executive Summary

**MCP NEXUS** is a centralized enterprise control plane engineered to connect, orchestrate, and govern **Model Context Protocol (MCP)** servers, autonomous AI agents, enterprise systems of record, and operational tools.

Built from the ground up to reflect the information density of Linear, the operational intelligence aesthetic of Palantir Foundry, the infrastructure observability of Datadog, and the technical precision of Vercel, MCP NEXUS avoids superficial UI mockups and delivers a fully functional, protocol-compliant system.

```
                      +-----------------------------------+
                      |      ENTERPRISE CONSUMERS        |
                      |  (Desktop Control Room, Web App) |
                      +-----------------+-----------------+
                                        | HTTPS / REST (JWT Bearer: iss, aud)
                                        v
+---------------------------------------------------------------------------------------+
|                             MCP NEXUS CONTROL PLANE                                   |
|                                                                                       |
|   +-------------------+    +--------------------+    +----------------------------+   |
|   |  FastAPI Gateway  |<-->| RBAC & Auth Gate   |<-->|  Immutable Audit Vault     |   |
|   | (Servers, Tools,  |    | (SuperAdmin, Admin,|    | (PostgreSQL/SQLite,        |   |
|   |  Agents, Traces)  |    |  Dev, Op, Viewer)  |    |  SecurityEvent, AuditLogs) |   |
|   +---------+---------+    +---------+----------+    +--------------+-------------+   |
|             |                        |                              |                 |
|             v                        v                              v                 |
|   +-------------------------------------------------------------------------------+   |
|   |                   POLICY INTELLIGENCE ENGINE                                  |   |
|   |   - Database-backed dynamic security policies (SecurityPolicy table)          |   |
|   |   - Ranked Rule Evaluation: Exact (100) > Pattern (50) > Server (30) > All (10)|   |
|   |   - Deny-First Precedence (DENY > REQUIRE_APPROVAL > ALLOW)                   |   |
|   |   - Dual-Person Approval State Machine (Anti-Self Approval Enforced)          |   |
|   +------------------------------------+------------------------------------------+   |
|                                        |                                              |
|                                        v                                              |
|   +-------------------------------------------------------------------------------+   |
|   |                   AUTONOMOUS AGENT ORCHESTRATION ENGINE                       |   |
|   |   - Dynamic Tool Discovery & Ranked Schema Selector                           |   |
|   |   - Multi-Provider LLM Abstraction (Gemini, OpenAI, Anthropic, Deterministic) |   |
|   |   - Concurrent Safe Execution via asyncio.gather                              |   |
|   |   - Infinite Loop Guardrail (max_execution_steps enforcement)                 |   |
|   |   - 6-Stage Distributed Waterfall Trace Pipeline                              |   |
|   +------------------------------------+------------------------------------------+   |
|                                        |                                              |
|                                        v                                              |
|   +-------------------------------------------------------------------------------+   |
|   |                   PROTOCOL-AWARE MCP CONNECTION MANAGER                       |   |
|   |   - Official MCP Python SDK Compatibility (JSON-RPC 2.0 / 2024-11-05)         |   |
|   |   - Subprocess STDIO & Streamable HTTP / SSE Transports                       |   |
|   |   - Capability Negotiation, Tools, Resources & Prompts Discovery              |   |
|   |   - Ping Handshake & Automated Subprocess Life-Cycle Supervision              |   |
|   |   - Self-Healing Circuit Breaker (CLOSED -> OPEN -> HALF_OPEN)                |   |
|   |   - Incident Telemetry & One-Click Administrative Recalibration               |   |
|   +------------------+------------------+------------------+----------------------+   |
+----------------------|------------------|------------------|--------------------------+
                       |                  |                  |
                       | STDIO (JSON-RPC) | STDIO (JSON-RPC) | STDIO / SSE
                       v                  v                  v
             +------------------+ +------------------+ +------------------+
             |   ERP MCP SERVER | | INVENTORY SERVER | | EQUIPMENT SERVER |
             | (Projects, CAPEX,| | (Structural Steel| | (Heavy Cranes,   |
             |  Milestones, WBS)| |  Flanges, Rebar) | |  TBMs, Telemetry)|
             +--------+---------+ +--------+---------+ +--------+---------+
                      |                    |                    |
                      v                    v                    v
             +------------------+ +------------------+ +------------------+
             |   SAP S/4HANA    | |    Oracle WMS    | |   IBM Maximo     |
             +------------------+ +------------------+ +------------------+
```

---

## Key Capabilities

### 1. Protocol-Aware MCP Server Management
- **Specification Compliance**: Fully conforms to the Model Context Protocol JSON-RPC 2.0 specification (`2024-11-05`).
- **Dual Transports**: Bidirectional communication over **STDIO** subprocesses and **Streamable HTTP / SSE**.
- **Capability Negotiation & Ping**: Negotiates client/server capabilities; measures round-trip latency via protocol `ping`.
- **Resources & Prompts Discovery**: Dynamically indexes exposed resources (`resources/list`) and prompts (`prompts/list`).
- **Endpoint Auto-Discovery**: Probes candidate executables or URLs (`POST /servers/discover`), validates schemas, and presents an interactive admin approval modal.
- **3 Industrial Domain Servers**:
  - **ERP Server**: Contracts, CAPEX/OPEX, milestone billings, burn rates.
  - **Inventory Server**: Warehouse yards, high-tensile rebar, cryogenic flanges, safety stock alerts.
  - **Equipment Server**: Heavy crawler cranes, tunnel boring machines, telemetry alarms, servicing schedules.

### 2. Autonomous Multi-Server AI Agent Orchestration
- **Dynamic Tool Discovery**: Queries active database records dynamically based on agent server assignments.
- **Multi-Provider LLM Abstraction**: Supports Google Gemini, OpenAI, Anthropic, and an air-gapped deterministic enterprise mode (`DEMO_DETERMINISTIC`).
- **Concurrent Safe Execution**: Dispatches non-mutating, read-only tools concurrently using `asyncio.gather` to minimize aggregate latency.
- **Execution Step Guardrails**: Strictly bounds execution depth (`max_execution_steps`) to eliminate recursive execution loops.

### 3. Enterprise Security & Policy Intelligence
- **Zero-Trust Authentication**: Cryptographic JWT validation with issuer (`iss == "mcp-nexus-gateway"`), audience (`aud == "mcp-nexus-enterprise"`), and expiration verification.
- **Strict 5-Tier RBAC**: `SUPER_ADMIN`, `ADMIN`, `DEVELOPER`, `OPERATOR`, `VIEWER` enforced at the API boundary. Unprivileged actions return HTTP 403 Forbidden.
- **Policy Intelligence Engine**: Database-backed `SecurityPolicy` table with ranked priority scoring (Exact Tool > Wildcard Pattern > Server Scope > Global Scope) and deny-first precedence (`DENY` > `REQUIRE_APPROVAL` > `ALLOW`).
- **Dual-Person Approval Workflow**: Enforces dual-control human-in-the-loop governance for destructive or high-risk operations. Requesters cannot self-approve, and two distinct administrators must sign off before execution proceeds.
- **Immutable Security Vault**: Records authentication failures, authorization breaches, approval events, and circuit breaker trips in `security_events`.

### 4. Self-Healing Infrastructure & Circuit Breaker
- **Circuit Breaker State Machine**: Monitors consecutive server failures. Automatically trips to `OPEN` (default: 3 failures) to isolate failing endpoints and prevent cascading system outages.
- **Incident Telemetry Radar**: Logs structured incident dossiers with timestamps, error messages, and failure counts displayed on the Alerts & Incidents radar.
- **One-Click Recalibration**: Administrators can inspect root causes and restore traffic with a single click (`POST /servers/{id}/circuit-breaker/reset`).

### 5. Deep Distributed Observability
- **Waterfall Trace Explorer**: Visualizes the 6-stage execution lifecycle:
  `USER_REQUEST -> AGENT_DECISION -> POLICY_VALIDATION -> MCP_SERVER -> TOOL_EXECUTION -> RESPONSE`.
- **Gantt Timeline**: Displays horizontal time bars with millisecond duration and percentage-of-total latency breakdown.
- **Span Inspection Drawer**: Slide-over drawer providing raw JSON input and output payloads with one-click copying.
- **Host Telemetry**: Real-time CPU, RAM, process RSS, and active thread counts measured dynamically via `psutil`.

### 6. Enterprise Civil Engineering Workflow Intelligence (Flagship Demonstration)
- Dedicated `/workflows` workspace featuring **Construction Project Risk Intelligence**:
  - Investigates cross-domain enterprise data across three independent MCP servers:
    1. **ERP MCP Server**: Project milestones, contract values, critical path items (`PRJ-HAZ-002`, `PRJ-MUM-001`, `PRJ-HYD-003`).
    2. **Equipment MCP Server**: Heavy machinery telemetry, vibration indices, and overdue maintenance schedules (`EQP-CRN-8800` Terex Crane, `EQP-TBM-004` TBM, `EQP-PLR-1400` Piling Rig).
    3. **Inventory MCP Server**: Warehouse yards, cryogenic flanges (`MAT-FLG-SS316`), and structural rebar (`MAT-STL-500D`) safety stock shortages.
  - 10-step autonomous sequence: request analysis, dynamic tool discovery, permission evaluation, concurrent read-only execution (`asyncio.gather`), cross-domain correlation, structured risk assessment (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), and immutable trace persistence.
  - Interactive Evidence Panel displaying factual JSON outputs supporting every finding.
  - Explicit demarcation: **SYNTHETIC DEMONSTRATION DATA (L&T Heavy Civil IC Simulation)**.

### 7. Interactive Infrastructure Topology Map
- Full graph visualization with **React Flow** linking AI agents, central gateway, MCP servers, and enterprise databases with live telemetry edges.

---

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, Pydantic v2, Official MCP SDK, SQLite (zero-config local) / PostgreSQL.
- **Frontend**: React 19, TypeScript, Vite 6, Tailwind CSS v4, TanStack Query, Recharts, React Flow (@xyflow/react), Lucide Icons.
- **Visual Identity Tokens**: Deep Graphite (`#101216`), Dark Steel (`#181C23`), Industrial Amber (`#F0A43A`), Cool Electric Cyan (`#48B9D0`), Muted Green (`#43B581`).

---

## Quickstart Guide

### Option 1: Local Development (Instant)

#### 1. Backend Setup
```bash
# Navigate to workspace
cd "c:\Users\Aravind\OneDrive\Desktop\MCP nexus"

# Install backend dependencies
pip install -r backend/requirements.txt

# Run automated integration tests (23 tests)
python -m pytest backend/app/tests/test_backend.py -v

# Start FastAPI backend server (Port 8000)
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

#### 2. Frontend Setup
```bash
# In a new terminal, navigate to frontend
cd frontend

# Install dependencies and start dev server
npm install
npm run dev
# Server running at http://localhost:5173
```

Open `http://localhost:5173` in your browser.

---

### Option 2: Docker Compose

```bash
docker-compose up --build
```
- Frontend Control Room: `http://localhost:5173`
- Backend API Docs (Swagger): `http://localhost:8000/docs`

---

## Automated Test Results

The backend test suite (`backend/app/tests/test_backend.py`) verifies all 35 capabilities (23 core platform tests + 12 flagship workflow intelligence tests):

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\Aravind\OneDrive\Desktop\MCP nexus
plugins: anyio-4.14.2, asyncio-1.4.1
collected 35 items

backend/app/tests/test_backend.py::test_root PASSED                      [  2%]
backend/app/tests/test_backend.py::test_auth_rejection_without_token PASSED [  5%]
backend/app/tests/test_backend.py::test_role_switcher_token_generation PASSED [  8%]
backend/app/tests/test_backend.py::test_unauthorized_role_execution_forbidden PASSED [ 11%]
backend/app/tests/test_backend.py::test_servers_and_tools_discovery PASSED [ 14%]
backend/app/tests/test_backend.py::test_command_center_metrics PASSED    [ 17%]
backend/app/tests/test_backend.py::test_playground_tool_execution PASSED [ 20%]
backend/app/tests/test_backend.py::test_sensitive_tool_approval_enforcement PASSED [ 22%]
backend/app/tests/test_backend.py::test_approval_workflow_review PASSED  [ 25%]
backend/app/tests/test_backend.py::test_dual_person_approval_workflow PASSED [ 28%]
backend/app/tests/test_backend.py::test_security_audit_events_logged PASSED [ 31%]
backend/app/tests/test_backend.py::test_tool_config_update PASSED        [ 34%]
backend/app/tests/test_backend.py::test_mcp_server_failure_handling PASSED [ 37%]
backend/app/tests/test_backend.py::test_agent_cross_server_orchestration PASSED [ 40%]
backend/app/tests/test_backend.py::test_infrastructure_topology PASSED   [ 42%]
backend/app/tests/test_backend.py::test_mcp_protocol_capabilities_and_ping PASSED [ 45%]
backend/app/tests/test_backend.py::test_mcp_resources_and_prompts_discovery PASSED [ 48%]
backend/app/tests/test_backend.py::test_circuit_breaker_resilience PASSED [ 51%]
backend/app/tests/test_backend.py::test_agent_dynamic_planning_and_concurrency PASSED [ 54%]
backend/app/tests/test_backend.py::test_agent_max_execution_steps_guard PASSED [ 57%]
backend/app/tests/test_backend.py::test_policy_crud_operations PASSED    [ 60%]
backend/app/tests/test_backend.py::test_policy_engine_dynamic_evaluation_rule PASSED [ 62%]
backend/app/tests/test_backend.py::test_mcp_auto_discovery_endpoint PASSED [ 65%]
backend/app/tests/test_backend.py::test_workflow_successful_cross_server PASSED [ 68%]
backend/app/tests/test_backend.py::test_workflow_dynamic_tool_discovery PASSED [ 71%]
backend/app/tests/test_backend.py::test_workflow_concurrent_read_only_execution PASSED [ 74%]
backend/app/tests/test_backend.py::test_workflow_missing_server_handling PASSED [ 77%]
backend/app/tests/test_backend.py::test_workflow_mcp_server_timeout PASSED [ 80%]
backend/app/tests/test_backend.py::test_workflow_invalid_tool_response PASSED [ 82%]
backend/app/tests/test_backend.py::test_workflow_permission_rejection PASSED [ 85%]
backend/app/tests/test_backend.py::test_workflow_approval_enforcement PASSED [ 88%]
backend/app/tests/test_backend.py::test_workflow_risk_calculation PASSED [ 91%]
backend/app/tests/test_backend.py::test_workflow_evidence_traceability PASSED [ 94%]
backend/app/tests/test_backend.py::test_workflow_execution_trace_creation PASSED [ 97%]
backend/app/tests/test_backend.py::test_workflow_failure_recovery PASSED [100%]

====================== 35 passed, 325 warnings in 9.00s =======================
```

---

## Enterprise Documentation Index

- [Architecture Specification (ARCHITECTURE.md)](docs/ARCHITECTURE.md)
- [Engineering & Security Audit (ENGINEERING_AUDIT.md)](docs/ENGINEERING_AUDIT.md)
- [Zero-Trust Security Model (SECURITY_MODEL.md)](docs/SECURITY_MODEL.md)
- [MCP Protocol Implementation (MCP_PROTOCOL_IMPLEMENTATION.md)](docs/MCP_PROTOCOL_IMPLEMENTATION.md)
- [AI Agent Orchestration (AGENT_ORCHESTRATION.md)](docs/AGENT_ORCHESTRATION.md)
- [Production Deployment Guide (DEPLOYMENT_GUIDE.md)](docs/DEPLOYMENT_GUIDE.md)
- [Phase Implementation Progress (PROGRESS.md)](PROGRESS.md)
