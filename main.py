"""
MCP SRE SSH Tools — Entry Point

Starts the FastMCP server and registers all tools defined in tools/tools.yaml.
Transport: SSE (Server-Sent Events) on host 0.0.0.0:8000
"""

import logging
import os

from mcp.server.fastmcp import FastMCP

from utils.tool_loader import register_tools

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
mcp = FastMCP("sre-ssh-server", host="0.0.0.0", port=8000)

_tools_yaml = os.path.join(os.path.dirname(__file__), "tools", "tools.yaml")
register_tools(mcp, _tools_yaml)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting MCP SRE SSH server (SSE transport) on port 8000…")
    mcp.run(transport="sse")
