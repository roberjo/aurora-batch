# Customization Guide

This guide covers advanced customization options for the Aurora to Snowflake replication system.

## Table of Contents

- [Custom Data Transformations](#custom-data-transformations)
- [Custom Schema Mapping](#custom-schema-mapping)
- [Custom Error Handling](#custom-error-handling)
- [Custom Logging](#custom-logging)
- [Custom Monitoring](#custom-monitoring)
- [Adding New Features](#adding-new-features)

## Custom Data Transformations

### Basic Transformations

Modify `src/replication.py` to add transformations:

```python
# Add transformation function
def apply_transformations(row, table_config):
    """Apply custom transformations based on table configuration."""
    transformed = row.copy()
    
    # Example: Date format conversion
    if 'date_field' in transformed and transformed['date_field']:
        transformed['date_field'] = convert_date_format(
            transformed['date_field'], 
            table_config.get('date_format', 'ISO')
        )
    
    # Example: String manipulation
    if 'email' in transformed:
        transformed['email'] = transformed['email'].lower().strip()
    
    # Example: Numeric calculations
    if 'price' in transformed and 'tax' in transformed:
        transformed['total'] = transformed['price'] + transformed['tax']
    
    return transformed

# Modify replicate_table method
def replicate_table(self, ...):
    # ... existing code ...
    
    # Apply transformations before loading
    transformed_data = [
        apply_transformations(row, table_config) 
        for row in batch_data
    ]
    
    rows_inserted = self.snowflake_client.load_data_batch(
        schema_name, table_name, transformed_data, truncate
    )
```

### Table-Specific Transformations

Create a transformation registry:

```python
# src/transformations.py
TRANSFORMATIONS = {
    'customers': {
        'email': lambda x: x.lower().strip() if x else None,
        'phone': lambda x: normalize_phone(x) if x else None,
        'created_at': lambda x: convert_to_utc(x),
    },
    'orders': {
        'order_date': lambda x: convert_to_utc(x),
        'total': lambda x: round(x, 2) if x else 0,
    },
    'products': {
        'price': lambda x: round(x, 2),
        'description': lambda x: sanitize_html(x) if x else None,
    }
}

def apply_table_transformations(table_name, row):
    """Apply table-specific transformations."""
    transforms = TRANSFORMATIONS.get(table_name, {})
    transformed = row.copy()
    
    for field, transform_func in transforms.items():
        if field in transformed:
            transformed[field] = transform_func(transformed[field])
    
    return transformed
```

### Data Validation

Add validation before loading:

```python
# src/validation.py
from typing import List, Dict, Tuple

def validate_row(row: Dict, schema: Dict) -> Tuple[bool, List[str]]:
    """Validate row against schema."""
    errors = []
    
    for column in schema:
        col_name = column['column_name']
        is_nullable = column.get('is_nullable') == 'YES'
        
        if col_name not in row and not is_nullable:
            errors.append(f"Required field {col_name} is missing")
        
        if col_name in row:
            value = row[col_name]
            data_type = column['data_type']
            
            # Type validation
            if not validate_type(value, data_type):
                errors.append(
                    f"Field {col_name} has invalid type. "
                    f"Expected {data_type}, got {type(value).__name__}"
                )
    
    return len(errors) == 0, errors

def validate_type(value, expected_type):
    """Validate value type."""
    type_mapping = {
        'integer': int,
        'bigint': int,
        'varchar': str,
        'text': str,
        'timestamp': (str, datetime),
        'boolean': bool,
        'numeric': (int, float),
    }
    
    expected_python_type = type_mapping.get(expected_type.lower())
    if expected_python_type:
        return isinstance(value, expected_python_type)
    return True  # Unknown type, skip validation
```

## Custom Schema Mapping

### Column Name Mapping

```python
# src/schema_mapping.py
COLUMN_MAPPINGS = {
    'customers': {
        'customer_id': 'id',
        'email_address': 'email',
        'phone_number': 'phone',
    },
    'orders': {
        'order_id': 'id',
        'order_date': 'created_at',
    }
}

def map_columns(table_name, row):
    """Map column names from Aurora to Snowflake."""
    mapping = COLUMN_MAPPINGS.get(table_name, {})
    mapped_row = {}
    
    for aurora_col, value in row.items():
        snowflake_col = mapping.get(aurora_col, aurora_col)
        mapped_row[snowflake_col] = value
    
    return mapped_row
```

### Data Type Mapping

Customize type mappings in `src/snowflake_client.py`:

```python
# Extend type_mapping dictionary
type_mapping = {
    # ... existing mappings ...
    'money': 'NUMBER(19,4)',
    'inet': 'VARCHAR',
    'cidr': 'VARCHAR',
    'macaddr': 'VARCHAR',
    'array': 'VARIANT',
    'hstore': 'VARIANT',
    'json': 'VARIANT',
    'jsonb': 'VARIANT',
    'uuid': 'VARCHAR(36)',
    'xml': 'VARIANT',
}
```

### Schema Name Mapping

```python
# In src/lambda_function.py or src/replication.py
SCHEMA_MAPPING = {
    'public': 'PUBLIC',
    'sales': 'SALES_DATA',
    'analytics': 'ANALYTICS_WAREHOUSE',
    'staging': 'STAGING_SCHEMA',
}

def get_target_schema(source_schema):
    """Map source schema to target schema."""
    return SCHEMA_MAPPING.get(source_schema, source_schema.upper())
```

## Custom Error Handling

### Retry Logic

Add exponential backoff retry:

```python
# src/utils.py
import time
from functools import wraps

def retry_with_backoff(max_retries=3, backoff_factor=2):
    """Decorator for retrying functions with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    
                    wait_time = backoff_factor ** attempt
                    log_event('WARNING', 
                             f'Retry attempt {attempt + 1}/{max_retries}',
                             correlation_id,
                             error=str(e),
                             wait_time=wait_time)
                    time.sleep(wait_time)
        return wrapper
    return decorator

# Usage
@retry_with_backoff(max_retries=3)
def connect_to_aurora():
    # ... connection logic
    pass
```

### Error Notification

Send errors to SNS or Slack:

```python
# src/error_handler.py
import boto3
import json

def send_error_notification(error, context, correlation_id):
    """Send error notification to SNS."""
    sns = boto3.client('sns')
    topic_arn = os.getenv('ERROR_SNS_TOPIC_ARN')
    
    if not topic_arn:
        return
    
    message = {
        'error': str(error),
        'correlation_id': correlation_id,
        'function_name': context.function_name,
        'request_id': context.aws_request_id,
        'timestamp': datetime.utcnow().isoformat(),
    }
    
    sns.publish(
        TopicArn=topic_arn,
        Message=json.dumps(message),
        Subject=f'Replication Error: {context.function_name}'
    )
```

### Error Recovery

Implement checkpoint/resume functionality:

```python
# src/checkpoint.py
import boto3
import json

def save_checkpoint(table_name, last_processed_id, correlation_id):
    """Save replication checkpoint."""
    s3 = boto3.client('s3')
    bucket = os.getenv('CHECKPOINT_S3_BUCKET')
    
    checkpoint = {
        'table_name': table_name,
        'last_processed_id': last_processed_id,
        'correlation_id': correlation_id,
        'timestamp': datetime.utcnow().isoformat(),
    }
    
    key = f'checkpoints/{table_name}/latest.json'
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(checkpoint)
    )

def load_checkpoint(table_name):
    """Load replication checkpoint."""
    s3 = boto3.client('s3')
    bucket = os.getenv('CHECKPOINT_S3_BUCKET')
    key = f'checkpoints/{table_name}/latest.json'
    
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(response['Body'].read())
    except s3.exceptions.NoSuchKey:
        return None
```

## Custom Logging

### Structured Logging with Context

```python
# src/logger.py
import json
import logging
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')

class StructuredLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
    
    def _log(self, level, message, **kwargs):
        log_data = {
            'correlation_id': correlation_id_var.get(),
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            **kwargs
        }
        
        log_message = json.dumps(log_data)
        getattr(self.logger, level)(log_message)
    
    def info(self, message, **kwargs):
        self._log('info', message, **kwargs)
    
    def error(self, message, **kwargs):
        self._log('error', message, **kwargs)
    
    def warning(self, message, **kwargs):
        self._log('warning', message, **kwargs)
```

### Log Filtering

Add log levels and filters:

```python
# In src/lambda_function.py
import logging

# Set log level from environment
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logger.setLevel(getattr(logging, log_level))

# Add filters
class CorrelationFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = correlation_id_var.get()
        return True

logger.addFilter(CorrelationFilter())
```

### Log Aggregation

Send logs to external systems:

```python
# src/log_aggregator.py
def send_to_datadog(log_data):
    """Send logs to Datadog."""
    import requests
    
    datadog_api_key = os.getenv('DATADOG_API_KEY')
    if not datadog_api_key:
        return
    
    requests.post(
        'https://http-intake.logs.datadoghq.com/v1/input/' + datadog_api_key,
        json=log_data
    )

def send_to_splunk(log_data):
    """Send logs to Splunk."""
    import requests
    
    splunk_url = os.getenv('SPLUNK_HEC_URL')
    splunk_token = os.getenv('SPLUNK_HEC_TOKEN')
    
    if not splunk_url or not splunk_token:
        return
    
    requests.post(
        splunk_url,
        headers={'Authorization': f'Splunk {splunk_token}'},
        json=log_data
    )
```

## Custom Monitoring

### Custom CloudWatch Metrics

```python
# src/metrics.py
import boto3

cloudwatch = boto3.client('cloudwatch')

def put_metric(metric_name, value, unit='Count', dimensions=None):
    """Put custom CloudWatch metric."""
    metric_data = {
        'MetricName': metric_name,
        'Value': value,
        'Unit': unit,
    }
    
    if dimensions:
        metric_data['Dimensions'] = [
            {'Name': k, 'Value': v} for k, v in dimensions.items()
        ]
    
    cloudwatch.put_metric_data(
        Namespace='AuroraSnowflakeReplication',
        MetricData=[metric_data]
    )

# Usage
put_metric('RowsReplicated', rows_count, 'Count', {
    'TableName': table_name,
    'SchemaName': schema_name
})

put_metric('ReplicationDuration', duration_seconds, 'Seconds', {
    'TableName': table_name
})

put_metric('DataSize', data_size_bytes, 'Bytes', {
    'TableName': table_name
})
```

### Performance Metrics

```python
# Track performance metrics
import time

start_time = time.time()
# ... replication logic ...
duration = time.time() - start_time

put_metric('ReplicationDuration', duration, 'Seconds')
put_metric('RowsPerSecond', rows_count / duration, 'Count/Second')
```

### Business Metrics

```python
# Track business-specific metrics
def track_business_metrics(row_count, table_name):
    """Track business-relevant metrics."""
    if table_name == 'orders':
        put_metric('OrdersReplicated', row_count, 'Count')
    elif table_name == 'customers':
        put_metric('CustomersReplicated', row_count, 'Count')
```

## Adding New Features

### Adding New Data Sources

To add support for other databases:

1. Create new client class (e.g., `mysql_client.py`)
2. Implement same interface as `AuroraClient`
3. Update `lambda_function.py` to support multiple sources

```python
# src/mysql_client.py
class MySQLClient:
    def __init__(self, connection_params):
        # Similar to AuroraClient
        pass
    
    def connect(self):
        # MySQL connection logic
        pass
    
    def extract_table_data(self, schema_name, table_name, **kwargs):
        # MySQL extraction logic
        pass
```

### Adding Data Quality Checks

```python
# src/data_quality.py
def check_data_quality(source_data, target_data, table_name):
    """Perform data quality checks."""
    checks = {
        'row_count_match': len(source_data) == len(target_data),
        'null_values': check_null_values(target_data),
        'duplicates': check_duplicates(target_data),
        'data_types': check_data_types(target_data),
    }
    
    return checks

def check_null_values(data):
    """Check for unexpected null values."""
    # Implementation
    pass
```

### Adding Data Lineage Tracking

```python
# src/lineage.py
def track_lineage(source_table, target_table, row_count, correlation_id):
    """Track data lineage."""
    lineage_data = {
        'source': {
            'database': 'aurora',
            'schema': source_table['schema'],
            'table': source_table['table'],
        },
        'target': {
            'database': 'snowflake',
            'schema': target_table['schema'],
            'table': target_table['table'],
        },
        'row_count': row_count,
        'replication_time': datetime.utcnow().isoformat(),
        'correlation_id': correlation_id,
    }
    
    # Store in DynamoDB or send to lineage system
    # Implementation
    pass
```

### Adding Change Data Capture (CDC)

For future CDC implementation:

```python
# src/cdc.py
def enable_logical_replication(connection):
    """Enable logical replication in PostgreSQL."""
    # Implementation for CDC
    pass

def read_wal_changes(connection):
    """Read changes from WAL."""
    # Implementation for CDC
    pass
```

## Best Practices

1. **Keep Transformations Simple:** Complex transformations should be done in Snowflake or separate ETL jobs
2. **Use Configuration Files:** Store mappings and transformations in config files, not code
3. **Test Thoroughly:** Test all customizations in development before production
4. **Monitor Performance:** Track metrics for custom features
5. **Document Changes:** Document all customizations in code comments and documentation
6. **Version Control:** Use feature flags or versioning for custom features
7. **Error Handling:** Always handle errors gracefully in custom code
8. **Logging:** Log all custom operations for debugging

## Examples

See `examples/` directory for complete customization examples:
- `examples/transformations/` - Custom transformation examples
- `examples/monitoring/` - Custom monitoring examples
- `examples/error_handling/` - Error handling examples

