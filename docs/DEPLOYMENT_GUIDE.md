# MCP NEXUS — ENTERPRISE DEPLOYMENT & PRODUCTION RUNBOOK

**Project:** MCP NEXUS — CONNECT. ORCHESTRATE. GOVERN.
**Release:** v1.0.0-rc1
**Target Environments:** Docker Compose / Kubernetes / On-Premise Enterprise Infrastructure
**Stack:** FastAPI (Python 3.11+ / 3.14), PostgreSQL 15+ (Clustered), React 19 + TypeScript + Vite, Nginx

---

## 1. Quickstart Architecture

MCP NEXUS provides two deployment topologies:
1. **Local Evaluation & Development:** Single-worker FastAPI with local SQLite database (`mcp_nexus.db`) and Vite dev server.
2. **Enterprise Production Clustered:** Multi-worker Uvicorn (`WORKERS >= 2`) with clustered PostgreSQL 15+ and Nginx static frontend.

---

## 2. Local Evaluation (Standard Run)

### 2.1 Native Python & Node.js

#### Backend Setup
```bash
# 1. Install backend dependencies
pip install -r backend/requirements.txt

# 2. Run backend test suite (197 verified tests)
python -m pytest backend/app/tests/ -v

# 3. Start FastAPI backend (Port 8000)
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

#### Frontend Setup
```bash
# In a separate terminal:
cd frontend

# 1. Install dependencies
npm install

# 2. Verify TypeScript and production build
npx tsc --noEmit
npm run build

# 3. Start Vite development server
npm run dev
# Accessible at http://localhost:5173
```

---

## 3. Docker Compose Deployment

### 3.1 Local Zero-Config Evaluation
```bash
# Start local development stack with SQLite (Port 5173 -> Frontend, Port 8000 -> Backend)
docker compose up -d --build

# Verify container status
docker compose ps
```

### 3.2 Production Deployment with PostgreSQL
```bash
# Launch production cluster with PostgreSQL 15 and multi-worker FastAPI
docker compose -f docker-compose.prod.yml up -d --build

# Check database readiness and logs
docker compose -f docker-compose.prod.yml logs -f backend
```

---

## 4. Production Environment Configuration (`.env.production`)

Production environments strictly fail closed if invalid or insecure settings are detected.

```env
# Mandatory Profile
ENVIRONMENT=Production
DEBUG=False
WORKERS=4

# Cryptographic Token Key (must be >= 32 chars, non-trivial)
SECRET_KEY=Enterprise-Class-Production-Secret-Key-Random-2026-X99

# Clustered Database (SQLite is strictly forbidden in Production and when WORKERS > 1)
DATABASE_URL=postgresql://mcp_admin:SecureProductionPassword2026@pg-cluster:5432/mcp_nexus_prod

# LLM Gateway
LLM_PROVIDER=DEMO_DETERMINISTIC
LLM_MODEL=gemini-1.5-pro
LLM_API_KEY=

# Persistent Sessions (Disabled by default in Production)
ENABLE_PERSISTENT_MCP_SESSIONS=False
PERSISTENT_MCP_SERVERS=
```

---

## 5. Administrator Security & Credential Management

### 5.1 Production Administrator Bootstrap
In `Production` (`ENVIRONMENT=Production`), default credentials and demo users are **strictly prohibited and never provisioned**. Initial administrator provisioning is performed via environment bootstrap:

1. Configure `BOOTSTRAP_ADMIN_PASSWORD` (minimum 12 characters, non-trivial, no default keywords) in `.env.production`.
2. Optionally configure `BOOTSTRAP_ADMIN_EMAIL` (default: `admin@mcp-nexus.enterprise`).
3. On first startup, the platform idempotently provisions the Super Admin with a bcrypt-hashed password.
4. Subsequent restarts detect the existing Super Admin and preserve credentials without modification.

### 5.2 Development & Evaluation Accounts
In local `Development` mode only, the database is pre-seeded with 5 least-privilege demo accounts:

| Email | Password (Dev Only) | Role | Permissions |
| :--- | :--- | :--- | :--- |
| `admin@mcp-nexus.enterprise` | `NexusAdmin@2026` | `SUPER_ADMIN` | Full governance, server registration, approval authority, policy creation |
| `ops.lead@mcp-nexus.enterprise` | `NexusAdmin@2026` | `ADMIN` | Server management, approval review, audit logs, monitoring |
| `dev.arch@mcp-nexus.enterprise` | `NexusAdmin@2026` | `DEVELOPER` | Tool execution, playground testing, server registration |
| `operator.site@mcp-nexus.enterprise` | `NexusAdmin@2026` | `OPERATOR` | Agent orchestration, read-only telemetry, operational workflows |
| `audit.viewer@mcp-nexus.enterprise` | `NexusAdmin@2026` | `VIEWER` | Read-only compliance audit trail and metrics inspection |

---

## 6. Verification & Health Monitoring

### 6.1 System Health Endpoint
```bash
curl -f http://localhost:8000/health
# Returns: {"status":"HEALTHY","environment":"...","database":"CONNECTED","governance_engine":"ACTIVE",...}
```

### 6.2 Full Test Suite Execution
```bash
# Complete backend test suite (209 passing tests)
python -m pytest backend/app/tests/ -v

# Run PostgreSQL Integration Suite (requires live PostgreSQL instance)
POSTGRES_TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/mcp_test python -m pytest backend/app/tests/test_postgresql_integration.py -v

# Frontend typecheck & build
cd frontend
npx tsc --noEmit
npm run build
```
