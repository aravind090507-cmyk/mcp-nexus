"""
Inventory MCP Server
Provides real-time warehouse inventory, stock level verification, and replenishment alerts.
Complies with Model Context Protocol (MCP) JSON-RPC 2.0 STDIO transport.
"""
import sys
import json
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="[INV-MCP] %(asctime)s - %(message)s")

INVENTORY_DATABASE = [
    {
        "item_code": "MAT-STL-500D",
        "description": "Fe-500D Thermo-Mechanically Treated High-Tensile Rebar (32mm)",
        "category": "Structural Materials",
        "unit": "Metric Tons",
        "warehouse_id": "WH-HAZ-CENTRAL",
        "location": "Hazira Yard Bay 4",
        "stock_on_hand": 14.5,
        "safety_stock": 50.0,
        "allocated_stock": 12.0,
        "available_stock": 2.5,
        "unit_cost_inr": 62500,
        "lead_time_days": 18,
        "status": "CRITICAL_LOW_STOCK"
    },
    {
        "item_code": "MAT-FLG-SS316",
        "description": "High-Pressure Cryogenic Flanges SS-316L (600# 12-inch)",
        "category": "Piping & Valves",
        "unit": "Units",
        "warehouse_id": "WH-HAZ-CENTRAL",
        "location": "Hazira Cryo Store Rack B",
        "stock_on_hand": 8,
        "safety_stock": 40,
        "allocated_stock": 8,
        "available_stock": 0,
        "unit_cost_inr": 48000,
        "lead_time_days": 28,
        "status": "OUT_OF_STOCK"
    },
    {
        "item_code": "MAT-CEM-OPC53",
        "description": "Grade 53 Ordinary Portland Cement (Microfine Blast-Furnace Slag)",
        "category": "Structural Materials",
        "unit": "Bags (50kg)",
        "warehouse_id": "WH-MUM-WORLI",
        "location": "Worli Batching Silo 2",
        "stock_on_hand": 2850,
        "safety_stock": 1000,
        "allocated_stock": 800,
        "available_stock": 2050,
        "unit_cost_inr": 420,
        "lead_time_days": 3,
        "status": "SUFFICIENT"
    },
    {
        "item_code": "HYD-VAL-900",
        "description": "Heavy Hydraulic Actuator Valves for Tunnel Boring Slurry Circuit",
        "category": "Mechanical Spares",
        "unit": "Units",
        "warehouse_id": "WH-MUM-WORLI",
        "location": "Shaft Spare Warehouse",
        "stock_on_hand": 3,
        "safety_stock": 6,
        "allocated_stock": 1,
        "available_stock": 2,
        "unit_cost_inr": 215000,
        "lead_time_days": 14,
        "status": "LOW_STOCK"
    },
    {
        "item_code": "ELE-TX-33KV",
        "description": "33kV Traction Substation Dry Type Cast Resin Transformer",
        "category": "Electrical & Traction",
        "unit": "Sets",
        "warehouse_id": "WH-HYD-METRO",
        "location": "Raidurg Substation Depot",
        "stock_on_hand": 4,
        "safety_stock": 2,
        "allocated_stock": 2,
        "available_stock": 2,
        "unit_cost_inr": 3400000,
        "lead_time_days": 45,
        "status": "SUFFICIENT"
    }
]

TOOLS = [
    {
        "name": "get_inventory",
        "description": "List enterprise warehouse inventory items with filters by material category or warehouse identifier.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category: 'Structural Materials', 'Piping & Valves', 'Mechanical Spares', 'Electrical & Traction'"
                },
                "warehouse_id": {
                    "type": "string",
                    "description": "Filter by warehouse code (e.g. WH-HAZ-CENTRAL, WH-MUM-WORLI, WH-HYD-METRO)"
                }
            }
        }
    },
    {
        "name": "check_stock_availability",
        "description": "Verify whether a requested material quantity is immediately available without violating safety stock thresholds.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_code": {
                    "type": "string",
                    "description": "Material code (e.g. MAT-STL-500D, MAT-FLG-SS316, MAT-CEM-OPC53, HYD-VAL-900)"
                },
                "quantity": {
                    "type": "number",
                    "description": "Required quantity"
                }
            },
            "required": ["item_code", "quantity"]
        }
    },
    {
        "name": "get_low_stock_items",
        "description": "Identify all material stocks falling below safety threshold that risk halting construction or installation workflows.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "threshold_multiplier": {
                    "type": "number",
                    "description": "Safety threshold multiplier (default 1.0; 1.5 checks items near warning levels)"
                }
            }
        }
    }
]

def handle_call_tool(name: str, args: dict) -> dict:
    if name == "get_inventory":
        cat = args.get("category")
        wh = args.get("warehouse_id")
        results = INVENTORY_DATABASE
        if cat:
            results = [i for i in results if cat.lower() in i["category"].lower()]
        if wh:
            results = [i for i in results if wh.lower() in i["warehouse_id"].lower()]
        return {"total_count": len(results), "items": results}

    elif name == "check_stock_availability":
        code = args.get("item_code", "").strip().upper()
        req_qty = float(args.get("quantity", 0))
        item = next((i for i in INVENTORY_DATABASE if i["item_code"] == code), None)
        if not item:
            return {"error": f"Item '{code}' not recognized in central inventory database."}
        
        is_avail = item["available_stock"] >= req_qty
        deficit = max(0.0, req_qty - item["available_stock"])
        return {
            "item_code": code,
            "description": item["description"],
            "warehouse_id": item["warehouse_id"],
            "requested_quantity": req_qty,
            "available_stock": item["available_stock"],
            "is_available": is_avail,
            "deficit": deficit,
            "lead_time_days": item["lead_time_days"] if not is_avail else 0,
            "status": "APPROVED_FOR_DISPATCH" if is_avail else "STOCK_SHORTAGE_BACKORDER_REQUIRED"
        }

    elif name == "get_low_stock_items":
        mult = float(args.get("threshold_multiplier", 1.0))
        low = []
        for i in INVENTORY_DATABASE:
            limit = i["safety_stock"] * mult
            if i["stock_on_hand"] <= limit:
                low.append({
                    "item_code": i["item_code"],
                    "description": i["description"],
                    "warehouse_id": i["warehouse_id"],
                    "stock_on_hand": i["stock_on_hand"],
                    "safety_stock": i["safety_stock"],
                    "available_stock": i["available_stock"],
                    "deficit": round(limit - i["stock_on_hand"], 2),
                    "status": i["status"],
                    "lead_time_days": i["lead_time_days"]
                })
        return {
            "low_stock_items_count": len(low),
            "threshold_multiplier_used": mult,
            "items": low
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
                            "name": "Inventory MCP Server",
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
                                "uri": "inventory://safety-stock/matrix",
                                "name": "Central Warehouse Safety Stock Matrix",
                                "description": "Minimum threshold multipliers by material category.",
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
                                "name": "check_low_stock_materials",
                                "description": "Identify all construction supplies below safety thresholds.",
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
