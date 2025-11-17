variable "terraform_cloud_organization" {
  description = "Terraform Cloud organization name"
  type        = string
}

variable "terraform_cloud_workspace" {
  description = "Terraform Cloud workspace name"
  type        = string
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "aurora-snowflake-replication"
}

variable "schedule_expression" {
  description = "EventBridge cron expression for scheduling"
  type        = string
  default     = "cron(0 2 * * ? *)" # Daily at 2 AM UTC
}

variable "vpc_id" {
  description = "VPC ID where Lambda will run"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for Lambda VPC configuration"
  type        = list(string)
}

variable "snowflake_vpc_endpoint_id" {
  description = "Existing VPC endpoint ID for Snowflake PrivateLink"
  type        = string
}

variable "aurora_endpoint" {
  description = "Aurora cluster endpoint"
  type        = string
}

variable "environment" {
  description = "Environment name (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 900 # 15 minutes
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 512
}

variable "vault_addr" {
  description = "Hashicorp Vault address"
  type        = string
  sensitive   = true
}

variable "vault_role" {
  description = "IAM role for Vault authentication"
  type        = string
  default     = ""
}

variable "vault_secret_path_aurora" {
  description = "Vault path for Aurora secrets"
  type        = string
  default     = "secret/aurora/connection"
}

variable "vault_secret_path_snowflake" {
  description = "Vault path for Snowflake secrets"
  type        = string
  default     = "secret/snowflake/credentials"
}

variable "snowflake_endpoint" {
  description = "Snowflake PrivateLink endpoint URL"
  type        = string
}

variable "replication_mode" {
  description = "Replication mode: 'full' or 'incremental'"
  type        = string
  default     = "full"
  validation {
    condition     = contains(["full", "incremental"], var.replication_mode)
    error_message = "Replication mode must be 'full' or 'incremental'."
  }
}

variable "incremental_column" {
  description = "Column name for incremental extraction (if incremental mode)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "s3_stage_prefix" {
  description = "S3 prefix/path for staging files"
  type        = string
  default     = "staging"
}

variable "s3_file_format" {
  description = "File format for S3 staging: 'csv' or 'parquet'"
  type        = string
  default     = "csv"
  validation {
    condition     = contains(["csv", "parquet"], var.s3_file_format)
    error_message = "S3 file format must be 'csv' or 'parquet'."
  }
}

variable "snowflake_storage_integration" {
  description = "Snowflake storage integration name (optional, uses IAM role if not provided)"
  type        = string
  default     = ""
}

variable "cleanup_s3_files" {
  description = "Whether to delete S3 files after successful load to Snowflake"
  type        = string
  default     = "true"
}

variable "s3_cleanup_mode" {
  description = "S3 cleanup mode: 'after_all' (clean after all batches load), 'after_each' (clean after each file), 'never' (rely on lifecycle policy)"
  type        = string
  default     = "after_all"
  validation {
    condition     = contains(["after_all", "after_each", "never"], var.s3_cleanup_mode)
    error_message = "S3 cleanup mode must be 'after_all', 'after_each', or 'never'."
  }
}

