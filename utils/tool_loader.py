"""
Tool Loader

Reads tool definitions from a YAML file and dynamically registers each one
as a FastMCP tool with a properly-typed handler signature.

YAML schema (each item under ``tools:``):
    name        (str)  — tool identifier exposed to the LLM
    description (str)  — human-readable description shown to the LLM
    command     (str)  — shell command template; use <placeholder> for args
    category    (str)  — "read" (default) | "execute"
                         "execute" tools are prefixed with an approval notice

Dynamic parameters:
    Every ``<placeholder>`` found in the command template (except ``host`` and
    ``port``, which are always present) becomes a required string argument.
    ``host`` is always required; ``port`` defaults to 22.
"""

import inspect
import logging
import re

import yaml
from mcp.server.fastmcp import FastMCP

from .ssh_client import run_ssh_command

logger = logging.getLogger(__name__)

_EXECUTE_PREFIX = "⚠️ EXECUTE — Requires user approval before running.\n"


def _build_description(tool_def: dict) -> str:
    """Compose the full description shown to the LLM for a given tool."""
    desc = tool_def["description"].strip()
    if tool_def.get("category") == "execute":
        desc = f"{_EXECUTE_PREFIX}{desc}"
    return f"{desc}\n\nCommand: {tool_def['command'].strip()}"


def _make_handler(cmd_template: str, placeholder_map: dict[str, str]):
    """Return an async handler function whose signature matches the values
    in *placeholder_map*.

    The handler replaces tokens in *cmd_template* using the mapping:
    normalized_name -> original_placeholder.

    A custom ``__signature__`` is attached so that FastMCP can derive the
    correct JSON schema to expose to the LLM.
    """

    async def handler(host: str, port: int = 22, **kwargs) -> dict:
        # Build the substitution context (including host and port)
        # and normalize all keys to lowercase for internal mapping
        context = {"host": host, "port": port}
        context.update(kwargs)

        # Perform replacements
        command = cmd_template

        # Replace placeholders using the normalized name map
        # This handles custom placeholders (e.g. <PID>) as well as <host> or <port>
        for norm_name, original_placeholder in placeholder_map.items():
            if norm_name in context:
                command = command.replace(
                    f"<{original_placeholder}>", str(context[norm_name])
                )
        
        # Fallback for explicit <host> and <port> if they weren't in placeholder_map
        # (though they should be if they used the <name> syntax)
        for key in ("host", "port"):
            if f"<{key}>" in command:
                command = command.replace(f"<{key}>", str(context[key]))

        return await run_ssh_command(
            host=host,
            command=command,
            port=port,
            # Pass optional SSH overrides when provided by the caller
            **{k: kwargs[k] for k in ("username", "password") if k in kwargs},
        )

    # Build a typed signature so FastMCP generates the right JSON schema.
    # Required args (no default) must come before optional ones (port=22).
    params = [
        inspect.Parameter(
            "host", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str
        ),
    ]

    for norm_name in placeholder_map:
        if norm_name not in ("host", "port"):
            params.append(
                inspect.Parameter(
                    norm_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str
                )
            )

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


def register_tools(mcp: FastMCP, yaml_path: str) -> None:
    """Load *yaml_path* and register every tool definition with *mcp*.

    Args:
        mcp:       The FastMCP server instance.
        yaml_path: Absolute path to the tools YAML file.

    Raises:
        FileNotFoundError: If *yaml_path* does not exist.
        KeyError:          If the YAML is missing required fields.
    """
    with open(yaml_path) as f:
        config = yaml.safe_load(f)

    tools = config.get("tools", [])
    logger.info("Registering %d tool(s) from %s", len(tools), yaml_path)

    for tool_def in tools:
        name = tool_def["name"]
        cmd_template = tool_def["command"]
        description = _build_description(tool_def)

        # Find all <placeholder> tokens
        raw_placeholders = re.findall(r"<(\w+)>", cmd_template)

        # Create a map from lowercase_name -> original_case_placeholder
        # e.g. {"pid": "PID", "service_name": "SERVICE_NAME"}
        placeholder_map = {}
        for p in raw_placeholders:
            placeholder_map[p.lower()] = p

        handler = _make_handler(cmd_template, placeholder_map)
        mcp.tool(name=name, description=description)(handler)

        logger.debug(
            "Registered tool '%s' (parameters: %s)",
            name,
            list(placeholder_map.keys()) or "none",
        )
