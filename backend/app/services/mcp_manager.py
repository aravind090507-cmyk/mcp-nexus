import datetime
import os
import sys
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.all_models import MCPServer, MCPTool, User
from app.mcp.client import MCPClient, MCPClientError, MCPConnectionManager
from app.services.audit_service import AuditService
from app.services.policy_engine import PolicyEngine
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class MCPManager:
    _fallback_counts: Dict[str, int] = {}

    @classmethod
    def get_fallback_counts(cls) -> Dict[str, int]:
        return dict(cls._fallback_counts)

    @classmethod
    def reset_fallback_counts(cls):
        cls._fallback_counts.clear()

    @staticmethod
    def is_persistent_enabled(server: MCPServer) -> bool:
        """
        Determines whether persistent session transport is active for the given MCP server.
        Requires:
        1. Global setting ENABLE_PERSISTENT_MCP_SESSIONS == True
        2. Transport type == STDIO
        3. Emergency kill switch is NOT engaged
        4. Server is enabled
        5. Deployment state is not DISABLED or ROLLBACK
        6. Server is in PERSISTENT_MCP_SERVERS allowlist (wildcards forbidden in Staging/Production)
        7. Not explicitly disabled in server.env_vars
        """
        if not getattr(settings, "ENABLE_PERSISTENT_MCP_SESSIONS", False):
            return False
        if server.transport_type != "STDIO":
            return False
        if not getattr(server, "is_enabled", True):
            return False

        from app.mcp.persistent_session import PersistentSessionManager
        if PersistentSessionManager.is_emergency_disabled():
            return False

        # Check deployment governance state
        from app.services.deployment_governance import DeploymentGovernanceService, DeploymentState
        dep_state = DeploymentGovernanceService.get_server_state(server)
        if dep_state in (DeploymentState.DISABLED, DeploymentState.ROLLBACK):
            return False

        # Check server environment variables override
        env_vars = server.env_vars or {}
        if str(env_vars.get("ENABLE_PERSISTENT_SESSION", "")).lower() in ("false", "0", "no"):
            return False
        if str(env_vars.get("ENABLE_PERSISTENT_SESSION", "")).lower() in ("true", "1", "yes"):
            return True

        # Check rollout allowlist
        allowed_servers = getattr(settings, "PERSISTENT_MCP_SERVERS", "")
        if not allowed_servers or not allowed_servers.strip() or allowed_servers.strip().lower() == "none":
            return False

        current_env = getattr(settings, "ENVIRONMENT", "Development").capitalize()
        if allowed_servers.strip() == "*":
            # Wildcard is strictly forbidden in Staging and Production canary modes
            if current_env in ("Staging", "Production"):
                return False
            return True

        items = [x.strip().lower() for x in allowed_servers.split(",") if x.strip()]
        identifier = (server.identifier or "").lower()
        server_id = (server.id or "").lower()
        server_name = (server.name or "").lower()

        return any(item in (identifier, server_id, server_name) for item in items)

    @staticmethod
    def get_client_for_server(server: MCPServer) -> MCPClient:
        return MCPClient(
            transport_type=server.transport_type,
            command=server.command,
            args=server.args or [],
            env_vars=server.env_vars or {},
            endpoint=server.endpoint,
            auth_token=server.auth_token,
            timeout=server.connection_timeout or 15
        )

    @staticmethod
    async def test_server_connection(server: MCPServer) -> Tuple[bool, str, float, Dict[str, Any]]:
        client = MCPManager.get_client_for_server(server)
        lock = MCPConnectionManager.get_lock(server.id)
        async with lock:
            try:
                res, latency_ms = await client.initialize()
                MCPConnectionManager.record_success(server.id)
                return True, "Connected successfully via Model Context Protocol.", latency_ms, res
            except Exception as e:
                logger.error(f"Failed connection to MCP Server '{server.name}': {e}")
                MCPConnectionManager.record_failure(server.id)
                return False, str(e), 0.0, {}

    @staticmethod
    async def ping_server(server: MCPServer) -> Tuple[bool, float, str]:
        """Sends a protocol ping returning (success, latency_ms, message)."""
        if MCPManager.is_persistent_enabled(server):
            try:
                from app.mcp.persistent_session import PersistentSessionManager
                cmd = server.command
                if not cmd or not os.path.exists(cmd):
                    cmd = sys.executable
                session = PersistentSessionManager.get_session(
                    server_id=server.id,
                    server_name=server.name,
                    command=cmd,
                    args=server.args or [],
                    env_vars=server.env_vars or {},
                    cwd=os.getcwd(),
                    timeout=server.connection_timeout or 30.0
                )
                latency_ms = await session.send_ping()
                MCPConnectionManager.record_success(server.id)
                return True, latency_ms, "Pong received from persistent MCP session."
            except Exception as e:
                logger.warning(f"Persistent ping failed on '{server.name}' ({e}).")
                if not getattr(settings, "PERSISTENT_MCP_FALLBACK_TO_LEGACY", True):
                    MCPConnectionManager.record_failure(server.id)
                    return False, 0.0, str(e)
                logger.info(f"Falling back to legacy ping for '{server.name}'...")

        client = MCPManager.get_client_for_server(server)
        lock = MCPConnectionManager.get_lock(server.id)
        async with lock:
            try:
                latency_ms = await client.ping()
                MCPConnectionManager.record_success(server.id)
                return True, latency_ms, "Pong received from MCP server."
            except Exception as e:
                MCPConnectionManager.record_failure(server.id)
                return False, 0.0, str(e)

    @staticmethod
    async def discover_resources(server: MCPServer) -> List[Dict[str, Any]]:
        """Discovers MCP resources published by this server."""
        client = MCPManager.get_client_for_server(server)
        lock = MCPConnectionManager.get_lock(server.id)
        async with lock:
            try:
                return await client.list_resources()
            except Exception as e:
                logger.warning(f"Resource discovery error on {server.name}: {e}")
                return []

    @staticmethod
    async def discover_prompts(server: MCPServer) -> List[Dict[str, Any]]:
        """Discovers MCP prompts published by this server."""
        client = MCPManager.get_client_for_server(server)
        lock = MCPConnectionManager.get_lock(server.id)
        async with lock:
            try:
                return await client.list_prompts()
            except Exception as e:
                logger.warning(f"Prompt discovery error on {server.name}: {e}")
                return []

    @staticmethod
    async def discover_tools(db: Session, server: MCPServer) -> List[MCPTool]:
        client = MCPManager.get_client_for_server(server)
        lock = MCPConnectionManager.get_lock(server.id)
        async with lock:
            try:
                tools_data = await client.list_tools()
                MCPConnectionManager.record_success(server.id)
            except Exception as e:
                logger.error(f"Error discovering tools for {server.name}: {e}")
                server.status = "DEGRADED"
                db.commit()
                MCPConnectionManager.record_failure(server.id)
                raise MCPClientError(f"Failed to list tools: {str(e)}")

        existing_tools = {t.name: t for t in db.query(MCPTool).filter(MCPTool.server_id == server.id).all()}
        discovered_tools = []

        for td in tools_data:
            name = td.get("name")
            desc = td.get("description", "")
            schema = td.get("inputSchema", {})
            risk, req_approval = PolicyEngine.classify_risk(name, {})

            if name in existing_tools:
                tool = existing_tools[name]
                tool.description = desc
                tool.input_schema = schema
                tool.risk_level = risk
                tool.requires_approval = req_approval
            else:
                tool = MCPTool(
                    server_id=server.id,
                    name=name,
                    description=desc,
                    input_schema=schema,
                    risk_level=risk,
                    requires_approval=req_approval,
                    is_enabled=True
                )
                db.add(tool)
            discovered_tools.append(tool)

        server.status = "HEALTHY"
        server.last_health_check = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        return discovered_tools

    @staticmethod
    async def execute_tool(
        db: Session,
        server: MCPServer,
        tool: MCPTool,
        arguments: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], float, bool, Optional[str]]:
        from app.services.observability_service import ObservabilityService

        # Circuit breaker check
        if MCPConnectionManager.is_circuit_open(server.id):
            ObservabilityService.record_execution(0.0, success=False, is_fallback=False)
            return {}, 0.0, False, f"Circuit breaker OPEN for server '{server.name}' due to repeated failures. Automatic failover active."

        # Tenant Defense-in-Depth: Server organization identity validation (fail closed)
        if not server.organization_id or not str(server.organization_id).strip():
            logger.error(f"Tenant isolation failure: Server '{server.name}' has no organization_id configured.")
            ObservabilityService.record_security_event("CROSS_TENANT_ACCESS")
            return {}, 0.0, False, f"Access denied: Server '{server.name}' has no authoritative organization_id configured."

        auth_org_id = str(server.organization_id).strip()

        # Validate that the organization exists and is valid
        if db is not None:
            from app.models.all_models import Organization
            org_exists = db.query(Organization).filter(Organization.id == auth_org_id).first()
            if not org_exists:
                logger.error(f"Tenant isolation failure: Server '{server.name}' references invalid organization_id '{auth_org_id}'.")
                ObservabilityService.record_security_event("CROSS_TENANT_ACCESS")
                return {}, 0.0, False, f"Access denied: Server '{server.name}' has invalid organization_id '{auth_org_id}'."

        # Authoritative Tenant Binding: Never trust caller-supplied tenant arguments
        effective_args = dict(arguments or {})
        effective_args["organization_id"] = auth_org_id
        effective_args["tenant_id"] = auth_org_id

        # Sanitize any alternate or alias parameter keys if present
        for alias in ("org_id", "organizationId", "tenantId", "org"):
            if alias in effective_args:
                effective_args[alias] = auth_org_id

        # Sanitize nested context arguments (e.g. arguments["context"]["organization_id"])
        if isinstance(effective_args.get("context"), dict):
            ctx = dict(effective_args["context"])
            for ctx_key in ("organization_id", "tenant_id", "org_id", "organizationId", "tenantId"):
                if ctx_key in ctx:
                    ctx[ctx_key] = auth_org_id
            effective_args["context"] = ctx

        effective_env = dict(server.env_vars or {})
        effective_env["MCP_SERVER_ORGANIZATION_ID"] = auth_org_id

        is_fallback = False

        if MCPManager.is_persistent_enabled(server):
            try:
                from app.mcp.persistent_session import PersistentSessionManager
                cmd = server.command
                if not cmd or not os.path.exists(cmd):
                    cmd = sys.executable
                res, duration_ms = await PersistentSessionManager.execute_tool(
                    server_id=server.id,
                    server_name=server.name,
                    command=cmd,
                    args=server.args or [],
                    env_vars=effective_env,
                    cwd=os.getcwd(),
                    tool_name=tool.name,
                    arguments=effective_args,
                    timeout=server.connection_timeout or 30.0
                )
                MCPConnectionManager.record_success(server.id)
                ObservabilityService.record_execution(duration_ms, success=True, is_fallback=False)

                # Update metrics
                tool.total_executions += 1
                tool.last_executed_at = datetime.datetime.now(datetime.timezone.utc)
                server.total_calls += 1
                server.avg_response_time_ms = round((server.avg_response_time_ms * 0.8) + (duration_ms * 0.2), 2)
                db.commit()

                return res, duration_ms, True, None
            except Exception as e:
                logger.warning(f"Persistent session execution failed for '{server.name}' tool '{tool.name}': {e}")
                if getattr(settings, "PERSISTENT_MCP_FALLBACK_TO_LEGACY", True):
                    is_fallback = True
                    MCPManager._fallback_counts[server.id] = MCPManager._fallback_counts.get(server.id, 0) + 1
                    logger.info(f"Safely falling back to legacy transport for '{server.name}' tool '{tool.name}' (fallback_count={MCPManager._fallback_counts[server.id]})...")
                else:
                    tool.failed_executions += 1
                    server.error_rate = round(min(1.0, server.error_rate + 0.05), 3)
                    tripped = MCPConnectionManager.record_failure(server.id, server.name)
                    ObservabilityService.record_execution(0.0, success=False, is_fallback=False)
                    db.commit()
                    msg = f"Tool execution error: {str(e)}"
                    if tripped:
                        msg += " [Circuit breaker TRIPPED to OPEN state]."
                    return {}, 0.0, False, msg

        # Legacy Per-Call Transport
        client = MCPManager.get_client_for_server(server)
        lock = MCPConnectionManager.get_lock(server.id)
        async with lock:
            try:
                res, duration_ms = await client.call_tool(tool.name, effective_args)
                MCPConnectionManager.record_success(server.id)
                ObservabilityService.record_execution(duration_ms, success=True, is_fallback=is_fallback)

                # Update metrics
                tool.total_executions += 1
                tool.last_executed_at = datetime.datetime.now(datetime.timezone.utc)
                server.total_calls += 1
                server.avg_response_time_ms = round((server.avg_response_time_ms * 0.8) + (duration_ms * 0.2), 2)
                db.commit()

                return res, duration_ms, True, None
            except Exception as e:
                tool.failed_executions += 1
                server.error_rate = round(min(1.0, server.error_rate + 0.05), 3)
                tripped = MCPConnectionManager.record_failure(server.id, server.name)
                ObservabilityService.record_execution(0.0, success=False, is_fallback=is_fallback)
                db.commit()
                msg = f"Tool execution error: {str(e)}"
                if tripped:
                    msg += " [Circuit breaker TRIPPED to OPEN state]."
                return {}, 0.0, False, msg
