resource "aws_s3_bucket" "snowflake_stage" {
  # S3 bucket names must be globally unique
  # Using a hash of region and function name to ensure uniqueness
  bucket = "${var.lambda_function_name}-snowflake-stage-${var.environment}-${substr(md5("${var.aws_region}${var.lambda_function_name}"), 0, 8)}"

  tags = merge(
    var.tags,
    {
      Name        = "${var.lambda_function_name}-snowflake-stage"
      Environment = var.environment
      Purpose     = "Snowflake external stage"
    }
  )
}

resource "aws_s3_bucket_versioning" "snowflake_stage" {
  bucket = aws_s3_bucket.snowflake_stage.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "snowflake_stage" {
  bucket = aws_s3_bucket.snowflake_stage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "snowflake_stage" {
  bucket = aws_s3_bucket.snowflake_stage.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    # Transition to Infrequent Access after 1 day
    transition {
      days          = 1
      storage_class = "STANDARD_IA"
    }

    # Transition to Glacier after 7 days
    transition {
      days          = var.s3_stage_retention_days
      storage_class = "GLACIER"
    }

    # Delete files after retention period
    expiration {
      days = var.s3_stage_retention_days
    }

    # Delete old versions
    noncurrent_version_expiration {
      noncurrent_days = var.s3_stage_retention_days
    }

    # Clean up incomplete multipart uploads
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  # Rule for failed/error files (keep longer for debugging)
  rule {
    id     = "error-files-retention"
    status = "Enabled"
    prefix = "${var.s3_stage_prefix}/errors/"

    expiration {
      days = var.s3_stage_retention_days * 2  # Keep error files twice as long
    }
  }
}

resource "aws_s3_bucket_public_access_block" "snowflake_stage" {
  bucket = aws_s3_bucket.snowflake_stage.id

  block_public_acls       = true
  block_public_policy    = true
  ignore_public_acls     = true
  restrict_public_buckets = true
}

# IAM role for Snowflake to access S3 (for storage integration)
# Only create if snowflake_iam_user_arn or snowflake_external_id is provided
resource "aws_iam_role" "snowflake_s3_access" {
  count = var.snowflake_iam_user_arn != "" || var.snowflake_external_id != "" ? 1 : 0
  name  = "${var.lambda_function_name}-snowflake-s3-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = var.snowflake_iam_user_arn != "" ? var.snowflake_iam_user_arn : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action = "sts:AssumeRole"
        Condition = var.snowflake_external_id != "" ? {
          StringEquals = {
            "sts:ExternalId" = var.snowflake_external_id
          }
        } : {}
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.lambda_function_name}-snowflake-s3-role"
    }
  )
}

resource "aws_iam_role_policy" "snowflake_s3_access" {
  count = var.snowflake_iam_user_arn != "" || var.snowflake_external_id != "" ? 1 : 0
  name  = "${var.lambda_function_name}-snowflake-s3-access"
  role  = aws_iam_role.snowflake_s3_access[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.snowflake_stage.arn,
          "${aws_s3_bucket.snowflake_stage.arn}/*"
        ]
      }
    ]
  })
}

variable "s3_stage_retention_days" {
  description = "Number of days to retain files in S3 stage bucket"
  type        = number
  default     = 7
}

variable "snowflake_iam_user_arn" {
  description = "ARN of Snowflake IAM user (for storage integration). Leave empty if using storage integration ARN."
  type        = string
  default     = ""
}

variable "snowflake_external_id" {
  description = "External ID for Snowflake IAM role assumption"
  type        = string
  default     = ""
}

