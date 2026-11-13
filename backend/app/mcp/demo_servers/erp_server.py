"""
ERP MCP Server
Provides enterprise project data, financial summaries, and milestone tracking.
Complies with Model Context Protocol (MCP) JSON-RPC 2.0 STDIO transport.
Includes tenant-aware data partitioning and fail-closed defense-in-depth security.
"""
import sys
import os
import json
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="[ERP-MCP] %(asctime)s - %(message)s")

# Primary enterprise tenant
PRIMARY_ORGANIZATION_ID = os.getenv("MCP_PRIMARY_ORG_ID", "abbc6079-36ce-4b73-b8ee-0796f7de5821")
SECONDARY_ORGANIZATION_ID = "org-tenant-beta-02"

# Multi-tenant partitioned project records
PROJECTS_DATABASE = {
    "PRJ-MUM-001": {
        "project_id": "PRJ-MUM-001",
        "organization_id": PRIMARY_ORGANIZATION_ID,
        "name": "Mumbai Coastal Road Tunnel & Sea Bridge Package 4",
        "division": "Heavy Civil Infrastructure IC",
        "client": "Municipal Corporation of Greater Mumbai",
        "contract_value_inr_cr": 4560.00,
        "completion_percentage": 84.5,
        "status": "ACTIVE_ON_TRACK",
        "scheduled_completion": "2027-03-31",
        "project_manager": "R. Swaminathan (AVP Projects)",
        "active_sites": ["Worli Sea Face Shaft", "Priyardarshini Park South Portal"],
        "critical_path_items": ["Undersea segment sealing", "Ventilation cross-passage drilling"]
    },
    "PRJ-HAZ-002": {
        "project_id": "PRJ-HAZ-002",
        "organization_id": PRIMARY_ORGANIZATION_ID,
        "name": "Hazira Cryogenic LNG Expansion & Gas Compression",
        "division": "Hydrocarbon Engineering IC",
        "client": "Petro-Global Infra Ltd",
        "contract_value_inr_cr": 2890.50,
        "completion_percentage": 68.2,
        "status": "DELAYED_MAINTENANCE_BOTTLENECK",
        "scheduled_completion": "2026-12-15",
        "project_manager": "Dr. Anand Kulkarni",
        "active_sites": ["Jetty 3 Cryo Storage", "Compressor House B"],
        "critical_path_items": ["Turbine alignment", "Delayed crane maintenance", "Low stock of structural flanges"]
    },
    "PRJ-HYD-003": {
        "project_id": "PRJ-HYD-003",
        "organization_id": PRIMARY_ORGANIZATION_ID,
        "name": "Hyderabad Airport Metro Express Rail Package 1",
        "division": "Transportation Infrastructure IC",
        "client": "Hyderabad Airport Metro Limited",
        "contract_value_inr_cr": 5680.00,
        "completion_percentage": 42.0,
        "status": "ACTIVE_AHEAD_OF_SCHEDULE",
        "scheduled_completion": "2028-06-30",
        "project_manager": "K. V. Muralidharan",
        "active_sites": ["Shamshabad Depot", "Raidurg Elevated Corridor"],
        "critical_path_items": ["Viaduct pier casting", "Substation utility diversion"]
    },
    "PRJ-T2-001": {
        "project_id": "PRJ-T2-001",
        "organization_id": SECONDARY_ORGANIZATION_ID,
        "name": "Bengaluru International Tech Corridor Phase 2",
        "division": "Urban Infrastructure IC",
        "client": "Karnataka State Industrial Board",
        "contract_value_inr_cr": 3200.00,
        "completion_percentage": 55.0,
        "status": "ACTIVE_ON_TRACK",
        "scheduled_completion": "2027-11-30",
        "project_manager": "G. Venkatesh",
        "active_sites": ["Whitefield Junction", "Kadugodi Elevated Section"],
        "critical_path_items": ["Pier cap erection", "Track alignment survey"]
    }
}

FINANCIALS_DATABASE = {
    "PRJ-MUM-001": {
        "project_id": "PRJ-MUM-001",
        "organization_id": PRIMARY_ORGANIZATION_ID,
        "capex_budget_cr": 4100.0,
        "capex_spent_cr": 3464.5,
        "opex_spent_cr": 210.0,
        "invoiced_amount_cr": 3520.0,
        "pending_milestone_payments_cr": 480.0,
        "burn_rate_monthly_cr": 42.5,
        "operating_margin_pct": 14.8,
        "budget_health": "OPTIMAL"
    },
    "PRJ-HAZ-002": {
        "project_id": "PRJ-HAZ-002",
        "organization_id": PRIMARY_ORGANIZATION_ID,
        "capex_budget_cr": 2650.0,
        "capex_spent_cr": 2120.0,
        "opex_spent_cr": 310.0,
        "invoiced_amount_cr": 1950.0,
        "pending_milestone_payments_cr": 620.0,
        "burn_rate_monthly_cr": 38.0,
        "operating_margin_pct": 9.2,
        "budget_health": "AT_RISK_COST_OVERRUN"
    },
    "PRJ-HYD-003": {
        "project_id": "PRJ-HYD-003",
        "organization_id": PRIMARY_ORGANIZATION_ID,
        "capex_budget_cr": 5100.0,
        "capex_spent_cr": 2142.0,
        "opex_spent_cr": 95.0,
        "invoiced_amount_cr": 2200.0,
        "pending_milestone_payments_cr": 180.0,
        "burn_rate_monthly_cr": 55.0,
        "operating_margin_pct": 16.2,
        "budget_health": "OPTIMAL"
    },
    "PRJ-T2-001": {
        "project_id": "PRJ-T2-001",
        "organization_id": SECONDARY_ORGANIZATION_ID,
        "capex_budget_cr": 2800.0,
        "capex_spent_cr": 1540.0,
        "opex_spent_cr": 110.0,
        "invoiced_amount_cr": 1400.0,
        "pending_milestone_payments_cr": 320.0,
        "burn_rate_monthly_cr": 32.0,
        "operating_margin_pct": 15.5,
        "budget_health": "OPTIMAL"
    }
}

TOOLS = [
    {
        "name": "get_project_details",
        "description": "Retrieve comprehensive enterprise ERP project records, contract values, milestones and operational divisions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The unique enterprise project code (e.g. PRJ-MUM-001, PRJ-HAZ-002, PRJ-HYD-003)"
                },
                "organization_id": {
                    "type": "string",
                    "description": "Tenant organization context for multi-tenant defense-in-depth"
                }
            },
            "required": ["project_id"]
        }
    },
    {
        "name": "get_financial_summary",
        "description": "Fetch CAPEX/OPEX financial health, monthly burn rates, invoiced billings, and operating margins for a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The enterprise project identifier"
                },
                "organization_id": {
                    "type": "string",
                    "description": "Tenant organization context for multi-tenant defense-in-depth"
                }
            },
            "required": ["project_id"]
        }
    },
    {
        "name": "get_project_status",
        "description": "Get real-time operational status, delayed bottlenecks, and critical path risk indicators across all or specific projects.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Optional project identifier. If omitted, returns status summary for all ongoing projects in tenant."
                },
                "organization_id": {
                    "type": "string",
                    "description": "Tenant organization context for multi-tenant defense-in-depth"
                }
            }
        }
    }
]

def _resolve_tenant_context(args: dict) -> str:
    """
    Extracts tenant organization context. Fails closed if missing.
    Per-request argument context strictly takes precedence over static process environment variables.
    """
    if "tenant_id" in args:
        return str(args.get("tenant_id") or "").strip()
    if "organization_id" in args:
        return str(args.get("organization_id") or "").strip()
    return str(os.getenv("MCP_SERVER_ORGANIZATION_ID") or "").strip()

def handle_call_tool(name: str, args: dict) -> dict:
    # 1. Tenant Context Validation (Defense-in-Depth)
    caller_org = _resolve_tenant_context(args)
    if not caller_org:
        return {
            "error": "Access denied: Missing tenant context. Organization ID must be provided.",
            "code": "MISSING_TENANT_CONTEXT"
        }

    if name == "get_project_details":
        p_id = args.get("project_id", "").strip().upper()
        if p_id in PROJECTS_DATABASE:
            p = PROJECTS_DATABASE[p_id]
            if p.get("organization_id") != caller_org:
                return {
                    "error": f"Access denied: Project '{p_id}' belongs to a different organization.",
                    "code": "CROSS_TENANT_ACCESS_DENIED"
                }
            return {"project": p}
        return {"error": f"Project '{p_id}' not found in ERP records."}
    
    elif name == "get_financial_summary":
        p_id = args.get("project_id", "").strip().upper()
        if p_id in FINANCIALS_DATABASE:
            f = FINANCIALS_DATABASE[p_id]
            if f.get("organization_id") != caller_org:
                return {
                    "error": f"Access denied: Financial records for '{p_id}' belong to a different organization.",
                    "code": "CROSS_TENANT_ACCESS_DENIED"
                }
            return {"financial_summary": f}
        return {"error": f"Financial records for '{p_id}' not found."}
    
    elif name == "get_project_status":
        p_id = args.get("project_id", "").strip().upper() if args.get("project_id") else None
        if p_id:
            if p_id in PROJECTS_DATABASE:
                p = PROJECTS_DATABASE[p_id]
                if p.get("organization_id") != caller_org:
                    return {
                        "error": f"Access denied: Project '{p_id}' belongs to a different organization.",
                        "code": "CROSS_TENANT_ACCESS_DENIED"
                    }
                return {
                    "project_id": p_id,
                    "name": p["name"],
                    "status": p["status"],
                    "completion_pct": p["completion_percentage"],
                    "critical_path_items": p["critical_path_items"]
                }
            return {"error": f"Project '{p_id}' not found."}
        else:
            # Filter projects strictly by tenant
            summary = [
                {
                    "project_id": k,
                    "name": v["name"],
                    "status": v["status"],
                    "completion_pct": v["completion_percentage"],
                    "critical_issues": v["critical_path_items"]
                }
                for k, v in PROJECTS_DATABASE.items()
                if v.get("organization_id") == caller_org
            ]
            return {"total_projects": len(summary), "projects": summary}
    
    return {"error": f"Unknown tool: {name}"}

def run_server():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "initialize":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                            "resources": {},
                            "prompts": {}
                        },
                        "serverInfo": {
                            "name": "ERP MCP Server",
                            "version": "1.0.0"
                        }
                    }
                }
                print(json.dumps(res), flush=True)

            elif method == "notifications/initialized":
                pass

            elif method == "ping":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {}
                }
                print(json.dumps(res), flush=True)

            elif method == "tools/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": TOOLS
                    }
                }
                print(json.dumps(res), flush=True)

            elif method == "resources/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "resources": [
                            {
                                "uri": "erp://projects/specs",
                                "name": "L&T Heavy Civil Strategic Projects Specifications",
                                "description": "Master scope documents, contract terms, and milestone delivery dates.",
                                "mimeType": "application/json"
                            },
                            {
                                "uri": "erp://financials/budget-q3",
                                "name": "Q3 Infrastructure Project CAPEX Budgets",
                                "description": "Capital expenditure allocations and actual burn rates.",
                                "mimeType": "application/json"
                            }
                        ]
                    }
                }
                print(json.dumps(res), flush=True)

            elif method == "prompts/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "prompts": [
                            {
                                "name": "audit_project_milestones",
                                "description": "Perform financial and milestone audit for a specific infrastructure package.",
                                "arguments": [
                                    {"name": "project_id", "description": "The project code (e.g. PRJ-MUM-001)", "required": True}
                                ]
                            }
                        ]
                    }
                }
                print(json.dumps(res), flush=True)

            elif method == "tools/call":
                t_name = params.get("name")
                t_args = params.get("arguments", {})
                tool_result = handle_call_tool(t_name, t_args)
                is_err = "error" in tool_result
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(tool_result, indent=2)
                            }
                        ],
                        "isError": is_err
                    }
                }
                print(json.dumps(res), flush=True)

            else:
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method '{method}' not found."
                    }
                }
                print(json.dumps(res), flush=True)

        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal RPC processing error: {str(e)}"
                }
            }
            print(json.dumps(err_res), flush=True)

if __name__ == "__main__":
    run_server()
