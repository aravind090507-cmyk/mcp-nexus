# MCP NEXUS — ENTERPRISE DEPLOYMENT & PRODUCTION RUNBOOK

**Target Environment:** Docker Compose / Kubernetes / On-Premise Enterprise Infrastructure  
**Stack:** FastAPI (Python 3.11+ / 3.14), PostgreSQL 15+, React 19 + TypeScript + Vite, Nginx  

---

## 1. Quickstart (Docker Compose)

### 1.1 Prerequisites
- Docker Engine 24+ & Docker Compose v2+
- Git

### 1.2 Booting the Control Plane
```bash
# Clone the repository
git clone https://github.com/aravind/mcp-nexus.git
cd mcp-nexus

# Start all services (Database, Backend API, Frontend Nginx)
docker compose up -d --build

# Verify container health
docker compose ps
```

### 1.3 Service URLs & Ports
- **Frontend Dashboard:** `http://localhost:5173`
- **Backend API & Swagger Docs:** `http://localhost:8000/docs`
- **PostgreSQL Database:** `localhost:5432`

---

## 2. Environment Variables Configuration

Create a `.env` file in the root directory:

```env
# Application Core
PROJECT_NAME="MCP NEXUS"
TAGLINE="CONNECT. ORCHESTRATE. GOVERN."
ENVIRONMENT="Production"
DEBUG=False

# Cryptography & Token Security
SECRET_KEY="mcp-nexus-enterprise-vault-supersecret-key-2026-xyz"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Database Connection (PostgreSQL for Production, SQLite for Local Dev)
DATABASE_URL="postgresql://mcp_user:mcp_password@db:5432/mcp_nexus"

# LLM Gateway Configuration
LLM_PROVIDER="DEMO_DETERMINISTIC" # Options: GEMINI, OPENAI, ANTHROPIC, DEMO_DETERMINISTIC
LLM_API_KEY=""
LLM_MODEL="gemini-1.5-pro"

# CORS Configuration
BACKEND_CORS_ORIGINS=["http://localhost:5173","http://localhost:3000","http://127.0.0.1:5173"]
```

---

## 3. Verification & Health Monitoring

### 3.1 Backend Healthcheck
```bash
curl -f http://localhost:8000/health
# Output: {"status":"healthy","version":"1.0.0","environment":"Production"}
```

### 3.2 Running the Integration Test Suite
```bash
# Run pytest directly with all 23 verified integration tests
python -m pytest backend/app/tests/test_backend.py -v
```

---

## 4. Default Enterprise User Credentials

Out of the box, MCP NEXUS seeds 5 least-privilege enterprise accounts:

| Email | Password | Role | Permissions |
| :--- | :--- | :--- | :--- |
| `admin@mcpnexus.io` | `admin123` | `SUPER_ADMIN` | Complete governance, server management, dual approvals, policy creation |
| `ops@mcpnexus.io` | `admin123` | `ADMIN` | Server connection, approval review, audit logs, monitoring |
| `dev@mcpnexus.io` | `admin123` | `DEVELOPER` | Tool execution, playground testing, server registration |
| `operator@mcpnexus.io` | `admin123` | `OPERATOR` | Agent orchestration, read-only telemetry, operational workflows |
| `auditor@mcpnexus.io` | `admin123` | `VIEWER` | Read-only compliance audit trail and metrics inspection |
