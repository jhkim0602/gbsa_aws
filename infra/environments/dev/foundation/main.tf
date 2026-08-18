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
  description = "Null in dev, which has no hosted zone. See sender_address and console_base_urls."
  type        = string
  default     = null
}

variable "sender_address" {
  description = <<-EOT
    The single address SES verifies and sends invitations from, standing in for a domain
    identity dev has no zone to publish DKIM records into.

    It has to be a mailbox someone can open: SES emails a confirmation link, and the identity
    stays unverified -- every send failing -- until that link is clicked. In the sandbox the
    same constraint applies to recipients, so an applicant invitation only arrives at an
    address that has also been verified.
  EOT
  type        = string
  default     = null
}

variable "console_base_urls" {
  description = <<-EOT
    Origins the company console may complete a Cognito login from.

    Dev keeps `http://localhost:5173` here so the SPA can run on a workstation against this
    deployed pool. The CloudFront origin is added after the application root has been applied
    once and its distribution domain is known -- until then, login works locally only.
  EOT
  type        = list(string)
  default     = ["http://localhost:5173"]
}

variable "cognito_domain_prefix" {
  description = <<-EOT
    Prefix for the hosted login domain, e.g. `iep-dev-company` becomes
    `iep-dev-company.auth.ap-northeast-2.amazoncognito.com`.

    Required, with no default, because the console cannot log anybody in without it: the SPA
    sends the user to `/oauth2/authorize` on this domain, and a pool without one has no such
    endpoint. Defaulted to null it produced an environment that applied cleanly, built a
    console that fell back to a demo token, and rejected every request with a 401 that named
    nothing.

    Must be globally unique within the region, which is why the account id is appended in the
    committed dev values rather than left to chance.
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]{3,63}$", var.cognito_domain_prefix))
    error_message = "cognito_domain_prefix must contain 3-63 lowercase letters, numbers, or hyphens."
  }
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
  sender_address        = var.sender_address
  console_base_urls     = var.console_base_urls
  cognito_domain_prefix = var.cognito_domain_prefix
  deletion_protection   = false
  # On in dev, off in prod. The browser suite runs against this environment and has no human
  # to complete a hosted login, so it needs the app client that lets an admin caller exchange
  # a password for a token. See the module for why that grants a browser nothing.
  create_e2e_client = true
  tags              = local.tags
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
    e2e_client_id                 = module.identity.e2e_client_id
    user_pool_endpoint            = module.identity.user_pool_endpoint
    user_pool_login_domain        = module.identity.user_pool_login_domain
    from_address                  = module.identity.from_address
    email_identity                = module.identity.email_identity
    email_sender_role_arn         = module.identity.email_sender_role_arn
    application_runtime_role_arn  = module.identity.application_runtime_role_arn
    application_runtime_role_name = module.identity.application_runtime_role_name
  }
}

# What a human still has to do by hand, printed where they will see it rather than left in
# a document. Two different states, and they are not interchangeable: with no
# `sender_address` this environment cannot send at all and the application root will refuse
# to plan, while with one, SES has emailed a confirmation link and every send fails with
# MessageRejected until it is clicked.
output "manual_verification" {
  value = (
    module.identity.email_identity == null
    ? {
      email_identity = null
      status_command = null
      next_step      = "set sender_address to a mailbox you can open, then apply this root again"
    }
    : {
      email_identity = module.identity.email_identity
      status_command = "aws sesv2 get-email-identity --email-identity ${module.identity.email_identity} --region ${var.aws_region} --query VerifiedForSendingStatus"
      next_step      = "click the confirmation link SES sent to ${module.identity.email_identity}"
    }
  )
}
