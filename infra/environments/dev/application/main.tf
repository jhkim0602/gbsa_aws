terraform {
  required_version = ">= 1.10.0"

  backend "s3" {
    key          = "dev/application/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "ap-northeast-2"
}

variable "state_bucket" {
  type = string
}

variable "hosted_zone_id" {
  type = string
}

variable "company_domain" {
  type = string
}

variable "applicant_domain" {
  type = string
}

variable "api_image" {
  type = string
}

variable "worker_image" {
  type = string
}

variable "interview_model_id" {
  type = string
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "dev"
      ManagedBy   = "Terraform"
      Project     = "InterviewEvidencePlatform"
    }
  }
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

data "terraform_remote_state" "foundation" {
  backend = "s3"
  config = {
    bucket       = var.state_bucket
    key          = "dev/foundation/terraform.tfstate"
    region       = var.aws_region
    use_lockfile = true
  }
}

data "terraform_remote_state" "data_ai" {
  backend = "s3"
  config = {
    bucket       = var.state_bucket
    key          = "dev/data-ai/terraform.tfstate"
    region       = var.aws_region
    use_lockfile = true
  }
}

locals {
  name      = data.terraform_remote_state.foundation.outputs.name
  data      = data.terraform_remote_state.data_ai.outputs.data
  workflow  = data.terraform_remote_state.data_ai.outputs.workflow
  ai_search = data.terraform_remote_state.data_ai.outputs.ai_search
  tags = {
    Environment = "dev"
  }
  bucket_resources = concat(
    values(local.data.bucket_arns),
    [for arn in values(local.data.bucket_arns) : "${arn}/*"],
  )
}

module "compute" {
  source = "../../../modules/compute"

  name                          = local.name
  vpc_id                        = data.terraform_remote_state.foundation.outputs.network.vpc_id
  private_subnet_ids            = data.terraform_remote_state.foundation.outputs.network.private_subnet_ids
  alb_subnet_ids                = data.terraform_remote_state.foundation.outputs.network.public_subnet_ids
  alb_security_group_id         = data.terraform_remote_state.foundation.outputs.network.alb_security_group_id
  application_security_group_id = data.terraform_remote_state.foundation.outputs.network.application_security_group_id
  api_image                     = var.api_image
  worker_image                  = var.worker_image
  task_role_arn                 = data.terraform_remote_state.foundation.outputs.identity.application_runtime_role_arn
  task_role_name                = data.terraform_remote_state.foundation.outputs.identity.application_runtime_role_name
  create_task_role              = false
  secret_arns                   = [local.data.application_secret_arn, local.data.aurora_master_secret_arn]
  kms_key_arns                  = [local.data.kms_key_arn]
  data_resource_arns = concat(
    local.bucket_resources,
    [local.data.dynamodb_table_arn],
    values(local.workflow.queue_arns),
  )
  task_environment = {
    APPLICANT_ACCESS_BASE_URL  = "https://${var.applicant_domain}/access"
    APP_ENVIRONMENT            = "dev"
    AWS_REGION                 = var.aws_region
    AURORA_DATABASE            = local.data.aurora_database_name
    AURORA_ENDPOINT            = local.data.aurora_endpoint
    AURORA_MASTER_SECRET_ARN   = local.data.aurora_master_secret_arn
    BEDROCK_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
    BEDROCK_GUARDRAIL_ID       = local.ai_search.guardrail_id
    BEDROCK_MODEL_ID           = var.interview_model_id
    COGNITO_USER_POOL_ID       = data.terraform_remote_state.foundation.outputs.identity.user_pool_id
    DYNAMODB_TABLE_NAME        = local.data.dynamodb_table_name
    EVENT_BUS_ARN              = local.workflow.event_bus_arn
    KMS_KEY_ARN                = local.data.kms_key_arn
    MEDIA_BUCKET               = local.data.bucket_ids["media"]
    RETRIEVAL_BACKEND          = "aurora"
    SES_FROM_ADDRESS           = "noreply@${var.company_domain}"
    SOURCE_BUCKET              = local.data.bucket_ids["source"]
    SQS_ANALYSIS_QUEUE_URL     = local.workflow.queue_urls["analysis"]
    SQS_DELETION_QUEUE_URL     = local.workflow.queue_urls["deletion"]
    SQS_MEDIA_QUEUE_URL        = local.workflow.queue_urls["media"]
    SQS_REPORTING_QUEUE_URL    = local.workflow.queue_urls["reporting"]
  }
  tags = local.tags
}

module "edge" {
  source = "../../../modules/edge"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  name                         = local.name
  hosted_zone_id               = var.hosted_zone_id
  company_domain               = var.company_domain
  applicant_domain             = var.applicant_domain
  company_bucket_id            = local.data.bucket_ids["company-spa"]
  company_bucket_arn           = local.data.bucket_arns["company-spa"]
  company_bucket_domain_name   = local.data.bucket_regional_domain_names["company-spa"]
  applicant_bucket_id          = local.data.bucket_ids["applicant-spa"]
  applicant_bucket_arn         = local.data.bucket_arns["applicant-spa"]
  applicant_bucket_domain_name = local.data.bucket_regional_domain_names["applicant-spa"]
  api_origin_domain_name       = module.compute.alb_dns_name
  tags                         = local.tags
}

output "application" {
  value = {
    cluster_name              = module.compute.cluster_name
    api_service_name          = module.compute.api_service_name
    worker_service_name       = module.compute.worker_service_name
    api_repository_url        = module.compute.api_repository_url
    worker_repository_url     = module.compute.worker_repository_url
    distribution_ids          = module.edge.distribution_ids
    distribution_domain_names = module.edge.distribution_domain_names
  }
}
