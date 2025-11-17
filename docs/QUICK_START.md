# Quick Start Guide

Get up and running with Aurora to Snowflake replication in minutes.

## Prerequisites Checklist

- [ ] AWS Account with Aurora PostgreSQL cluster
- [ ] Snowflake account with PrivateLink endpoint configured
- [ ] Terraform Cloud account and workspace
- [ ] Hashicorp Vault instance
- [ ] GitHub repository
- [ ] Artifactory access
- [ ] Harness CI/CD access

## Step-by-Step Setup

### Step 1: Configure Vault Secrets

**Aurora Connection** (`secret/aurora/connection`):
```bash
vault kv put secret/aurora/connection \
  host="aurora-cluster.region.rds.amazonaws.com" \
  port=5432 \
  database="your_database" \
  user="replication_user" \
  password="secure_password"
```

**Snowflake Credentials** (`secret/snowflake/credentials`):
```bash
vault kv put secret/snowflake/credentials \
  account="your_account" \
  user="replication_user" \
  password="secure_password" \
  warehouse="COMPUTE_WH" \
  database="REPLICATION_DB" \
  schema="PUBLIC" \
  role="REPLICATION_ROLE"
```

### Step 2: Configure Terraform Variables

Copy the example file:
```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Edit `terraform/terraform.tfvars` with your values:
```hcl
terraform_cloud_organization = "your-org"
terraform_cloud_workspace   = "aurora-snowflake-replication"
aws_region                  = "us-east-1"
vpc_id                      = "vpc-xxxxxxxxx"
subnet_ids                  = ["subnet-xxxxxxxxx"]
snowflake_vpc_endpoint_id   = "vpce-xxxxxxxxx"
aurora_endpoint             = "aurora-cluster.region.rds.amazonaws.com"
vault_addr                  = "https://vault.example.com"
snowflake_endpoint          = "snowflake.example.com"
```

### Step 3: Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### Step 4: Configure Table to Replicate

**Option A: Environment Variable (Single Table)**
```hcl
# In terraform/lambda.tf, add to environment variables:
SCHEMA_NAME = "public"
TABLE_NAME  = "customers"
```

**Option B: Event-Driven (Flexible)**
No changes needed - specify table in Lambda invocation.

### Step 5: Set Replication Schedule

Edit `terraform/terraform.tfvars`:
```hcl
schedule_expression = "cron(0 2 * * ? *)"  # Daily at 2 AM UTC
```

Apply changes:
```bash
terraform apply
```

### Step 6: Build and Deploy Lambda

1. Push code to GitHub (triggers build)
2. Run Harness pipeline to deploy Lambda function

### Step 7: Test Replication

**Manual Test:**
```bash
aws lambda invoke \
  --function-name aurora-snowflake-replication \
  --payload '{"schema_name":"public","table_name":"customers"}' \
  response.json

cat response.json
```

**Check CloudWatch Logs:**
```bash
aws logs tail /aws/lambda/aurora-snowflake-replication --follow
```

**Verify in Snowflake:**
```sql
SELECT COUNT(*) FROM PUBLIC.customers;
```

## Common Scenarios

### Scenario 1: Replicate Single Table Daily

1. Set `TABLE_NAME` in Lambda environment variables
2. Set schedule to `cron(0 2 * * ? *)`
3. Set `replication_mode = "full"`

### Scenario 2: Replicate Multiple Tables

1. Create separate Lambda functions per table, OR
2. Use event-driven invocation with table list
3. Configure separate schedules if needed

### Scenario 3: Incremental Replication

1. Set `replication_mode = "incremental"`
2. Set `incremental_column = "updated_at"`
3. Implement state tracking (see Configuration Guide)

### Scenario 4: High-Frequency Replication

1. Set schedule to `cron(*/15 * * * ? *)` (every 15 minutes)
2. Use incremental mode
3. Increase Lambda memory and timeout
4. Consider using Step Functions for parallel processing

## Next Steps

- Read [Configuration Guide](CONFIGURATION.md) for detailed options
- Read [Customization Guide](CUSTOMIZATION.md) for advanced features
- Review [Troubleshooting](README.md#troubleshooting) section

## Verification Checklist

- [ ] Lambda function deployed successfully
- [ ] EventBridge rule created and enabled
- [ ] CloudWatch log group created
- [ ] Security groups configured correctly
- [ ] VPC endpoints accessible
- [ ] Vault secrets accessible
- [ ] Test invocation successful
- [ ] Data appears in Snowflake
- [ ] CloudWatch alarms configured

## Getting Help

- Check [Troubleshooting](README.md#troubleshooting) section
- Review CloudWatch logs for errors
- Verify all prerequisites are met
- Check IAM permissions
- Verify network connectivity

