# MCP NEXUS - Architecture & Technical Specification
**Enterprise AI Integration, Orchestration & Governance Platform**  
*Tagline: CONNECT. ORCHESTRATE. GOVERN.*  
*Target Review: Larsen & Toubro (L&T) Technical Architecture Team*

---

## 1. High-Level System Architecture

MCP NEXUS serves as a centralized, enterprise-grade control plane bridging Model Context Protocol (MCP) servers, autonomous AI agents, systems of record (ERP, WMS, CMMS), and security governance policies.

```
                      +-----------------------------------+
                      |      ENTERPRISE CONSUMERS        |
                      |  (Desktop Control Room, Web App) |
                      +-----------------+-----------------+
                                        | HTTPS / REST
                                        v
+--------------------------------------------------------------------------------+
|                             MCP NEXUS CONTROL PLANE                            |
|                                                                                |
|   +-------------------+    +--------------------+    +---------------------+   |
|   |  FastAPI Router   |<-->|  RBAC Policy Gate  |<-->|  Audit Vault & DB   |   |
|   | (Auth, Servers,   |    | (SuperAdmin, Admin,|    | (PostgreSQL Schema, |   |
|   |  Tools, Traces)   |    |  Dev, Op, Viewer)  |    |  Traces, Approvals) |   |
|   +---------+---------+    +---------+----------+    +----------+----------+   |
|             |                        |                          |              |
|             v                        v                          v              |
|   +------------------------------------------------------------------------+   |
|   |                   AUTONOMOUS AGENT ORCHESTRATOR                        |   |
|   |   - Multi-step cross-server reasoning (Atlas & Aegis Agents)           |   |
|   |   - Dynamic Tool Selection & Execution Planner                         |   |
|   |   - Transparent Engine (Live LLM API or Deterministic Enterprise)      |   |
|   +------------------------------------+-----------------------------------+   |
|                                        |                                       |
|                                        v                                       |
|   +------------------------------------------------------------------------+   |
|   |                   PROTOCOL-AWARE MCP CLIENT MANAGER                    |   |
|   |   - Standard JSON-RPC 2.0 (2024-11-05 Specification)                   |   |
|   |   - Bidirectional STDIO Subprocess Transports & Streamable HTTP / SSE  |   |
|   |   - Protocol Handshake: initialize -> initialized -> tools/list/call   |   |
|   +------------------+------------------+------------------+---------------+   |
+----------------------|------------------|------------------|-------------------+
                       |                  |                  |
                       | STDIO (JSON-RPC) | STDIO (JSON-RPC) | STDIO (JSON-RPC)
                       v                  v                  v
             +------------------+ +------------------+ +------------------+
             |   ERP MCP SERVER | |  INVENTORY SERVER| | EQUIPMENT SERVER |
             | (Projects, CAPEX,| | (Structural Steel| | (Heavy Cranes,   |
             |  Milestones)     | |  Flanges, Rebar) | |  TBMs, Servicing)|
             +--------+---------+ +--------+---------+ +--------+---------+
                      |                    |                    |
                      v                    v                    v
             +------------------+ +------------------+ +------------------+
             |   SAP S/4HANA    | |    Oracle WMS    | |   IBM Maximo     |
             +------------------+ +------------------+ +------------------+
```

---

## 2. Model Context Protocol (MCP) Compliance

MCP NEXUS adheres strictly to the official Model Context Protocol JSON-RPC 2.0 specification:

### 2.1 Handshake Sequence
1. **Client Handshake Initialization**:
   ```json
   {
     "jsonrpc": "2.0",
     "id": 1,
     "method": "initialize",
     "params": {
       "protocolVersion": "2024-11-05",
       "capabilities": {},
       "clientInfo": { "name": "mcp-nexus", "version": "1.0.0" }
     }
   }
   ```
2. **Server Capability Response**:
   Server responds with `capabilities.tools` and metadata.
3. **Initialized Notification**:
   Client delivers `{"jsonrpc": "2.0", "method": "notifications/initialized"}`.
4. **Tool Discovery**:
   Client invokes `{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}` and automatically registers schemas into the central database.
5. **Tool Execution**:
   Client delivers `{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "...", "arguments": {...}}}`.

---

## 3. Defense-in-Depth Security & Governance

### 3.1 Role-Based Access Control (RBAC) Matrix
- **SUPER_ADMIN**: Unrestricted control plane access, server decommissioning, master policy override.
- **ADMIN**: Server registration, policy management, approval authorization.
- **DEVELOPER**: Tool testing in Playground, server registration in non-prod.
- **OPERATOR**: Authorized agent query execution, safe tool invocation.
- **VIEWER**: Read-only monitoring, trace exploration, and audit visibility.

### 3.2 Two-Stage Sensitive Tool Execution Gate
Destructive or safety-critical tool operations (e.g. `report_equipment_issue` with CRITICAL severity):
1. **Policy Gate Validation**: Backend Policy Engine flags the call as high/critical risk.
2. **Execution Halt & Enqueue**: The operation is halted, preventing raw execution. An `ApprovalRequest` record is enqueued in the Administrative Approval Queue.
3. **Audit Event Logged**: A `SecurityEvent` of type `APPROVAL_REQUESTED` is immutably logged.
4. **Administrative Review**: An authorized administrator reviews the parameters, enters justification, and approves the request.
5. **Deferred Tool Execution**: Only upon approval does the backend execute the real tool and update the telemetry.

---

## 4. Execution Trace Timeline (6 Critical Pipeline Gates)

Every orchestration or individual tool call emits an `ExecutionTrace` containing 6 inspectable gates:
```
USER_REQUEST (Query ingestion, user role resolution)
     │
     ▼
AGENT_DECISION (Multi-step tool planning & cross-server reasoning)
     │
     ▼
POLICY_VALIDATION (RBAC, risk classification & approval checks)
     │
     ▼
MCP_SERVER (Protocol transport handshake & latency probe)
     │
     ▼
TOOL_EXECUTION (Subprocess / HTTP tool dispatch & schema execution)
     │
     ▼
RESPONSE (Consolidated intelligence synthesis & serialization)
```
