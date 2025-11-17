# S3 Lifecycle Management and Cleanup Strategy

This document explains the S3 bucket lifecycle management and cleanup strategies for maintaining optimal bucket size and preventing data accumulation.

## Cleanup Strategy Overview

### When Files Are Cleaned

**Current Behavior:**
- Files are cleaned **AFTER all batches are successfully loaded** (not after each batch)
- This ensures all files are available for Snowflake COPY INTO
- COPY INTO can load multiple files in parallel, so we need all files present

**Why Not After Each Batch?**
- Snowflake COPY INTO loads files in parallel for better performance
- We need all files available when COPY INTO executes
- Cleaning after each batch would require sequential loading (slower)

### Cleanup Modes

The system supports three cleanup modes:

1. **`after_all`** (Recommended - Default)
   - Clean up files after ALL batches are successfully loaded
   - Best for: Normal operations, ensures data integrity
   - Files are deleted only if all loads succeed

2. **`after_each`**
   - Clean up each file immediately after it's successfully loaded
   - Best for: Very large datasets where you want immediate cleanup
   - Note: Files are loaded sequentially in this mode (slower)

3. **`never`**
   - Never delete files automatically
   - Rely entirely on S3 lifecycle policies
   - Best for: Debugging, audit requirements, or manual cleanup

## S3 Lifecycle Policies

### Automatic Lifecycle Management

The S3 bucket has automatic lifecycle policies configured:

#### Storage Class Transitions

```
Standard → Standard-IA (after 1 day) → Glacier (after 7 days) → Deleted (after retention period)
```

**Benefits:**
- **Day 1-7**: Standard storage (fast access)
- **After 7 days**: Glacier storage (cheaper, slower access)
- **After retention period**: Automatic deletion

#### Lifecycle Rules

1. **Standard Files Rule**
   - Transition to Standard-IA after 1 day
   - Transition to Glacier after retention period
   - Delete after retention period
   - Clean up incomplete multipart uploads after 1 day

2. **Error Files Rule**
   - Files in `errors/` prefix kept twice as long
   - Allows debugging of failed loads

### Configuration

```hcl
# In terraform/terraform.tfvars
s3_stage_retention_days = 7  # Files deleted after 7 days
s3_cleanup_mode         = "after_all"  # Cleanup mode
cleanup_s3_files       = "true"  # Enable cleanup
```

## Bucket Maintenance Strategies

### 1. Immediate Cleanup (Recommended)

**Configuration:**
```hcl
cleanup_s3_files = "true"
s3_cleanup_mode  = "after_all"
```

**How It Works:**
- Files are deleted immediately after successful load
- Lifecycle policy acts as safety net for any missed files
- Minimal storage costs
- Fastest cleanup

**Use When:**
- Normal production operations
- Cost optimization is important
- You don't need to retain files for debugging

### 2. Lifecycle-Only Cleanup

**Configuration:**
```hcl
cleanup_s3_files = "false"
s3_cleanup_mode  = "never"
```

**How It Works:**
- Files are never deleted by Lambda
- Lifecycle policy handles all cleanup
- Files transition to cheaper storage classes
- Automatic deletion after retention period

**Use When:**
- You want to keep files for debugging
- Audit requirements
- Manual cleanup preferred

### 3. Hybrid Approach

**Configuration:**
```hcl
cleanup_s3_files = "true"
s3_cleanup_mode  = "after_all"
s3_stage_retention_days = 3  # Shorter retention
```

**How It Works:**
- Lambda deletes files after successful load
- Lifecycle policy cleans up any orphaned files quickly
- Best of both worlds

## Monitoring and Alerts

### CloudWatch Metrics

The system monitors:

1. **Bucket Size** (`BucketSizeBytes`)
   - Alerts if bucket exceeds threshold (default: 100 GB)
   - Helps prevent unexpected costs

2. **Object Count** (`NumberOfObjects`)
   - Alerts if too many objects (default: 10,000)
   - Indicates potential cleanup issues

### Configuration

```hcl
# In terraform/terraform.tfvars
s3_bucket_size_alarm_threshold_gb = 100
s3_bucket_object_count_alarm_threshold = 10000
cloudwatch_alarm_sns_topic_arn = "arn:aws:sns:..."
```

## Orphaned File Cleanup

### What Are Orphaned Files?

Orphaned files are files that were uploaded to S3 but never successfully loaded into Snowflake. This can happen if:
- Lambda function fails mid-process
- Snowflake COPY INTO fails
- Network issues interrupt the process

### Automatic Cleanup Lambda (Optional)

A separate Lambda function can be enabled to clean up orphaned files:

```hcl
# In terraform/terraform.tfvars
enable_s3_cleanup_lambda = true
s3_cleanup_schedule_expression = "cron(0 3 * * ? *)"  # Daily at 3 AM
s3_cleanup_orphaned_max_age_hours = 24  # Clean files older than 24 hours
```

**Features:**
- Runs on schedule (default: daily at 3 AM)
- Identifies files older than threshold
- Deletes orphaned files automatically
- Can be run manually for immediate cleanup

### Manual Cleanup

You can manually invoke the cleanup Lambda:

```bash
# Get bucket statistics
aws lambda invoke \
  --function-name aurora-snowflake-replication-s3-cleanup \
  --payload '{"action":"stats"}' \
  response.json

# Clean up old files (dry run)
aws lambda invoke \
  --function-name aurora-snowflake-replication-s3-cleanup \
  --payload '{"action":"cleanup_old","older_than_days":7,"dry_run":true}' \
  response.json

# Clean up orphaned files
aws lambda invoke \
  --function-name aurora-snowflake-replication-s3-cleanup \
  --payload '{"action":"cleanup_orphaned","max_age_hours":24,"dry_run":false}' \
  response.json
```

## Best Practices

### 1. Enable Immediate Cleanup

```hcl
cleanup_s3_files = "true"
s3_cleanup_mode  = "after_all"
```

**Benefits:**
- Minimal storage costs
- Fast cleanup
- Lifecycle policy as safety net

### 2. Set Appropriate Retention

```hcl
s3_stage_retention_days = 7  # Adjust based on needs
```

**Considerations:**
- Shorter retention = lower costs
- Longer retention = better debugging capability
- Balance based on your needs

### 3. Enable Monitoring

```hcl
s3_bucket_size_alarm_threshold_gb = 50  # Alert at 50 GB
s3_bucket_object_count_alarm_threshold = 5000  # Alert at 5K objects
```

**Benefits:**
- Early warning of issues
- Cost control
- Performance monitoring

### 4. Use Storage Class Transitions

The lifecycle policy automatically transitions files:
- Standard → Standard-IA (after 1 day) - 50% cost savings
- Standard-IA → Glacier (after 7 days) - 80% cost savings

**Cost Impact:**
- Standard: ~$0.023/GB/month
- Standard-IA: ~$0.0125/GB/month
- Glacier: ~$0.004/GB/month

### 5. Enable Cleanup Lambda for Orphaned Files

```hcl
enable_s3_cleanup_lambda = true
```

**Benefits:**
- Automatic cleanup of failed uploads
- Prevents bucket growth
- No manual intervention needed

## Cost Optimization

### Storage Costs

**Example Calculation:**
- Average file size: 10 MB
- Files per replication: 10 files
- Replications per day: 1
- Retention: 7 days

**Storage:**
- Peak storage: 10 files × 10 MB × 7 days = 700 MB
- Average storage: ~350 MB (files deleted as they age)
- Monthly cost: ~$0.008 (very low)

### Lifecycle Transitions

Files automatically transition to cheaper storage:
- Day 1-7: Standard storage
- After 7 days: Glacier (if not deleted)
- Cost savings: ~80% for old files

### Cleanup Impact

**With Immediate Cleanup:**
- Files deleted after load
- Storage: ~100 MB peak
- Monthly cost: ~$0.002

**Without Cleanup (Lifecycle Only):**
- Files kept for 7 days
- Storage: ~700 MB peak
- Monthly cost: ~$0.016

**Savings:** ~87% with immediate cleanup

## Troubleshooting

### Bucket Growing Too Large

**Symptoms:** Bucket size exceeds expectations

**Solutions:**
1. Check if cleanup is enabled: `cleanup_s3_files = "true"`
2. Verify cleanup mode: `s3_cleanup_mode = "after_all"`
3. Check for failed loads (files not being cleaned)
4. Review CloudWatch logs for cleanup errors
5. Run manual cleanup Lambda

### Files Not Being Cleaned

**Symptoms:** Files accumulate in S3

**Solutions:**
1. Verify `CLEANUP_S3_FILES` environment variable is "true"
2. Check `S3_CLEANUP_MODE` setting
3. Review Lambda logs for cleanup errors
4. Verify IAM permissions for S3 delete
5. Check if loads are failing (failed files aren't cleaned)

### High Storage Costs

**Symptoms:** Unexpected S3 charges

**Solutions:**
1. Enable immediate cleanup
2. Reduce retention period
3. Enable cleanup Lambda for orphaned files
4. Review bucket size alarms
5. Check for large files (optimize batch size)

## Configuration Examples

### Production (Cost-Optimized)

```hcl
cleanup_s3_files              = "true"
s3_cleanup_mode              = "after_all"
s3_stage_retention_days      = 3
enable_s3_cleanup_lambda     = true
s3_cleanup_orphaned_max_age_hours = 12
```

### Development (Debug-Friendly)

```hcl
cleanup_s3_files              = "false"
s3_cleanup_mode              = "never"
s3_stage_retention_days      = 14
enable_s3_cleanup_lambda     = false
```

### Balanced

```hcl
cleanup_s3_files              = "true"
s3_cleanup_mode              = "after_all"
s3_stage_retention_days      = 7
enable_s3_cleanup_lambda     = true
s3_cleanup_orphaned_max_age_hours = 24
```

## Summary

**Recommended Configuration:**
- ✅ Enable immediate cleanup (`cleanup_s3_files = "true"`)
- ✅ Use `after_all` mode (clean after all batches load)
- ✅ Set retention to 7 days (safety net)
- ✅ Enable cleanup Lambda for orphaned files
- ✅ Monitor bucket size and object count
- ✅ Use lifecycle transitions for cost savings

This approach ensures:
- Minimal storage costs
- Fast cleanup
- Safety net for failures
- Automatic orphaned file cleanup
- Cost-effective storage transitions

