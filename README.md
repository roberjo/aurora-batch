# Aurora PostgreSQL to Snowflake Batch Replication

A serverless batch replication system that extracts data from AWS Aurora v2 PostgreSQL and loads it into Snowflake via PrivateLink. All infrastructure is managed via Terraform Cloud, secrets are stored in Hashicorp Vault, builds are executed via GitHub Actions, artifacts are stored in Artifactory, and deployments are managed via Harness CI/CD.

## Architecture Overview

The system uses AWS Lambda (scheduled via EventBridge) to perform batch replication from Aurora PostgreSQL to Snowflake. The Lambda function runs in a VPC with PrivateLink connectivity to Snowflake, ensuring secure, private data transfer without traversing the public internet.

### Key Components

- **Lambda Function**: Python-based batch replication service with VPC configuration
- **EventBridge**: Scheduled trigger for batch replication (configurable cron expression)
- **VPC Endpoints**: Interface endpoints for Snowflake PrivateLink connectivity
- **Security Groups**: Network security rules for Lambda → Aurora and Lambda → Snowflake
- **IAM Roles**: Least-privilege permissions for Lambda execution
- **CloudWatch**: Logging and monitoring

## Prerequisites

- AWS Account with appropriate permissions
- Terraform Cloud account and workspace
- Hashicorp Vault instance with secrets configured
- Snowflake account with PrivateLink endpoint configured
- GitHub repository with Actions enabled
- Artifactory instance for artifact storage
- Harness CI/CD platform access

## Project Structure

```
aurora-batch/
├── terraform/              # Terraform infrastructure as code
│   ├── main.tf            # Main Terraform configuration
│   ├── variables.tf      # Variable definitions
│   ├── outputs.tf        # Output values
│   ├── lambda.tf         # Lambda function resource
│   ├── vpc-endpoints.tf   # VPC endpoint configuration
│   ├── security-groups.tf # Security group rules
│   ├── iam.tf             # IAM roles and policies
│   ├── eventbridge.tf     # EventBridge scheduling
│   └── cloudwatch.tf      # CloudWatch logs and alarms
├── src/                   # Lambda function source code
│   ├── lambda_function.py # Main Lambda handler
│   ├── aurora_client.py   # Aurora PostgreSQL client
│   ├── snowflake_client.py # Snowflake client
│   ├── vault_client.py    # Hashicorp Vault client
│   ├── replication.py     # Core replication logic
│   └── utils.py           # Utility functions
├── tests/                 # Unit tests
│   ├── test_lambda_function.py
│   ├── test_aurora_client.py
│   ├── test_snowflake_client.py
│   └── test_vault_client.py
├── docs/                  # Documentation
│   ├── CONFIGURATION.md   # Configuration guide
│   └── CUSTOMIZATION.md   # Customization guide
├── .github/
│   └── workflows/
│       ├── build.yml      # Build workflow
│       ├── lint.yml       # Linting workflow
│       ├── code-quality.yml # Code quality workflow
│       └── security-scan.yml # Security scanning workflow
├── harness/
│   └── pipeline.yaml      # Harness pipeline definition
├── requirements.txt       # Python dependencies
├── setup.py              # Package setup
└── README.md             # This file
```

## Setup and Configuration

### 1. Terraform Cloud Configuration

1. Create a Terraform Cloud workspace
2. Configure workspace variables:
   - `terraform_cloud_organization`: Your Terraform Cloud org name
   - `terraform_cloud_workspace`: Your workspace name
   - `aws_region`: AWS region for resources
   - `vpc_id`: VPC ID where Lambda will run
   - `subnet_ids`: Subnet IDs for Lambda VPC configuration
   - `snowflake_vpc_endpoint_id`: Existing VPC endpoint ID for Snowflake
   - `aurora_endpoint`: Aurora cluster endpoint
   - `vault_addr`: Hashicorp Vault address
   - `snowflake_endpoint`: Snowflake PrivateLink endpoint URL
   - Other variables as needed

### 2. Hashicorp Vault Secrets

Store the following secrets in Vault:

**Aurora Connection** (path: `secret/aurora/connection`):
```json
{
  "host": "aurora-cluster-endpoint.region.rds.amazonaws.com",
  "port": 5432,
  "database": "database_name",
  "user": "username",
  "password": "password"
}
```

**Snowflake Credentials** (path: `secret/snowflake/credentials`):
```json
{
  "account": "account_identifier",
  "user": "username",
  "password": "password",
  "warehouse": "warehouse_name",
  "database": "database_name",
  "schema": "schema_name",
  "role": "role_name"
}
```

### 3. GitHub Actions Secrets

Configure the following secrets in GitHub:
- `ARTIFACTORY_URL`: Artifactory base URL
- `ARTIFACTORY_REPO`: Artifactory repository name
- `ARTIFACTORY_USER`: Artifactory username
- `ARTIFACTORY_PASSWORD`: Artifactory password/token

**Note**: The GitHub Actions workflows will automatically run on push and pull requests:
- **Lint Workflow**: Code formatting and style checks
- **Code Quality Workflow**: Complexity and quality analysis
- **Security Scan Workflow**: Vulnerability and secret scanning (also runs weekly)
- **Build Workflow**: Tests and Lambda package creation

### 4. Harness Configuration

1. Import the pipeline from `harness/pipeline.yaml`
2. Configure Harness secrets:
   - `terraform_cloud_token`: Terraform Cloud API token
   - `artifactory_user`: Artifactory username
   - `artifactory_password`: Artifactory password/token
3. Configure pipeline inputs:
   - `terraform_cloud_org`: Terraform Cloud organization
   - `terraform_cloud_workspace`: Terraform Cloud workspace
   - `artifactory_url`: Artifactory base URL
   - `artifactory_repo`: Artifactory repository name
   - `package_name`: Lambda package name (from GitHub Actions)
   - `aws_region`: AWS region

## Deployment

### Initial Infrastructure Deployment

1. **Deploy Terraform Infrastructure**:
   ```bash
   cd terraform
   terraform init
   terraform plan
   terraform apply
   ```

   Or use Terraform Cloud to run the plan/apply.

2. **Build Lambda Package**:
   - Push code to GitHub main branch
   - GitHub Actions will automatically build and upload to Artifactory

3. **Deploy Lambda Function**:
   - Run Harness pipeline with appropriate inputs
   - Pipeline will download from Artifactory and update Lambda function

### Updating Lambda Function

1. Make code changes
2. Push to GitHub (triggers GitHub Actions build)
3. Run Harness pipeline with new package name

## Quick Start Guide

### 1. Configure Tables to Replicate

**Option A: Single Table (Environment Variable)**
```hcl
# In terraform/lambda.tf
environment {
  variables = {
    SCHEMA_NAME = "public"
    TABLE_NAME  = "customers"
  }
}
```

**Option B: Event-Driven (Recommended)**
Invoke Lambda with table configuration:
```json
{
  "schema_name": "public",
  "table_name": "customers"
}
```

**Option C: Multiple Tables**
See [Configuration Guide](docs/CONFIGURATION.md#replicating-different-tables) for details.

### 2. Set Replication Schedule

Edit `terraform/terraform.tfvars`:
```hcl
# Daily at 2 AM UTC
schedule_expression = "cron(0 2 * * ? *)"

# Every 6 hours
schedule_expression = "cron(0 */6 * * ? *)"

# Every Monday at 1 AM UTC
schedule_expression = "cron(0 1 ? * MON *)"
```

See [Configuration Guide](docs/CONFIGURATION.md#changing-replication-schedule) for more examples.

### 3. Choose Replication Mode

**Full Replication** (default):
```hcl
replication_mode = "full"
```

**Incremental Replication**:
```hcl
replication_mode    = "incremental"
incremental_column  = "updated_at"  # or "id", "created_at", etc.
```

See [Configuration Guide](docs/CONFIGURATION.md#replication-modes) for details.

## Usage

### Scheduled Replication

The Lambda function runs automatically based on the EventBridge schedule configured in Terraform (default: daily at 2 AM UTC).

### Manual Invocation

You can manually invoke the Lambda function with an event:

```json
{
  "schema_name": "public",
  "table_name": "your_table",
  "last_value": "2024-01-01T00:00:00"
}
```

**AWS CLI Example:**
```bash
aws lambda invoke \
  --function-name aurora-snowflake-replication \
  --payload '{"schema_name":"public","table_name":"customers"}' \
  response.json
```

### Replication Modes

**Full Replication** (default):
- Replicates all data from the source table
- Truncates target table before loading
- Best for: Small tables, initial loads, data integrity requirements

**Incremental Replication**:
- Only replicates new/changed rows based on incremental column
- Requires `INCREMENTAL_COLUMN` environment variable
- Uses `last_value` from event or previous run
- Best for: Large tables, frequent updates, cost optimization

### S3 Staging (Recommended for Large Datasets)

The system uses S3 as an external stage for Snowflake data loading:

1. **Extract**: Data extracted from Aurora in batches
2. **Stage**: Batches uploaded to S3 as CSV or Parquet files
3. **Load**: Snowflake COPY INTO loads from S3
4. **Cleanup**: Files cleaned after all batches load successfully (configurable)

**Benefits:**
- Faster loading for large datasets
- More cost-effective than direct INSERT
- Better error handling and retry capabilities
- Handles very large datasets efficiently

**Cleanup Strategy:**
- Files are cleaned **after all batches load successfully** (not after each batch)
- This ensures COPY INTO can load files in parallel
- Lifecycle policies provide safety net for any missed files
- Optional cleanup Lambda for orphaned files

See [S3 Staging Documentation](docs/S3_STAGING.md) and [S3 Lifecycle Management](docs/S3_LIFECYCLE_MANAGEMENT.md) for details.

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[Configuration Guide](docs/CONFIGURATION.md)**: Complete configuration reference
  - Replicating different tables
  - Changing replication schedules
  - Replication modes (full vs incremental)
  - Advanced configuration options
  - Environment-specific settings
  - Performance tuning

- **[Customization Guide](docs/CUSTOMIZATION.md)**: Advanced customization
  - Custom data transformations
  - Schema mapping
  - Error handling
  - Custom logging and monitoring
  - Adding new features

### Common Customizations

**Changing Tables:**
See [Replicating Different Tables](docs/CONFIGURATION.md#replicating-different-tables)

**Changing Schedule:**
See [Changing Replication Schedule](docs/CONFIGURATION.md#changing-replication-schedule)

**Custom Transformations:**
See [Custom Data Transformations](docs/CUSTOMIZATION.md#custom-data-transformations)

**Performance Tuning:**
See [Performance Tuning](docs/CONFIGURATION.md#performance-tuning)

## Environment Variables

The Lambda function uses the following environment variables:

- `VAULT_ADDR`: Hashicorp Vault address (required)
- `VAULT_ROLE`: IAM role for Vault authentication (optional, if using IAM auth)
- `VAULT_TOKEN`: Vault token (optional, if using token auth)
- `VAULT_SECRET_PATH_AURORA`: Vault path for Aurora secrets (default: `secret/aurora/connection`)
- `VAULT_SECRET_PATH_SNOWFLAKE`: Vault path for Snowflake secrets (default: `secret/snowflake/credentials`)
- `SNOWFLAKE_ENDPOINT`: Snowflake PrivateLink endpoint URL (required)
- `REPLICATION_MODE`: `full` or `incremental` (default: `full`)
- `INCREMENTAL_COLUMN`: Column name for incremental extraction (required for incremental mode)
- `BATCH_SIZE`: Number of rows to process per batch (default: 10000)
- `SCHEMA_NAME`: Default schema name (default: `public`)
- `TABLE_NAME`: Default table name (can be overridden in event)

## Monitoring

### CloudWatch Logs

Lambda execution logs are available in CloudWatch Logs:
- Log Group: `/aws/lambda/aurora-snowflake-replication`

### CloudWatch Metrics

The following metrics are automatically tracked:
- `Invocations`: Number of Lambda invocations
- `Errors`: Number of failed invocations
- `Duration`: Execution duration
- `Throttles`: Number of throttled invocations

### CloudWatch Alarms

Alarms are configured for:
- Lambda errors (threshold: > 0)
- Lambda duration approaching timeout (threshold: 90% of timeout)

## Security Considerations

- **Secrets Management**: All credentials stored in Hashicorp Vault, never in code or Terraform state
- **Network Security**: Lambda runs in VPC with security groups restricting access
- **PrivateLink**: Snowflake connectivity via PrivateLink (no public internet)
- **IAM Roles**: Least-privilege IAM roles for Lambda execution
- **Encryption**: TLS encryption for Aurora and Snowflake connections
- **CloudWatch Logs**: Logs encrypted at rest

## Cost Optimization

- **Serverless**: Lambda only runs on schedule (no always-on infrastructure)
- **Efficient Queries**: Batch processing with configurable batch sizes
- **Snowflake COPY**: Uses efficient bulk loading methods
- **Appropriate Timeouts**: Configurable Lambda timeout and memory settings

## Development

### Local Testing

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run tests:
   ```bash
   pytest tests/ -v
   ```

3. Set environment variables for local testing:
   ```bash
   export VAULT_ADDR=https://vault.example.com
   export VAULT_TOKEN=your-token
   export SNOWFLAKE_ENDPOINT=snowflake.example.com
   # ... other variables
   ```

### Code Quality and Linting

The project includes automated code quality checks via GitHub Actions:

**Linting Workflow** (`.github/workflows/lint.yml`):
- Black (code formatting)
- isort (import sorting)
- Flake8 (style guide enforcement)
- Pylint (code analysis)
- MyPy (type checking)

**Code Quality Workflow** (`.github/workflows/code-quality.yml`):
- Bandit (security linting)
- Radon (code complexity analysis)
- Xenon (complexity monitoring)
- Vulture (dead code detection)

**Security Scan Workflow** (`.github/workflows/security-scan.yml`):
- pip-audit (Python dependency vulnerabilities)
- Safety (dependency security check)
- Bandit (code security scanning)
- TFLint (Terraform linting)
- Checkov (Terraform security scanning)
- Gitleaks (secret scanning)
- TruffleHog (secret detection)

Run locally:
```bash
# Linting
make lint

# Or individually
black --check src/ tests/
isort --check-only src/ tests/
flake8 src/ tests/
pylint src/ tests/
mypy src/

# Code quality
bandit -r src/
radon cc src/
radon mi src/

# Security scans
pip-audit --requirement requirements.txt
safety check --file requirements.txt
```

### Building Lambda Package Locally

```bash
make build
```

Or manually:
```bash
mkdir -p package
cp -r src/* package/
pip install -r requirements.txt -t package/
cd package
zip -r ../lambda-deployment.zip .
```

## Troubleshooting

### Lambda Timeout

**Symptoms:** Lambda function times out before completing replication

**Solutions:**
- Increase `lambda_timeout` in Terraform variables (max: 900 seconds)
- Reduce `BATCH_SIZE` environment variable
- Optimize Aurora queries (add indexes, use WHERE clauses)
- Increase Lambda memory (affects CPU allocation)
- Split large tables into smaller batches

**Example:**
```hcl
lambda_timeout = 900  # 15 minutes
lambda_memory_size = 2048  # 2 GB
BATCH_SIZE = 5000  # Smaller batches
```

### Connection Issues

**Symptoms:** Cannot connect to Aurora or Snowflake

**Solutions:**
- Verify VPC endpoint for Snowflake is configured correctly
- Check security group rules allow outbound traffic:
  - Port 5432 to Aurora
  - Port 443 to VPC endpoint and Vault
- Verify Lambda is in correct subnets
- Check NAT Gateway or VPC endpoints for internet access
- Verify Aurora endpoint is correct and accessible
- Test connectivity from Lambda VPC using AWS Systems Manager Session Manager

**Debug Steps:**
```bash
# Check security group rules
aws ec2 describe-security-groups --group-ids sg-xxxxxxxxx

# Test VPC endpoint
aws ec2 describe-vpc-endpoints --vpc-endpoint-ids vpce-xxxxxxxxx

# Check Lambda VPC configuration
aws lambda get-function-configuration --function-name aurora-snowflake-replication
```

### Authentication Errors

**Symptoms:** Vault authentication fails

**Solutions:**
- Verify Vault credentials and authentication method
- Check IAM role has permissions for Vault (if using IAM auth)
- Verify Vault token is valid (if using token auth)
- Check Vault address is accessible from Lambda VPC
- Verify Vault secret paths are correct

**Debug Steps:**
```bash
# Test Vault connectivity
curl -H "X-Vault-Token: $VAULT_TOKEN" $VAULT_ADDR/v1/sys/health

# Verify secrets exist
vault kv get secret/aurora/connection
vault kv get secret/snowflake/credentials
```

### Data Not Appearing in Snowflake

**Symptoms:** Lambda succeeds but no data in Snowflake

**Solutions:**
- Check CloudWatch logs for errors
- Verify Snowflake user has INSERT permissions
- Check table exists in Snowflake (or auto-create is enabled)
- Verify schema mapping is correct
- Check for data type mismatches
- Review Snowflake query history

**Debug Steps:**
```bash
# Check Lambda logs
aws logs tail /aws/lambda/aurora-snowflake-replication --follow

# Check Snowflake query history
SELECT * FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY())
WHERE QUERY_TEXT LIKE '%INSERT%'
ORDER BY START_TIME DESC;
```

### Performance Issues

**Symptoms:** Replication is slow

**Solutions:**
- Increase Lambda memory (more memory = more CPU)
- Optimize Aurora queries (add indexes, use WHERE clauses)
- Increase batch size (fewer Lambda invocations)
- Use incremental mode for large tables
- Optimize Snowflake warehouse size
- Use Snowflake COPY INTO instead of INSERT for large batches

**Performance Tuning:**
```hcl
lambda_memory_size = 2048  # Increase memory
BATCH_SIZE = 50000  # Larger batches
```

### Memory Errors

**Symptoms:** Lambda runs out of memory

**Solutions:**
- Increase `lambda_memory_size` in Terraform
- Reduce `BATCH_SIZE` environment variable
- Optimize data processing (avoid loading all data into memory)
- Use streaming/chunked processing

### Permission Errors

**Symptoms:** Access denied errors

**Solutions:**
- Verify IAM role has required permissions
- Check Aurora user has SELECT permissions on tables
- Verify Snowflake role has CREATE TABLE and INSERT permissions
- Check Vault access policies
- Verify security group rules

### Schedule Not Running

**Symptoms:** Lambda not invoked on schedule

**Solutions:**
- Verify EventBridge rule is enabled
- Check rule schedule expression syntax
- Verify Lambda permission for EventBridge
- Check CloudWatch Events/EventBridge logs
- Verify rule target is correct

**Debug Steps:**
```bash
# Check EventBridge rule
aws events describe-rule --name aurora-snowflake-replication-schedule

# Check rule targets
aws events list-targets-by-rule --rule aurora-snowflake-replication-schedule

# Check Lambda permissions
aws lambda get-policy --function-name aurora-snowflake-replication
```

### Incremental Replication Issues

**Symptoms:** Duplicate data or missing rows

**Solutions:**
- Verify incremental column is indexed in Aurora
- Check last_value is being tracked correctly
- Ensure incremental column is never NULL
- Use timestamp columns for time-based incremental
- Implement proper state tracking (DynamoDB or Parameter Store)

For more detailed troubleshooting, see the [Configuration Guide](docs/CONFIGURATION.md#troubleshooting-configuration-issues).

## Contributing

1. Create a feature branch
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Documentation Index

- **[Quick Start Guide](docs/QUICK_START.md)**: Get started quickly
- **[Configuration Guide](docs/CONFIGURATION.md)**: Complete configuration reference
  - Replicating different tables
  - Changing replication schedules
  - Replication modes
  - Advanced configuration
  - Performance tuning
- **[Customization Guide](docs/CUSTOMIZATION.md)**: Advanced customization options
  - Custom transformations
  - Schema mapping
  - Error handling
  - Custom monitoring
- **[Project Review](docs/REVIEW_SUMMARY.md)**: Review summary and recommendations
- **[Gaps and Improvements](docs/GAPS_AND_IMPROVEMENTS.md)**: Detailed gap analysis and improvement suggestions
- **[S3 Staging Guide](docs/S3_STAGING.md)**: S3 staging architecture and configuration
- **[S3 Lifecycle Management](docs/S3_LIFECYCLE_MANAGEMENT.md)**: S3 cleanup strategies and bucket maintenance
- **[Architecture Documentation](docs/ARCHITECTURE.md)**: Complete solution architecture documentation
- **[Architecture Diagrams](docs/ARCHITECTURE_DIAGRAMS.md)**: Detailed architecture diagrams

## Support

For issues and questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review the [Configuration Guide](docs/CONFIGURATION.md)
3. Check CloudWatch logs for detailed error messages
4. Open an issue in the GitHub repository with:
   - Error messages from CloudWatch logs
   - Configuration details (sanitized)
   - Steps to reproduce
