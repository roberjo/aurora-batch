# Optional Lambda function for S3 cleanup maintenance
# This can be scheduled to run periodically to clean up orphaned files

resource "aws_lambda_function" "s3_cleanup" {
  count = var.enable_s3_cleanup_lambda ? 1 : 0

  filename         = var.lambda_deployment_package_path != "" ? var.lambda_deployment_package_path : null
  function_name    = "${var.lambda_function_name}-s3-cleanup"
  role            = aws_iam_role.lambda_execution.arn
  handler         = "s3_cleanup_lambda.lambda_handler"
  runtime         = "python3.11"
  timeout         = 300  # 5 minutes
  memory_size     = 256
  source_code_hash = var.lambda_deployment_package_path != "" ? filebase64sha256(var.lambda_deployment_package_path) : null

  environment {
    variables = {
      S3_STAGE_BUCKET = aws_s3_bucket.snowflake_stage.id
      S3_STAGE_PREFIX = var.s3_stage_prefix
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.lambda_function_name}-s3-cleanup"
    }
  )

  depends_on = [
    aws_cloudwatch_log_group.s3_cleanup
  ]
}

resource "aws_cloudwatch_log_group" "s3_cleanup" {
  count             = var.enable_s3_cleanup_lambda ? 1 : 0
  name              = "/aws/lambda/${var.lambda_function_name}-s3-cleanup"
  retention_in_days = 14

  tags = merge(
    var.tags,
    {
      Name = "${var.lambda_function_name}-s3-cleanup-logs"
    }
  )
}

resource "aws_cloudwatch_event_rule" "s3_cleanup_schedule" {
  count = var.enable_s3_cleanup_lambda ? 1 : 0

  name                = "${var.lambda_function_name}-s3-cleanup-schedule"
  description         = "Schedule for S3 cleanup maintenance"
  schedule_expression = var.s3_cleanup_schedule_expression

  tags = merge(
    var.tags,
    {
      Name = "${var.lambda_function_name}-s3-cleanup-schedule"
    }
  )
}

resource "aws_cloudwatch_event_target" "s3_cleanup" {
  count = var.enable_s3_cleanup_lambda ? 1 : 0

  rule      = aws_cloudwatch_event_rule.s3_cleanup_schedule[0].name
  target_id = "${var.lambda_function_name}-s3-cleanup-target"
  arn       = aws_lambda_function.s3_cleanup[0].arn

  input = jsonencode({
    action         = "cleanup_orphaned"
    max_age_hours  = var.s3_cleanup_orphaned_max_age_hours
    dry_run        = false
  })
}

resource "aws_lambda_permission" "s3_cleanup_eventbridge" {
  count = var.enable_s3_cleanup_lambda ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.s3_cleanup[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.s3_cleanup_schedule[0].arn
}

variable "enable_s3_cleanup_lambda" {
  description = "Enable separate Lambda function for S3 cleanup maintenance"
  type        = bool
  default     = false
}

variable "s3_cleanup_schedule_expression" {
  description = "Schedule expression for S3 cleanup Lambda (e.g., daily at 3 AM)"
  type        = string
  default     = "cron(0 3 * * ? *)"  # Daily at 3 AM UTC
}

variable "s3_cleanup_orphaned_max_age_hours" {
  description = "Maximum age in hours before considering S3 file orphaned"
  type        = number
  default     = 24  # 24 hours
}

