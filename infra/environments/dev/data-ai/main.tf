terraform {
  required_version = ">= 1.10.0"

  backend "s3" {
    key          = "dev/data-ai/terraform.tfstate"
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

variable "embedding_model_arn" {
  type    = string
  default = "arn:aws:bedrock:ap-northeast-2::foundation-model/amazon.titan-embed-text-v2:0"
}

variable "alarm_email" {
  type    = string
  default = null
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

data "terraform_remote_state" "foundation" {
  backend = "s3"
  config = {
    bucket       = var.state_bucket
    key          = "dev/foundation/terraform.tfstate"
    region       = var.aws_region
    use_lockfile = true
  }
}

locals {
  name = data.terraform_remote_state.foundation.outputs.name
  tags = {
    Environment = "dev"
  }
}

module "data" {
  source = "../../../modules/data"

  name                       = local.name
  private_subnet_ids         = data.terraform_remote_state.foundation.outputs.network.private_subnet_ids
  database_security_group_id = data.terraform_remote_state.foundation.outputs.network.database_security_group_id
  deletion_protection        = false
  force_destroy              = true
  aurora_min_capacity        = 0.5
  aurora_max_capacity        = 8
  tags                       = local.tags
}

module "async_workflow" {
  source = "../../../modules/async-workflow"

  name        = local.name
  kms_key_arn = module.data.kms_key_arn
  tags        = local.tags
}

module "ai_search" {
  source = "../../../modules/ai-search"

  name                 = local.name
  vpc_id               = data.terraform_remote_state.foundation.outputs.network.vpc_id
  private_subnet_ids   = data.terraform_remote_state.foundation.outputs.network.private_subnet_ids
  security_group_ids   = [data.terraform_remote_state.foundation.outputs.network.endpoint_security_group_id]
  source_bucket_arn    = module.data.bucket_arns["source"]
  application_role_arn = data.terraform_remote_state.foundation.outputs.identity.application_runtime_role_arn
  kms_key_arn          = module.data.kms_key_arn
  embedding_model_arn  = var.embedding_model_arn
  tags                 = local.tags
}

module "observability" {
  source = "../../../modules/observability"

  name        = local.name
  alarm_email = var.alarm_email
  queue_arns  = module.async_workflow.queue_arns
  dlq_arns    = module.async_workflow.dlq_arns
  tags        = local.tags
}

output "data" {
  value = {
    kms_key_arn                  = module.data.kms_key_arn
    bucket_ids                   = module.data.bucket_ids
    bucket_arns                  = module.data.bucket_arns
    bucket_regional_domain_names = module.data.bucket_regional_domain_names
    aurora_cluster_arn           = module.data.aurora_cluster_arn
    aurora_endpoint              = module.data.aurora_endpoint
    aurora_master_secret_arn     = module.data.aurora_master_secret_arn
    application_secret_arn       = module.data.application_secret_arn
    dynamodb_table_arn           = module.data.dynamodb_table_arn
  }
  sensitive = true
}

output "workflow" {
  value = {
    queue_arns        = module.async_workflow.queue_arns
    queue_urls        = module.async_workflow.queue_urls
    dlq_arns          = module.async_workflow.dlq_arns
    event_bus_arn     = module.async_workflow.event_bus_arn
    state_machine_arn = module.async_workflow.state_machine_arn
  }
}

output "ai_search" {
  value = {
    collection_arn              = module.ai_search.collection_arn
    collection_endpoint         = module.ai_search.collection_endpoint
    knowledge_base_id           = module.ai_search.knowledge_base_id
    guardrail_id                = module.ai_search.guardrail_id
    index_mapping_parameter_arn = module.ai_search.index_mapping_parameter_arn
  }
}
