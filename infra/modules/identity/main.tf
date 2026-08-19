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
  description = "Mail and console domain. Null in an environment that has no domain yet."
  type        = string
  default     = null
}

variable "sender_address" {
  description = <<-EOT
    The address transactional mail is sent from, and the SES identity that is verified.

    Two shapes, because SES verifies two kinds of identity. Left null, this module verifies
    `company_domain` as a domain identity with Easy DKIM and sends from `noreply@` it --
    what production wants, and what needs DNS records in a hosted zone. Set to an address,
    it verifies that single address instead: no DNS, one confirmation click, which is the
    only way a domainless environment can send at all.
  EOT
  type        = string
  default     = null

  validation {
    condition     = var.sender_address == null || can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.sender_address))
    error_message = "sender_address must be an email address."
  }
}

variable "console_base_urls" {
  description = <<-EOT
    Every origin the company console may complete a login from. Cognito refuses a
    redirect_uri that is not on this list, so an origin missing here fails at login, not at
    apply.

    A list rather than one value, for two reasons. It breaks an ordering deadlock: this
    module is in the foundation root, the console's CloudFront origin only exists after the
    application root, and a single required origin would mean neither can be applied first.
    And `http://localhost:5173` -- the one non-TLS origin Cognito accepts -- lets the SPA run
    on a workstation against this deployed pool, which is the fastest way to exercise the
    real thing.

    `company_domain` contributes its origin automatically when set, so production needs
    nothing here.
  EOT
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for url in var.console_base_urls :
      can(regex("^(https://[^/?#]+|http://localhost(:[0-9]+)?)$", url))
    ])
    error_message = "each console_base_urls entry must be an https origin, or http://localhost with an optional port."
  }
}

variable "cognito_domain_prefix" {
  type    = string
  default = null
}

variable "create_e2e_client" {
  description = <<-EOT
    Whether to create the app client the browser suite authenticates through.

    Off by default, and left off in prod: the client allows an admin caller to exchange a
    password for an access token, which is how CI gets a token with no human at the hosted
    login UI, and which is not a capability to keep beside real applicant data. See the
    resource for why the flow it enables grants nothing to a browser.
  EOT
  type        = bool
  default     = false
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}

data "aws_region" "current" {}

locals {
  tags = merge(var.tags, {
    Component = "identity"
  })
  # An address identity when one is given, otherwise the domain, and null when there is
  # neither. `from_address` follows whichever identity was chosen rather than being assembled
  # separately, because SES rejects a From that its verified identity does not cover and the
  # two drifting apart is a runtime-only failure.
  #
  # Written with explicit null branches instead of `coalesce`, which fails outright on two
  # nulls, and instead of interpolating `company_domain` unguarded, which fails with "cannot
  # include a null value in a string template". Both errors point at this file and name a
  # function -- not at the root that left mail unconfigured, which is the actual cause and
  # what `send_email` below reports.
  email_identity = var.sender_address != null ? var.sender_address : var.company_domain
  from_address = (
    var.sender_address != null
    ? var.sender_address
    : var.company_domain != null ? "noreply@${var.company_domain}" : null
  )
  console_origins = distinct(concat(
    var.company_domain != null ? ["https://${var.company_domain}"] : [],
    var.console_base_urls,
  ))
}

# Not required, so that a domainless environment can be applied before a mailbox has been
# chosen and confirmed -- SES verification is a human step with a link to click, and blocking
# the whole apply on it would mean nothing else could be deployed or tested in the meantime.
# What is guaranteed instead is that the absence is total: no identity, no configuration set,
# no send grant, and no SES_FROM_ADDRESS for the API to start with.
locals {
  send_email = local.email_identity != null
}

resource "terraform_data" "identity_inputs" {
  lifecycle {
    precondition {
      condition     = length(local.console_origins) > 0
      error_message = "identity requires company_domain or at least one console_base_urls entry."
    }
  }
}

resource "aws_sesv2_configuration_set" "transactional" {
  count = local.send_email ? 1 : 0

  configuration_set_name = "${var.name}-transactional"
  reputation_options {
    reputation_metrics_enabled = true
  }
  sending_options {
    sending_enabled = true
  }
}

resource "aws_sesv2_email_identity" "company" {
  count = local.send_email ? 1 : 0

  email_identity = local.email_identity

  configuration_set_name = one(aws_sesv2_configuration_set.transactional[*].configuration_set_name)

  # Easy DKIM signs on behalf of a domain by publishing CNAMEs in its zone. An address
  # identity has no zone to publish into, and SES rejects the request, so the block only
  # exists for the domain shape.
  dynamic "dkim_signing_attributes" {
    for_each = var.sender_address == null ? [1] : []
    content {
      next_signing_key_length = "RSA_2048_BIT"
    }
  }

  tags = local.tags
}

resource "aws_cognito_user_pool" "company" {
  name                = "${var.name}-company-users"
  deletion_protection = var.deletion_protection ? "ACTIVE" : "INACTIVE"
  username_attributes = ["email"]

  auto_verified_attributes = ["email"]
  mfa_configuration        = "OPTIONAL"

  /**
   * The tenant the token belongs to, carried by the identity rather than inferred.
   *
   * `AwsCognitoPrincipalProvider.get_company_principal` reads `custom:company_id` and
   * `custom:company_user_id` from GetUser and raises PrincipalNotFoundError when either is
   * absent -- so a pool without these two attributes authenticates a user successfully and
   * then rejects every API call as an unknown principal. That is the whole authenticated
   * surface, failing identically for a wrong password and a correct one.
   *
   * They are declared here and not added later on purpose: Cognito allows no new custom
   * attribute on an existing pool and no change to one, so the only fix after an apply is
   * to replace the pool and every user in it.
   *
   * `required = false` because admin_create_user supplies them, and a required custom
   * attribute would additionally have to be writable at self-signup, which is disabled.
   */
  schema {
    name                     = "company_id"
    attribute_data_type      = "String"
    mutable                  = false
    required                 = false
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 36
      max_length = 36
    }
  }

  schema {
    name                     = "company_user_id"
    attribute_data_type      = "String"
    mutable                  = false
    required                 = false
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 36
      max_length = 36
    }
  }

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

  # `aws.cognito.signin.user.admin` is what makes the token usable, not an extra privilege.
  # `AwsCognitoPrincipalProvider.get_company_principal` resolves the caller by calling
  # GetUser with the access token, and GetUser requires exactly this scope -- without it
  # Cognito answers `NotAuthorizedException: Access Token does not have required scopes`,
  # the provider raises PrincipalNotFoundError, and every authenticated request is a 401.
  # A hosted login therefore succeeded and produced a token that could not read its own
  # user, which reads as a broken password rather than a missing scope.
  #
  # It grants the token holder GetUser and the self-service attribute writes on itself,
  # bounded by `write_attributes` below -- so the tenant attributes stay unwritable.
  allowed_oauth_scopes         = ["email", "openid", "profile", "aws.cognito.signin.user.admin"]
  callback_urls                = [for origin in local.console_origins : "${origin}/auth/callback"]
  logout_urls                  = [for origin in local.console_origins : "${origin}/"]
  supported_identity_providers = ["COGNITO"]

  # GetUser returns only what the calling app client is allowed to read, so leaving this
  # implicit puts the tenant attributes one provider default away from disappearing from
  # the response -- and the principal lookup reads them from exactly that response.
  read_attributes = [
    "email",
    "email_verified",
    "custom:company_id",
    "custom:company_user_id",
  ]

  # Nothing self-service writes these: users are created by an administrator, and a token
  # holder that could rewrite `custom:company_id` could move itself into another tenant.
  write_attributes = ["email"]

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

/**
 * A second app client, for the browser suite to obtain a token without a browser login.
 *
 * The console client above allows only the authorization-code flow, which needs a human at
 * the hosted login UI: there is no way for CI to complete it. The e2e suite had been sending
 * `Bearer local-company-token`, a string only the local `FakePrincipalProvider` maps to a
 * principal, so every request against a deployed environment would have been a 401 -- the
 * suite could not have run against dev at all.
 *
 * `ADMIN_USER_PASSWORD_AUTH` is the flow that works without one. It is admin-only: the caller
 * needs `cognito-idp:AdminInitiateAuth` on the pool, which the deploy role has and no browser
 * has, so possessing this client id grants nothing by itself. The user-facing flows are left
 * off, and this client is deliberately not given callback URLs -- it cannot participate in a
 * hosted login even if its id leaked.
 *
 * Optional, and absent in prod, because a test client that can exchange a password for a
 * token has no business existing beside real applicant data.
 */
resource "aws_cognito_user_pool_client" "e2e" {
  count = var.create_e2e_client ? 1 : 0

  name         = "${var.name}-e2e"
  user_pool_id = aws_cognito_user_pool.company.id

  generate_secret         = false
  enable_token_revocation = true
  access_token_validity   = 60
  id_token_validity       = 60
  refresh_token_validity  = 1

  # The admin flow only. `ALLOW_USER_PASSWORD_AUTH` would let anyone holding the client id
  # exchange a password unauthenticated; the admin variant requires signed IAM credentials.
  explicit_auth_flows = ["ALLOW_ADMIN_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]

  # The same two attributes the console client reads, because the token this client mints is
  # resolved by the same `AwsCognitoPrincipalProvider.get_company_principal` -- which reads
  # them from the GetUser response and fails if either is absent.
  read_attributes  = ["email", "email_verified", "custom:company_id", "custom:company_user_id"]
  write_attributes = ["email"]

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

# No identity, no grant. An `aws:SourceArn` of null would render as a policy matching nothing
# and read, in a review, as if sending had been permitted.
resource "aws_iam_role_policy" "email_sender" {
  count = local.send_email ? 1 : 0

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
      Resource = one(aws_sesv2_email_identity.company[*].arn)
      Condition = {
        StringEquals = {
          "ses:FromAddress" = local.from_address
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "application_metrics" {
  name = "publish-application-metrics"
  role = aws_iam_role.application_runtime.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["cloudwatch:PutMetricData"]
      Resource = "*"
      Condition = {
        StringEquals = {
          "cloudwatch:namespace" = "InterviewEvidencePlatform"
        }
      }
    }]
  })
}

# The From the IAM condition above allows. A root that assembles its own copy for
# SES_FROM_ADDRESS can disagree with the grant, and the send then fails at the first
# invitation with an AccessDenied that names neither side.
output "from_address" {
  value = local.from_address
}

output "email_identity" {
  description = <<-EOT
    The SES identity to verify: a domain, a single address in sandbox, or null when this
    environment cannot send mail yet.
  EOT
  value       = one(aws_sesv2_email_identity.company[*].email_identity)
}

# The exact redirect targets the pool will accept. A root that hands the console a
# `redirect_uri` this list does not contain gets `redirect_mismatch` from Cognito, which
# names neither the value sent nor the values allowed -- so the two are compared here instead.
output "callback_urls" {
  value = aws_cognito_user_pool_client.company.callback_urls
}

# The custom attribute names the pool declares. Cognito assigns the pool id at apply, so it is
# null in any plan and cannot stand in for "the pool exists"; these names are known from the
# configuration, and they are the part that can never be added to a live pool.
output "pool_schema_names" {
  value = [for entry in aws_cognito_user_pool.company.schema : entry.name]
}

output "user_pool_id" {
  value = aws_cognito_user_pool.company.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.company.id
}

# Null in an environment without the test client, which is what prod is. A caller that reads
# this and finds null is being told the browser suite cannot authenticate here, rather than
# being handed a client id that would fail at AdminInitiateAuth with `InvalidParameter`.
output "e2e_client_id" {
  value = one(aws_cognito_user_pool_client.e2e[*].id)
}

output "user_pool_endpoint" {
  value = aws_cognito_user_pool.company.endpoint
}

# The origin the SPA sends a user to for `/oauth2/authorize`, which is not the pool endpoint
# above -- that one serves the token-verification API and has no login UI. Null until a
# domain prefix is set, so a caller can tell "no browser login yet" from a wrong URL.
output "user_pool_login_domain" {
  value = one([
    for domain in aws_cognito_user_pool_domain.company :
    "https://${domain.domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
  ])
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
