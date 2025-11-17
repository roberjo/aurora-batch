"""Tests for Snowflake client."""

import unittest
from unittest.mock import MagicMock, patch

import snowflake.connector

from src.snowflake_client import SnowflakeClient


class TestSnowflakeClient(unittest.TestCase):
    """Test cases for SnowflakeClient."""

    def setUp(self):
        """Set up test fixtures."""
        self.connection_params = {
            'account': 'test-account',
            'user': 'testuser',
            'password': 'testpass',
            'warehouse': 'TEST_WH',
            'database': 'TEST_DB',
            'schema': 'PUBLIC'
        }
        self.client = SnowflakeClient(self.connection_params)

    @patch('src.snowflake_client.snowflake.connector.connect')
    def test_connect_success(self, mock_connect):
        """Test successful connection."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        self.client.connect()
        
        mock_connect.assert_called_once()
        self.assertEqual(self.client.connection, mock_conn)

    @patch('src.snowflake_client.snowflake.connector.connect')
    def test_connect_failure(self, mock_connect):
        """Test connection failure."""
        mock_connect.side_effect = Exception("Connection failed")
        
        with self.assertRaises(Exception):
            self.client.connect()

    def test_disconnect(self):
        """Test disconnection."""
        self.client.connection = MagicMock()
        self.client.disconnect()
        
        self.assertIsNone(self.client.connection)

    def test_execute_query_not_connected(self):
        """Test query execution without connection."""
        with self.assertRaises(ValueError):
            self.client.execute_query("SELECT 1")

    def test_execute_query_success(self):
        """Test successful query execution."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{'id': 1, 'name': 'test'}]
        mock_conn.cursor.return_value = mock_cursor
        self.client.connection = mock_conn
        
        result = self.client.execute_query("SELECT * FROM test")
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 1)

    def test_create_table_if_not_exists(self):
        """Test creating table."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        self.client.connection = mock_conn
        
        columns = [
            {
                'column_name': 'id',
                'data_type': 'integer',
                'character_maximum_length': None,
                'is_nullable': 'NO',
                'column_default': None
            }
        ]
        
        self.client.create_table_if_not_exists('PUBLIC', 'test', columns)
        
        mock_cursor.execute.assert_called_once()
        mock_cursor.close.assert_called_once()

    def test_load_data_batch(self):
        """Test loading data batch."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 2
        mock_conn.cursor.return_value = mock_cursor
        self.client.connection = mock_conn
        
        data = [
            {'id': 1, 'name': 'test1'},
            {'id': 2, 'name': 'test2'}
        ]
        
        rows_inserted = self.client.load_data_batch('PUBLIC', 'test', data)
        
        self.assertEqual(rows_inserted, 2)
        mock_cursor.executemany.assert_called_once()
        mock_cursor.close.assert_called_once()

    def test_load_data_batch_empty(self):
        """Test loading empty data batch."""
        mock_conn = MagicMock()
        self.client.connection = mock_conn
        
        rows_inserted = self.client.load_data_batch('PUBLIC', 'test', [])
        
        self.assertEqual(rows_inserted, 0)


if __name__ == '__main__':
    unittest.main()

