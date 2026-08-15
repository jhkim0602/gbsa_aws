terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

variable "name" {
  type = string
}

variable "company_domain" {
  type = string
}

variable "cognito_domain_prefix" {
  type    = string
  default = null
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  tags = merge(var.tags, {
    Component = "identity"
  })
}

resource "aws_sesv2_configuration_set" "transactional" {
  configuration_set_name = "${var.name}-transactional"
  reputation_options {
    reputation_metrics_enabled = true
  }
  sending_options {
    sending_enabled = true
  }
}

resource "aws_sesv2_email_identity" "company" {
  email_identity = var.company_domain

  configuration_set_name = aws_sesv2_configuration_set.transactional.configuration_set_name
  dkim_signing_attributes {
    next_signing_key_length = "RSA_2048_BIT"
  }
  tags = local.tags
}

resource "aws_cognito_user_pool" "company" {
  name                = "${var.name}-company-users"
  deletion_protection = var.deletion_protection ? "ACTIVE" : "INACTIVE"
  username_attributes = ["email"]

  auto_verified_attributes = ["email"]
  mfa_configuration        = "OPTIONAL"

  software_token_mfa_configuration {
    enabled = true
  }

  password_policy {
    minimum_length                   = 14
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 3
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  user_attribute_update_settings {
    attributes_require_verification_before_update = ["email"]
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = local.tags
}

resource "aws_cognito_user_pool_client" "company" {
  name         = "${var.name}-company-console"
  user_pool_id = aws_cognito_user_pool.company.id

  generate_secret                      = false
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  access_token_validity                = 15
  id_token_validity                    = 15
  refresh_token_validity               = 1
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  callback_urls                        = ["https://${var.company_domain}/auth/callback"]
  logout_urls                          = ["https://${var.company_domain}/"]
  supported_identity_providers         = ["COGNITO"]

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "aws_cognito_user_pool_domain" "company" {
  count = var.cognito_domain_prefix == null ? 0 : 1

  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.company.id
}

resource "aws_iam_role" "email_sender" {
  name = "${var.name}-email-sender"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role" "application_runtime" {
  name = "${var.name}-application-runtime"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "email_sender" {
  name = "send-tenant-invitations"
  role = aws_iam_role.email_sender.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ses:SendEmail",
        "ses:SendRawEmail",
      ]
      Resource = aws_sesv2_email_identity.company.arn
      Condition = {
        StringEquals = {
          "ses:FromAddress" = "noreply@${var.company_domain}"
        }
      }
    }]
  })
}

output "user_pool_id" {
  value = aws_cognito_user_pool.company.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.company.id
}

output "user_pool_endpoint" {
  value = aws_cognito_user_pool.company.endpoint
}

output "email_sender_role_arn" {
  value = aws_iam_role.email_sender.arn
}

output "application_runtime_role_arn" {
  value = aws_iam_role.application_runtime.arn
}

output "application_runtime_role_name" {
  value = aws_iam_role.application_runtime.name
}
