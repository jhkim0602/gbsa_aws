variable "environment_name" {
  description = "Stable environment identifier used in resource names and tags."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z0-9-]{2,20}$", var.environment_name))
    error_message = "environment_name must contain 2-20 lowercase letters, numbers, or hyphens."
  }
}

variable "pilot_company_id" {
  description = <<-EOT
    UUID of the development tenant, carried as a `PilotTenant` tag on everything this root
    creates so a resource can be traced back to the tenant it was stood up for.

    It defaults to the same UUID `local_production.LOCAL_COMPANY_ID` seeds, so the tenant a
    developer works against locally and the one dev is tagged for are the same row rather
    than two that have to be kept in step by hand.
  EOT
  type        = string
  default     = "00000000-0000-7000-8000-000000000001"

  validation {
    condition     = can(regex("^[0-9a-fA-F-]{36}$", var.pilot_company_id))
    error_message = "pilot_company_id must be a UUID string."
  }
}

variable "pilot_company_name" {
  description = "Display name for the development tenant."
  type        = string
  default     = "GBSA Pilot"

  validation {
    condition     = length(trimspace(var.pilot_company_name)) > 0
    error_message = "pilot_company_name cannot be empty."
  }
}

variable "company_identity_provider_issuer" {
  description = <<-EOT
    An external OIDC issuer to accept company-user tokens from, instead of the pool this
    root creates.

    Nothing reads it yet, and it is optional rather than required for a concrete reason: this
    root *is* the identity provider, so the issuer is a value it produces
    (`https://cognito-idp.<region>.amazonaws.com/<user_pool_id>`) and not one a caller can
    know before the first apply. Left required, a plan could only be made by inventing a URL
    that no code consults.
  EOT
  type        = string
  default     = null

  validation {
    condition     = var.company_identity_provider_issuer == null || can(regex("^https://", var.company_identity_provider_issuer))
    error_message = "company_identity_provider_issuer must be an HTTPS URL."
  }
}

variable "default_retention_days" {
  description = "Default immutable retention snapshot applied when applicant consent is recorded."
  type        = number
  default     = 180

  validation {
    condition     = var.default_retention_days >= 1 && var.default_retention_days <= 3650
    error_message = "default_retention_days must be between 1 and 3650."
  }
}

variable "applicant_session_ttl_minutes" {
  description = "Maximum applicant session lifetime; invitation expiry can shorten it."
  type        = number
  default     = 720

  validation {
    condition     = var.applicant_session_ttl_minutes >= 15 && var.applicant_session_ttl_minutes <= 1440
    error_message = "applicant_session_ttl_minutes must be between 15 and 1440."
  }
}
