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

variable "interview_model_id" {
  type = string
}

variable "cognito_domain_prefix" {
  description = <<-EOT
    Prefix of the hosted login domain, e.g. `iep-prod-company` becomes
    `iep-prod-company.auth.<region>.amazoncognito.com`. Globally unique within the region.

    Required, unlike in dev: the console sends a user to `/oauth2/authorize` on this domain,
    and a pool without one has no such endpoint. Left unset the console builds cleanly, falls
    back to a demo token the API rejects, and prod ships with no way to log in.
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

  name                  = local.name
  company_domain        = var.company_domain
  cognito_domain_prefix = var.cognito_domain_prefix
  deletion_protection   = true
  tags                  = local.tags
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

  name = local.name
  tags = local.tags
}

module "observability" {
  source = "../../modules/observability"

  name       = local.name
  queue_arns = module.async_workflow.queue_arns
  dlq_arns   = module.async_workflow.dlq_arns
  # The dimension AWS/RDS metrics carry, which is what creates the two Aurora alarms. Prod
  # holds every module in one root, so no state read is involved here.
  aurora_cluster_identifier = module.data.aurora_cluster_identifier
  # `aurora_max_connections` is left at its default. Aurora PostgreSQL Serverless v2 sets
  # `max_connections` from the current ACU in steps, and 0.5 through 2 ACU all resolve to 189 --
  # so prod's 2-ACU floor is the same ceiling as dev's 0.5, and an override here would only
  # invent a difference the engine does not have.
  tags = local.tags
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
  worker_queue_names = toset([
    for arn in values(module.async_workflow.queue_arns) : element(reverse(split(":", arn)), 0)
  ])
  enable_deletion_protection = true
  task_role_arn              = module.identity.application_runtime_role_arn
  task_role_name             = module.identity.application_runtime_role_name
  create_task_role           = false
  secret_arns                = [module.data.application_secret_arn, module.data.aurora_master_secret_arn]
  kms_key_arns               = [module.data.kms_key_arn]
  data_resource_arns = concat(
    values(module.data.bucket_arns),
    [for arn in values(module.data.bucket_arns) : "${arn}/*"],
    [module.data.dynamodb_table_arn],
    values(module.async_workflow.queue_arns),
  )
  access_log_bucket = module.observability.access_log_bucket
  access_log_prefix = module.observability.access_log_prefix
  alarm_topic_arn   = module.observability.alarm_topic_arn
  # Explicit, because the module cannot infer it from the ARN above: the topic is created in
  # this same apply, so its ARN is unknown while planning, and a `count` derived from it fails
  # the plan with "depends on resource attributes that cannot be determined until apply".
  create_alarms  = true
  enable_tracing = true
  task_environment = {
    APPLICANT_ACCESS_BASE_URL       = "${module.edge.site_urls["applicant"]}/access"
    APP_ENVIRONMENT                 = "prod"
    AUTOMATED_INTERVIEW_ENABLED     = "true"
    AI_PROVIDER                     = "gcp"
    EMBEDDING_PROVIDER              = "aws"
    AWS_REGION                      = var.aws_region
    AURORA_DATABASE                 = module.data.aurora_database_name
    AURORA_ENDPOINT                 = module.data.aurora_endpoint
    AURORA_MASTER_SECRET_ARN        = module.data.aurora_master_secret_arn
    BEDROCK_EMBEDDING_MODEL_ID      = "amazon.titan-embed-text-v2:0"
    BEDROCK_GUARDRAIL_ID            = module.ai_search.guardrail_id
    BEDROCK_MODEL_ID                = var.interview_model_id
    COGNITO_USER_POOL_ID            = module.identity.user_pool_id
    DOCUMENT_OCR_PROVIDER           = "gcp_document_ai"
    DYNAMODB_TABLE_NAME             = module.data.dynamodb_table_name
    KMS_KEY_ARN                     = module.data.kms_key_arn
    MEDIA_BUCKET                    = module.data.bucket_ids["media"]
    RETRIEVAL_BACKEND               = "aurora"
    GCP_DOCUMENT_AI_LOCATION        = "us"
    GCP_DOCUMENT_AI_TIMEOUT_SECONDS = "120"
    GCP_STT_FINAL_TIMEOUT_SECONDS   = "8"
    GCP_STT_LANGUAGE_CODE           = "ko-KR"
    GCP_STT_MODEL                   = "latest_long"
    GCP_TTS_LANGUAGE_CODE           = "ko-KR"
    GCP_TTS_SAMPLE_RATE_HZ          = "24000"
    GCP_TTS_VOICE_NAME              = "ko-KR-Chirp3-HD-Achird"
    GCP_VERTEX_AI_LOCATION          = "global"
    GCP_VERTEX_AI_MAX_ATTEMPTS      = "2"
    GCP_VERTEX_AI_MODEL_ID          = "gemini-2.5-flash"
    GCP_VERTEX_AI_THINKING_BUDGET   = "0"
    GCP_VERTEX_AI_TIMEOUT_SECONDS   = "30"
    STT_PROVIDER                    = "gcp_streaming"
    TTS_PROVIDER                    = "gcp_streaming"
    SES_FROM_ADDRESS                = module.identity.from_address
    SOURCE_BUCKET                   = module.data.bucket_ids["source"]
    SQS_ANALYSIS_QUEUE_URL          = module.async_workflow.queue_urls["analysis"]
    SQS_DELETION_QUEUE_URL          = module.async_workflow.queue_urls["deletion"]
    SQS_MEDIA_QUEUE_URL             = module.async_workflow.queue_urls["media"]
    SQS_REPORTING_QUEUE_URL         = module.async_workflow.queue_urls["reporting"]
    SQS_CAPACITY_QUEUE_URL          = module.async_workflow.queue_urls["capacity"]
    ECS_CLUSTER_NAME                = local.name
    ECS_API_SERVICE_NAME            = "${local.name}-api"
    ECS_WORKER_SERVICE_NAME         = "${local.name}-worker"
  }
  # A GitHub credential, so it is referenced rather than passed: the analysis worker
  # needs it to read a candidate's public repository above the 60-request anonymous
  # hourly limit. The JSON key is written into the secret outside Terraform.
  task_secrets = {
    GITHUB_TOKEN                 = "${module.data.application_secret_arn}:github_token::"
    GCP_DOCUMENT_AI_PROCESSOR_ID = "${module.data.application_secret_arn}:gcp_document_ai_processor_id::"
    GCP_DOCUMENT_AI_PROJECT_ID   = "${module.data.application_secret_arn}:gcp_project_id::"
    GCP_SERVICE_ACCOUNT_JSON     = "${module.data.application_secret_arn}:gcp_service_account_json::"
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

# The same shape the dev application root publishes, because one pipeline job reads it for
# both environments. See that root for why these are outputs rather than repository
# variables; here the domain is fixed, so only the bucket names and distribution ids are
# genuinely unknowable in advance.
output "frontend" {
  value = {
    api_base_url = ""
    sites = {
      company = {
        bucket          = module.data.bucket_ids["company-spa"]
        distribution_id = module.edge.distribution_ids["company"]
        url             = module.edge.site_urls["company"]
      }
      applicant = {
        bucket          = module.data.bucket_ids["applicant-spa"]
        distribution_id = module.edge.distribution_ids["applicant"]
        url             = module.edge.site_urls["applicant"]
      }
    }
    cognito = {
      login_domain = module.identity.user_pool_login_domain
      client_id    = module.identity.user_pool_client_id
      redirect_uri = "${module.edge.site_urls["company"]}/auth/callback"
    }
  }
}
