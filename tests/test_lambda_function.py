"""Tests for Lambda function."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from src.lambda_function import lambda_handler


class TestLambdaFunction(unittest.TestCase):
    """Test cases for Lambda function."""

    def setUp(self):
        """Set up test fixtures."""
        self.event = {
            'schema_name': 'public',
            'table_name': 'test_table'
        }
        self.context = MagicMock()

    @patch.dict(os.environ, {
        'VAULT_ADDR': 'https://vault.example.com',
        'VAULT_SECRET_PATH_AURORA': 'secret/aurora/connection',
        'VAULT_SECRET_PATH_SNOWFLAKE': 'secret/snowflake/credentials',
        'SNOWFLAKE_ENDPOINT': 'snowflake.example.com',
        'REPLICATION_MODE': 'full'
    })
    @patch('src.lambda_function.VaultClient')
    @patch('src.lambda_function.AuroraClient')
    @patch('src.lambda_function.SnowflakeClient')
    @patch('src.lambda_function.ReplicationEngine')
    def test_lambda_handler_success(self, mock_engine_class, mock_sf_client_class,
                                    mock_aurora_client_class, mock_vault_class):
        """Test successful Lambda execution."""
        # Mock Vault client
        mock_vault = MagicMock()
        mock_vault.get_secret.side_effect = [
            {
                'host': 'aurora.example.com',
                'port': 5432,
                'database': 'testdb',
                'user': 'testuser',
                'password': 'testpass'
            },
            {
                'account': 'test-account',
                'user': 'testuser',
                'password': 'testpass',
                'warehouse': 'TEST_WH',
                'database': 'TEST_DB'
            }
        ]
        mock_vault_class.return_value = mock_vault

        # Mock replication engine
        mock_engine = MagicMock()
        mock_engine.replicate_table.return_value = {
            'success': True,
            'rows_replicated': 100
        }
        mock_engine_class.return_value = mock_engine

        # Mock context managers
        mock_aurora_client = MagicMock()
        mock_aurora_client.__enter__ = MagicMock(return_value=mock_aurora_client)
        mock_aurora_client.__exit__ = MagicMock(return_value=None)
        mock_aurora_client_class.return_value = mock_aurora_client

        mock_sf_client = MagicMock()
        mock_sf_client.__enter__ = MagicMock(return_value=mock_sf_client)
        mock_sf_client.__exit__ = MagicMock(return_value=None)
        mock_sf_client_class.return_value = mock_sf_client

        result = lambda_handler(self.event, self.context)

        self.assertEqual(result['statusCode'], 200)
        self.assertIn('correlation_id', result)
        self.assertTrue(result['result']['success'])

    @patch.dict(os.environ, {
        'VAULT_ADDR': 'https://vault.example.com',
        'VAULT_SECRET_PATH_AURORA': 'secret/aurora/connection',
        'VAULT_SECRET_PATH_SNOWFLAKE': 'secret/snowflake/credentials',
        'SNOWFLAKE_ENDPOINT': 'snowflake.example.com'
    })
    def test_lambda_handler_missing_table_name(self):
        """Test Lambda execution with missing table name."""
        event = {'schema_name': 'public'}
        
        result = lambda_handler(event, self.context)
        
        self.assertEqual(result['statusCode'], 500)
        self.assertIn('error', result)

    @patch.dict(os.environ, {}, clear=True)
    def test_lambda_handler_missing_env_vars(self):
        """Test Lambda execution with missing environment variables."""
        result = lambda_handler(self.event, self.context)
        
        self.assertEqual(result['statusCode'], 500)
        self.assertIn('error', result)


if __name__ == '__main__':
    unittest.main()

