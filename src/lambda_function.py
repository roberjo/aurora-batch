"""Lambda function handler for Aurora to Snowflake replication."""

import json
import logging
import os
from typing import Any, Dict

try:
    from aurora_client import AuroraClient
    from replication import ReplicationEngine
    from snowflake_client import SnowflakeClient
    from utils import create_response, get_correlation_id, get_environment_variable, log_event
    from vault_client import VaultClient
except ImportError:
    # For local development/testing
    from .aurora_client import AuroraClient
    from .replication import ReplicationEngine
    from .snowflake_client import SnowflakeClient
    from .utils import create_response, get_correlation_id, get_environment_variable, log_event
    from .vault_client import VaultClient

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function handler for batch replication.

    Args:
        event: Lambda event (can contain table configuration)
        context: Lambda context

    Returns:
        Response dictionary
    """
    correlation_id = get_correlation_id()
    
    try:
        log_event('INFO', 'Lambda function started', correlation_id, 
                 event=json.dumps(event) if event else '{}')

        # Get configuration from environment variables
        vault_addr = get_environment_variable('VAULT_ADDR')
        vault_role = os.getenv('VAULT_ROLE', '')
        vault_secret_path_aurora = get_environment_variable('VAULT_SECRET_PATH_AURORA')
        vault_secret_path_snowflake = get_environment_variable('VAULT_SECRET_PATH_SNOWFLAKE')
        snowflake_endpoint = get_environment_variable('SNOWFLAKE_ENDPOINT')
        replication_mode = os.getenv('REPLICATION_MODE', 'full')
        incremental_column = os.getenv('INCREMENTAL_COLUMN', '')

        # Get table configuration from event or environment
        # Default: replicate all tables or specific table from event
        schema_name = event.get('schema_name', os.getenv('SCHEMA_NAME', 'public'))
        table_name = event.get('table_name', os.getenv('TABLE_NAME', ''))
        
        if not table_name:
            raise ValueError("table_name must be provided in event or environment variable")

        log_event('INFO', 'Retrieving secrets from Vault', correlation_id)
        
        # Initialize Vault client and retrieve secrets
        vault_client = VaultClient(vault_addr, vault_role if vault_role else None)
        
        if vault_role:
            vault_client.authenticate_iam()
        else:
            vault_token = os.getenv('VAULT_TOKEN')
            if not vault_token:
                raise ValueError("Either VAULT_ROLE or VAULT_TOKEN must be set")
            vault_client.authenticate_token(vault_token)

        # Retrieve Aurora connection secrets
        aurora_secrets = vault_client.get_secret(vault_secret_path_aurora)
        aurora_connection_params = {
            'host': aurora_secrets.get('host') or aurora_secrets.get('endpoint'),
            'port': aurora_secrets.get('port', 5432),
            'database': aurora_secrets.get('database') or aurora_secrets.get('dbname'),
            'user': aurora_secrets.get('user') or aurora_secrets.get('username'),
            'password': aurora_secrets.get('password'),
        }

        # Retrieve Snowflake connection secrets
        snowflake_secrets = vault_client.get_secret(vault_secret_path_snowflake)
        snowflake_connection_params = {
            'account': snowflake_secrets.get('account'),
            'user': snowflake_secrets.get('user') or snowflake_secrets.get('username'),
            'password': snowflake_secrets.get('password'),
            'warehouse': snowflake_secrets.get('warehouse'),
            'database': snowflake_secrets.get('database') or snowflake_secrets.get('dbname'),
            'schema': snowflake_secrets.get('schema', 'PUBLIC'),
            'role': snowflake_secrets.get('role', ''),
            'private_link_url': snowflake_endpoint,
        }

        log_event('INFO', f'Starting replication: {schema_name}.{table_name}', 
                 correlation_id, mode=replication_mode)

        # Initialize clients and perform replication
        with AuroraClient(aurora_connection_params) as aurora_client, \
             SnowflakeClient(snowflake_connection_params) as snowflake_client:
            
            replication_engine = ReplicationEngine(aurora_client, snowflake_client)
            
            result = replication_engine.replicate_table(
                schema_name=schema_name,
                table_name=table_name,
                replication_mode=replication_mode,
                incremental_column=incremental_column if incremental_column else None,
                last_value=event.get('last_value'),
                batch_size=int(os.getenv('BATCH_SIZE', '10000')),
                correlation_id=correlation_id
            )

        log_event('INFO', 'Lambda function completed successfully', correlation_id, 
                 result=result)

        return create_response(
            status_code=200,
            message='Replication completed successfully',
            correlation_id=correlation_id,
            result=result
        )

    except Exception as e:
        error_message = f"Lambda function failed: {str(e)}"
        log_event('ERROR', error_message, correlation_id, error=str(e))
        
        return create_response(
            status_code=500,
            message=error_message,
            correlation_id=correlation_id,
            error=str(e)
        )

