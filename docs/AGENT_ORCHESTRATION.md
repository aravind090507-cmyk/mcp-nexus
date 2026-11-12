# MCP NEXUS — AI AGENT ORCHESTRATION & ROUTING ENGINE

**Platform:** MCP NEXUS Intelligent Agent Routing  
**Supported Providers:** Google Gemini, OpenAI, Anthropic, Demo Deterministic  
**Execution Modes:** Concurrent Safe Dispatch (`asyncio.gather`), Sequential Guarded Execution  

---

## 1. Orchestration Engine Architecture

The MCP Nexus Agent Orchestrator converts natural-language operational queries into structured, multi-server MCP tool executions, enforcing zero-trust governance and execution guards at every step.

```
+-------------------------------------------------------------------------------+
|                       NATURAL LANGUAGE OPERATIONAL QUERY                      |
|  "Find delayed projects across Hazira LNG expansion with crane maintenance    |
|                         and flange stock shortages"                           |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| 1. TOOL DISCOVERY & SCHEMA AGGREGATION                                        |
|    Discovers all active tools from DB across online MCP Servers                |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| 2. LLM PROVIDER ABSTRACTION & DYNAMIC PLANNING                                |
|    Gemini / OpenAI / Anthropic / Domain Deterministic Reasoning               |
|    Outputs structured execution plan with target servers, tools, arguments     |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| 3. EXECUTION STEP GUARD (agent.max_execution_steps limit check)               |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| 4. CONCURRENCY CLASSIFICATION                                                 |
|    - Read-only queries (low risk): Dispatched concurrently (asyncio.gather)   |
|    - Mutating / High-risk: Dispatched sequentially with approval checks       |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| 5. GOVERNANCE & POLICY VALIDATION (PolicyEngine.validate_execution)          |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| 6. MCP TRANSPORT INVOCATION (call_tool via MCPConnectionManager)              |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| 7. ENTERPRISE CORRELATION & RESPONSE SYNTHESIS                               |
|    Extracts real returned JSON; formulates structured remediation dossier     |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| 8. DISTRIBUTED EXECUTION TRACE PERSISTENCE (Waterfall spans saved to DB)     |
+-------------------------------------------------------------------------------+
```

---

## 2. LLM Provider Abstraction

The orchestrator dynamically routes planning queries according to environment configuration:

### 2.1 Supported Providers
1. **Google Gemini (`GEMINI`):** Calls `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` with structured JSON schema response formatting.
2. **OpenAI (`OPENAI`):** Calls `https://api.openai.com/v1/chat/completions` with `json_object` response format.
3. **Anthropic (`ANTHROPIC`):** Calls `https://api.anthropic.com/v1/messages` with structured output guidance.
4. **Domain Deterministic (`DEMO_DETERMINISTIC`):** Intelligent offline domain reasoning tailored for L&T civil engineering, equipment telemetry, inventory stock levels, and capex milestones. Extracts real project codes (`PRJ-HAZ-002`, `PRJ-MUM-001`), equipment tags (`EQP-CRN-8800`), and stock thresholds.

---

## 3. Concurrency & Performance Optimization

When an operational inquiry requires data from multiple independent servers (e.g. ERP project progress + Equipment maintenance schedules + Inventory low stock), the orchestrator identifies that all three queries are read-only and concurrent-safe:
- The orchestrator validates governance policies for all steps.
- Concurrently dispatches all 3 JSON-RPC calls via `asyncio.gather`.
- Individual durations and protocol latency are captured in separate waterfall spans.
- Total wall-clock time drops by up to 65% compared to serial invocation.

---

## 5. Construction Project Risk Intelligence Workflow

### 5.1 Business Scenario & Execution Sequence
The flagship workflow `CONSTRUCTION PROJECT RISK INTELLIGENCE` enables infrastructure operations teams to enter:
> *"Identify construction projects at risk due to delayed milestones, equipment failures and insufficient inventory."*

The orchestrator executes a 10-step sequence across 3 independent MCP servers:
1. **Understand User Request:** Parses prompt intent and extracts target domain parameters.
2. **Identify Required Information:** Maps requirements to project milestones (ERP), machinery maintenance & vibration alarms (Equipment), and inventory safety stock deficits (Inventory).
3. **Discover Relevant MCP Tools Dynamically:** Queries active database records registered to online MCP servers (`get_project_status`, `get_maintenance_schedule`, `get_low_stock_items`).
4. **Check User Permissions:** Evaluates backend RBAC (`AGENTS_ORCHESTRATE`) and Policy Engine dynamic rules before dispatch.
5. **Create Execution Plan:** Formulates a concurrent-safe read-only dispatch plan bounded by `max_execution_steps`.
6. **Execute Concurrent Read-Only Tool Calls:** Dispatches parallel tool calls via `asyncio.gather` through `MCPManager`, utilizing the official Python MCP SDK (`mcp.client.stdio.stdio_client` and `ClientSession.call_tool`).
7. **Collect Responses:** Gathers parsed JSON responses; handles missing servers or timeouts gracefully without terminating.
8. **Correlate Domain Information:** Cross-references data by project code, machinery site, and warehouse location.
9. **Generate Structured Risk Assessment:** The `RiskIntelligenceEngine` calculates project risk scores (0–100) and classifications (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
10. **Store Execution Trace & Result:** Commits an `ExecutionTrace` with 6-stage lifecycle spans and logs audit records to `AuditService`.

### 5.2 Structured Risk Assessment Schema
For every evaluated project, the risk engine outputs:
- `project_id`: Unique project identifier (e.g. `PRJ-HAZ-002`)
- `project_name`: Descriptive capital project title
- `overall_risk`: `CRITICAL` | `HIGH` | `MEDIUM` | `LOW`
- `risk_score`: Quantitative risk score from 0 to 100
- `erp_status`: Milestone health and completion percentage
- `affected_equipment`: Overdue machinery and sensor alarm descriptions
- `affected_materials`: Out-of-stock items, safety stock deficits, and replenishment lead times
- `evidence`: Provable evidence points derived directly from actual MCP tool responses
- `business_impact`: Operational disruption assessment
- `recommended_action`: Remediation action plan
- `source_servers`: Online MCP servers providing supporting data

### 5.3 Governance & Safety Controls
- **Read-Only by Default:** The risk intelligence workflow operates in read-only analysis mode and never mutates project or asset records automatically.
- **Zero-Trust Token Validation:** Enforces cryptographically verified JWT tokens with issuer and audience validation.
- **Anti-Self-Approval Gate:** If any mutating recommendations (such as `report_equipment_issue`) are queued, the system mandates two distinct administrative approvers and strictly rejects requester self-approval.
- **Synthetic Data Transparency:** Clearly demarcated with `SYNTHETIC DEMONSTRATION DATA (L&T Heavy Civil IC Simulation)`. No direct connectivity to proprietary L&T S/4HANA or Maximo instances is claimed.
