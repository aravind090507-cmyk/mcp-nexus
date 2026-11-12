"""
Equipment MCP Server
Provides industrial heavy machinery monitoring, telemetry, maintenance schedules, and defect logging.
Complies with Model Context Protocol (MCP) JSON-RPC 2.0 STDIO transport.
"""
import sys
import json
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="[EQP-MCP] %(asctime)s - %(message)s")

EQUIPMENT_DATABASE = {
    "EQP-CRN-8800": {
        "equipment_id": "EQP-CRN-8800",
        "name": "Terex Demag CC-8800-1 Heavy Crawler Crane (1,600t)",
        "project_id": "PRJ-HAZ-002",
        "site": "Hazira Cryo Terminal Jetty 3",
        "operating_hours": 8420.5,
        "vibration_index_mm_s": 6.8,       # Normal: < 3.5, Alert: > 5.0
        "hydraulic_oil_temp_c": 88.5,       # Warning > 80C
        "telemetry_status": "MAINTENANCE_OVERDUE_ALARM",
        "current_task": "Cold box heavy lift module positioning",
        "last_inspection": "2026-08-10",
        "operator": "M. Deshmukh (Certified Master Rigger)"
    },
    "EQP-TBM-004": {
        "equipment_id": "EQP-TBM-004",
        "name": "Herrenknecht Mixshield 12.2m Slurry Tunnel Boring Machine",
        "project_id": "PRJ-MUM-001",
        "site": "Mumbai Coastal Road Worli Shaft",
        "operating_hours": 4210.0,
        "vibration_index_mm_s": 2.1,
        "hydraulic_oil_temp_c": 64.0,
        "telemetry_status": "OPERATIONAL_NOMINAL",
        "current_task": "Segment ring 840 erection",
        "last_inspection": "2026-10-28",
        "operator": "Tunnel Boring Crew Charlie"
    },
    "EQP-PLR-1400": {
        "equipment_id": "EQP-PLR-1400",
        "name": "Bauer BG-40 High-Torque Hydraulic Rotary Piling Rig",
        "project_id": "PRJ-HYD-003",
        "site": "Hyderabad Metro Raidurg Pier 42",
        "operating_hours": 6150.2,
        "vibration_index_mm_s": 2.8,
        "hydraulic_oil_temp_c": 71.0,
        "telemetry_status": "OPERATIONAL_NOMINAL",
        "current_task": "Bored pile drilling (1800mm dia)",
        "last_inspection": "2026-10-15",
        "operator": "S. K. Naidu"
    }
}

MAINTENANCE_DATABASE = [
    {
        "maintenance_id": "MNT-2026-089",
        "equipment_id": "EQP-CRN-8800",
        "project_id": "PRJ-HAZ-002",
        "task_name": "Slew bearing ultrasonic test & main hoist gearbox oil change",
        "scheduled_date": "2026-10-01",
        "overdue_days": 42,
        "is_overdue": True,
        "severity": "CRITICAL",
        "status": "OVERDUE_HALT_RECOMMENDED",
        "technician_team": "Heavy Plant Maintenance Wing Surat"
    },
    {
        "maintenance_id": "MNT-2026-112",
        "equipment_id": "EQP-TBM-004",
        "project_id": "PRJ-MUM-001",
        "task_name": "Cutterhead disc roller replacement inspection",
        "scheduled_date": "2026-11-20",
        "overdue_days": 0,
        "is_overdue": False,
        "severity": "MEDIUM",
        "status": "SCHEDULED_ON_TRACK",
        "technician_team": "Mechanized Tunnelling Division"
    },
    {
        "maintenance_id": "MNT-2026-105",
        "equipment_id": "EQP-PLR-1400",
        "project_id": "PRJ-HYD-003",
        "task_name": "Kelly bar hydraulic swivel seal replacement",
        "scheduled_date": "2026-11-25",
        "overdue_days": 0,
        "is_overdue": False,
        "severity": "LOW",
        "status": "SCHEDULED_ON_TRACK",
        "technician_team": "South Zone Plant Depot"
    }
]

TOOLS = [
    {
        "name": "get_equipment_status",
        "description": "Inspect industrial heavy machinery operational status, vibration metrics, operating hours and active job sites.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "equipment_id": {
                    "type": "string",
                    "description": "Optional machinery identifier (e.g. EQP-CRN-8800, EQP-TBM-004, EQP-PLR-1400). If omitted, returns all fleet assets."
                }
            }
        }
    },
    {
        "name": "get_maintenance_schedule",
        "description": "Retrieve heavy equipment preventative maintenance schedules and flag overdue servicing bottlenecks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "equipment_id": {
                    "type": "string",
                    "description": "Filter by machinery identifier"
                },
                "overdue_only": {
                    "type": "boolean",
                    "description": "If true, returns only equipment with past-due maintenance schedules"
                }
            }
        }
    },
    {
        "name": "report_equipment_issue",
        "description": "File a critical safety or mechanical breakdown issue against heavy equipment. Destructive/High-impact tool requiring administrative approval when flagged as CRITICAL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "equipment_id": {
                    "type": "string",
                    "description": "The machinery identifier"
                },
                "severity": {
                    "type": "string",
                    "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    "description": "Fault severity classification"
                },
                "description": {
                    "type": "string",
                    "description": "Technical diagnosis and breakdown narrative"
                }
            },
            "required": ["equipment_id", "severity", "description"]
        }
    }
]

def handle_call_tool(name: str, args: dict) -> dict:
    if name == "get_equipment_status":
        eq_id = args.get("equipment_id", "").strip().upper() if args.get("equipment_id") else None
        if eq_id:
            if eq_id in EQUIPMENT_DATABASE:
                return {"equipment": EQUIPMENT_DATABASE[eq_id]}
            return {"error": f"Equipment '{eq_id}' not found. Available: {list(EQUIPMENT_DATABASE.keys())}"}
        else:
            return {"total_fleet_units": len(EQUIPMENT_DATABASE), "equipment_list": list(EQUIPMENT_DATABASE.values())}

    elif name == "get_maintenance_schedule":
        eq_id = args.get("equipment_id", "").strip().upper() if args.get("equipment_id") else None
        overdue_only = bool(args.get("overdue_only", False))
        res = MAINTENANCE_DATABASE
        if eq_id:
            res = [m for m in res if m["equipment_id"] == eq_id]
        if overdue_only:
            res = [m for m in res if m["is_overdue"]]
        return {"count": len(res), "maintenance_records": res}

    elif name == "report_equipment_issue":
        eq_id = args.get("equipment_id", "").strip().upper()
        sev = args.get("severity", "MEDIUM").upper()
        desc = args.get("description", "")
        
        ticket_id = f"TKT-SAFETY-{int(datetime.now(timezone.utc).timestamp())}"
        # Update in-memory state
        if eq_id in EQUIPMENT_DATABASE:
            EQUIPMENT_DATABASE[eq_id]["telemetry_status"] = f"FAULT_RECORDED_{sev}"
        
        return {
            "incident_ticket_id": ticket_id,
            "equipment_id": eq_id,
            "severity": sev,
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "status": "LOGGED_ALERT_DISPATCHED",
            "message": f"Critical incident {ticket_id} created for {eq_id}. Telemetry status updated."
        }

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
                            "name": "Equipment MCP Server",
                            "version": "1.0.0"
                        }
                    }
                }
                print(json.dumps(res), flush=True)

            elif method == "notifications/initialized":
                continue

            elif method == "ping":
                res = {"jsonrpc": "2.0", "id": req_id, "result": {}}
                print(json.dumps(res), flush=True)

            elif method == "tools/list":
                res = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
                print(json.dumps(res), flush=True)

            elif method == "resources/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "resources": [
                            {
                                "uri": "equipment://fleet/telemetry-alarms",
                                "name": "Heavy Plant Real-Time Alarms Stream",
                                "description": "Continuous telemetry feed for heavy machinery with vibration and oil temperature exceedances.",
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
                                "name": "audit_equipment_overdue",
                                "description": "Scan heavy equipment fleet for overdue preventative maintenance and vibration alarms.",
                                "arguments": []
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
                        "content": [{"type": "text", "text": json.dumps(tool_result, indent=2)}],
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
