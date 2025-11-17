# CloudWatch metrics and alarms for S3 bucket

resource "aws_cloudwatch_metric_alarm" "s3_bucket_size" {
  alarm_name          = "${var.lambda_function_name}-s3-bucket-size"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "BucketSizeBytes"
  namespace           = "AWS/S3"
  period              = 86400  # 24 hours
  statistic           = "Average"
  threshold           = var.s3_bucket_size_alarm_threshold_gb * 1024 * 1024 * 1024  # Convert GB to bytes
  alarm_description   = "This metric monitors S3 bucket size"
  treat_missing_data  = "notBreaching"

  dimensions = {
    BucketName  = aws_s3_bucket.snowflake_stage.id
    StorageType = "StandardStorage"
  }

  alarm_actions = var.cloudwatch_alarm_sns_topic_arn != "" ? [var.cloudwatch_alarm_sns_topic_arn] : []

  tags = merge(
    var.tags,
    {
      Name = "${var.lambda_function_name}-s3-bucket-size-alarm"
    }
  )
}

resource "aws_cloudwatch_metric_alarm" "s3_number_of_objects" {
  alarm_name          = "${var.lambda_function_name}-s3-number-of-objects"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "NumberOfObjects"
  namespace           = "AWS/S3"
  period              = 86400  # 24 hours
  statistic           = "Average"
  threshold           = var.s3_bucket_object_count_alarm_threshold
  alarm_description   = "This metric monitors number of objects in S3 bucket"
  treat_missing_data  = "notBreaching"

  dimensions = {
    BucketName  = aws_s3_bucket.snowflake_stage.id
    StorageType = "AllStorageTypes"
  }

  alarm_actions = var.cloudwatch_alarm_sns_topic_arn != "" ? [var.cloudwatch_alarm_sns_topic_arn] : []

  tags = merge(
    var.tags,
    {
      Name = "${var.lambda_function_name}-s3-object-count-alarm"
    }
  )
}

variable "s3_bucket_size_alarm_threshold_gb" {
  description = "S3 bucket size alarm threshold in GB"
  type        = number
  default     = 100  # Alert if bucket exceeds 100 GB
}

variable "s3_bucket_object_count_alarm_threshold" {
  description = "S3 bucket object count alarm threshold"
  type        = number
  default     = 10000  # Alert if bucket has more than 10,000 objects
}

