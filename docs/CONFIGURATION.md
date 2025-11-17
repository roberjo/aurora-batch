# Configuration Guide

This guide covers all configuration options for the Aurora to Snowflake replication system.

## Table of Contents

- [Basic Configuration](#basic-configuration)
- [Replicating Different Tables](#replicating-different-tables)
- [Changing Replication Schedule](#changing-replication-schedule)
- [Replication Modes](#replication-modes)
- [Advanced Configuration](#advanced-configuration)
- [Environment-Specific Settings](#environment-specific-settings)

## Basic Configuration

### Terraform Variables

The main configuration is done through Terraform variables. See `terraform/terraform.tfvars.example` for a complete example.

**Required Variables:**

```hcl
terraform_cloud_organization = "your-org"
terraform_cloud_workspace   = "aurora-snowflake-replication"
aws_region                  = "us-east-1"
vpc_id                      = "vpc-xxxxxxxxx"
subnet_ids                  = ["subnet-xxxxxxxxx", "subnet-yyyyyyyyy"]
snowflake_vpc_endpoint_id   = "vpce-xxxxxxxxx"
aurora_endpoint             = "aurora-cluster.region.rds.amazonaws.com"
vault_addr                  = "https://vault.example.com"
snowflake_endpoint          = "snowflake.example.com"
```

### Vault Secrets Configuration

#### Aurora Connection Secrets

Path: `secret/aurora/connection` (configurable via `vault_secret_path_aurora`)

```json
{
  "host": "aurora-cluster-endpoint.region.rds.amazonaws.com",
  "port": 5432,
  "database": "your_database",
  "user": "replication_user",
  "password": "secure_password"
}
```

**Note:** The user specified here must have SELECT permissions on the tables you want to replicate.

#### Snowflake Credentials

Path: `secret/snowflake/credentials` (configurable via `vault_secret_path_snowflake`)

```json
{
  "account": "your_account_identifier",
  "user": "replication_user",
  "password": "secure_password",
  "warehouse": "COMPUTE_WH",
  "database": "REPLICATION_DB",
  "schema": "PUBLIC",
  "role": "REPLICATION_ROLE"
}
```

**Note:** The Snowflake user must have:
- USAGE privilege on the warehouse
- CREATE TABLE privilege on the target schema
- INSERT privilege on target tables

## Replicating Different Tables

### Method 1: Event-Driven (Recommended)

Invoke the Lambda function with a specific table configuration:

```json
{
  "schema_name": "public",
  "table_name": "your_table_name",
  "last_value": null
}
```

**Use Cases:**
- One-time replication
- Manual triggers
- Different schedules for different tables
- Testing specific tables

**Example: Manual Invocation via AWS CLI**

```bash
aws lambda invoke \
  --function-name aurora-snowflake-replication \
  --payload '{"schema_name":"public","table_name":"customers"}' \
  response.json
```

### Method 2: Environment Variables

Set default table in Lambda environment variables:

```hcl
# In terraform/lambda.tf
environment {
  variables = {
    SCHEMA_NAME = "public"
    TABLE_NAME  = "your_table_name"
    # ... other variables
  }
}
```

**Use Cases:**
- Single table replication
- Consistent replication target
- Simple deployments

### Method 3: Multiple Lambda Functions

Create separate Lambda functions for different tables:

```hcl
# terraform/lambda_customers.tf
resource "aws_lambda_function" "replication_customers" {
  function_name = "aurora-snowflake-replication-customers"
  # ... same configuration but different TABLE_NAME env var
}

# terraform/lambda_orders.tf
resource "aws_lambda_function" "replication_orders" {
  function_name = "aurora-snowflake-replication-orders"
  # ... same configuration but different TABLE_NAME env var
}
```

**Use Cases:**
- Different schedules per table
- Different batch sizes per table
- Independent scaling and monitoring

### Method 4: Table List Configuration

Modify the Lambda function to accept a list of tables:

**Step 1:** Update Lambda handler to process multiple tables:

```python
# In src/lambda_function.py
def lambda_handler(event, context):
    tables = event.get('tables', [])
    
    if not tables:
        # Fall back to single table mode
        tables = [{
            'schema_name': event.get('schema_name', 'public'),
            'table_name': event.get('table_name')
        }]
    
    results = []
    for table_config in tables:
        result = replicate_single_table(table_config)
        results.append(result)
    
    return create_response(200, 'Replication completed', correlation_id, results=results)
```

**Step 2:** Configure EventBridge with table list:

```json
{
  "tables": [
    {"schema_name": "public", "table_name": "customers"},
    {"schema_name": "public", "table_name": "orders"},
    {"schema_name": "sales", "table_name": "transactions"}
  ]
}
```

### Schema Mapping

If your Aurora and Snowflake schemas differ:

**Option 1: Use Snowflake Schema Mapping**

```python
# In src/replication.py, modify create_table_if_not_exists
schema_mapping = {
    'public': 'PUBLIC',
    'sales': 'SALES_SCHEMA',
    'analytics': 'ANALYTICS_SCHEMA'
}

target_schema = schema_mapping.get(schema_name, schema_name.upper())
```

**Option 2: Environment Variable Mapping**

```hcl
# In terraform/lambda.tf
environment {
  variables = {
    SCHEMA_MAPPING = '{"public":"PUBLIC","sales":"SALES_SCHEMA"}'
  }
}
```

## Changing Replication Schedule

### EventBridge Cron Expression

The schedule is controlled by the `schedule_expression` Terraform variable.

### Common Schedule Examples

**Daily at 2 AM UTC:**
```hcl
schedule_expression = "cron(0 2 * * ? *)"
```

**Every 6 hours:**
```hcl
schedule_expression = "cron(0 */6 * * ? *)"
```

**Every Monday at 1 AM UTC:**
```hcl
schedule_expression = "cron(0 1 ? * MON *)"
```

**First day of month at midnight:**
```hcl
schedule_expression = "cron(0 0 1 * ? *)"
```

**Every weekday at 3 AM UTC:**
```hcl
schedule_expression = "cron(0 3 ? * MON-FRI *)"
```

**Every 15 minutes:**
```hcl
schedule_expression = "cron(*/15 * * * ? *)"
```

### Cron Expression Format

```
cron(Minutes Hours Day-of-month Month Day-of-week Year)
```

- **Minutes**: 0-59
- **Hours**: 0-23
- **Day-of-month**: 1-31, ? (any), * (all)
- **Month**: 1-12, JAN-DEC, * (all)
- **Day-of-week**: 1-7 (SUN-SAT), ? (any), * (all)
- **Year**: 1970-2199, * (all)

**Special Characters:**
- `*` - Matches all values
- `?` - Matches any value (used for day-of-month or day-of-week)
- `-` - Range (e.g., MON-FRI)
- `,` - List (e.g., MON,WED,FRI)
- `/` - Increment (e.g., */15 for every 15 minutes)

### Changing Schedule

**Step 1:** Update Terraform variable:

```hcl
# terraform/terraform.tfvars
schedule_expression = "cron(0 3 * * ? *)"  # Daily at 3 AM
```

**Step 2:** Apply Terraform changes:

```bash
cd terraform
terraform plan
terraform apply
```

**Step 3:** Verify in AWS Console:

- Go to EventBridge → Rules
- Find your rule: `aurora-snowflake-replication-schedule`
- Verify the schedule expression

### Multiple Schedules

To run replication at multiple times, create additional EventBridge rules:

```hcl
# terraform/eventbridge_additional.tf
resource "aws_cloudwatch_event_rule" "schedule_additional" {
  name                = "${var.lambda_function_name}-schedule-additional"
  description         = "Additional schedule for Aurora to Snowflake replication"
  schedule_expression = "cron(0 12 * * ? *)"  # Daily at noon
}

resource "aws_cloudwatch_event_target" "lambda_additional" {
  rule      = aws_cloudwatch_event_rule.schedule_additional.name
  target_id = "${var.lambda_function_name}-target-additional"
  arn       = aws_lambda_function.replication.arn
}
```

## Replication Modes

### Full Replication

Replicates all data from source table, truncating target first.

**Configuration:**
```hcl
replication_mode = "full"
```

**Use Cases:**
- Initial load
- Small tables (< 1M rows)
- When data integrity requires full refresh
- When incremental tracking is not possible

**Lambda Event:**
```json
{
  "schema_name": "public",
  "table_name": "small_table"
}
```

### Incremental Replication

Only replicates new or changed rows based on a timestamp or ID column.

**Configuration:**
```hcl
replication_mode    = "incremental"
incremental_column   = "updated_at"  # or "id", "created_at", etc.
```

**Use Cases:**
- Large tables (> 1M rows)
- Frequently updated tables
- Cost optimization (less data transfer)
- Real-time or near-real-time replication

**Lambda Event:**
```json
{
  "schema_name": "public",
  "table_name": "large_table",
  "last_value": "2024-01-15T10:30:00"
}
```

**Important Notes:**
- The incremental column must be indexed in Aurora for performance
- Use timestamp columns for time-based incremental replication
- Use auto-incrementing ID columns for ID-based incremental replication
- The `last_value` should be stored and passed between runs (consider DynamoDB or Parameter Store)

### Implementing State Tracking

To track `last_value` between runs, modify the Lambda function:

```python
# Add to src/lambda_function.py
import boto3

def get_last_value(table_name):
    dynamodb = boto3.client('dynamodb')
    response = dynamodb.get_item(
        TableName='replication-state',
        Key={'table_name': {'S': table_name}}
    )
    if 'Item' in response:
        return response['Item']['last_value']['S']
    return None

def save_last_value(table_name, last_value):
    dynamodb = boto3.client('dynamodb')
    dynamodb.put_item(
        TableName='replication-state',
        Item={
            'table_name': {'S': table_name},
            'last_value': {'S': str(last_value)},
            'updated_at': {'S': datetime.utcnow().isoformat()}
        }
    )
```

## Advanced Configuration

### Batch Size

Control how many rows are processed per batch:

```hcl
# In Lambda environment variables
BATCH_SIZE = 50000  # Default: 10000
```

**Considerations:**
- Larger batches = fewer Lambda invocations but more memory usage
- Smaller batches = more invocations but lower memory usage
- Recommended: 10,000-50,000 rows per batch

### Lambda Memory and Timeout

```hcl
lambda_timeout   = 900   # 15 minutes (max: 900 seconds)
lambda_memory_size = 1024 # 1 GB (affects CPU allocation)
```

**Memory Guidelines:**
- 512 MB: Small tables (< 100K rows)
- 1024 MB: Medium tables (100K - 1M rows)
- 2048 MB: Large tables (> 1M rows)
- 3008 MB: Very large tables with complex transformations

**Timeout Guidelines:**
- Small tables: 300 seconds (5 minutes)
- Medium tables: 600 seconds (10 minutes)
- Large tables: 900 seconds (15 minutes)

### VPC Configuration

**Subnet Selection:**
- Use private subnets for Lambda (recommended)
- Ensure subnets have NAT Gateway or VPC endpoints for Vault access
- Use multiple subnets across AZs for high availability

**Security Groups:**
- Outbound to Aurora (port 5432)
- Outbound to VPC endpoint (port 443)
- Outbound to Vault (port 443)

### Error Handling and Retries

**Dead Letter Queue (DLQ):**

Add to `terraform/lambda.tf`:

```hcl
resource "aws_sqs_queue" "lambda_dlq" {
  name = "${var.lambda_function_name}-dlq"
}

resource "aws_lambda_function" "replication" {
  # ... existing configuration
  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq.arn
  }
}
```

**Retry Configuration:**

EventBridge automatically retries failed invocations:
- Maximum retry attempts: 2 (default)
- Maximum event age: 24 hours (default)

### Monitoring and Alerts

**CloudWatch Alarms:**

Already configured in `terraform/cloudwatch.tf`. Customize thresholds:

```hcl
# For error rate alarm
threshold = 1  # Alert if any errors occur

# For duration alarm
threshold = var.lambda_timeout * 1000 * 0.8  # 80% of timeout
```

**Custom Metrics:**

Add custom CloudWatch metrics in Lambda:

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

cloudwatch.put_metric_data(
    Namespace='AuroraSnowflakeReplication',
    MetricData=[{
        'MetricName': 'RowsReplicated',
        'Value': rows_replicated,
        'Unit': 'Count',
        'Dimensions': [
            {'Name': 'TableName', 'Value': table_name},
            {'Name': 'SchemaName', 'Value': schema_name}
        ]
    }]
)
```

## Environment-Specific Settings

### Development Environment

```hcl
environment = "dev"
lambda_timeout = 300
lambda_memory_size = 512
schedule_expression = "cron(0 2 * * ? *)"  # Daily
```

### Staging Environment

```hcl
environment = "staging"
lambda_timeout = 600
lambda_memory_size = 1024
schedule_expression = "cron(0 */6 * * ? *)"  # Every 6 hours
```

### Production Environment

```hcl
environment = "prod"
lambda_timeout = 900
lambda_memory_size = 2048
schedule_expression = "cron(0 1 * * ? *)"  # Daily at 1 AM
cloudwatch_alarm_sns_topic_arn = "arn:aws:sns:region:account:alerts"
```

### Multi-Environment Setup

Use Terraform workspaces:

```bash
# Development
terraform workspace select dev
terraform apply -var-file=dev.tfvars

# Staging
terraform workspace select staging
terraform apply -var-file=staging.tfvars

# Production
terraform workspace select prod
terraform apply -var-file=prod.tfvars
```

## Custom Transformations

### Adding Data Transformations

Modify `src/replication.py`:

```python
def transform_row(row, schema_name, table_name):
    """Apply custom transformations to a row."""
    transformed = row.copy()
    
    # Example: Convert timestamp to UTC
    if 'created_at' in transformed:
        transformed['created_at'] = convert_to_utc(transformed['created_at'])
    
    # Example: Mask sensitive data
    if 'ssn' in transformed:
        transformed['ssn'] = mask_ssn(transformed['ssn'])
    
    # Example: Add computed columns
    transformed['replication_timestamp'] = datetime.utcnow().isoformat()
    
    return transformed

# In replicate_table method:
transformed_data = [transform_row(row, schema_name, table_name) for row in batch_data]
```

### Filtering Data

Add WHERE clause filtering:

```python
# In src/aurora_client.py
def extract_table_data(self, schema_name, table_name, 
                      where_clause=None,  # Add this parameter
                      incremental_column=None,
                      last_value=None,
                      batch_size=10000):
    query = f'SELECT * FROM "{schema_name}"."{table_name}"'
    
    conditions = []
    if where_clause:
        conditions.append(where_clause)
    if incremental_column and last_value:
        conditions.append(f'"{incremental_column}" > %s')
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    
    query += f' LIMIT %s'
    # ... rest of implementation
```

## Performance Tuning

### Aurora Query Optimization

1. **Add Indexes:**
   ```sql
   CREATE INDEX idx_updated_at ON table_name(updated_at);
   ```

2. **Use Partitioning:**
   ```sql
   CREATE TABLE table_name (
     -- columns
   ) PARTITION BY RANGE (created_at);
   ```

3. **Analyze Tables:**
   ```sql
   ANALYZE table_name;
   ```

### Snowflake Optimization

1. **Use COPY INTO for Large Loads:**
   Modify `snowflake_client.py` to use COPY INTO instead of INSERT for large batches.

2. **Cluster Keys:**
   ```sql
   CREATE TABLE table_name (
     -- columns
   ) CLUSTER BY (date_column);
   ```

3. **Warehouse Sizing:**
   - Use larger warehouse for faster loads
   - Auto-suspend when not in use

### Lambda Optimization

1. **Reserved Concurrency:**
   ```hcl
   reserved_concurrent_executions = 5
   ```

2. **Provisioned Concurrency:**
   ```hcl
   provisioned_concurrent_executions = 2
   ```

3. **Parallel Processing:**
   Use Step Functions or multiple Lambda invocations for parallel table replication.

## Troubleshooting Configuration Issues

### Common Issues

1. **Lambda Timeout:**
   - Increase `lambda_timeout`
   - Reduce `BATCH_SIZE`
   - Optimize queries

2. **Memory Errors:**
   - Increase `lambda_memory_size`
   - Reduce `BATCH_SIZE`

3. **Connection Errors:**
   - Verify security groups
   - Check VPC endpoint configuration
   - Verify Vault connectivity

4. **Permission Errors:**
   - Check IAM roles
   - Verify database user permissions
   - Check Snowflake role privileges

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed troubleshooting guide.

