import os
from io import StringIO
import paramiko

async def run_ssh_command(host: str, command: str, port: int = 22) -> str:
    """Connects via SSH and runs a command."""
    key_string = os.getenv("SSH_KEY")
    
    # Handle host:port format
    if ":" in host:
        host, port_str = host.split(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            pass

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Load key from memory (StringIO)
    pkey = paramiko.RSAKey.from_private_key(StringIO(key_string))

    try:
        # Connect as the dedicated 'sre-agent' user
        client.connect(hostname=host, port=port, username="sre-agent", pkey=pkey, timeout=15)
        stdin, stdout, stderr = client.exec_command(command)

        result = stdout.read().decode()
        error = stderr.read().decode()
        
        return result if result else f"Error: {error}"
    except Exception as e:
        return f"SSH Connection Failed: {str(e)}"
    finally:
        client.close()