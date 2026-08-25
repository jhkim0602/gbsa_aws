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
  create_application_secret  = false
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

  name = local.name
  tags = local.tags
}

module "observability" {
  source = "../../../modules/observability"

  name                  = local.name
  alarm_email           = var.alarm_email
  force_destroy_buckets = true
  queue_arns            = module.async_workflow.queue_arns
  dlq_arns              = module.async_workflow.dlq_arns
  # The identifier rather than the ARN, because that is the dimension AWS/RDS metrics carry.
  # Passing it here is what creates the two Aurora alarms at all; the module defaults it to
  # null so the root can be applied before the cluster exists.
  aurora_cluster_identifier = module.data.aurora_cluster_identifier
  tags                      = local.tags
}

output "data" {
  value = {
    kms_key_arn                  = module.data.kms_key_arn
    bucket_ids                   = module.data.bucket_ids
    bucket_arns                  = module.data.bucket_arns
    bucket_regional_domain_names = module.data.bucket_regional_domain_names
    aurora_cluster_arn           = module.data.aurora_cluster_arn
    aurora_database_name         = module.data.aurora_database_name
    aurora_endpoint              = module.data.aurora_endpoint
    aurora_master_secret_arn     = module.data.aurora_master_secret_arn
    application_secret_arn       = module.data.application_secret_arn
    dynamodb_table_arn           = module.data.dynamodb_table_arn
    dynamodb_table_name          = module.data.dynamodb_table_name
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
    guardrail_id = module.ai_search.guardrail_id
  }
}

# Read by the application root, which creates the load balancer and the services these three
# values configure. The alarms on them cannot live in this root -- it applies first and cannot
# see an ALB that does not exist yet -- so what crosses the boundary is the topic to publish to
# and the bucket to write into, not the resources themselves.
output "observability" {
  value = {
    alarm_topic_arn   = module.observability.alarm_topic_arn
    access_log_bucket = module.observability.access_log_bucket
    access_log_prefix = module.observability.access_log_prefix
  }
}
