"""Aurora PostgreSQL client for data extraction."""

import logging
from typing import Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class AuroraClient:
    """Client for connecting to Aurora PostgreSQL."""

    def __init__(self, connection_params: Dict[str, str]):
        """
        Initialize Aurora client.

        Args:
            connection_params: Dictionary with connection parameters:
                - host: Aurora endpoint
                - port: Database port (default: 5432)
                - database: Database name
                - user: Username
                - password: Password
        """
        self.connection_params = connection_params
        self.connection = None

    def connect(self) -> None:
        """Establish connection to Aurora PostgreSQL."""
        try:
            self.connection = psycopg2.connect(
                host=self.connection_params['host'],
                port=self.connection_params.get('port', 5432),
                database=self.connection_params['database'],
                user=self.connection_params['user'],
                password=self.connection_params['password'],
                connect_timeout=10,
                sslmode='require'
            )
            logger.info(f"Successfully connected to Aurora PostgreSQL at {self.connection_params['host']}")
        except Exception as e:
            logger.error(f"Failed to connect to Aurora PostgreSQL: {str(e)}")
            raise

    def disconnect(self) -> None:
        """Close connection to Aurora PostgreSQL."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Disconnected from Aurora PostgreSQL")

    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, any]]:
        """
        Execute a SELECT query and return results.

        Args:
            query: SQL query string
            params: Query parameters for parameterized queries

        Returns:
            List of dictionaries representing rows
        """
        if not self.connection:
            raise ValueError("Not connected to database. Call connect() first.")

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                # Convert RealDictRow to regular dict
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to execute query: {str(e)}")
            raise

    def get_table_schema(self, schema_name: str, table_name: str) -> List[Dict[str, any]]:
        """
        Get table schema information.

        Args:
            schema_name: Schema name
            table_name: Table name

        Returns:
            List of dictionaries with column information
        """
        query = """
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        return self.execute_query(query, (schema_name, table_name))

    def get_table_count(self, schema_name: str, table_name: str, 
                       incremental_column: Optional[str] = None,
                       last_value: Optional[any] = None) -> int:
        """
        Get count of rows in table, optionally filtered by incremental column.

        Args:
            schema_name: Schema name
            table_name: Table name
            incremental_column: Column name for incremental filtering
            last_value: Last processed value for incremental mode

        Returns:
            Row count
        """
        query = f'SELECT COUNT(*) as count FROM "{schema_name}"."{table_name}"'
        
        if incremental_column and last_value:
            query += f' WHERE "{incremental_column}" > %s'
            result = self.execute_query(query, (last_value,))
        else:
            result = self.execute_query(query)
        
        return result[0]['count'] if result else 0

    def extract_table_data(self, schema_name: str, table_name: str,
                          incremental_column: Optional[str] = None,
                          last_value: Optional[any] = None,
                          batch_size: int = 10000) -> List[Dict[str, any]]:
        """
        Extract data from a table.

        Args:
            schema_name: Schema name
            table_name: Table name
            incremental_column: Column name for incremental extraction
            last_value: Last processed value for incremental mode
            batch_size: Number of rows to fetch per batch

        Returns:
            List of dictionaries representing rows
        """
        query = f'SELECT * FROM "{schema_name}"."{table_name}"'
        
        if incremental_column and last_value:
            query += f' WHERE "{incremental_column}" > %s ORDER BY "{incremental_column}" LIMIT %s'
            return self.execute_query(query, (last_value, batch_size))
        else:
            query += f' LIMIT %s'
            return self.execute_query(query, (batch_size,))

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

