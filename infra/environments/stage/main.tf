terraform {
  required_version = ">= 1.10.0"

  backend "s3" {
    key          = "stage/terraform.tfstate"
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
      Environment = "stage"
      ManagedBy   = "Terraform"
      Project     = "InterviewEvidencePlatform"
    }
  }
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

locals {
  name = "iep-stage"
  tags = {
    Environment = "stage"
  }
}

module "network" {
  source = "../../modules/network"
  name   = local.name
  tags   = local.tags
}

module "identity" {
  source = "../../modules/identity"

  name                = local.name
  company_domain      = var.company_domain
  deletion_protection = false
  tags                = local.tags
}

module "data" {
  source = "../../modules/data"

  name                       = local.name
  private_subnet_ids         = module.network.private_subnet_ids
  database_security_group_id = module.network.database_security_group_id
  deletion_protection        = false
  force_destroy              = false
  aurora_min_capacity        = 1
  aurora_max_capacity        = 16
  tags                       = local.tags
}

module "async_workflow" {
  source      = "../../modules/async-workflow"
  name        = local.name
  kms_key_arn = module.data.kms_key_arn
  tags        = local.tags
}

module "ai_search" {
  source = "../../modules/ai-search"

  name = local.name
  tags = local.tags
}

module "observability" {
  source = "../../modules/observability"

  name       = local.name
  queue_arns = module.async_workflow.queue_arns
  dlq_arns   = module.async_workflow.dlq_arns
  tags       = local.tags
}

module "compute" {
  source = "../../modules/compute"

  name                          = local.name
  vpc_id                        = module.network.vpc_id
  private_subnet_ids            = module.network.private_subnet_ids
  alb_subnet_ids                = module.network.public_subnet_ids
  alb_security_group_id         = module.network.alb_security_group_id
  application_security_group_id = module.network.application_security_group_id
  api_image                     = var.api_image
  worker_image                  = var.worker_image
  task_role_arn                 = module.identity.application_runtime_role_arn
  task_role_name                = module.identity.application_runtime_role_name
  create_task_role              = false
  secret_arns                   = [module.data.application_secret_arn, module.data.aurora_master_secret_arn]
  kms_key_arns                  = [module.data.kms_key_arn]
  data_resource_arns = concat(
    values(module.data.bucket_arns),
    [for arn in values(module.data.bucket_arns) : "${arn}/*"],
    [module.data.dynamodb_table_arn],
    values(module.async_workflow.queue_arns),
  )
  task_environment = {
    APPLICANT_ACCESS_BASE_URL  = "https://${var.applicant_domain}/access"
    APP_ENVIRONMENT            = "stage"
    AWS_REGION                 = var.aws_region
    AURORA_DATABASE            = module.data.aurora_database_name
    AURORA_ENDPOINT            = module.data.aurora_endpoint
    AURORA_MASTER_SECRET_ARN   = module.data.aurora_master_secret_arn
    BEDROCK_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
    BEDROCK_GUARDRAIL_ID       = module.ai_search.guardrail_id
    BEDROCK_MODEL_ID           = var.interview_model_id
    COGNITO_USER_POOL_ID       = module.identity.user_pool_id
    DYNAMODB_TABLE_NAME        = module.data.dynamodb_table_name
    KMS_KEY_ARN                = module.data.kms_key_arn
    MEDIA_BUCKET               = module.data.bucket_ids["media"]
    RETRIEVAL_BACKEND          = "aurora"
    SES_FROM_ADDRESS           = "noreply@${var.company_domain}"
    SOURCE_BUCKET              = module.data.bucket_ids["source"]
    SQS_ANALYSIS_QUEUE_URL     = module.async_workflow.queue_urls["analysis"]
    SQS_DELETION_QUEUE_URL     = module.async_workflow.queue_urls["deletion"]
    SQS_MEDIA_QUEUE_URL        = module.async_workflow.queue_urls["media"]
    SQS_REPORTING_QUEUE_URL    = module.async_workflow.queue_urls["reporting"]
  }
  tags = local.tags
}

module "edge" {
  source = "../../modules/edge"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  name                         = local.name
  hosted_zone_id               = var.hosted_zone_id
  company_domain               = var.company_domain
  applicant_domain             = var.applicant_domain
  company_bucket_id            = module.data.bucket_ids["company-spa"]
  company_bucket_arn           = module.data.bucket_arns["company-spa"]
  company_bucket_domain_name   = module.data.bucket_regional_domain_names["company-spa"]
  applicant_bucket_id          = module.data.bucket_ids["applicant-spa"]
  applicant_bucket_arn         = module.data.bucket_arns["applicant-spa"]
  applicant_bucket_domain_name = module.data.bucket_regional_domain_names["applicant-spa"]
  api_origin_domain_name       = module.compute.alb_dns_name
  tags                         = local.tags
}
