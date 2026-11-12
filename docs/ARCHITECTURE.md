# MCP NEXUS — Enterprise Architecture & Technical Specification
**Enterprise AI Integration, Orchestration & Governance Platform**  
**Tagline:** CONNECT. ORCHESTRATE. GOVERN.  
**Target Review:** Larsen & Toubro (L&T Heavy Civil IC & Enterprise AI Architecture Team)  
**System Version:** 2.0.0-Enterprise  

---

## 1. High-Level System Architecture

MCP NEXUS serves as a centralized, mission-critical control plane bridging Model Context Protocol (MCP) servers, autonomous AI agents, enterprise systems of record (ERP, WMS, CMMS), and policy enforcement gateways.

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

## 2. Model Context Protocol (MCP) Compliance

MCP NEXUS adheres strictly to the official Model Context Protocol JSON-RPC 2.0 specification (`2024-11-05`).

### 2.1 Handshake Sequence
1. **Client Handshake Initialization (`initialize`)**:
   ```json
   {
     "jsonrpc": "2.0",
     "id": 1,
     "method": "initialize",
     "params": {
       "protocolVersion": "2024-11-05",
       "capabilities": {
         "roots": { "listChanged": true },
         "sampling": {}
       },
       "clientInfo": { "name": "mcp-nexus-gateway", "version": "2.0.0" }
     }
   }
   ```
2. **Server Capability Response**:
   Server responds with negotiated protocol version and capability flags (`tools`, `resources`, `prompts`).
3. **Initialized Notification (`notifications/initialized`)**:
   Client signals operational readiness:
   ```json
   { "jsonrpc": "2.0", "method": "notifications/initialized" }
   ```
4. **Tools, Resources & Prompts Discovery**:
   - `tools/list`: Client discovers all registered tools with strictly typed JSON schemas (`inputSchema`).
   - `resources/list`: Client indexes exposed system resources and URI schemes.
   - `prompts/list`: Client indexes prompt templates where supported.
5. **Protocol Ping (`ping`)**:
   - `{"jsonrpc": "2.0", "id": 99, "method": "ping"}` probes endpoint round-trip latency.
6. **Tool Invocation (`tools/call`)**:
   - `{"jsonrpc": "2.0", "id": 100, "method": "tools/call", "params": {"name": "...", "arguments": {...}}}`.

---

## 3. Centralized Connection Manager & Self-Healing Resilience

The `MCPConnectionManager` (`backend/app/mcp/client.py`) provides thread-safe, non-blocking connection pooling and lifecycle supervision:

### 3.1 Official Python MCP SDK STDIO Transport
- **Official SDK Client (`mcp.client.stdio.stdio_client` & `ClientSession`)**: STDIO communication executes through the official Python MCP SDK (`mcp>=1.0.0`, version 2.3.0) eliminating custom JSON-RPC request serialization and line-delimited stream parsing.
- **`StdioServerParameters`**: Configures command, arguments, environment dictionary, and UTF-8 encoding.
- **Windows Proactor Compatibility Architecture**: On Windows platforms under development servers utilizing `_WindowsSelectorEventLoop` (such as Uvicorn with `--reload`), asynchronous subprocess pipe operations trigger `NotImplementedError`. The `MCPClient` architecture transparently resolves this by dispatching SDK session operations to a dedicated worker thread via `asyncio.to_thread` utilizing a thread-isolated `asyncio.WindowsProactorEventLoopPolicy().new_event_loop()`. This guarantees 100% native SDK compliance with zero protocol monkeypatching or fallback to raw sockets.
- **Streamable HTTP / SSE Transport**: Supports asynchronous HTTP connections with Server-Sent Events (`text/event-stream`) streaming for remote microservices.

### 3.2 Self-Healing Circuit Breaker State Machine
To protect enterprise infrastructure from cascading failures:
1. **CLOSED (Nominal)**: Normal operation. Successive successful tool calls maintain zero failure counter.
2. **FAILURE ACCUMULATION**: Consecutive failures (subprocess crashes, JSON-RPC timeouts) increment a failure counter.
3. **OPEN (Isolated)**: Upon reaching the failure threshold (default: 3 consecutive failures), the circuit breaker trips to `OPEN`.
   - Tool dispatches to this server are blocked immediately with `CircuitBreakerOpenError`, returning early without blocking the caller.
   - An operational `CircuitBreakerIncident` is created and broadcast to the Alerts & Incidents telemetry radar.
4. **RECALIBRATION & HALF_OPEN**: Administrators can inspect incident root causes and trigger a one-click recalibration (`POST /servers/{id}/circuit-breaker/reset`), closing the circuit and restoring traffic once health checks pass.

---

## 4. Intelligent Agent Orchestration Engine

The orchestration engine (`backend/app/services/agent_orchestrator.py`) enables autonomous multi-step reasoning across decoupled enterprise MCP servers.

### 4.1 Dynamic Tool Discovery & Planning
Rather than using static tool mappings, the agent:
1. Ingests natural-language enterprise queries (e.g. *"Investigate the Mumbai Metro Line 3 milestone delays, verify hydraulic pressure alarms on TBM-01, and check stock for 32mm rebar."*).
2. Dynamically queries the database for active tools registered to permitted MCP servers.
3. Maps dependencies across ERP, Equipment, and Inventory domains.

### 4.2 LLM Provider Abstraction (`LLMProviderService`)
Supports enterprise multi-model flexibility:
- **Google Gemini**: Enterprise Gemini models via Vertex AI / Gemini API.
- **OpenAI**: GPT-4o / GPT-4 Turbo.
- **Anthropic**: Claude 3.5 Sonnet / Haiku.
- **DEMO_DETERMINISTIC**: Built-in deterministic enterprise intelligence engine for air-gapped environments, CI/CD validation, and zero-token testing.

### 4.3 Concurrent Safe Execution
- Read-only tools (e.g. `get_project_milestones` and `get_equipment_telemetry`) are planned and executed concurrently using `asyncio.gather`, minimizing aggregate orchestration latency.
- Mutating or safety-critical tools are executed sequentially with intermediate state verification.

### 4.4 Guardrails & Recursion Control
- `agent.max_execution_steps` (default: 5 steps) strictly bounds execution depth, preventing infinite recursive execution loops or hallucinated runaway tool chains.

---

## 5. Defense-in-Depth Security & Policy Intelligence Engine

### 5.1 Cryptographic Authentication
- Production JWT tokens signed with secure keys (PBKDF2 SHA-256 password hashing).
- Mandatory validation of token claims:
  - Expiration (`exp`)
  - Issuer (`iss == "mcp-nexus-gateway"`)
  - Audience (`aud == "mcp-nexus-enterprise"`)
- Requests lacking authenticated Bearer tokens strictly return HTTP 401 Unauthorized.

### 5.2 Role-Based Access Control (RBAC)
Strictly enforced at the API route boundary:
- **SUPER_ADMIN**: Full system governance, master policy override, server decommissioning.
- **ADMIN**: Server registration, policy management, dual-person approval authorization.
- **DEVELOPER**: Tool testing in Playground, non-prod server auto-discovery.
- **OPERATOR**: Query execution against approved AI agents and workflows.
- **VIEWER**: Strictly read-only access to monitoring, traces, and metrics. Unprivileged mutation attempts return HTTP 403 Forbidden.

### 5.3 Policy Intelligence Engine (`SecurityPolicy`)
Dynamic database-backed rules evaluate tool execution requests:
- **Ranked Evaluation Priority**:
  1. *Exact Tool Match* (`tool_pattern == tool.name`): Rank 100
  2. *Wildcard Pattern* (`tool_pattern == "get_*"` or `"report_*"`): Rank 50
  3. *Server-Level Scope*: Rank 30
  4. *Global Scope*: Rank 10
- **Deny-First Precedence**:
  If multiple policies match, `DENY` (weight 3) supersedes `REQUIRE_APPROVAL` (weight 2), which supersedes `ALLOW` (weight 1).
- **Environment Scoping**: Policies target `ALL`, `PRODUCTION`, `STAGING`, or `DEVELOPMENT`.

### 5.4 Dual-Person Approval State Machine
Destructive or safety-critical tool executions (e.g. `report_equipment_issue` with `CRITICAL` severity):
1. **Intercept & Halt**: Policy engine halts raw dispatch, sets execution status to `REQUIRE_APPROVAL`.
2. **Approval Request Enqueued**: Creates an `ApprovalRequest` record with status `PENDING`.
3. **Anti-Self-Approval Enforcement**: Requesters are strictly prohibited from approving their own requests.
4. **Dual Approver Requirement**: Two distinct authorized administrators (`ADMIN` or `SUPER_ADMIN`) must approve high-risk operations before status transitions to `APPROVED`.
5. **Rejection Terminal State**: If rejected, execution is permanently blocked and cannot be retroactively dispatched.
6. **Immutable Audit Vault**: Every authorization step generates a `SecurityEvent` record in `security_events`.

---

## 6. Observability & Distributed Tracing

### 6.1 Waterfall Trace Explorer
Every agent orchestration or standalone tool call generates a structured `ExecutionTrace` with 6 inspectable lifecycle stages:

```
[1. USER_REQUEST]      --> Ingestion, JWT claims validation & role resolution
         │
         ▼
[2. AGENT_DECISION]    --> Dynamic tool planning & cross-server dependency mapping
         │
         ▼
[3. POLICY_VALIDATION] --> Ranked dynamic security policy evaluation & approval gating
         │
         ▼
[4. MCP_SERVER]        --> Protocol transport connection & capability validation
         │
         ▼
[5. TOOL_EXECUTION]    --> Subprocess / HTTP JSON-RPC dispatch & output serialization
         │
         ▼
[6. RESPONSE]          --> Synthesis of operational intelligence & consolidated payload
```

- **Interactive Gantt Timeline**: Displays horizontal time bars for each stage with millisecond precision and percentage-of-total latency breakdown.
- **Span Inspection Drawer**: Slide-over drawer exposing stage metadata, status flags, and raw JSON payloads.

---

## 7. Enterprise Civil Engineering Workflow Intelligence

Built specifically to demonstrate cross-server operational intelligence for Larsen & Toubro (L&T Heavy Civil IC):

### 7.1 Construction Project Risk Intelligence (Flagship Demonstration)
The flagship workflow (`CONSTRUCTION PROJECT RISK INTELLIGENCE`) evaluates multi-source operational data across three independent MCP servers to identify capital projects at risk.

#### 10-Step Execution Sequence:
1. **Understand Request**: Parses the natural-language task (*"Identify construction projects at risk due to delayed milestones, equipment failures and insufficient inventory"*).
2. **Identify Required Information**: Maps data requirements to ERP project milestones, equipment maintenance/vibration telemetry, and inventory stock deficits.
3. **Discover Tools Dynamically**: Dynamically queries active database records registered to online MCP servers (`get_project_status`, `get_maintenance_schedule`, `get_low_stock_items`).
4. **Check User Permissions**: Enforces backend RBAC (`AGENTS_ORCHESTRATE`) and evaluates dynamic security policies before dispatch.
5. **Create Execution Plan**: Plans concurrent read-only calls bounded by `agent.max_execution_steps`.
6. **Execute Read-Only Calls Concurrently**: Dispatches parallel JSON-RPC calls via `asyncio.gather`.
7. **Collect Responses**: Handles tool outputs and server timeouts gracefully without terminating.
8. **Correlate Multi-Domain Information**: Links data by project identifier (`PRJ-HAZ-002`, `PRJ-MUM-001`, `PRJ-HYD-003`), active site, and warehouse yard.
9. **Generate Structured Risk Assessment**: `RiskIntelligenceEngine` calculates project risk scores (0–100) and classifications (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
10. **Store Execution Trace & Result**: Persists 6-stage lifecycle spans to `execution_traces` and audit history to `audit_logs`.

### 7.2 Cross-Domain Risk Intelligence Correlation
Correlates 3 distinct enterprise systems into a unified executive dossier:
1. **ERP (SAP S/4HANA bridge)**: Project milestones (e.g. *Hazira Cryogenic LNG Expansion* `PRJ-HAZ-002`), cost variance, delayed status flags, and critical path items.
2. **Equipment (IBM Maximo bridge)**: Heavy machinery telemetry (e.g. *Terex Demag CC-8800-1 Crane* `EQP-CRN-8800`), vibration alarms (6.8 mm/s vs 3.5 mm/s limit), and overdue slew bearing overhaul tasks (42 days overdue).
3. **Inventory (Oracle WMS bridge)**: Warehouse yards (e.g. *Hazira Central Yard* `WH-HAZ-CENTRAL`), high-pressure cryogenic flanges `MAT-FLG-SS316` (0 units available, 40 deficit, 28-day lead time), and rebar `MAT-STL-500D` shortages.

#### Risk Scoring Model:
$$\text{Risk Score} = \min(100, S_{\text{milestone}} + S_{\text{equipment}} + S_{\text{inventory}})$$
- **CRITICAL ($\ge 75$):** Active milestone delay with concurrent equipment breakdown alarm and zero safety stock (e.g. `PRJ-HAZ-002`).
- **HIGH ($50 - 74$):** Overdue maintenance or material deficits threatening critical path.
- **MEDIUM ($25 - 49$):** Project on track but spare parts near safety buffer (e.g. `PRJ-MUM-001`).
- **LOW ($< 25$):** Nominal operations and sufficient inventory buffers (e.g. `PRJ-HYD-003`).

---

## 8. Database Schema & Data Models

- **`organizations`**: Multi-tenant enterprise tenant isolation.
- **`users`**: Enterprise identity, hashed credentials, role assignment, active flags.
- **`mcp_servers`**: Connection parameters, transport type (`STDIO`, `HTTP_SSE`), timeout, circuit breaker status (`CLOSED`, `CIRCUIT_OPEN`).
- **`mcp_tools`**: Dynamic tool registry, schema definitions (`input_schema`), risk levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), approval requirement flags.
- **`ai_agents`**: Autonomous orchestrators, LLM model configurations, temperature, max step limits, assigned server scopes.
- **`security_policies`**: Dynamic governance policies, environment scoping, tool pattern matching, action flags (`ALLOW`, `DENY`, `REQUIRE_APPROVAL`).
- **`approval_requests`**: Dual-person human-in-the-loop queue, requester ID, first approver ID, second approver ID, status lifecycle (`PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`).
- **`execution_traces`**: 6-stage distributed tracing spans, latency timings, input/output JSON payloads.
- **`security_events`**: Immutable security audit vault logging auth failures, policy violations, dual-person approvals, and circuit breaker trip events.

---

## 9. Deployment & Infrastructure Hardening

- **Docker Compose**: Containerized multi-service deployment with healthchecks, environment variable segregation, and service dependency ordering (`frontend` waits for `backend` healthy state).
- **Zero-Config Local Development**: Out-of-the-box SQLite support with instant migration and synthetic seed data for L&T civil engineering workflows.
- **Enterprise Ready**: Full compatibility with external PostgreSQL (Lakebase), Redis task queues, and OTLP distributed tracing exporters.
