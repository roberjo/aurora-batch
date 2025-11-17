# Note: VPC endpoint for Snowflake is assumed to already exist
# This file documents the dependency and can be used for data source lookup if needed

data "aws_vpc_endpoint" "snowflake" {
  id = var.snowflake_vpc_endpoint_id
}

