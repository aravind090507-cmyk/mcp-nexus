"""
ERP MCP Server
Provides enterprise project data, financial summaries, and milestone tracking.
Complies with Model Context Protocol (MCP) JSON-RPC 2.0 STDIO transport.
"""
import sys
import json
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="[ERP-MCP] %(asctime)s - %(message)s")

# Realistic enterprise project synthetic data tailored for infrastructure projects (e.g. L&T Heavy Civil / EPC)
PROJECTS_DATABASE = {
    "PRJ-MUM-001": {
        "project_id": "PRJ-MUM-001",
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
    }
}

FINANCIALS_DATABASE = {
    "PRJ-MUM-001": {
        "project_id": "PRJ-MUM-001",
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
        "capex_budget_cr": 5100.0,
        "capex_spent_cr": 2142.0,
        "opex_spent_cr": 95.0,
        "invoiced_amount_cr": 2200.0,
        "pending_milestone_payments_cr": 180.0,
        "burn_rate_monthly_cr": 55.0,
        "operating_margin_pct": 16.2,
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
                    "description": "Optional project identifier. If omitted, returns status summary for all ongoing projects."
                }
            }
        }
    }
]

def handle_call_tool(name: str, args: dict) -> dict:
    if name == "get_project_details":
        p_id = args.get("project_id", "").strip().upper()
        if p_id in PROJECTS_DATABASE:
            return {"project": PROJECTS_DATABASE[p_id]}
        return {"error": f"Project '{p_id}' not found in ERP records. Available projects: {list(PROJECTS_DATABASE.keys())}"}
    
    elif name == "get_financial_summary":
        p_id = args.get("project_id", "").strip().upper()
        if p_id in FINANCIALS_DATABASE:
            return {"financial_summary": FINANCIALS_DATABASE[p_id]}
        return {"error": f"Financial records for '{p_id}' not found."}
    
    elif name == "get_project_status":
        p_id = args.get("project_id", "").strip().upper() if args.get("project_id") else None
        if p_id:
            if p_id in PROJECTS_DATABASE:
                p = PROJECTS_DATABASE[p_id]
                return {
                    "project_id": p_id,
                    "name": p["name"],
                    "status": p["status"],
                    "completion_pct": p["completion_percentage"],
                    "critical_path_items": p["critical_path_items"]
                }
            return {"error": f"Project '{p_id}' not found."}
        else:
            summary = [
                {
                    "project_id": k,
                    "name": v["name"],
                    "status": v["status"],
                    "completion_pct": v["completion_percentage"],
                    "critical_issues": v["critical_path_items"]
                }
                for k, v in PROJECTS_DATABASE.items()
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
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "ERP MCP Server",
                            "version": "1.0.0"
                        }
                    }
                }
                print(json.dumps(res), flush=True)

            elif method == "notifications/initialized":
                # client acknowledges initialization
                continue

            elif method == "ping":
                res = {"jsonrpc": "2.0", "id": req_id, "result": {}}
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
                err_res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method '{method}' not found"}
                }
                print(json.dumps(err_res), flush=True)

        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)}
            }
            print(json.dumps(err_res), flush=True)

if __name__ == "__main__":
    run_server()
