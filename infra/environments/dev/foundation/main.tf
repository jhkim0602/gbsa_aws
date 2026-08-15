terraform {
  required_version = ">= 1.10.0"

  backend "s3" {
    key          = "dev/foundation/terraform.tfstate"
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

variable "company_domain" {
  type = string
}

variable "cognito_domain_prefix" {
  type    = string
  default = null
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment_name
      ManagedBy   = "Terraform"
      Project     = "InterviewEvidencePlatform"
    }
  }
}

locals {
  name = "iep-${var.environment_name}"
  tags = {
    Environment = var.environment_name
    PilotTenant = var.pilot_company_id
  }
}

module "network" {
  source = "../../../modules/network"

  name               = local.name
  enable_nat_gateway = true
  tags               = local.tags
}

module "identity" {
  source = "../../../modules/identity"

  name                  = local.name
  company_domain        = var.company_domain
  cognito_domain_prefix = var.cognito_domain_prefix
  deletion_protection   = false
  tags                  = local.tags
}

output "name" {
  value = local.name
}

output "network" {
  value = {
    vpc_id                        = module.network.vpc_id
    public_subnet_ids             = module.network.public_subnet_ids
    private_subnet_ids            = module.network.private_subnet_ids
    alb_security_group_id         = module.network.alb_security_group_id
    application_security_group_id = module.network.application_security_group_id
    database_security_group_id    = module.network.database_security_group_id
    endpoint_security_group_id    = module.network.endpoint_security_group_id
  }
}

output "identity" {
  value = {
    user_pool_id                  = module.identity.user_pool_id
    user_pool_client_id           = module.identity.user_pool_client_id
    user_pool_endpoint            = module.identity.user_pool_endpoint
    email_sender_role_arn         = module.identity.email_sender_role_arn
    application_runtime_role_arn  = module.identity.application_runtime_role_arn
    application_runtime_role_name = module.identity.application_runtime_role_name
  }
}
