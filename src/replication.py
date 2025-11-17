"""Core replication logic for Aurora to Snowflake."""

import logging
from typing import Dict, List, Optional

from .aurora_client import AuroraClient
from .snowflake_client import SnowflakeClient
from .utils import log_event

logger = logging.getLogger(__name__)


class ReplicationEngine:
    """Engine for replicating data from Aurora to Snowflake."""

    def __init__(self, aurora_client: AuroraClient, snowflake_client: SnowflakeClient):
        """
        Initialize replication engine.

        Args:
            aurora_client: Aurora PostgreSQL client
            snowflake_client: Snowflake client
        """
        self.aurora_client = aurora_client
        self.snowflake_client = snowflake_client

    def replicate_table(self, schema_name: str, table_name: str,
                       replication_mode: str = 'full',
                       incremental_column: Optional[str] = None,
                       last_value: Optional[any] = None,
                       batch_size: int = 10000,
                       correlation_id: str = '') -> Dict[str, any]:
        """
        Replicate a table from Aurora to Snowflake.

        Args:
            schema_name: Schema name
            table_name: Table name
            replication_mode: 'full' or 'incremental'
            incremental_column: Column name for incremental extraction
            last_value: Last processed value for incremental mode
            batch_size: Number of rows to process per batch
            correlation_id: Correlation ID for logging

        Returns:
            Dictionary with replication results
        """
        log_event('INFO', f'Starting replication for {schema_name}.{table_name}', 
                 correlation_id, mode=replication_mode)

        try:
            # Get table schema from Aurora
            log_event('INFO', f'Retrieving schema for {schema_name}.{table_name}', correlation_id)
            schema = self.aurora_client.get_table_schema(schema_name, table_name)
            
            if not schema:
                raise ValueError(f"Table {schema_name}.{table_name} not found in Aurora")

            # Create table in Snowflake if it doesn't exist
            log_event('INFO', f'Creating/verifying table in Snowflake: {schema_name}.{table_name}', 
                     correlation_id)
            self.snowflake_client.create_table_if_not_exists(schema_name, table_name, schema)

            # Determine if we should truncate (full mode only)
            truncate = replication_mode == 'full'

            # Extract and load data in batches
            total_rows = 0
            rows_processed = 0
            max_value = last_value

            while True:
                # Extract batch from Aurora
                log_event('INFO', f'Extracting batch from Aurora (offset: {rows_processed})', 
                         correlation_id)
                
                batch_data = self.aurora_client.extract_table_data(
                    schema_name=schema_name,
                    table_name=table_name,
                    incremental_column=incremental_column if replication_mode == 'incremental' else None,
                    last_value=max_value if replication_mode == 'incremental' else None,
                    batch_size=batch_size
                )

                if not batch_data:
                    break

                # Load batch into Snowflake
                log_event('INFO', f'Loading {len(batch_data)} rows into Snowflake', correlation_id)
                
                # Truncate only on first batch in full mode
                should_truncate = truncate and rows_processed == 0
                rows_inserted = self.snowflake_client.load_data_batch(
                    schema_name=schema_name,
                    table_name=table_name,
                    data=batch_data,
                    truncate=should_truncate
                )

                rows_processed += len(batch_data)
                total_rows += rows_inserted

                # Update max value for incremental mode
                if incremental_column and batch_data:
                    max_value = max(row.get(incremental_column) for row in batch_data 
                                  if incremental_column in row and row[incremental_column] is not None)

                log_event('INFO', f'Processed batch: {len(batch_data)} rows', 
                         correlation_id, total_rows=rows_processed)

                # If we got fewer rows than batch_size, we're done
                if len(batch_data) < batch_size:
                    break

            log_event('INFO', f'Replication completed for {schema_name}.{table_name}', 
                     correlation_id, total_rows=total_rows)

            return {
                'success': True,
                'schema': schema_name,
                'table': table_name,
                'rows_replicated': total_rows,
                'last_value': max_value if incremental_column else None
            }

        except Exception as e:
            log_event('ERROR', f'Replication failed for {schema_name}.{table_name}: {str(e)}', 
                     correlation_id)
            raise

