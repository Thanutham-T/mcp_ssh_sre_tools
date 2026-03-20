"""
Bitwarden Secrets Manager (BWS) Utilities

Fetches secrets (e.g. SSH private keys) from Bitwarden Secrets Manager
using the bitwarden-sdk.  Configuration is read from environment variables
(loaded via python-dotenv).

Required environment variables:
    BWS_ACCESS_TOKEN   — Bitwarden machine account access token
    SSH_KEY_SECRET_ID  — UUID of the secret that holds the SSH private key
"""

import logging
import os

from bitwarden_sdk import BitwardenClient, ClientSettings
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_ssh_key_from_bws() -> str | None:
    """Return the SSH private key stored in Bitwarden Secrets Manager.

    Returns:
        The secret value (private key string) on success, or ``None`` when
        the required environment variables are missing or the lookup fails.
    """
    access_token = os.getenv("BWS_ACCESS_TOKEN")
    secret_id = os.getenv("SSH_KEY_SECRET_ID")

    if not access_token or not secret_id:
        logger.warning(
            "BWS_ACCESS_TOKEN or SSH_KEY_SECRET_ID not set — skipping Bitwarden lookup."
        )
        return None

    try:
        client = BitwardenClient(ClientSettings())
        client.auth().login_access_token(access_token)
        response = client.secrets().get(secret_id)

        if response.success:
            logger.info("SSH key retrieved successfully from Bitwarden.")
            return response.data.value

        logger.error("Bitwarden secret fetch failed: %s", response.error_message)
        return None

    except Exception:
        logger.exception("Unexpected error while connecting to Bitwarden.")
        return None
