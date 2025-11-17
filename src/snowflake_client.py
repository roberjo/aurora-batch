"""Snowflake client for data loading."""

import logging
from typing import Dict, List, Optional

import snowflake.connector
from snowflake.connector import DictCursor

logger = logging.getLogger(__name__)


class SnowflakeClient:
    """Client for connecting to Snowflake."""

    def __init__(self, connection_params: Dict[str, str]):
        """
        Initialize Snowflake client.

        Args:
            connection_params: Dictionary with connection parameters:
                - account: Snowflake account identifier
                - user: Username
                - password: Password
                - warehouse: Warehouse name
                - database: Database name
                - schema: Schema name
                - role: Role name (optional)
                - private_link_url: PrivateLink endpoint URL (optional)
        """
        self.connection_params = connection_params
        self.connection = None

    def connect(self) -> None:
        """Establish connection to Snowflake."""
        try:
            conn_params = {
                'account': self.connection_params['account'],
                'user': self.connection_params['user'],
                'password': self.connection_params['password'],
                'warehouse': self.connection_params['warehouse'],
                'database': self.connection_params['database'],
                'schema': self.connection_params.get('schema', 'PUBLIC'),
            }

            # Add role if provided
            if 'role' in self.connection_params:
                conn_params['role'] = self.connection_params['role']

            # Use PrivateLink URL if provided
            if 'private_link_url' in self.connection_params:
                conn_params['host'] = self.connection_params['private_link_url']

            self.connection = snowflake.connector.connect(**conn_params)
            logger.info(f"Successfully connected to Snowflake account {self.connection_params['account']}")
        except Exception as e:
            logger.error(f"Failed to connect to Snowflake: {str(e)}")
            raise

    def disconnect(self) -> None:
        """Close connection to Snowflake."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Disconnected from Snowflake")

    def execute_query(self, query: str, params: Optional[List] = None) -> List[Dict[str, any]]:
        """
        Execute a query and return results.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of dictionaries representing rows
        """
        if not self.connection:
            raise ValueError("Not connected to Snowflake. Call connect() first.")

        try:
            cursor = self.connection.cursor(DictCursor)
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            return results
        except Exception as e:
            logger.error(f"Failed to execute query: {str(e)}")
            raise

    def create_table_if_not_exists(self, schema_name: str, table_name: str, 
                                   columns: List[Dict[str, str]]) -> None:
        """
        Create table if it doesn't exist based on Aurora schema.

        Args:
            schema_name: Schema name
            table_name: Table name
            columns: List of column definitions from Aurora schema
        """
        if not self.connection:
            raise ValueError("Not connected to Snowflake. Call connect() first.")

        # Map PostgreSQL types to Snowflake types
        type_mapping = {
            'integer': 'NUMBER',
            'bigint': 'NUMBER',
            'smallint': 'NUMBER',
            'numeric': 'NUMBER',
            'decimal': 'NUMBER',
            'real': 'FLOAT',
            'double precision': 'FLOAT',
            'character varying': 'VARCHAR',
            'varchar': 'VARCHAR',
            'character': 'VARCHAR',
            'char': 'VARCHAR',
            'text': 'VARCHAR',
            'timestamp without time zone': 'TIMESTAMP_NTZ',
            'timestamp with time zone': 'TIMESTAMP_TZ',
            'date': 'DATE',
            'time': 'TIME',
            'boolean': 'BOOLEAN',
            'json': 'VARIANT',
            'jsonb': 'VARIANT',
            'uuid': 'VARCHAR',
        }

        column_definitions = []
        for col in columns:
            pg_type = col['data_type'].lower()
            sf_type = type_mapping.get(pg_type, 'VARCHAR')
            
            # Handle character length
            if 'character_maximum_length' in col and col['character_maximum_length']:
                if sf_type == 'VARCHAR':
                    sf_type = f"VARCHAR({col['character_maximum_length']})"
            
            nullable = 'NULL' if col.get('is_nullable') == 'YES' else 'NOT NULL'
            column_definitions.append(f'"{col["column_name"]}" {sf_type} {nullable}')

        create_table_query = f'''
            CREATE TABLE IF NOT EXISTS "{schema_name}"."{table_name}" (
                {', '.join(column_definitions)}
            )
        '''

        try:
            cursor = self.connection.cursor()
            cursor.execute(create_table_query)
            cursor.close()
            logger.info(f"Created or verified table {schema_name}.{table_name}")
        except Exception as e:
            logger.error(f"Failed to create table {schema_name}.{table_name}: {str(e)}")
            raise

    def load_data_batch(self, schema_name: str, table_name: str, 
                       data: List[Dict[str, any]], 
                       truncate: bool = False) -> int:
        """
        Load data into Snowflake table using INSERT statements.
        Note: For large batches, use load_from_s3() instead.

        Args:
            schema_name: Schema name
            table_name: Table name
            data: List of dictionaries representing rows
            truncate: Whether to truncate table before loading

        Returns:
            Number of rows inserted
        """
        if not self.connection:
            raise ValueError("Not connected to Snowflake. Call connect() first.")

        if not data:
            logger.warning("No data to load")
            return 0

        try:
            cursor = self.connection.cursor()

            if truncate:
                cursor.execute(f'TRUNCATE TABLE "{schema_name}"."{table_name}"')

            # Get column names from first row
            columns = list(data[0].keys())
            placeholders = ', '.join(['%s'] * len(columns))
            column_names = ', '.join([f'"{col}"' for col in columns])

            insert_query = f'INSERT INTO "{schema_name}"."{table_name}" ({column_names}) VALUES ({placeholders})'

            # Prepare values
            values = [[row.get(col) for col in columns] for row in data]

            # Execute batch insert
            cursor.executemany(insert_query, values)
            rows_inserted = cursor.rowcount
            cursor.close()

            logger.info(f"Inserted {rows_inserted} rows into {schema_name}.{table_name}")
            return rows_inserted

        except Exception as e:
            logger.error(f"Failed to load data into Snowflake: {str(e)}")
            raise

    def load_from_s3(self, schema_name: str, table_name: str,
                     s3_bucket: str, s3_key: str,
                     storage_integration: Optional[str] = None,
                     file_format: str = 'csv',
                     truncate: bool = False,
                     on_error: str = 'ABORT_STATEMENT') -> int:
        """
        Load data from S3 into Snowflake table using COPY INTO.

        Args:
            schema_name: Schema name
            table_name: Table name
            s3_bucket: S3 bucket name
            s3_key: S3 key/path of file
            storage_integration: Snowflake storage integration name (optional)
            file_format: File format ('csv' or 'parquet')
            truncate: Whether to truncate table before loading
            on_error: Error handling ('ABORT_STATEMENT', 'SKIP_FILE', 'CONTINUE')

        Returns:
            Number of rows loaded
        """
        if not self.connection:
            raise ValueError("Not connected to Snowflake. Call connect() first.")

        try:
            cursor = self.connection.cursor()

            if truncate:
                cursor.execute(f'TRUNCATE TABLE "{schema_name}"."{table_name}"')

            # Build S3 path
            s3_path = f"s3://{s3_bucket}/{s3_key}"

            # Build COPY INTO command
            if storage_integration:
                copy_command = f'''
                    COPY INTO "{schema_name}"."{table_name}"
                    FROM '{s3_path}'
                    STORAGE_INTEGRATION = {storage_integration}
                    FILE_FORMAT = (TYPE = '{file_format.upper()}')
                    ON_ERROR = '{on_error}'
                '''
            else:
                # Use IAM role if storage integration not provided
                # Try to get IAM role from connection params or environment
                iam_role = self.connection_params.get('aws_iam_role')
                if not iam_role:
                    import os
                    iam_role = os.getenv('SNOWFLAKE_AWS_IAM_ROLE')
                
                if not iam_role:
                    raise ValueError(
                        "Either storage_integration or aws_iam_role must be provided. "
                        "Set SNOWFLAKE_AWS_IAM_ROLE environment variable or provide in connection params."
                    )

                copy_command = f'''
                    COPY INTO "{schema_name}"."{table_name}"
                    FROM '{s3_path}'
                    CREDENTIALS = (AWS_IAM_ROLE = '{iam_role}')
                    FILE_FORMAT = (TYPE = '{file_format.upper()}')
                    ON_ERROR = '{on_error}'
                '''

            logger.info(f"Executing COPY INTO from S3: {s3_path}")
            cursor.execute(copy_command)

            # Get load result
            result = cursor.fetchone()
            rows_loaded = result[1] if result else 0  # Second column is usually rows_loaded

            cursor.close()

            logger.info(f"Loaded {rows_loaded} rows from S3 into {schema_name}.{table_name}")
            return rows_loaded

        except Exception as e:
            logger.error(f"Failed to load data from S3 into Snowflake: {str(e)}")
            raise

    def create_external_stage(self, stage_name: str, s3_bucket: str, s3_prefix: str,
                              storage_integration: Optional[str] = None) -> None:
        """
        Create an external stage in Snowflake pointing to S3.

        Args:
            stage_name: Name of the stage
            s3_bucket: S3 bucket name
            s3_prefix: S3 prefix/path
            storage_integration: Snowflake storage integration name (optional)
        """
        if not self.connection:
            raise ValueError("Not connected to Snowflake. Call connect() first.")

        try:
            cursor = self.connection.cursor()

            s3_url = f"s3://{s3_bucket}/{s3_prefix.rstrip('/')}/"

            if storage_integration:
                create_stage = f'''
                    CREATE STAGE IF NOT EXISTS {stage_name}
                    URL = '{s3_url}'
                    STORAGE_INTEGRATION = {storage_integration}
                '''
            else:
                iam_role = self.connection_params.get('aws_iam_role')
                if not iam_role:
                    raise ValueError("Either storage_integration or aws_iam_role must be provided")

                create_stage = f'''
                    CREATE STAGE IF NOT EXISTS {stage_name}
                    URL = '{s3_url}'
                    CREDENTIALS = (AWS_IAM_ROLE = '{iam_role}')
                '''

            cursor.execute(create_stage)
            cursor.close()

            logger.info(f"Created external stage: {stage_name}")

        except Exception as e:
            logger.error(f"Failed to create external stage: {str(e)}")
            raise

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

