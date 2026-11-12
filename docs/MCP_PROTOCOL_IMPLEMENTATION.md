# MCP NEXUS — PROTOCOL IMPLEMENTATION ARCHITECTURE

**Specification:** Model Context Protocol (MCP) — Official Specification 2024-11-05  
**Transport Types Supported:** STDIO Subprocesses, Streamable HTTP (SSE), Standard HTTP POST  
**Target Integration:** Python `mcp` SDK & JSON-RPC 2.0  

---

## 1. Protocol Architecture & Transports

MCP NEXUS serves as an enterprise-grade control plane and centralized connection manager for Model Context Protocol servers.

```
+-------------------------------------------------------------------------------+
|                           MCP NEXUS CONTROL PLANE                             |
|                           (MCPConnectionManager)                              |
+-------------------------------------------------------------------------------+
           |                                                      |
           | [STDIO Transport]                                    | [HTTP_SSE Transport]
           v                                                      v
+-----------------------------+                        +------------------------+
| Python Subprocess Exchange  |                        | httpx.AsyncClient /    |
| (stdin / stdout JSON-RPC)   |                        | mcp.client.sse         |
+-----------------------------+                        +------------------------+
           |                                                      |
           v                                                      v
+-----------------------------+                        +------------------------+
| Local MCP Server Containers |                        | Remote Cloud Endpoints |
| (ERP, Inventory, Equipment) |                        | (Microservices, SaaS)  |
+-----------------------------+                        +------------------------+
```

---

## 2. Capability Negotiation & Handshake Sequence

Every connection initiation executes standard JSON-RPC 2.0 handshake negotiation:

### 2.1 Initialization Request
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": { "listChanged": true },
      "resources": { "subscribe": true },
      "prompts": { "listChanged": true }
    },
    "clientInfo": {
      "name": "MCP-Nexus-Control-Plane",
      "version": "1.0.0"
    }
  }
}
```

### 2.2 Initialized Notification
Immediately following receipt of the server's initialization response, the client dispatches the initialized notification:
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized",
  "params": {}
}
```

---

## 3. Discovered Primitives

MCP NEXUS supports all three primary primitives of the MCP specification:

### 3.1 Tools Discovery (`tools/list` & `tools/call`)
- Discovers available tools, parameter schemas (`inputSchema`), and descriptions.
- Synchronously invokes tools with validated parameters.

### 3.2 Resources Discovery (`resources/list`)
- Discovers structured data resources exposed by servers (e.g. `erp://projects/active`, `telemetry://sensors/vibration`, `inventory://catalog`).
- Enables agents to read contextual datasets without mutating system state.

### 3.3 Prompts Discovery (`prompts/list`)
- Discovers server-provided prompt templates (e.g., `audit_project_milestones`, `analyze_machinery_vibration`, `evaluate_stock_shortages`).
- Enables zero-shot domain-specific prompting tailored by backend server authors.

### 3.4 Ping Handshake (`ping`)
- Standard protocol ping verification measuring network and subprocess latency down to fractional milliseconds.

---

## 4. Centralized Connection Manager (`MCPConnectionManager`)

To support high-throughput multi-agent concurrent operations without blocking FastAPI event loops:
1. **Per-Server Asynchronous Mutex Locks:** Each server maintains an isolated `asyncio.Lock` preventing interleaved stdout/stdin corruptions during concurrent tool invocations.
2. **Circuit Breaker Pattern:**
   - **CLOSED:** Normal healthy operation. Consecutive failures are reset on success.
   - **OPEN:** After 3 consecutive failed calls or timeouts, the circuit trips to `OPEN`. Subsequent requests are rejected immediately without waiting for subprocess timeouts, protecting the control plane.
   - **Incident Recording:** Tripping generates an automated Incident entry in the Self-Healing Radar.
   - **Recalibration & Reset:** Administrators can reset the circuit via `POST /servers/{id}/reset-circuit` after addressing root causes.
