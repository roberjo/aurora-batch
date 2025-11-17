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
├── .github/
│   └── workflows/
│       └── build.yml      # GitHub Actions workflow
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

### Replication Modes

**Full Replication** (default):
- Replicates all data from the source table
- Truncates target table before loading

**Incremental Replication**:
- Only replicates new/changed rows based on incremental column
- Requires `INCREMENTAL_COLUMN` environment variable
- Uses `last_value` from event or previous run

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

- Increase `lambda_timeout` in Terraform variables
- Reduce `BATCH_SIZE` environment variable
- Optimize Aurora queries

### Connection Issues

- Verify VPC endpoint for Snowflake is configured correctly
- Check security group rules allow outbound traffic
- Verify Vault connectivity from Lambda VPC

### Authentication Errors

- Verify Vault credentials and authentication method
- Check IAM role has permissions for Vault (if using IAM auth)
- Verify Vault token is valid (if using token auth)

## Contributing

1. Create a feature branch
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions, please open an issue in the GitHub repository.
