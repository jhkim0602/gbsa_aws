terraform {
  required_version = ">= 1.10.0"

  backend "s3" {
    key          = "dev/application/terraform.tfstate"
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

variable "create_dns" {
  description = <<-EOT
    Whether this environment has a domain. False is the working default for dev: no hosted
    zone exists, and the edge module would otherwise try to issue a certificate it cannot
    validate. Each SPA is then reached at its own CloudFront hostname.
  EOT
  type        = bool
  default     = false
}

variable "hosted_zone_id" {
  type    = string
  default = null
}

variable "company_domain" {
  type    = string
  default = null
}

variable "applicant_domain" {
  type    = string
  default = null
}

variable "api_image" {
  description = <<-EOT
    Overridden by the deployment pipeline on every run, so it defaults to what the compute
    module already defaults to. Terraform is not the owner of the running revision: it
    registers a task definition and `ignore_changes` keeps it from fighting the pipeline,
    which registers a new revision per commit. A required variable here would only mean the
    infrastructure root could not be applied before any image had ever been built.
  EOT
  type        = string
  default     = "public.ecr.aws/docker/library/python:3.12-slim"
}

variable "worker_image" {
  type    = string
  default = "public.ecr.aws/docker/library/python:3.12-slim"
}

variable "interview_model_id" {
  description = <<-EOT
    An inference profile id, not a bare foundation-model id.

    In ap-northeast-2 the current Sonnet models report `inferenceTypesSupported:
    ["INFERENCE_PROFILE"]`, and invoking one by its bare id fails with a ValidationException
    -- "on-demand throughput isn't supported" -- at the first question of the first
    interview, not at apply. Verified by calling InvokeModel directly: the bare
    `anthropic.claude-3-5-sonnet-20241022-v2:0` is rejected while the `apac.` profile below
    answers.

    The `apac.` prefix, rather than `global.`, keeps inference inside the APAC region set.
    That matters here because the prompts carry Korean applicant answers.
  EOT
  type        = string
  default     = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"
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

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
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

data "terraform_remote_state" "data_ai" {
  backend = "s3"
  config = {
    bucket       = var.state_bucket
    key          = "dev/data-ai/terraform.tfstate"
    region       = var.aws_region
    use_lockfile = true
  }
}

locals {
  name      = data.terraform_remote_state.foundation.outputs.name
  data      = data.terraform_remote_state.data_ai.outputs.data
  workflow  = data.terraform_remote_state.data_ai.outputs.workflow
  ai_search = data.terraform_remote_state.data_ai.outputs.ai_search
  identity  = data.terraform_remote_state.foundation.outputs.identity
  # `lookup` with a default rather than a direct read: the output was added after the data-ai
  # root had already been applied once, and a state written before it exists would make this
  # root fail to plan on a missing attribute. Absent, the load balancer runs without access
  # logs and no alarms are created -- which is what the modules already do by default.
  observability = lookup(
    data.terraform_remote_state.data_ai.outputs,
    "observability",
    { alarm_topic_arn = null, access_log_bucket = null, access_log_prefix = "alb" },
  )
  tags = {
    Environment = "dev"
  }
  bucket_resources = concat(
    values(local.data.bucket_arns),
    [for arn in values(local.data.bucket_arns) : "${arn}/*"],
  )
}

# The API reads SES_FROM_ADDRESS through `_required`, so it exits at startup when the value is
# absent -- and a null reaching the task definition would be sent as the literal string
# "null", which starts cleanly and then fails at the first invitation with an SES rejection
# naming an address nobody configured. Refused here instead, where the cause is one variable
# away.
resource "terraform_data" "mail_configured" {
  lifecycle {
    precondition {
      condition     = local.identity.from_address != null
      error_message = "the foundation root has no sender_address; the API cannot start without SES_FROM_ADDRESS."
    }
  }
}

module "compute" {
  source = "../../../modules/compute"

  name                          = local.name
  vpc_id                        = data.terraform_remote_state.foundation.outputs.network.vpc_id
  private_subnet_ids            = data.terraform_remote_state.foundation.outputs.network.private_subnet_ids
  alb_subnet_ids                = data.terraform_remote_state.foundation.outputs.network.public_subnet_ids
  alb_security_group_id         = data.terraform_remote_state.foundation.outputs.network.alb_security_group_id
  application_security_group_id = data.terraform_remote_state.foundation.outputs.network.application_security_group_id
  api_image                     = var.api_image
  worker_image                  = var.worker_image
  worker_queue_names = toset([
    for arn in values(local.workflow.queue_arns) : element(reverse(split(":", arn)), 0)
  ])
  task_role_arn    = local.identity.application_runtime_role_arn
  task_role_name   = local.identity.application_runtime_role_name
  create_task_role = false
  secret_arns      = [local.data.application_secret_arn, local.data.aurora_master_secret_arn]
  kms_key_arns     = [local.data.kms_key_arn]
  data_resource_arns = concat(
    local.bucket_resources,
    [local.data.dynamodb_table_arn],
    values(local.workflow.queue_arns),
  )
  # Created in the data-ai root, which applies first. The bucket must exist before the balancer
  # that logs into it, and the topic before the alarms that publish to it.
  access_log_bucket = local.observability.access_log_bucket
  access_log_prefix = local.observability.access_log_prefix
  alarm_topic_arn   = local.observability.alarm_topic_arn
  # Keyed off the topic being present rather than hardcoded true, because the `lookup` above
  # defaults it to null when the data-ai root has not yet been applied with the output. That
  # test is safe here and not in prod: the ARN comes from an already-applied root's state, so
  # it is a known value at plan time.
  create_alarms = local.observability.alarm_topic_arn != null
  # On in dev because dev is where a slow request is diagnosed. The sampling rule and the error
  # group already exist in the observability module; without a collector in the task nothing
  # emits, and the X-Ray console reads "no data" whether the cause is no traffic or no wiring.
  enable_tracing = true
  task_environment = {
    # From the edge module, not assembled here: without a domain the applicant SPA lives at
    # a CloudFront hostname this root cannot predict, and the invitation email carries this
    # value verbatim. A wrong base URL produces mail whose link 404s, with nothing in the
    # API to notice it.
    APPLICANT_ACCESS_BASE_URL       = "${module.edge.site_urls["applicant"]}/access"
    APP_ENVIRONMENT                 = "dev"
    AUTOMATED_INTERVIEW_ENABLED     = "true"
    AI_PROVIDER                     = "gcp"
    EMBEDDING_PROVIDER              = "aws"
    AWS_REGION                      = var.aws_region
    AURORA_DATABASE                 = local.data.aurora_database_name
    AURORA_ENDPOINT                 = local.data.aurora_endpoint
    AURORA_MASTER_SECRET_ARN        = local.data.aurora_master_secret_arn
    BEDROCK_EMBEDDING_MODEL_ID      = "amazon.titan-embed-text-v2:0"
    BEDROCK_GUARDRAIL_ID            = local.ai_search.guardrail_id
    BEDROCK_MODEL_ID                = var.interview_model_id
    COGNITO_USER_POOL_ID            = local.identity.user_pool_id
    DOCUMENT_OCR_PROVIDER           = "gcp_document_ai"
    DYNAMODB_TABLE_NAME             = local.data.dynamodb_table_name
    EVENT_BUS_ARN                   = local.workflow.event_bus_arn
    KMS_KEY_ARN                     = local.data.kms_key_arn
    MEDIA_BUCKET                    = local.data.bucket_ids["media"]
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
    # The address the foundation root verified and granted, rather than a second copy of the
    # rule that builds it. The IAM policy conditions on `ses:FromAddress`, so a value that
    # disagrees is an AccessDenied at the first invitation.
    SES_FROM_ADDRESS        = local.identity.from_address
    SOURCE_BUCKET           = local.data.bucket_ids["source"]
    SQS_ANALYSIS_QUEUE_URL  = local.workflow.queue_urls["analysis"]
    SQS_DELETION_QUEUE_URL  = local.workflow.queue_urls["deletion"]
    SQS_MEDIA_QUEUE_URL     = local.workflow.queue_urls["media"]
    SQS_REPORTING_QUEUE_URL = local.workflow.queue_urls["reporting"]
    SQS_CAPACITY_QUEUE_URL  = local.workflow.queue_urls["capacity"]
    ECS_CLUSTER_NAME        = local.name
    ECS_API_SERVICE_NAME    = "${local.name}-api"
    ECS_WORKER_SERVICE_NAME = "${local.name}-worker"
  }
  # A GitHub credential, so it is referenced rather than passed: the analysis worker
  # needs it to read a candidate's public repository above the 60-request anonymous
  # hourly limit. The JSON key is written into the secret outside Terraform.
  task_secrets = {
    GITHUB_TOKEN                 = "${local.data.application_secret_arn}:github_token::"
    GCP_DOCUMENT_AI_PROCESSOR_ID = "${local.data.application_secret_arn}:gcp_document_ai_processor_id::"
    GCP_DOCUMENT_AI_PROJECT_ID   = "${local.data.application_secret_arn}:gcp_project_id::"
    GCP_SERVICE_ACCOUNT_JSON     = "${local.data.application_secret_arn}:gcp_service_account_json::"
  }
  tags = local.tags
}

module "edge" {
  source = "../../../modules/edge"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  name                         = local.name
  create_dns                   = var.create_dns
  hosted_zone_id               = var.hosted_zone_id
  company_domain               = var.company_domain
  applicant_domain             = var.applicant_domain
  company_bucket_id            = local.data.bucket_ids["company-spa"]
  company_bucket_arn           = local.data.bucket_arns["company-spa"]
  company_bucket_domain_name   = local.data.bucket_regional_domain_names["company-spa"]
  applicant_bucket_id          = local.data.bucket_ids["applicant-spa"]
  applicant_bucket_arn         = local.data.bucket_arns["applicant-spa"]
  applicant_bucket_domain_name = local.data.bucket_regional_domain_names["applicant-spa"]
  api_origin_domain_name       = module.compute.alb_dns_name
  tags                         = local.tags
}

output "application" {
  value = {
    cluster_name              = module.compute.cluster_name
    api_service_name          = module.compute.api_service_name
    worker_service_name       = module.compute.worker_service_name
    api_repository_url        = module.compute.api_repository_url
    worker_repository_url     = module.compute.worker_repository_url
    distribution_ids          = module.edge.distribution_ids
    distribution_domain_names = module.edge.distribution_domain_names
  }
}

/**
 * Everything the pipeline needs to build and publish the two browser applications.
 *
 * Grouped into one output, and read from state rather than kept as repository variables,
 * because none of these values can be known before the first apply: a bucket name, a
 * distribution id and -- without a domain -- the hostname the console redirects a login back
 * to are all created here. Held by hand they make the first deployment impossible in
 * principle (the variables cannot be filled until the apply that needs them has run) and
 * silently wrong afterwards, since a replaced distribution changes its id while the variable
 * keeps the old one and every publish invalidates a distribution nobody is served by.
 *
 * `api_base_url` is deliberately empty. Each distribution routes `/v1/*` to the ALB
 * alongside its own SPA origin, so the browser reaches the API on the origin it was served
 * from, and both applications already fall back to that. An absolute URL here would put the
 * API on a second origin and make every request a CORS preflight for no gain.
 */
output "frontend" {
  value = {
    api_base_url = ""
    sites = {
      company = {
        bucket          = local.data.bucket_ids["company-spa"]
        distribution_id = module.edge.distribution_ids["company"]
        url             = module.edge.site_urls["company"]
      }
      applicant = {
        bucket          = local.data.bucket_ids["applicant-spa"]
        distribution_id = module.edge.distribution_ids["applicant"]
        url             = module.edge.site_urls["applicant"]
      }
    }
    # Null until `cognito_domain_prefix` is set in the foundation root. The console reads all
    # three or none: `readCompanyAuthConfig` returns null if any is missing and falls back to
    # a demo token the deployed API will not accept, so a half-configured build is a console
    # that cannot log in rather than one that reports why.
    cognito = {
      login_domain = local.identity.user_pool_login_domain
      client_id    = local.identity.user_pool_client_id
      redirect_uri = "${module.edge.site_urls["company"]}/auth/callback"
    }
  }
}

/**
 * The one wiring step that cannot be resolved inside a single apply.
 *
 * Cognito rejects a `redirect_uri` that is not registered on the app client, the client
 * lives in the foundation root, and the console's CloudFront hostname is created here -- so
 * the first application apply is what makes the value knowable. Printing the exact command
 * is the difference between a five-second follow-up and a login that fails with
 * `redirect_mismatch` and no indication of which side is wrong.
 */
output "next_step" {
  value = {
    reason = "register the deployed console origin with Cognito, then re-apply the foundation root"
    console_base_urls = [
      "http://localhost:5173",
      module.edge.site_urls["company"],
    ]
  }
}
