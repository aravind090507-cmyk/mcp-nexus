# MCP NEXUS
### Centralized Enterprise AI Integration, Orchestration & Governance Platform
**Tagline:** CONNECT. ORCHESTRATE. GOVERN.  
**Audience:** Technical Architecture Showcase for Larsen & Toubro (L&T)

---

## Executive Summary

**MCP NEXUS** is a production-oriented enterprise control plane for managing, orchestrating, and governing **Model Context Protocol (MCP)** servers, autonomous AI agents, and corporate tools.

Built from the ground up to reflect the information hierarchy of Linear, the operational intelligence aesthetic of Palantir Foundry, the infrastructure observability of Datadog, and the technical precision of Vercel, MCP NEXUS avoids superficial UI mockups and delivers a fully functional, protocol-compliant system.

---

## Key Capabilities

1. **Protocol-Aware MCP Server Management**
   - Live bidirectional JSON-RPC 2.0 communication over **STDIO** subprocesses and **Streamable HTTP / SSE**.
   - Automatic server handshake, health probing, latency calculation, and dynamic tool schema discovery.
   - 3 pre-configured, operational industrial demo servers:
     - **ERP MCP Server**: Contracts, CAPEX/OPEX, milestone billings, burn rates.
     - **Inventory MCP Server**: Warehouse yards, high-tensile rebar, cryogenic flanges, safety stock alerts.
     - **Equipment MCP Server**: Heavy crawler cranes, tunnel boring machines, telemetry alarms, servicing schedules.

2. **Autonomous Cross-Server AI Agent Orchestration**
   - Natural language workspace coordinating multi-step cross-server investigations.
   - Example scenario: *"Find all projects with delayed equipment maintenance and insufficient inventory."*
   - Transparent engine indicator: Clearly shows when running in **Deterministic Enterprise Mode** vs. **Live LLM API**, ensuring complete architectural integrity.

3. **Enterprise Security & Policy Governance**
   - Backend-enforced **Role-Based Access Control (RBAC)** across 5 roles: `SUPER_ADMIN`, `ADMIN`, `DEVELOPER`, `OPERATOR`, `VIEWER`.
   - **Sensitive Tool Approval Queue**: Destructive operations (e.g. reporting severe machinery breakdown) are halted at the policy layer and queued for administrative approval before dispatch.
   - Live session role switcher in top navbar to demonstrate permissions in real time.

4. **Deep Distributed Observability**
   - **Execution Trace Explorer** with a 6-stage inspectable pipeline:
     `USER_REQUEST -> AGENT_DECISION -> POLICY_VALIDATION -> MCP_SERVER -> TOOL_EXECUTION -> RESPONSE`.
   - Percentile latency metrics (p50, p95, p99), throughput gauges, and forensic audit trails.

5. **Interactive Infrastructure Topology Map**
   - Full graph visualization with **React Flow** linking AI agents, central gateway, MCP servers, and enterprise databases with live telemetry edges.

---

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, Pydantic, Official MCP SDK, SQLite (zero-config local) / PostgreSQL.
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query, Recharts, React Flow (@xyflow/react), Lucide Icons.
- **Design Tokens**: Deep Graphite (`#101216`), Dark Steel (`#181C23`), Industrial Amber (`#F0A43A`), Cool Electric Cyan (`#48B9D0`), Muted Green (`#43B581`).

---

## Quickstart Guide

### Option 1: Local Development (Instant)

#### 1. Backend Setup
```bash
# Navigate to workspace
cd "c:\Users\Aravind\OneDrive\Desktop\MCP nexus"

# Install backend dependencies
pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy httpx python-multipart python-jose cryptography mcp pytest pytest-asyncio

# Run automated tests
python -m pytest backend/app/tests/test_backend.py -v

# Start FastAPI backend server (Port 8000)
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

#### 2. Frontend Setup
```bash
# In a new terminal, navigate to frontend
cd frontend

# Run frontend build or dev server
npm run dev
# Server running at http://localhost:5173
```

Open `http://localhost:5173` in your browser.

---

### Option 2: Docker Compose

```bash
docker-compose up --build
```
- Frontend: `http://localhost:5173`
- Backend API Docs: `http://localhost:8000/docs`

---

## Verification & Test Results

Run the full automated test suite verifying protocol connectivity, RBAC gating, sensitive tool approval queue enforcement, and cross-server agent orchestration:

```bash
python -m pytest backend/app/tests/test_backend.py -v
```
All 7 tests pass in ~3.5 seconds.
