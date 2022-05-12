locals {
  tags_prod = {
    Source  = "terraform"
    Project = "mentor-upload-processor"
    Stage   = "prod"
  }
}

module "firewall_prod" {
  source         = "git@github.com:mentorpal/terraform-modules//modules/api-waf?ref=tags/v1.2.0"
  name           = "mentor-upload-processor-prod"
  aws_region     = "us-west-2"
  enable_logging = true

  tags = local.tags_prod

  providers = {
    aws = aws.us_west_2
  }
}

# This cannot be done in TF because serverless needs to create its ApiGateway first:
# resource "aws_wafv2_web_acl_association" "waf_api_gateway" {
#   resource_arn = ?
#   web_acl_arn  = aws_wafv2_web_acl.firewall_qa.arn
# }
# solution - export arn to SSM and let serverless associate them:
resource "aws_ssm_parameter" "web_acl_prod_arn" {
  name  = "/mentorpal/mentor-upload-processor/prod/firewall/WEBACL_ARN"
  type  = "String"
  value = module.firewall_qa.wafv2_webacl_arn
  tags  = local.tags_prod
}
