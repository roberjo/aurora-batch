"""Tests for Vault client."""

import unittest
from unittest.mock import MagicMock, patch

import hvac
import requests

from src.vault_client import VaultClient


class TestVaultClient(unittest.TestCase):
    """Test cases for VaultClient."""

    def setUp(self):
        """Set up test fixtures."""
        self.vault_addr = "https://vault.example.com"
        self.vault_role = "test-role"
        self.client = VaultClient(self.vault_addr, self.vault_role)

    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.client.vault_addr, self.vault_addr)
        self.assertEqual(self.client.vault_role, self.vault_role)
        self.assertIsInstance(self.client.client, hvac.Client)

    @patch('src.vault_client.requests.post')
    @patch('src.vault_client.get_credentials')
    def test_authenticate_iam_success(self, mock_get_creds, mock_post):
        """Test successful IAM authentication."""
        mock_creds = MagicMock()
        mock_get_creds.return_value = mock_creds
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'auth': {'client_token': 'test-token'}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        self.client.authenticate_iam()
        
        self.assertTrue(self.client._authenticated)
        self.assertEqual(self.client.client.token, 'test-token')

    def test_authenticate_iam_no_role(self):
        """Test IAM authentication without role."""
        client = VaultClient(self.vault_addr, None)
        
        with self.assertRaises(ValueError):
            client.authenticate_iam()

    @patch.object(hvac.Client, 'is_authenticated')
    def test_authenticate_token_success(self, mock_is_auth):
        """Test successful token authentication."""
        mock_is_auth.return_value = True
        
        self.client.authenticate_token('test-token')
        
        self.assertTrue(self.client._authenticated)
        self.assertEqual(self.client.client.token, 'test-token')

    @patch.object(hvac.Client, 'is_authenticated')
    def test_authenticate_token_failure(self, mock_is_auth):
        """Test token authentication failure."""
        mock_is_auth.return_value = False
        
        with self.assertRaises(ValueError):
            self.client.authenticate_token('invalid-token')

    @patch.object(hvac.Client, 'secrets')
    def test_get_secret_kv_v2(self, mock_secrets):
        """Test getting secret from KV v2."""
        self.client._authenticated = True
        mock_kv = MagicMock()
        mock_kv.v2.read_secret_version.return_value = {
            'data': {'data': {'key': 'value'}}
        }
        mock_secrets.kv = mock_kv
        
        result = self.client.get_secret('secret/test')
        
        self.assertEqual(result, {'key': 'value'})

    @patch.object(hvac.Client, 'secrets')
    def test_get_secret_kv_v1(self, mock_secrets):
        """Test getting secret from KV v1."""
        self.client._authenticated = True
        mock_kv = MagicMock()
        mock_kv.v2.read_secret_version.side_effect = Exception("Not found")
        mock_kv.v1.read_secret.return_value = {'data': {'key': 'value'}}
        mock_secrets.kv = mock_kv
        
        result = self.client.get_secret('secret/test')
        
        self.assertEqual(result, {'key': 'value'})

    def test_get_secret_not_authenticated(self):
        """Test getting secret without authentication."""
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ValueError):
                self.client.get_secret('secret/test')


if __name__ == '__main__':
    unittest.main()

