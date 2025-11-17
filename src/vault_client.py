"""Hashicorp Vault client for retrieving secrets."""

import json
import logging
import os
from typing import Dict, Optional

import hvac
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import get_credentials

logger = logging.getLogger(__name__)


class VaultClient:
    """Client for interacting with Hashicorp Vault."""

    def __init__(self, vault_addr: str, vault_role: Optional[str] = None):
        """
        Initialize Vault client.

        Args:
            vault_addr: Vault server address
            vault_role: IAM role for Vault authentication (optional)
        """
        self.vault_addr = vault_addr.rstrip('/')
        self.vault_role = vault_role
        self.client = hvac.Client(url=self.vault_addr)
        self._authenticated = False

    def authenticate_iam(self) -> None:
        """Authenticate to Vault using AWS IAM."""
        if not self.vault_role:
            raise ValueError("Vault role is required for IAM authentication")

        try:
            # Get AWS credentials
            credentials = get_credentials()
            if not credentials:
                raise ValueError("Unable to retrieve AWS credentials")

            # Create IAM request
            request = AWSRequest(
                method='POST',
                url=f"{self.vault_addr}/v1/auth/aws/login",
                data=json.dumps({"role": self.vault_role})
            )
            SigV4Auth(credentials, 'sts', 'us-east-1').add_auth(request)

            # Prepare headers
            headers = dict(request.headers)
            headers['Content-Type'] = 'application/json'

            # Make request
            response = requests.post(
                f"{self.vault_addr}/v1/auth/aws/login",
                headers=headers,
                data=json.dumps({"role": self.vault_role}),
                timeout=10
            )
            response.raise_for_status()

            auth_data = response.json()
            self.client.token = auth_data['auth']['client_token']
            self._authenticated = True
            logger.info("Successfully authenticated to Vault using IAM")

        except Exception as e:
            logger.error(f"Failed to authenticate to Vault using IAM: {str(e)}")
            raise

    def authenticate_token(self, token: str) -> None:
        """Authenticate to Vault using a token."""
        self.client.token = token
        try:
            if self.client.is_authenticated():
                self._authenticated = True
                logger.info("Successfully authenticated to Vault using token")
            else:
                raise ValueError("Invalid Vault token")
        except Exception as e:
            logger.error(f"Failed to authenticate to Vault using token: {str(e)}")
            raise

    def get_secret(self, path: str) -> Dict[str, any]:
        """
        Retrieve a secret from Vault.

        Args:
            path: Vault secret path (e.g., 'secret/aurora/connection')

        Returns:
            Dictionary containing secret data
        """
        if not self._authenticated:
            # Try to authenticate using token from environment
            token = os.getenv('VAULT_TOKEN')
            if token:
                self.authenticate_token(token)
            elif self.vault_role:
                self.authenticate_iam()
            else:
                raise ValueError("Not authenticated to Vault and no authentication method available")

        try:
            # Handle KV v1 and v2
            if path.startswith('secret/data/'):
                # KV v2
                response = self.client.secrets.kv.v2.read_secret_version(path=path.replace('secret/data/', ''))
                return response['data']['data']
            elif path.startswith('secret/'):
                # Try KV v2 first
                try:
                    kv2_path = path.replace('secret/', '')
                    response = self.client.secrets.kv.v2.read_secret_version(path=kv2_path)
                    return response['data']['data']
                except Exception:
                    # Fall back to KV v1
                    response = self.client.secrets.kv.v1.read_secret(path=path)
                    return response['data']
            else:
                # Direct path
                response = self.client.read(path)
                if response and 'data' in response:
                    return response['data']
                raise ValueError(f"Secret not found at path: {path}")

        except Exception as e:
            logger.error(f"Failed to retrieve secret from path {path}: {str(e)}")
            raise

