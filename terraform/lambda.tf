resource "aws_lambda_function" "replication" {
  filename         = var.lambda_deployment_package_path != "" ? var.lambda_deployment_package_path : null
  function_name    = var.lambda_function_name
  role            = aws_iam_role.lambda_execution.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.11"
  timeout         = var.lambda_timeout
  memory_size     = var.lambda_memory_size
  source_code_hash = var.lambda_deployment_package_path != "" ? filebase64sha256(var.lambda_deployment_package_path) : null

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      VAULT_ADDR                = var.vault_addr
      VAULT_ROLE                = var.vault_role
      VAULT_SECRET_PATH_AURORA  = var.vault_secret_path_aurora
      VAULT_SECRET_PATH_SNOWFLAKE = var.vault_secret_path_snowflake
      SNOWFLAKE_ENDPOINT        = var.snowflake_endpoint
      REPLICATION_MODE          = var.replication_mode
      INCREMENTAL_COLUMN        = var.incremental_column
      ENVIRONMENT               = var.environment
    }
  }

  tags = merge(
    var.tags,
    {
      Name = var.lambda_function_name
    }
  )

  depends_on = [
    aws_iam_role_policy_attachment.lambda_vpc_execution,
    aws_cloudwatch_log_group.lambda
  ]
}

variable "lambda_deployment_package_path" {
  description = "Path to Lambda deployment package (zip file). Leave empty for initial creation."
  type        = string
  default     = ""
}

