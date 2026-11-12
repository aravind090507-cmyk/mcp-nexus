from enum import Enum
from typing import Set, Dict

class RoleEnum(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"

class PermissionEnum(str, Enum):
    # Servers
    SERVERS_READ = "servers:read"
    SERVERS_WRITE = "servers:write"
    SERVERS_DELETE = "servers:delete"
    SERVERS_CONNECT = "servers:connect"
    
    # Tools
    TOOLS_READ = "tools:read"
    TOOLS_EXECUTE = "tools:execute"
    TOOLS_TEST = "tools:test"
    TOOLS_CONFIG = "tools:config"
    
    # Agents
    AGENTS_READ = "agents:read"
    AGENTS_WRITE = "agents:write"
    AGENTS_ORCHESTRATE = "agents:orchestrate"
    
    # Governance
    GOVERNANCE_READ = "governance:read"
    GOVERNANCE_APPROVE = "governance:approve"
    GOVERNANCE_POLICIES = "governance:policies"
    
    # Observability
    TRACES_READ = "traces:read"
    METRICS_READ = "metrics:read"
    AUDIT_READ = "audit:read"
    
    # Settings
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"

ROLE_PERMISSIONS: Dict[RoleEnum, Set[PermissionEnum]] = {
    RoleEnum.SUPER_ADMIN: {
        PermissionEnum.SERVERS_READ, PermissionEnum.SERVERS_WRITE, PermissionEnum.SERVERS_DELETE, PermissionEnum.SERVERS_CONNECT,
        PermissionEnum.TOOLS_READ, PermissionEnum.TOOLS_EXECUTE, PermissionEnum.TOOLS_TEST, PermissionEnum.TOOLS_CONFIG,
        PermissionEnum.AGENTS_READ, PermissionEnum.AGENTS_WRITE, PermissionEnum.AGENTS_ORCHESTRATE,
        PermissionEnum.GOVERNANCE_READ, PermissionEnum.GOVERNANCE_APPROVE, PermissionEnum.GOVERNANCE_POLICIES,
        PermissionEnum.TRACES_READ, PermissionEnum.METRICS_READ, PermissionEnum.AUDIT_READ,
        PermissionEnum.SETTINGS_READ, PermissionEnum.SETTINGS_WRITE
    },
    RoleEnum.ADMIN: {
        PermissionEnum.SERVERS_READ, PermissionEnum.SERVERS_WRITE, PermissionEnum.SERVERS_CONNECT,
        PermissionEnum.TOOLS_READ, PermissionEnum.TOOLS_EXECUTE, PermissionEnum.TOOLS_TEST, PermissionEnum.TOOLS_CONFIG,
        PermissionEnum.AGENTS_READ, PermissionEnum.AGENTS_WRITE, PermissionEnum.AGENTS_ORCHESTRATE,
        PermissionEnum.GOVERNANCE_READ, PermissionEnum.GOVERNANCE_APPROVE, PermissionEnum.GOVERNANCE_POLICIES,
        PermissionEnum.TRACES_READ, PermissionEnum.METRICS_READ, PermissionEnum.AUDIT_READ,
        PermissionEnum.SETTINGS_READ
    },
    RoleEnum.DEVELOPER: {
        PermissionEnum.SERVERS_READ, PermissionEnum.SERVERS_WRITE, PermissionEnum.SERVERS_CONNECT,
        PermissionEnum.TOOLS_READ, PermissionEnum.TOOLS_TEST, PermissionEnum.TOOLS_CONFIG,
        PermissionEnum.AGENTS_READ, PermissionEnum.AGENTS_WRITE,
        PermissionEnum.TRACES_READ, PermissionEnum.METRICS_READ,
        PermissionEnum.SETTINGS_READ
    },
    RoleEnum.OPERATOR: {
        PermissionEnum.SERVERS_READ,
        PermissionEnum.TOOLS_READ, PermissionEnum.TOOLS_EXECUTE,
        PermissionEnum.AGENTS_READ, PermissionEnum.AGENTS_ORCHESTRATE,
        PermissionEnum.TRACES_READ, PermissionEnum.METRICS_READ,
        PermissionEnum.SETTINGS_READ
    },
    RoleEnum.VIEWER: {
        PermissionEnum.SERVERS_READ,
        PermissionEnum.TOOLS_READ,
        PermissionEnum.AGENTS_READ,
        PermissionEnum.TRACES_READ,
        PermissionEnum.METRICS_READ,
        PermissionEnum.GOVERNANCE_READ,
        PermissionEnum.SETTINGS_READ
    }
}

def has_permission(role: RoleEnum, permission: PermissionEnum) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
