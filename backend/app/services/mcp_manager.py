import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.all_models import MCPServer, MCPTool, User
from app.mcp.client import MCPClient, MCPClientError
from app.services.audit_service import AuditService
from app.services.policy_engine import PolicyEngine
import logging

logger = logging.getLogger(__name__)

class MCPManager:
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
        try:
            res, latency_ms = await client.initialize()
            return True, "Connected successfully via Model Context Protocol.", latency_ms, res
        except Exception as e:
            logger.error(f"Failed connection to MCP Server '{server.name}': {e}")
            return False, str(e), 0.0, {}

    @staticmethod
    async def discover_tools(db: Session, server: MCPServer) -> List[MCPTool]:
        client = MCPManager.get_client_for_server(server)
        try:
            tools_data = await client.list_tools()
        except Exception as e:
            logger.error(f"Error discovering tools for {server.name}: {e}")
            server.status = "DEGRADED"
            db.commit()
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
        server.last_health_check = datetime.datetime.utcnow()
        db.commit()
        return discovered_tools

    @staticmethod
    async def execute_tool(
        db: Session,
        server: MCPServer,
        tool: MCPTool,
        arguments: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], float, bool, Optional[str]]:
        client = MCPManager.get_client_for_server(server)
        try:
            res, duration_ms = await client.call_tool(tool.name, arguments)
            
            # Update metrics
            tool.total_executions += 1
            tool.last_executed_at = datetime.datetime.utcnow()
            server.total_calls += 1
            server.avg_response_time_ms = round((server.avg_response_time_ms * 0.8) + (duration_ms * 0.2), 2)
            db.commit()

            return res, duration_ms, True, None
        except Exception as e:
            tool.failed_executions += 1
            server.error_rate = round(min(1.0, server.error_rate + 0.05), 3)
            db.commit()
            return {}, 0.0, False, str(e)
