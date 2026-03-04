import os
from mcp.server.fastmcp import FastMCP
from utils.tool_loader import register_tools

mcp = FastMCP("sre-ssh-server", host="0.0.0.0", port=8000)

# Register tools from YAML
tools_path = os.path.join(os.path.dirname(__file__), "tools", "tools.yaml")
register_tools(mcp, tools_path)

if __name__ == "__main__":
    # Start the server using SSE transport
    mcp.run(transport="sse")
