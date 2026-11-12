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

## 4. Failure Recovery & Step Guards

1. **Step Limit Guard:** If an agent's planned execution steps exceed `agent.max_execution_steps`, the pipeline halts immediately with status `BLOCKED` and records an `Execution Limit Guard Violation` span.
2. **Graceful Degradation:** If an individual server times out or fails, the orchestrator catches the error, records a diagnostic recovery span, and completes partial synthesis for the remaining successful servers rather than terminating the agent.
