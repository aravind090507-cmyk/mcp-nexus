# MCP NEXUS — LOCAL SETUP AND RELEASE GUIDE
## Production-Grade Developer Environment, Database Management & CI Operations

**Application Version:** `v1.0.0-rc2.1`  
**Architecture:** FastAPI (Backend) + React TypeScript / Vite (Frontend) + SQLAlchemy & Alembic (Data Layer) + PostgreSQL 15 / SQLite  

---

## 1. PREREQUISITES
- **Python:** 3.10+ (tested through 3.14)
- **Node.js:** 18+ or 20+ LTS
- **Package Managers:** `pip`, `npm`
- **Database (Optional for Production / Full Test Suite):** PostgreSQL 15+ (SQLite supported for local development)

---

## 2. BACKEND ENVIRONMENT SETUP

1. **Navigate to backend and create virtual environment (optional but recommended):**
   ```bash
   cd backend
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```

2. **Install backend dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install pytest pytest-asyncio psycopg2-binary alembic
   ```

---

## 3. FRONTEND ENVIRONMENT SETUP

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install frontend dependencies:**
   ```bash
   npm install
   ```

---

## 4. ENVIRONMENT VARIABLE CONFIGURATION

Create `.env` in repository root for local development:
```ini
ENVIRONMENT=Development
DEBUG=True
DATABASE_URL=sqlite:///./mcp_nexus.db
SECRET_KEY=local-dev-secret-key-32-chars-long-minimum-length
WORKERS=1
ENABLE_PERSISTENT_MCP_SESSIONS=False
```

For Production environments, use `.env.production` (never committed to Git):
```ini
ENVIRONMENT=Production
DEBUG=False
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<dbname>
SECRET_KEY=<generate-strong-high-entropy-secret-key-min-32-chars>
BOOTSTRAP_ADMIN_EMAIL=admin@your-company.com
BOOTSTRAP_ADMIN_PASSWORD=<generate-strong-bootstrap-password>
WORKERS=4
ENABLE_PERSISTENT_MCP_SESSIONS=False
```

---

## 5. DATABASE INITIALIZATION & MIGRATIONS

MCP NEXUS uses Alembic for zero-drift schema migration management.

### Option A: Fresh Database Initialization
To initialize a fresh development or staging database to the current schema head:
```bash
# Run from repository root
alembic upgrade head
```

### Option B: PostgreSQL Production Database Migration
```bash
# With explicit connection URL
alembic -x db_url=postgresql://<user>:<password>@localhost:5432/<dbname> upgrade head
```

### Option C: Adopting an Existing Pre-Migration Database
If adopting an existing database that already contains the 13 canonical tables, use the safe adoption engine:
```python
from app.database.adoption import safely_adopt_existing_database
success, message = safely_adopt_existing_database("sqlite:///./mcp_nexus.db")
print(message)
```

---

## 6. STARTING THE APPLICATION

### 1. Start Backend API Server
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Base: `http://127.0.0.1:8000`
- Swagger OpenAPI Docs: `http://127.0.0.1:8000/docs`
- ReDoc Docs: `http://127.0.0.1:8000/redoc`

### 2. Start Frontend Development Server
```bash
cd frontend
npm run dev
```
- Web Application UI: `http://localhost:5173`

---

## 7. RUNNING TESTS

### 1. Run Complete Backend Regression Test Suite
```bash
# Local SQLite run:
python -m pytest backend/app/tests -v --durations=10

# Full run with Live PostgreSQL 15:
# (Set environment variable before running)
export POSTGRES_TEST_DATABASE_URL="postgresql://postgres:postgrespassword2026@localhost:5432/mcp_nexus_test"
python -m pytest backend/app/tests -v --durations=10 --junitxml=backend-test-report.xml
```

### 2. Verify Strict CI Test Accounting Gate
```bash
python scripts/verify_ci_test_report.py backend-test-report.xml
```

### 3. Verify Database Integrity & Clean-Checkout Contract
```bash
python scripts/verify_database_integrity_contract.py
```

### 4. Run Frontend Validation & Production Build
```bash
cd frontend
npx tsc --noEmit
npm run build
```

---

## 8. TROUBLESHOOTING COMMON STARTUP FAILURES

1. **`RuntimeError: CRITICAL STARTUP ERROR: Alembic version table 'alembic_version' is missing`**:
   - Cause: Starting in `ENVIRONMENT=Production` without running migrations.
   - Fix: Run `alembic upgrade head` before starting the service.

2. **`RuntimeError: CRITICAL CONFIGURATION ERROR: Production environment cannot use SQLite database`**:
   - Cause: `ENVIRONMENT=Production` requires PostgreSQL; SQLite is forbidden in production for concurrent reliability.
   - Fix: Set `DATABASE_URL=postgresql://...` in `.env.production`.

3. **`RuntimeError: CRITICAL STARTUP ERROR: Database is unreachable`**:
   - Cause: PostgreSQL daemon is not running or credentials/port are misconfigured.
   - Fix: Ensure PostgreSQL is running on port 5432 and credentials in `DATABASE_URL` match.
