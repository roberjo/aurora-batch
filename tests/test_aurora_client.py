"""Tests for Aurora client."""

import unittest
from unittest.mock import MagicMock, patch

import psycopg2
from psycopg2.extras import RealDictCursor

from src.aurora_client import AuroraClient


class TestAuroraClient(unittest.TestCase):
    """Test cases for AuroraClient."""

    def setUp(self):
        """Set up test fixtures."""
        self.connection_params = {
            'host': 'test-host',
            'port': 5432,
            'database': 'testdb',
            'user': 'testuser',
            'password': 'testpass'
        }
        self.client = AuroraClient(self.connection_params)

    @patch('src.aurora_client.psycopg2.connect')
    def test_connect_success(self, mock_connect):
        """Test successful connection."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        self.client.connect()
        
        mock_connect.assert_called_once()
        self.assertEqual(self.client.connection, mock_conn)

    @patch('src.aurora_client.psycopg2.connect')
    def test_connect_failure(self, mock_connect):
        """Test connection failure."""
        mock_connect.side_effect = psycopg2.Error("Connection failed")
        
        with self.assertRaises(psycopg2.Error):
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

    @patch('src.aurora_client.RealDictCursor')
    def test_execute_query_success(self, mock_cursor_class):
        """Test successful query execution."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)
        mock_cursor.fetchall.return_value = [{'id': 1, 'name': 'test'}]
        mock_conn.cursor.return_value = mock_cursor
        self.client.connection = mock_conn
        
        result = self.client.execute_query("SELECT * FROM test")
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 1)

    def test_get_table_schema(self):
        """Test getting table schema."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)
        mock_cursor.fetchall.return_value = [
            {
                'column_name': 'id',
                'data_type': 'integer',
                'character_maximum_length': None,
                'is_nullable': 'NO',
                'column_default': None
            }
        ]
        mock_conn.cursor.return_value = mock_cursor
        self.client.connection = mock_conn
        
        schema = self.client.get_table_schema('public', 'test')
        
        self.assertEqual(len(schema), 1)
        self.assertEqual(schema[0]['column_name'], 'id')

    def test_get_table_count(self):
        """Test getting table count."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)
        mock_cursor.fetchall.return_value = [{'count': 100}]
        mock_conn.cursor.return_value = mock_cursor
        self.client.connection = mock_conn
        
        count = self.client.get_table_count('public', 'test')
        
        self.assertEqual(count, 100)

    def test_extract_table_data(self):
        """Test extracting table data."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)
        mock_cursor.fetchall.return_value = [{'id': 1, 'name': 'test'}]
        mock_conn.cursor.return_value = mock_cursor
        self.client.connection = mock_conn
        
        data = self.client.extract_table_data('public', 'test', batch_size=10)
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], 1)


if __name__ == '__main__':
    unittest.main()

