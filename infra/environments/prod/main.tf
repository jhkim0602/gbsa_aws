terraform {
  required_version = ">= 1.10.0"

  backend "s3" {
    key          = "prod/terraform.tfstate"
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

variable "embedding_model_arn" {
  type    = string
  default = "arn:aws:bedrock:ap-northeast-2::foundation-model/amazon.titan-embed-text-v2:0"
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "prod"
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
  name = "iep-prod"
  tags = {
    Environment = "prod"
  }
}

module "network" {
  source = "../../modules/network"

  name               = local.name
  nat_gateway_per_az = true
  tags               = local.tags
}

module "identity" {
  source = "../../modules/identity"

  name                = local.name
  company_domain      = var.company_domain
  deletion_protection = true
  tags                = local.tags
}

module "data" {
  source = "../../modules/data"

  name                       = local.name
  private_subnet_ids         = module.network.private_subnet_ids
  database_security_group_id = module.network.database_security_group_id
  deletion_protection        = true
  force_destroy              = false
  aurora_min_capacity        = 2
  aurora_max_capacity        = 64
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

  name                 = local.name
  vpc_id               = module.network.vpc_id
  private_subnet_ids   = module.network.private_subnet_ids
  security_group_ids   = [module.network.endpoint_security_group_id]
  source_bucket_arn    = module.data.bucket_arns["source"]
  application_role_arn = module.identity.application_runtime_role_arn
  kms_key_arn          = module.data.kms_key_arn
  embedding_model_arn  = var.embedding_model_arn
  tags                 = local.tags
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
  api_desired_count             = 4
  worker_desired_count          = 4
  enable_deletion_protection    = true
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
    APP_ENVIRONMENT          = "prod"
    AURORA_DATABASE          = module.data.aurora_database_name
    AURORA_ENDPOINT          = module.data.aurora_endpoint
    AURORA_MASTER_SECRET_ARN = module.data.aurora_master_secret_arn
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
