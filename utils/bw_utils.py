import os
from bitwarden_sdk import BitwardenClient, ClientSettings
from dotenv import load_dotenv

load_dotenv()

def get_ssh_key_from_bws() -> str:
    """Fetches the SSH private key from Bitwarden Secrets Manager."""
    access_token = os.getenv("BWS_ACCESS_TOKEN")
    secret_id = os.getenv("SSH_KEY_SECRET_ID")
    
    if not access_token or not secret_id:
        return None

    try:
        client = BitwardenClient(ClientSettings())
        client.auth().login_access_token(access_token)
        response = client.secrets().get(secret_id)
        if response.success:
            return response.data.value
        else:
            print(f"Failed to get secret from Bitwarden: {response.error_message}")
            return None
    except Exception as e:
        print(f"Error connecting to Bitwarden: {e}")
        return None
