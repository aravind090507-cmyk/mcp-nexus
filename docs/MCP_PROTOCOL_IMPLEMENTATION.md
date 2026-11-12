# MCP NEXUS — PROTOCOL IMPLEMENTATION ARCHITECTURE

**Specification:** Model Context Protocol (MCP) — Official Specification 2024-11-05  
**Transport Types Supported:** Official SDK STDIO Subprocesses, Streamable HTTP (SSE), Standard HTTP POST  
**Target Integration:** Official Python `mcp` SDK (`mcp.client.stdio.stdio_client`, `ClientSession`) & JSON-RPC 2.0  

---

## 1. Protocol Architecture & Transports

MCP NEXUS serves as an enterprise-grade control plane and centralized connection manager for Model Context Protocol servers.

```
+-------------------------------------------------------------------------------+
|                           MCP NEXUS CONTROL PLANE                             |
|                           (MCPConnectionManager)                              |
+-------------------------------------------------------------------------------+
           |                                                      |
           | [Official SDK STDIO Transport]                       | [HTTP_SSE Transport]
           | (mcp.client.stdio.stdio_client + ClientSession)      |
           v                                                      v
+----------------------------------------------------+   +----------------------+
| Subprocess Execution via Official Python SDK       |   | httpx.AsyncClient /  |
| - StdioServerParameters (cmd, args, env, encoding) |   | mcp.client.sse       |
| - Dedicated Windows Proactor worker thread         |   +----------------------+
| - ClientSession (initialize, ping, call_tool)      |              |
+----------------------------------------------------+              |
           |                                                        |
           v                                                        v
+-----------------------------+                          +----------------------+
| Local MCP Server Containers |                          | Remote Microservices |
| (ERP, Inventory, Equipment) |                          | (Cloud APIs, SaaS)   |
+-----------------------------+                          +----------------------+
```

### 1.1 Official Python SDK STDIO Client Architecture

MCP Nexus connects to STDIO-based MCP servers using the official Python MCP SDK (`mcp>=1.0.0`, currently running `mcp 2.3.0`):

1. **`mcp.StdioServerParameters`**: Encapsulates executable path, arguments, environment variables, working directory, and encoding (`utf-8`).
2. **`mcp.client.stdio.stdio_client`**: Asynchronous context manager yielding read and write memory streams over standard process pipes.
3. **`mcp.ClientSession`**: Manages protocol handshake, capability exchange, bidirectional message framing, JSON-RPC schema compliance, and timeouts (`read_timeout_seconds`).
4. **Windows Compatibility Engine**:
   - On Windows, default event loops under some web server reload monitors (e.g., Uvicorn with `--reload`) initialize `_WindowsSelectorEventLoop`, which lacks asynchronous subprocess pipe support (`NotImplementedError`).
   - `MCPClient` detects non-proactor loops on Windows and transparently dispatches SDK operations to a dedicated worker thread running a fresh `asyncio.WindowsProactorEventLoopPolicy().new_event_loop()`.
   - Eliminates `NotImplementedError` while preserving zero custom JSON-RPC framing hacks.

---

## 2. Capability Negotiation & Handshake Sequence

The official `ClientSession.initialize()` executes standard JSON-RPC 2.0 handshake negotiation strictly adhering to specification `2024-11-05`:

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
      "name": "mcp-nexus-control-plane",
      "version": "1.0.0"
    }
  }
}
```

### 2.2 Initialized Notification
Immediately following receipt of the server's initialization response, `ClientSession.initialize()` dispatches the initialized notification:
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized",
  "params": {}
}
```

---

## 3. Discovered Primitives via Official SDK

MCP NEXUS supports all primary primitives of the MCP specification via native `ClientSession` methods:

### 3.1 Tools Discovery & Execution (`session.list_tools()`, `session.call_tool()`)
- Discovers available tools, typed parameter schemas (`inputSchema`), and descriptions directly into `ListToolsResult`.
- Invokes tools with validated arguments, handling typed `CallToolResult` and unpacking `TextContent` and structured payload representations.

### 3.2 Resources Discovery (`session.list_resources()`)
- Discovers structured data resources exposed by servers (e.g. `erp://projects/active`, `telemetry://sensors/vibration`, `inventory://catalog`).
- Returns typed `ListResourcesResult` enabling agents to read contextual datasets without mutating system state.

### 3.3 Prompts Discovery (`session.list_prompts()`)
- Discovers server-provided prompt templates (e.g., `audit_project_milestones`, `analyze_machinery_vibration`, `evaluate_stock_shortages`).
- Returns typed `ListPromptsResult` enabling zero-shot domain-specific prompting tailored by backend server authors.

### 3.4 Ping Handshake (`session.send_ping()`)
- Official protocol ping verification measuring subprocess round-trip latency down to fractional milliseconds.

---

## 4. Centralized Connection Manager (`MCPConnectionManager`)

To support high-throughput multi-agent concurrent operations without blocking FastAPI event loops:
1. **Per-Server Asynchronous Mutex Locks:** Each server maintains an isolated `asyncio.Lock` preventing interleaved stdout/stdin corruptions during concurrent tool invocations.
2. **Circuit Breaker Pattern:**
   - **CLOSED:** Normal healthy operation. Consecutive failures are reset on success.
   - **OPEN:** After 3 consecutive failed calls or timeouts, the circuit trips to `OPEN`. Subsequent requests are rejected immediately without waiting for subprocess timeouts, protecting the control plane.
   - **Incident Recording:** Tripping generates an automated Incident entry in the Self-Healing Radar.
   - **Recalibration & Reset:** Administrators can reset the circuit via `POST /servers/{id}/reset-circuit` after addressing root causes.
