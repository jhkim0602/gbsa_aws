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
  description = "UUID for the isolated development tenant seeded by the deployment pipeline."
  type        = string

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
  description = "OIDC issuer accepted for company-user authentication."
  type        = string

  validation {
    condition     = can(regex("^https://", var.company_identity_provider_issuer))
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
