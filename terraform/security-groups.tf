resource "aws_security_group" "lambda" {
  name        = "${var.lambda_function_name}-sg"
  description = "Security group for Lambda function"
  vpc_id      = var.vpc_id

  egress {
    description = "Allow outbound to Aurora PostgreSQL"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow outbound HTTPS for Vault and Snowflake"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow outbound to VPC endpoint"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.selected.cidr_block]
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.lambda_function_name}-sg"
    }
  )
}

data "aws_vpc" "selected" {
  id = var.vpc_id
}

