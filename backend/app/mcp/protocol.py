import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class JSONRPCMessage(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

class ToolDefinition(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]
    risk_level: str = "LOW" # LOW, MEDIUM, HIGH, CRITICAL
    requires_approval: bool = False

def format_jsonrpc_response(req_id: Any, result: Any) -> str:
    return json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result
    })

def format_jsonrpc_error(req_id: Any, code: int, message: str, data: Optional[Any] = None) -> str:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": err
    })
