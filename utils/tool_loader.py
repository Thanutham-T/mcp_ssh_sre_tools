"""
Tool Loader

Reads tool definitions from a YAML file and dynamically registers each one
as a FastMCP tool with a properly-typed handler signature.

YAML schema (each item under ``tools:``):
    name        (str)  — tool identifier exposed to the LLM
    description (str)  — human-readable description shown to the LLM
    command     (str)  — shell command template; use {placeholder} for args
    category    (str)  — "read" (default) | "execute"
                         "execute" tools are prefixed with an approval notice

Dynamic parameters:
    Every ``{placeholder}`` found in the command template (except ``host`` and
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


def _make_handler(cmd_template: str, placeholders: list[str]):
    """Return an async handler function whose signature matches *placeholders*.

    The handler replaces ``{placeholder}`` tokens in *cmd_template* with the
    values supplied at call time, then delegates to ``run_ssh_command``.

    A custom ``__signature__`` is attached so that FastMCP can derive the
    correct JSON schema to expose to the LLM.
    """

    async def handler(host: str, port: int = 22, **kwargs) -> str:
        # Build the substitution context
        context = {"host": host, "port": port, **kwargs}

        # Replace each {placeholder} in the template (avoids str.format issues
        # with shell characters like { } in the surrounding command text)
        command = cmd_template
        for key, value in context.items():
            command = command.replace(f"{{{key}}}", str(value))

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

    for name in placeholders:
        if name not in ("host", "port"):
            params.append(
                inspect.Parameter(
                    name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str
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
        placeholders = re.findall(r"\{(\w+)\}", cmd_template)

        handler = _make_handler(cmd_template, placeholders)
        mcp.tool(name=name, description=description)(handler)

        logger.debug(
            "Registered tool '%s' (placeholders: %s)", name, placeholders or "none"
        )
