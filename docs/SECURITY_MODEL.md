# MCP NEXUS — ENTERPRISE SECURITY & GOVERNANCE MODEL

**Platform:** MCP NEXUS (Enterprise AI Integration, Orchestration & Governance Platform)  
**Standard:** NIST SP 800-207 Zero Trust Architecture & Model Context Protocol 2024-11-05 Specification  
**Environment Target:** Larsen & Toubro (L&T) Heavy Civil Infrastructure Control Plane  

---

## 1. Executive Security Architecture

MCP NEXUS enforces a synchronous, zero-bypass governance model positioned between enterprise clients/AI agents and Model Context Protocol servers. Every request undergoes multi-stage validation prior to protocol dispatch.

```
+---------------------------------------------------------------------------------------------------+
|                                  USER / AI AGENT REQUEST                                          |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
| 1. AUTHENTICATION & TOKEN INTEGRITY (JWT with iss="mcp-nexus-auth", aud="mcp-nexus-api", HS256)   |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
| 2. ROLE-BASED ACCESS CONTROL (RBAC) (SUPER_ADMIN, ADMIN, DEVELOPER, OPERATOR, VIEWER)             |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
| 3. AGENT BOUNDARY VALIDATION (Assigned Servers & AgentToolPermission Matrix)                     |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
| 4. DYNAMIC POLICY INTELLIGENCE ENGINE (Ranked Evaluation: Exact Match > Pattern > Scope > Action) |
+---------------------------------------------------------------------------------------------------+
                   |                                       |                               |
              [DENY Action]                      [REQUIRE_APPROVAL]                  [ALLOW Action]
                   |                                       |                               |
                   v                                       v                               v
            HTTP 403 Forbidden             Dual-Control Human Sign-off          Protocol Transport
       SecurityEvent Logged                 (Requesters Cannot Approve;               Dispatch
                                            Two Distinct Admin Approvers)
```

---

## 2. Authentication & Session Security

### 2.1 Cryptographic Token Claims
Authentication issues cryptographically signed JSON Web Tokens (JWT) using HMAC-SHA256:
- `iss` (Issuer): `mcp-nexus-auth` — Strictly verified on every protected route.
- `aud` (Audience): `mcp-nexus-api` — Strictly verified to prevent cross-service token confusion attacks.
- `sub` (Subject): Immutable User UUID from the persistent database record.
- `iat` (Issued At) and `exp` (Expiration): Enforced with a 24-hour lifetime.

```python
# app/core/security.py
def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        issuer="mcp-nexus-auth",
        audience="mcp-nexus-api"
    )
```

### 2.2 Privilege Escalation Defense
- **Role Origin:** In production environments, user permissions are derived exclusively from verified database rows.
- **Role Switching Gating:** The `/auth/switch-role` simulation endpoint is strictly disabled in production environments (`ENVIRONMENT == "Production"`). Attempting simulation returns `HTTP 403 Forbidden` and records a `PERMISSION_VIOLATION` security event.

---

## 3. Dual-Control Human-in-the-Loop Governance

High-risk and critical operations (such as reporting crane lattice cracks, modifying equipment telemetry parameters, or stock adjustments) require human approval.

### 3.1 Strict Self-Approval Prevention
A requesting engineer or administrator **cannot approve their own operation**.
```python
if approval.requesting_user_id == current_user.id:
    raise HTTPException(
        status_code=403, 
        detail="Self-approval is strictly forbidden. A distinct authorized administrator must review this operation."
    )
```

### 3.2 Genuine Two-Person Rule for Critical Operations
For operations classified as `CRITICAL`:
1. **First Approver:** The first administrator reviews the request. Upon approval, status transitions to `PARTIALLY_APPROVED`.
2. **Duplicate Sign-off Prevention:** If the first approver attempts to provide the second approval, the system halts with `HTTP 400 Bad Request` ("Dual-person approval requires two distinct approvers").
3. **Second Distinct Approver:** A second administrator reviews the pending request. Upon approval, status transitions to `APPROVED` -> `EXECUTED`.

### 3.3 Expiration and State Transitions
- Approval requests carry an `expires_at` timestamp (default: 24 hours).
- Expired requests cannot be reviewed and automatically transition to `EXPIRED`.
- Rejected requests permanently transition to `REJECTED` with an immutable reason audit trail; execution is blocked.

---

## 4. Policy Intelligence Engine

The Policy Intelligence Engine provides database-backed, granular governance rules evaluated synchronously before any MCP tool invocation.

### 4.1 Actions Supported
- **ALLOW:** Permits immediate execution without administrative intervention.
- **DENY:** Hard block that immediately halts tool execution and logs a high-severity `POLICY_VIOLATION`.
- **REQUIRE_APPROVAL:** Suspends execution, enqueues an `ApprovalRequest`, and returns `NEEDS_APPROVAL`.

### 4.2 Priority & Specificity Resolution
To eliminate ambiguity, matching policies are evaluated in order of strict specificity:
1. **Tool Exact Match (Score: 100):** e.g., `tool_pattern = "get_project_status"`.
2. **Tool Wildcard Pattern (Score: 50):** e.g., `tool_pattern = "get_*"`.
3. **Server Scope (Score: 30):** e.g., `server_id = "erp-mcp-server"`.
4. **Global Scope (Score: 10):** e.g., `scope = "GLOBAL"`.

**Action Weighting:** `DENY` (Weight: 3) > `REQUIRE_APPROVAL` (Weight: 2) > `ALLOW` (Weight: 1).  
If both an ALLOW and a DENY rule match, the **DENY rule always wins**.

### 4.3 Environment-Specific Overrides
Policies are scoped to environments:
- `ALL`: Evaluated across all deployments.
- `PRODUCTION`: Enforced only when `ENVIRONMENT == "Production"`.
- `STAGING` / `DEVELOPMENT`: Isolated sandbox constraints.

---

## 5. Security Auditing & Immutable Event Logs

All security-sensitive operations are synchronously recorded to the database:
- `AUTH_FAILURE`: Failed login attempts or invalid credentials.
- `PERMISSION_VIOLATION`: Unauthorized endpoint or tool execution attempts.
- `UNAUTHORIZED_APPROVAL_ATTEMPT`: Self-approval or duplicate approval attempts.
- `POLICY_VIOLATION`: Actions blocked by the Policy Intelligence Engine.
- `CIRCUIT_TRIP`: Failures causing circuit-breaker trip to OPEN state.

Each audit record captures:
- Timestamp (UTC)
- Actor (User email or Agent ID)
- Role & Permissions
- Target Resource (Server / Tool / Approval ID)
- Detailed Context & Diff
