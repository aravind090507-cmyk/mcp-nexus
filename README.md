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

### 1. Official MCP Python SDK Transport & Server Management
- **Official SDK Client (`mcp.client.stdio.stdio_client` & `ClientSession`)**: STDIO communication is powered directly by the official Python MCP SDK (`mcp>=1.0.0`, version 2.3.0), utilizing `StdioServerParameters` and `ClientSession` with native protocol framing.
- **Windows Proactor Compatibility Architecture**: Transparent worker-thread isolation ensures seamless `asyncio.create_subprocess_exec` execution across Windows development environments (including Uvicorn `--reload` loops) with zero custom JSON-RPC workarounds.
- **Specification Compliance**: Fully conforms to the Model Context Protocol JSON-RPC 2.0 specification (`2024-11-05`).
- **Dual Transports**: Bidirectional communication over **STDIO** subprocesses and **Streamable HTTP / SSE**.
- **Capability Negotiation & Ping**: Negotiates client/server capabilities; measures round-trip latency via official protocol `ping`.
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

# Run complete backend test suite (197 verified tests across all phases)
python -m pytest backend/app/tests/ -v

# Start FastAPI backend server (Port 8000)
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

#### 2. Frontend Setup
```bash
# In a new terminal, navigate to frontend
cd frontend

# Install dependencies and verify TypeScript
npm install
npx tsc --noEmit
npm run build

# Start Vite development server
npm run dev
# Server running at http://localhost:5173
```

Open `http://localhost:5173` in your browser.

---

### Option 2: Docker Compose

```bash
# For local evaluation (SQLite):
docker compose up -d --build

# For production deployment with PostgreSQL:
docker compose -f docker-compose.prod.yml up -d --build
```
- Frontend Control Room: `http://localhost:5173`
- Backend API Docs (Swagger): `http://localhost:8000/docs`

---

## Enterprise Default Accounts

The database comes pre-seeded with 5 least-privilege enterprise accounts:

| Email | Password | Role | Permissions |
| :--- | :--- | :--- | :--- |
| `admin@mcp-nexus.enterprise` | `NexusAdmin@2026` | `SUPER_ADMIN` | Full platform control, server registration, approval authority |
| `ops.lead@mcp-nexus.enterprise` | `NexusAdmin@2026` | `ADMIN` | Server connection, approval review, audit logs, monitoring |
| `dev.arch@mcp-nexus.enterprise` | `NexusAdmin@2026` | `DEVELOPER` | Tool execution, playground testing, server registration |
| `operator.site@mcp-nexus.enterprise` | `NexusAdmin@2026` | `OPERATOR` | Agent orchestration, read-only telemetry, operational workflows |
| `audit.viewer@mcp-nexus.enterprise` | `NexusAdmin@2026` | `VIEWER` | Read-only compliance audit trail and metrics inspection |

---

## Automated Test Results

The comprehensive test suite verifies all platform layers:
- Core Platform & Workflows (`test_backend.py`)
- Persistent Session Lifecycle & Concurrency (`test_phase15a_persistent_session.py`, `test_phase15b_stress_and_reliability.py`)
- Security & Policy Hardening (`test_phase15c1_security_audit.py`, `test_tenant_security_remediation.py`)
- Engine Lifecycle & Lease Management (`test_phase15d_engine_proxy.py`, `test_phase15d2_8_engine_finalizer_registry.py`)
- Production Canary Governance (`test_phase15d3_canary_governance.py`)
- SQLite Concurrency & Atomic Audit (`test_phase15d3_3_concurrency_atomic_audit.py`)
- Production Hardening & Fail-Closed Guardrails (`test_phase15d4_1_production_hardening.py`)

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\Aravind\OneDrive\Desktop\MCP nexus
plugins: anyio-4.14.2, asyncio-1.4.1
collected 197 items

================== 197 passed, 1 warning in 70.89s (0:01:10) ==================
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
