"""
SSH Client

Provides a single async helper — ``run_ssh_command`` — that opens an SSH
connection to a remote host, runs a shell command, and returns the output.

Authentication priority (first available wins):
    1. SSH_KEY env var  — PEM-encoded private key (any Paramiko-supported type)
    2. Bitwarden BWS    — fetched via bw_utils.get_ssh_key_from_bws()
    3. SSH_PASSWORD env var / ``password`` argument
    4. System SSH agent / user's ~/.ssh keys  (fallback when no key/password)
"""

import logging
import os
from io import StringIO

import paramiko

from utils.bw_utils import get_ssh_key_from_bws

logger = logging.getLogger(__name__)

# Default values — can be overridden per-call or via environment variables
_DEFAULT_USERNAME = "sre-agent"
_DEFAULT_PORT = 22
_CONNECT_TIMEOUT = 15  # seconds


def _load_private_key(key_string: str) -> paramiko.PKey | None:
    """Try to load a PEM private key from a string, trying common key types.

    Paramiko requires knowing the key type upfront; we attempt each type in
    order and return the first one that succeeds.  Returns ``None`` if the
    string cannot be parsed as any known key type.
    """
    key_classes = [
        paramiko.RSAKey,
        paramiko.Ed25519Key,
        paramiko.ECDSAKey,
    ]
    for cls in key_classes:
        try:
            return cls.from_private_key(StringIO(key_string))
        except Exception:
            continue

    logger.warning("Could not parse the private key — falling back to password auth.")
    return None


async def run_ssh_command(
    host: str,
    command: str,
    port: int = _DEFAULT_PORT,
    username: str = _DEFAULT_USERNAME,
    password: str | None = None,
) -> dict:
    """Connect to *host* via SSH and run *command*, returning the output.

    Args:
        host:     Target hostname or IP.  Supports ``host:port`` notation,
                  which takes precedence over the *port* argument.
        command:  Shell command to execute on the remote host.
        port:     SSH port (default 22).  Ignored when *host* contains ``:``.
        username: Remote user (default ``sre-agent``).
        password: Optional password.  Falls back to ``SSH_PASSWORD`` env var.

    Returns:
        A dictionary containing:
        - tool_result: "success" or "fail"
        - command_result: stdout/stderr output or error message
    """
    # ── Resolve host:port shorthand ──────────────────────────────────────────
    if ":" in host:
        host, port_str = host.split(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            logger.warning(
                "Invalid port '%s' in host string — using default %d.", port_str, port
            )

    # ── Gather credentials ───────────────────────────────────────────────────
    key_string = os.getenv("SSH_KEY") or get_ssh_key_from_bws()
    password = password or os.getenv("SSH_PASSWORD")

    pkey = _load_private_key(key_string) if key_string else None

    # ── Connect & execute ────────────────────────────────────────────────────
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            pkey=pkey,
            password=password,
            timeout=_CONNECT_TIMEOUT,
            look_for_keys=pkey is None,  # use agent/~/.ssh only when no explicit key
        )
        logger.debug("SSH connected to %s:%d as %s", host, port, username)

        stdin, stdout, stderr = client.exec_command(command)

        # stdout.read() and stderr.read() block until the command finishes
        output = stdout.read().decode()
        error = stderr.read().decode()
        exit_status = stdout.channel.recv_exit_status()

        # Combine stdout and stderr for the final response
        full_output = output
        if error:
            if full_output and not full_output.endswith("\n"):
                full_output += "\n"
            full_output += error

        if exit_status == 0:
            return {"tool_result": "success", "command_result": full_output}
        else:
            logger.warning(
                "SSH command failed (exit code %d) on %s: %s",
                exit_status,
                host,
                error.strip(),
            )
            return {"tool_result": "fail", "command_result": full_output}

    except paramiko.AuthenticationException:
        msg = (
            f"SSH Authentication Failed: check credentials for {username}@{host}:{port}"
        )
        logger.error(msg)
        return {"tool_result": "fail", "command_result": msg}
    except paramiko.SSHException as exc:
        msg = f"SSH Error: {exc}"
        logger.error("SSH error on %s:%d — %s", host, port, exc)
        return {"tool_result": "fail", "command_result": msg}
    except OSError as exc:
        msg = f"Connection Error: {exc}"
        logger.error("Network error connecting to %s:%d — %s", host, port, exc)
        return {"tool_result": "fail", "command_result": msg}
    finally:
        client.close()
