from fastapi import APIRouter

from app.mcp.models import McpToolCall
from app.mcp.server import McpToolServer

router = APIRouter(tags=["dev-mcp"])
server = McpToolServer()


@router.get("/dev/mcp/tools")
def dev_mcp_tools() -> list[dict]:
    return server.list_tools()


@router.post("/dev/mcp/call")
def dev_mcp_call(call: McpToolCall):
    return server.call_tool(call)
