resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = 14

  tags = merge(
    var.tags,
    {
      Name = "${var.lambda_function_name}-logs"
    }
  )
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.lambda_function_name}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "This metric monitors Lambda function errors"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.replication.function_name
  }

  alarm_actions = var.cloudwatch_alarm_sns_topic_arn != "" ? [var.cloudwatch_alarm_sns_topic_arn] : []

  tags = merge(
    var.tags,
    {
      Name = "${var.lambda_function_name}-errors-alarm"
    }
  )
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${var.lambda_function_name}-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Average"
  threshold           = var.lambda_timeout * 1000 * 0.9 # 90% of timeout
  alarm_description   = "This metric monitors Lambda function duration"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.replication.function_name
  }

  alarm_actions = var.cloudwatch_alarm_sns_topic_arn != "" ? [var.cloudwatch_alarm_sns_topic_arn] : []

  tags = merge(
    var.tags,
    {
      Name = "${var.lambda_function_name}-duration-alarm"
    }
  )
}

variable "cloudwatch_alarm_sns_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarms (optional)"
  type        = string
  default     = ""
}

