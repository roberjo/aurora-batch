"""Core replication logic for Aurora to Snowflake."""

import logging
import os
from typing import Dict, List, Optional

from .aurora_client import AuroraClient
from .s3_client import S3Client
from .snowflake_client import SnowflakeClient
from .utils import log_event

logger = logging.getLogger(__name__)


class ReplicationEngine:
    """Engine for replicating data from Aurora to Snowflake."""

    def __init__(self, aurora_client: AuroraClient, snowflake_client: SnowflakeClient,
                 s3_client: Optional[S3Client] = None):
        """
        Initialize replication engine.

        Args:
            aurora_client: Aurora PostgreSQL client
            snowflake_client: Snowflake client
            s3_client: S3 client for staging (optional, uses S3 if provided)
        """
        self.aurora_client = aurora_client
        self.snowflake_client = snowflake_client
        self.s3_client = s3_client
        self.use_s3_staging = s3_client is not None

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
            batch_number = 0
            s3_files = []

            # Truncate table if full mode (before any processing)
            if truncate:
                log_event('INFO', f'Truncating target table in full mode', correlation_id)
                cursor = self.snowflake_client.connection.cursor()
                cursor.execute(f'TRUNCATE TABLE "{schema_name}"."{table_name}"')
                cursor.close()

            while True:
                # Extract batch from Aurora
                log_event('INFO', f'Extracting batch {batch_number} from Aurora (offset: {rows_processed})', 
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

                if self.use_s3_staging:
                    # Upload batch to S3
                    log_event('INFO', f'Uploading batch {batch_number} ({len(batch_data)} rows) to S3', 
                             correlation_id)
                    s3_key = self.s3_client.upload_batch(
                        data=batch_data,
                        schema_name=schema_name,
                        table_name=table_name,
                        batch_number=batch_number,
                        correlation_id=correlation_id
                    )
                    s3_files.append(s3_key)
                    rows_processed += len(batch_data)
                else:
                    # Load batch directly into Snowflake using INSERT
                    log_event('INFO', f'Loading batch {batch_number} ({len(batch_data)} rows) into Snowflake', 
                             correlation_id)
                    rows_inserted = self.snowflake_client.load_data_batch(
                        schema_name=schema_name,
                        table_name=table_name,
                        data=batch_data,
                        truncate=False  # Already truncated if needed
                    )
                    rows_processed += len(batch_data)
                    total_rows += rows_inserted

                # Update max value for incremental mode
                if incremental_column and batch_data:
                    max_value = max(row.get(incremental_column) for row in batch_data 
                                  if incremental_column in row and row[incremental_column] is not None)

                log_event('INFO', f'Processed batch {batch_number}: {len(batch_data)} rows', 
                         correlation_id, total_rows=rows_processed)

                batch_number += 1

                # If we got fewer rows than batch_size, we're done
                if len(batch_data) < batch_size:
                    break

            # If using S3 staging, load all files into Snowflake
            if self.use_s3_staging and s3_files:
                log_event('INFO', f'Loading {len(s3_files)} files from S3 into Snowflake', 
                         correlation_id)
                
                s3_bucket = os.getenv('S3_STAGE_BUCKET')
                storage_integration = os.getenv('SNOWFLAKE_STORAGE_INTEGRATION', '')
                file_format = os.getenv('S3_FILE_FORMAT', 'csv').lower()
                cleanup_s3 = os.getenv('CLEANUP_S3_FILES', 'false').lower() == 'true'
                cleanup_mode = os.getenv('S3_CLEANUP_MODE', 'after_all').lower()  # 'after_all', 'after_each', 'never'

                successfully_loaded_files = []
                failed_files = []

                # Load files one by one to track success/failure
                for s3_key in s3_files:
                    try:
                        rows_loaded = self.snowflake_client.load_from_s3(
                            schema_name=schema_name,
                            table_name=table_name,
                            s3_bucket=s3_bucket,
                            s3_key=s3_key,
                            storage_integration=storage_integration if storage_integration else None,
                            file_format=file_format,
                            truncate=False,  # Already truncated if needed
                            on_error='ABORT_STATEMENT'
                        )
                        total_rows += rows_loaded
                        successfully_loaded_files.append(s3_key)
                        
                        # Clean up immediately after each successful load if configured
                        if cleanup_s3 and cleanup_mode == 'after_each':
                            log_event('INFO', f'Cleaning up file after successful load: {s3_key}', 
                                     correlation_id)
                            self.s3_client.delete_file(s3_key, correlation_id)
                            
                    except Exception as e:
                        log_event('ERROR', f'Failed to load file {s3_key}: {str(e)}', 
                                 correlation_id)
                        failed_files.append(s3_key)
                        # Continue with other files even if one fails
                        # (unless on_error='ABORT_STATEMENT' which would have stopped earlier)

                # Clean up all successfully loaded files if cleanup_mode is 'after_all'
                if cleanup_s3 and cleanup_mode == 'after_all' and successfully_loaded_files:
                    log_event('INFO', f'Cleaning up {len(successfully_loaded_files)} successfully loaded S3 files', 
                             correlation_id)
                    for s3_key in successfully_loaded_files:
                        self.s3_client.delete_file(s3_key, correlation_id)

                # Log summary
                if failed_files:
                    log_event('WARNING', f'{len(failed_files)} files failed to load, not cleaning up', 
                             correlation_id, failed_files=failed_files)
                else:
                    log_event('INFO', f'All {len(s3_files)} files loaded successfully', 
                             correlation_id)

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

