/**
 * The three things Terraform cannot create for itself.
 *
 * Every other root in this tree keeps its state in an S3 bucket and is applied by a role
 * GitHub Actions assumes over OIDC. Neither can be produced by a root that already needs
 * them, so this one owns both and keeps its own state on local disk.
 *
 * That state is *not* committed — `*.tfstate` is gitignored and the safety rules say state
 * files are never committed, and a bootstrap exception is not worth weakening an absolute.
 * The cost of losing it is bounded and documented: nothing here stores data, so the recovery
 * is `terraform import` of a bucket, an OIDC provider and a role, listed in the README. Until
 * something needs changing, a lost state file costs nothing at all — the resources stand.
 *
 * This root is applied by a human from a workstation, once. It is deliberately not reachable
 * from CI: the role CI uses to apply everything else is created here, and a pipeline that can
 * rewrite its own trust policy has no meaningful boundary.
 */

terraform {
  required_version = ">= 1.10.0"

  # Local, on purpose. See the file header.
  backend "local" {
    path = "terraform.tfstate"
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
  description = "Bucket holding the Terraform state of every other root."
  type        = string
}

variable "github_repository" {
  description = "The repository allowed to assume the deploy role, as owner/name."
  type        = string

  validation {
    condition     = can(regex("^[^/]+/[^/]+$", var.github_repository))
    error_message = "github_repository must be owner/name."
  }
}

variable "deploy_branch" {
  description = "The only branch whose workflow runs may assume the deploy role."
  type        = string
  default     = "main"
}

variable "deploy_environments" {
  description = <<-EOT
    GitHub Environments whose jobs may assume the deploy role. Each entry becomes a separate
    trusted subject, so a workflow job without a matching `environment:` cannot assume the
    role even when it runs on the trusted branch.
  EOT
  type        = list(string)
  default     = ["dev-plan", "dev-deploy", "prod-plan", "prod-deploy"]
}

variable "github_immutable_repository" {
  description = <<-EOT
    The same repository written the way GitHub's newer OIDC tokens name it —
    `owner@ownerid/name@repoid` — or null for an account still issuing the older form.

    GitHub has started signing subjects that identify the account and repository by numeric
    id rather than by name, and it is not something the repository can decline: `PUT
    /repos/OWNER/NAME/actions/oidc/customization/sub` with `use_default=true` answers 200
    and leaves `sub_claim_prefix` at the numeric value. The first deploy run failed here
    with `Not authorized to perform sts:AssumeRoleWithWebIdentity` and nothing else — the
    subject AWS rejected appears in no workflow log, only in the CloudTrail event's
    `userIdentity.userName`, which is where this value came from.

    Read the ids with `gh api repos/OWNER/NAME --jq '{owner: .owner.id, repo: .id}'`.
  EOT
  type        = string
  default     = null

  validation {
    condition = var.github_immutable_repository == null || can(regex(
      "^[^/]+@[0-9]+/[^/]+@[0-9]+$", coalesce(var.github_immutable_repository, "")
    ))
    error_message = "github_immutable_repository must be owner@ownerid/name@repoid."
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "bootstrap"
      ManagedBy   = "Terraform"
      Project     = "InterviewEvidencePlatform"
    }
  }
}

locals {
  tags = {
    Component = "bootstrap"
  }
}

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket
  tags   = local.tags

  # State is the only record of what is deployed. A destroy that silently takes it with it
  # leaves live infrastructure nothing can address.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  # Roots use `use_lockfile`, which serialises writers but does not undo a bad apply.
  # Versioning is what makes a corrupted state file recoverable.
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    id     = "expire-noncurrent-state"
    status = "Enabled"

    filter {}

    # Long enough to recover from a bad apply, short enough that the bucket does not grow
    # without bound. State objects are small; the count is what accumulates.
    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.state.json

  depends_on = [aws_s3_bucket_public_access_block.state]
}

data "aws_iam_policy_document" "state" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# ---------------------------------------------------------------------------
# GitHub OIDC
# ---------------------------------------------------------------------------

/**
 * No static access key exists for deployment, and none should. GitHub signs a short-lived
 * token per job; AWS verifies it against this provider and hands back credentials scoped to
 * the role below. A leaked workflow log therefore leaks nothing reusable.
 *
 * The thumbprint list is deliberately empty: since 2023 IAM validates GitHub's certificate
 * against its own trust store, and a pinned thumbprint is a rotation outage waiting to
 * happen — it fails closed, in the deploy path, with an opaque error.
 */
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = []
  tags            = local.tags

  lifecycle {
    ignore_changes = [thumbprint_list]
  }
}

data "aws_iam_policy_document" "deploy_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Scoped by both branch and GitHub Environment. `repo:owner/name:*` would let any
    # branch in the repository — including one opened by a fork's pull request — assume a
    # role that can apply Terraform.
    #
    # Both spellings of the repository are listed when `github_immutable_repository` is set,
    # because which one GitHub signs is GitHub's choice and it can change under a role that
    # is already deployed. Listing both is not a widening: every entry still names one
    # repository, one branch or one environment, and the numeric ids identify the same
    # repository more strictly than its name does — a name can be transferred to another
    # account, an id cannot.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = flatten([
        for repository in compact([var.github_repository, var.github_immutable_repository]) :
        concat(
          ["repo:${repository}:ref:refs/heads/${var.deploy_branch}"],
          [for name in var.deploy_environments : "repo:${repository}:environment:${name}"],
        )
      ])
    }
  }
}

resource "aws_iam_role" "deploy" {
  name               = "iep-github-deploy"
  description        = "Assumed by GitHub Actions to plan and apply the platform roots."
  assume_role_policy = data.aws_iam_policy_document.deploy_trust.json
  tags               = local.tags
}

/**
 * Administrator, and the reason is worth stating rather than hiding.
 *
 * These roots create IAM roles, KMS keys, VPC endpoints, Cognito pools, Bedrock guardrails,
 * Aurora resources and CloudTrail — across eight modules. A least-privilege policy for
 * that surface is a second, larger thing to maintain, and every gap in it appears as a
 * mid-apply failure with half the environment created. The trust policy above is where the
 * real restriction lives: this role is reachable only from one repository, one branch and
 * four named environments, and only ever as a token that expires with the job.
 *
 * Narrow it when the resource set stops moving, not before.
 */
resource "aws_iam_role_policy_attachment" "deploy" {
  role       = aws_iam_role.deploy.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

resource "aws_secretsmanager_secret" "dev_runtime" {
  name                    = "iep-dev/application/config"
  description             = "Persistent credentials used whenever the disposable dev environment is running."
  recovery_window_in_days = 7
  tags                    = local.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_sesv2_email_identity" "dev_sender" {
  email_identity = "seojh2j@naver.com"
  tags           = local.tags

  lifecycle {
    prevent_destroy = true
  }
}

output "state_bucket" {
  value = aws_s3_bucket.state.id
}

output "deploy_role_arn" {
  description = "Set this as the AWS_DEPLOY_ROLE_ARN repository variable in GitHub."
  value       = aws_iam_role.deploy.arn
}

output "dev_runtime_secret_arn" {
  value = aws_secretsmanager_secret.dev_runtime.arn
}

output "dev_sender_identity" {
  value = aws_sesv2_email_identity.dev_sender.email_identity
}
