import yaml
import re
import inspect
from mcp.server.fastmcp import FastMCP
from .ssh_client import run_ssh_command


def register_tools(mcp: FastMCP, yaml_path: str):
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)

    for tool_def in config["tools"]:
        name = tool_def["name"]
        description = tool_def["description"]
        category = tool_def.get("category", "read")

        cmd_template = tool_def["command"]

        if category == "execute":
            description = (
                f"EXECUTE — Requires user approval before running.\n{description}"
            )

        description = f"{description}\n\nCommand: {cmd_template}"

        # Parse placeholders from the command (e.g., {pid})
        placeholders = re.findall(r"\{(\w+)\}", cmd_template)

        # Factory to capture loop variables correctly
        def create_handler(template, p_holders):
            async def handler(host: str, port: int = 22, **kwargs) -> str:
                # Merge host/port with other keyword arguments
                context = {"host": host, "port": port, **kwargs}

                # Replace placeholders in the command template
                # Manual replacement avoids issues with complex shell characters like {{ }}
                command = template
                for key, val in context.items():
                    command = command.replace("{" + key + "}", str(val))

                # Map potential optional parameters to SSH client
                ssh_args = {"host": host, "command": command, "port": port}
                # Allow overrides for common SSH options if they were passed in kwargs
                for opt in ["username", "password"]:
                    if opt in kwargs:
                        ssh_args[opt] = kwargs[opt]

                return await run_ssh_command(**ssh_args)

            # Build a dynamic signature so FastMCP exposes the correct schema to the LLM
            # Placeholders from the command (like pid) are usually required, so they
            # must come BEFORE arguments with default values (like port=22).
            params = [
                inspect.Parameter(
                    "host", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str
                ),
            ]

            # Map each custom placeholder to a required string argument
            for p in p_holders:
                if p not in ("host", "port"):
                    params.append(
                        inspect.Parameter(
                            p, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str
                        )
                    )

            # Add port last as it has a default value
            params.append(
                inspect.Parameter(
                    "port",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=int,
                    default=22,
                )
            )

            handler.__signature__ = inspect.Signature(params)
            return handler

        # Register the tool with its dynamic handler
        mcp.tool(name=name, description=description)(
            create_handler(cmd_template, placeholders)
        )
