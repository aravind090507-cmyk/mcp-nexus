import subprocess
import json
import sys
import os

def test_server(name, script_path, test_tool, test_args):
    print(f"=== Testing {name} ===")
    assert os.path.exists(script_path), f"{script_path} does not exist"
    proc = subprocess.Popen(
        [sys.executable, script_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1
    )

    def send_req(req):
        line = json.dumps(req) + "\n"
        proc.stdin.write(line)
        proc.stdin.flush()
        if "id" in req:
            resp_line = proc.stdout.readline()
            return json.loads(resp_line.strip())
        return None

    init_res = send_req({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    })
    print("1. Init Result:", init_res["result"]["serverInfo"], "Protocol:", init_res["result"]["protocolVersion"])
    assert init_res["result"]["protocolVersion"] == "2024-11-05"

    send_req({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
    print("2. Initialized notification sent.")

    ping_res = send_req({"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}})
    print("3. Ping Result:", ping_res)

    tools_res = send_req({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}})
    tools = tools_res["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    print(f"4. Discovered {len(tools)} tools: {tool_names}")

    res_res = send_req({"jsonrpc": "2.0", "id": 4, "method": "resources/list", "params": {}})
    print(f"5. Discovered {len(res_res['result']['resources'])} resources")

    prompts_res = send_req({"jsonrpc": "2.0", "id": 5, "method": "prompts/list", "params": {}})
    print(f"6. Discovered {len(prompts_res['result']['prompts'])} prompts")

    call_res = send_req({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {"name": test_tool, "arguments": test_args}
    })
    text_content = call_res["result"]["content"][0]["text"]
    parsed = json.loads(text_content)
    print(f"7. Executed {test_tool}: result keys={list(parsed.keys())}")

    proc.terminate()
    proc.wait(timeout=2)
    print(f"8. Clean shutdown complete (exit code: {proc.returncode})\n")

if __name__ == "__main__":
    base = os.path.abspath("backend/app/mcp/demo_servers")
    test_server("ERP Server", os.path.join(base, "erp_server.py"), "get_project_status", {})
    test_server("Equipment Server", os.path.join(base, "equipment_server.py"), "get_maintenance_schedule", {"overdue_only": True})
    test_server("Inventory Server", os.path.join(base, "inventory_server.py"), "get_low_stock_items", {"threshold_multiplier": 1.0})
