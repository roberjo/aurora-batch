# S3 Staging Architecture

This document describes the S3 staging architecture for Snowflake data loading.

## Overview

The replication system uses S3 as an external stage for Snowflake data loading. This approach provides several benefits:

- **Performance**: COPY INTO is faster than INSERT for large datasets
- **Cost**: More cost-effective for bulk loading
- **Reliability**: Better error handling and retry capabilities
- **Scalability**: Handles very large datasets efficiently

## Architecture Flow

```
Aurora PostgreSQL → Lambda → S3 Bucket → Snowflake COPY INTO
```

### Process Flow

1. **Extract**: Lambda extracts data batches from Aurora PostgreSQL
2. **Stage**: Lambda uploads batches as files (CSV/Parquet) to S3
3. **Load**: Lambda triggers Snowflake COPY INTO to load from S3
4. **Cleanup**: Optionally delete S3 files after successful load

## S3 Bucket Configuration

### Bucket Properties

- **Name**: `{lambda-function-name}-snowflake-stage-{environment}-{hash}`
- **Versioning**: Enabled for data recovery
- **Encryption**: AES256 server-side encryption
- **Lifecycle**: Automatic deletion after retention period (default: 7 days)
- **Public Access**: Blocked

### File Organization

```
s3://bucket-name/
└── staging/
    └── {schema_name}/
        └── {table_name}/
            ├── {schema}_{table}_batch0_{timestamp}.csv
            ├── {schema}_{table}_batch1_{timestamp}.csv
            └── ...
```

## Snowflake Integration

### Storage Integration (Recommended)

Create a Snowflake storage integration:

```sql
CREATE STORAGE INTEGRATION s3_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::123456789012:role/snowflake-s3-role'
  ENABLED = TRUE
  STORAGE_AWS_OBJECT_ACL = 'bucket-owner-full-control';

-- Grant usage to replication role
GRANT USAGE ON INTEGRATION s3_integration TO ROLE replication_role;
```

### IAM Role Method (Alternative)

If not using storage integration, provide IAM role ARN directly:

```python
# In Lambda environment variables
SNOWFLAKE_STORAGE_INTEGRATION = ""  # Empty
# Snowflake will use IAM role from connection params
```

## Configuration

### Terraform Variables

```hcl
s3_stage_prefix              = "staging"
s3_file_format               = "csv"  # or "parquet"
s3_stage_retention_days      = 7
snowflake_storage_integration = "s3_integration"  # Optional
cleanup_s3_files             = "false"  # Set to "true" to auto-delete
snowflake_iam_user_arn       = ""  # For storage integration
snowflake_external_id        = ""  # For storage integration
```

### Lambda Environment Variables

- `S3_STAGE_BUCKET`: S3 bucket name (auto-set from Terraform)
- `S3_STAGE_PREFIX`: S3 prefix/path (default: "staging")
- `S3_FILE_FORMAT`: File format - "csv" or "parquet"
- `SNOWFLAKE_STORAGE_INTEGRATION`: Storage integration name (optional)
- `CLEANUP_S3_FILES`: "true" to delete files after load, "false" to keep

## File Formats

### CSV Format

**Pros:**
- Human-readable
- Smaller Lambda package (no pandas/pyarrow)
- Universal compatibility

**Cons:**
- Slower for large datasets
- Less efficient compression

**Use When:**
- Small to medium datasets
- Need human-readable files
- Want smaller Lambda package

### Parquet Format

**Pros:**
- Faster loading
- Better compression
- Columnar format optimized for analytics

**Cons:**
- Requires pandas/pyarrow (larger package)
- Not human-readable

**Use When:**
- Large datasets
- Performance is critical
- Storage costs matter

## COPY INTO Command

The system uses Snowflake COPY INTO command:

```sql
COPY INTO "schema"."table"
FROM 's3://bucket-name/staging/schema/table/file.csv'
STORAGE_INTEGRATION = s3_integration
FILE_FORMAT = (TYPE = 'CSV')
ON_ERROR = 'ABORT_STATEMENT'
```

### Error Handling

- `ABORT_STATEMENT`: Stop on any error (default)
- `SKIP_FILE`: Skip file on error
- `CONTINUE`: Continue loading other files

## Performance Considerations

### Batch Size

- **Small batches** (< 10K rows): Use INSERT (direct load)
- **Medium batches** (10K - 100K rows): Use S3 staging with CSV
- **Large batches** (> 100K rows): Use S3 staging with Parquet

### File Size

- Optimal file size: 100-250 MB compressed
- Too small: Many small files (overhead)
- Too large: Slower processing, memory issues

### Parallel Loading

Snowflake can load multiple files in parallel:
- Upload multiple files to S3
- COPY INTO loads all files concurrently
- Faster than sequential loading

## Cost Optimization

### S3 Costs

- **Storage**: ~$0.023/GB/month
- **PUT requests**: ~$0.005 per 1,000 requests
- **GET requests**: ~$0.0004 per 1,000 requests

### Snowflake Costs

- COPY INTO uses warehouse compute time
- More efficient than INSERT for large datasets
- Consider warehouse size and auto-suspend

### Lifecycle Policies

- Automatic deletion after retention period
- Reduces storage costs
- Configurable retention (default: 7 days)

## Security

### Encryption

- **In Transit**: TLS encryption for S3 uploads
- **At Rest**: AES256 server-side encryption
- **Snowflake**: Encrypted connection via PrivateLink

### Access Control

- **Lambda**: IAM role with S3 write permissions
- **Snowflake**: Storage integration or IAM role with read permissions
- **Bucket Policy**: Restrictive access rules

### Network Security

- S3 accessed via AWS network (no public internet)
- Snowflake accesses S3 via storage integration
- All traffic encrypted

## Monitoring

### S3 Metrics

Monitor via CloudWatch:
- `NumberOfObjects`: Number of files in bucket
- `BucketSizeBytes`: Total storage used
- `AllRequests`: Request count

### Lambda Metrics

- Upload duration
- File size
- Upload success/failure

### Snowflake Metrics

- COPY INTO duration
- Rows loaded
- Errors encountered

## Troubleshooting

### S3 Upload Failures

**Symptoms**: Lambda fails to upload files

**Solutions:**
- Check IAM permissions for Lambda
- Verify bucket exists and is accessible
- Check bucket policy
- Review CloudWatch logs

### Snowflake COPY INTO Failures

**Symptoms**: COPY INTO command fails

**Solutions:**
- Verify storage integration exists and is enabled
- Check IAM role permissions
- Verify file format matches COPY INTO format
- Check file exists in S3
- Review Snowflake query history

### File Format Mismatches

**Symptoms**: Data not loading correctly

**Solutions:**
- Verify CSV format (headers, delimiters, quotes)
- Check Parquet schema matches Snowflake table
- Review file encoding (UTF-8)

### Performance Issues

**Symptoms**: Slow loading

**Solutions:**
- Increase warehouse size
- Use Parquet format for large datasets
- Optimize batch sizes
- Use parallel file loading

## Migration from Direct INSERT

If migrating from direct INSERT to S3 staging:

1. **Deploy new Lambda code** with S3 client
2. **Create S3 bucket** via Terraform
3. **Create Snowflake storage integration**
4. **Update Lambda environment variables**
5. **Test with small dataset**
6. **Monitor performance and costs**
7. **Gradually migrate all tables**

## Best Practices

1. **Use Parquet for large datasets** (> 100K rows)
2. **Set appropriate retention** (7-30 days)
3. **Enable versioning** for recovery
4. **Monitor S3 costs** regularly
5. **Use storage integration** (more secure)
6. **Clean up files** after successful load (recommended: `after_all` mode)
7. **Optimize batch sizes** for your data
8. **Use parallel loading** when possible
9. **Enable cleanup Lambda** for orphaned file management
10. **Monitor bucket size** with CloudWatch alarms

See [S3 Lifecycle Management Guide](S3_LIFECYCLE_MANAGEMENT.md) for detailed cleanup strategies.

## Example Configuration

### Terraform

```hcl
s3_stage_prefix              = "staging"
s3_file_format               = "parquet"
s3_stage_retention_days      = 7
snowflake_storage_integration = "s3_integration"
cleanup_s3_files             = "true"
```

### Snowflake Storage Integration

```sql
CREATE STORAGE INTEGRATION s3_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::123456789012:role/aurora-snowflake-replication-snowflake-s3-role'
  ENABLED = TRUE;
```

### Lambda Event

```json
{
  "schema_name": "public",
  "table_name": "customers"
}
```

The system will automatically:
1. Extract data from Aurora
2. Upload batches to S3
3. Load from S3 to Snowflake
4. Clean up S3 files (if enabled)

