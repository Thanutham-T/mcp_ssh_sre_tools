import os
import paramiko
from io import StringIO
from utils.bw_utils import get_ssh_key_from_bws


async def run_ssh_command(
    host: str,
    command: str,
    port: int = 22,
    username: str = "sre-agent",
    password: str = None,
    **kwargs,
) -> str:
    """Connects via SSH and runs a command."""
    key_string = os.getenv("SSH_KEY")
    if not key_string:
        key_string = get_ssh_key_from_bws()
    password = password or os.getenv("SSH_PASSWORD")

    # Handle host:port format
    if ":" in host:
        host, port_str = host.split(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            pass

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    pkey = None
    if key_string:
        try:
            # Load key from memory (StringIO)
            pkey = paramiko.RSAKey.from_private_key(StringIO(key_string))
        except Exception as e:
            # If key loading fails, we'll try password if available
            pass

    try:
        # Connect using pkey, password, or both
        client.connect(
            hostname=host,
            port=port,
            username=username,
            pkey=pkey,
            password=password,
            timeout=15,
            look_for_keys=False if pkey else True,
        )
        stdin, stdout, stderr = client.exec_command(command, **kwargs)

        result = stdout.read().decode()
        error = stderr.read().decode()

        return result if result else f"Error: {error}"
    except Exception as e:
        return f"SSH Connection Failed: {str(e)}"
    finally:
        client.close()
