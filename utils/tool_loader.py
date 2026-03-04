import yaml
from mcp.server.fastmcp import FastMCP
from .ssh_client import run_ssh_command

def register_tools(mcp: FastMCP, yaml_path: str):
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)

    for tool_def in config["tools"]:
        name = tool_def["name"]
        description = tool_def["description"]
        cmd_template = tool_def["command"]

        # Use a factory function to correctly capture cmd_template in the closure
        def get_handler(template):
            async def create_handler(host: str) -> str:
                # Inject arguments into the command string
                return await run_ssh_command(host, cmd_template)
            return create_handler

        # Register with MCP
        mcp.tool(
            name=name,
            description=description
        )(get_handler(cmd_template))

