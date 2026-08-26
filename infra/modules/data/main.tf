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

variable "private_subnet_ids" {
  type = list(string)
}

variable "database_security_group_id" {
  type = string
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "force_destroy" {
  type    = bool
  default = false
}

variable "create_application_secret" {
  description = "Create the runtime secret with the data layer instead of using a persistent external secret."
  type        = bool
  default     = true
}

variable "database_engine" {
  description = "Database implementation. Use rds-postgres for a small private dev database and aurora-postgres for production."
  type        = string
  default     = "aurora-postgres"

  validation {
    condition     = contains(["aurora-postgres", "rds-postgres"], var.database_engine)
    error_message = "database_engine must be aurora-postgres or rds-postgres."
  }
}

variable "rds_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "rds_engine_version" {
  type    = string
  default = "16.11"
}

variable "rds_allocated_storage" {
  description = "Fixed general-purpose storage for the development RDS instance."
  type        = number
  default     = 20

  validation {
    condition     = var.rds_allocated_storage >= 20
    error_message = "rds_allocated_storage must be at least 20 GiB."
  }
}

variable "rds_backup_retention_period" {
  description = "Number of days RDS backups are retained."
  type        = number
  default     = 1

  validation {
    condition     = var.rds_backup_retention_period >= 0 && var.rds_backup_retention_period <= 35
    error_message = "rds_backup_retention_period must be between 0 and 35 days."
  }
}

variable "aurora_min_capacity" {
  type    = number
  default = 0.5
}

variable "aurora_max_capacity" {
  type    = number
  default = 8
}

variable "aurora_backup_retention_period" {
  description = "Number of days Aurora backups are retained. Defaults to 35 with deletion protection and 7 otherwise."
  type        = number
  default     = null

  validation {
    condition = (
      var.aurora_backup_retention_period == null ||
      (var.aurora_backup_retention_period >= 1 && var.aurora_backup_retention_period <= 35)
    )
    error_message = "aurora_backup_retention_period must be between 1 and 35 days."
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  is_aurora     = var.database_engine == "aurora-postgres"
  is_rds        = var.database_engine == "rds-postgres"
  database_name = "interview_evidence"
  bucket_names = toset([
    "source",
    "media",
    "artifacts",
    "audit",
    "company-spa",
    "applicant-spa",
  ])
  # The two SPA origins hold the built frontend -- `index.html` and hashed asset bundles,
  # served to every anonymous browser that opens the site. Everything else holds applicant
  # material: uploaded documents, interview recordings, generated reports, audit trails.
  #
  # The distinction decides the encryption key. A bucket encrypted with the customer key is
  # unreadable by CloudFront, which holds no grant on it, so S3 answers a request for an
  # object that exists with 403 -- indistinguishable from a permissions error, and it was:
  # every document returned `AccessDenied` from `server: AmazonS3` while a missing key still
  # returned 404 and `/v1/*` still reached the API. The deploy published both bundles and
  # reported success.
  #
  # Granting cloudfront.amazonaws.com `kms:Decrypt` on that key is the other way to make this
  # work, and it is the wrong one: the same key encrypts Aurora, the media bucket and the
  # audit trail, so a policy written to serve a public JavaScript bundle would also cover
  # applicant recordings. SSE-S3 on the SPA buckets keeps the customer key scoped to data
  # that is actually confidential.
  spa_bucket_names = toset(["company-spa", "applicant-spa"])
  tags = merge(var.tags, {
    Component = "data"
  })
}

resource "aws_kms_key" "data" {
  description             = "${var.name} durable data encryption"
  enable_key_rotation     = true
  deletion_window_in_days = var.deletion_protection ? 30 : 7
  tags                    = local.tags
}

resource "aws_kms_alias" "data" {
  name          = "alias/${var.name}-data"
  target_key_id = aws_kms_key.data.key_id
}

resource "aws_s3_bucket" "data" {
  for_each = local.bucket_names

  bucket        = "${var.name}-${each.key}-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.name}"
  force_destroy = var.force_destroy
  tags          = merge(local.tags, { DataClass = each.key })
}

resource "aws_s3_bucket_public_access_block" "data" {
  for_each = aws_s3_bucket.data

  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  for_each = aws_s3_bucket.data

  bucket = each.value.id
  rule {
    # SSE-S3 for the SPA origins, the customer key for applicant material. See
    # `local.spa_bucket_names` for why the two are not encrypted alike. Still encrypted at
    # rest either way, and both are private: the bucket policy admits one distribution and
    # public access is blocked four ways.
    apply_server_side_encryption_by_default {
      kms_master_key_id = contains(local.spa_bucket_names, each.key) ? null : aws_kms_key.data.arn
      sse_algorithm     = contains(local.spa_bucket_names, each.key) ? "AES256" : "aws:kms"
    }
    # A bucket key is a KMS cost optimisation and S3 rejects it on an SSE-S3 rule.
    bucket_key_enabled = !contains(local.spa_bucket_names, each.key)
  }
}

resource "aws_s3_bucket_versioning" "data" {
  for_each = aws_s3_bucket.data

  bucket = each.value.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  for_each = aws_s3_bucket.data

  bucket = each.value.id
  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-aurora"
  subnet_ids = var.private_subnet_ids
  tags       = local.tags
}

resource "aws_rds_cluster" "this" {
  count = local.is_aurora ? 1 : 0

  cluster_identifier              = "${var.name}-aurora"
  engine                          = "aurora-postgresql"
  database_name                   = local.database_name
  master_username                 = "platform_admin"
  manage_master_user_password     = true
  master_user_secret_kms_key_id   = aws_kms_key.data.arn
  db_subnet_group_name            = aws_db_subnet_group.this.name
  vpc_security_group_ids          = [var.database_security_group_id]
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.data.arn
  backup_retention_period         = coalesce(var.aurora_backup_retention_period, var.deletion_protection ? 35 : 7)
  preferred_backup_window         = "18:00-19:00"
  preferred_maintenance_window    = "sun:19:00-sun:20:00"
  deletion_protection             = var.deletion_protection
  skip_final_snapshot             = !var.deletion_protection
  final_snapshot_identifier       = var.deletion_protection ? "${var.name}-final" : null
  enabled_cloudwatch_logs_exports = ["postgresql"]

  serverlessv2_scaling_configuration {
    min_capacity = var.aurora_min_capacity
    max_capacity = var.aurora_max_capacity
  }

  tags = local.tags
}

resource "aws_rds_cluster_instance" "this" {
  count = local.is_aurora ? 2 : 0

  identifier         = "${var.name}-aurora-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.this[0].id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.this[0].engine
  engine_version     = aws_rds_cluster.this[0].engine_version
  tags               = local.tags
}

resource "aws_db_instance" "this" {
  count = local.is_rds ? 1 : 0

  identifier                      = "${var.name}-postgres"
  engine                          = "postgres"
  engine_version                  = var.rds_engine_version
  instance_class                  = var.rds_instance_class
  db_name                         = local.database_name
  username                        = "platform_admin"
  manage_master_user_password     = true
  master_user_secret_kms_key_id   = aws_kms_key.data.arn
  allocated_storage               = var.rds_allocated_storage
  max_allocated_storage           = 0
  storage_type                    = "gp3"
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.data.arn
  db_subnet_group_name            = aws_db_subnet_group.this.name
  vpc_security_group_ids          = [var.database_security_group_id]
  publicly_accessible             = false
  multi_az                        = false
  backup_retention_period         = var.rds_backup_retention_period
  backup_window                   = "18:00-19:00"
  maintenance_window              = "sun:19:00-sun:20:00"
  auto_minor_version_upgrade      = true
  apply_immediately               = !var.deletion_protection
  copy_tags_to_snapshot           = true
  deletion_protection             = var.deletion_protection
  skip_final_snapshot             = !var.deletion_protection
  final_snapshot_identifier       = var.deletion_protection ? "${var.name}-postgres-final" : null
  delete_automated_backups        = !var.deletion_protection
  enabled_cloudwatch_logs_exports = ["postgresql"]
  performance_insights_enabled    = false

  tags = local.tags
}

resource "aws_secretsmanager_secret" "application" {
  count = var.create_application_secret ? 1 : 0

  name                    = "${var.name}/application/config"
  kms_key_id              = aws_kms_key.data.arn
  recovery_window_in_days = var.deletion_protection ? 30 : 7
  tags                    = local.tags
}

output "kms_key_arn" {
  value = aws_kms_key.data.arn
}

output "bucket_ids" {
  value = { for name, bucket in aws_s3_bucket.data : name => bucket.id }
}

output "bucket_arns" {
  value = { for name, bucket in aws_s3_bucket.data : name => bucket.arn }
}

output "bucket_regional_domain_names" {
  value = {
    for name, bucket in aws_s3_bucket.data : name => bucket.bucket_regional_domain_name
  }
}

output "database_arn" {
  value = local.is_aurora ? aws_rds_cluster.this[0].arn : aws_db_instance.this[0].arn
}

output "database_identifier" {
  value = local.is_aurora ? aws_rds_cluster.this[0].cluster_identifier : aws_db_instance.this[0].identifier
}

output "database_metric_dimension_name" {
  value = local.is_aurora ? "DBClusterIdentifier" : "DBInstanceIdentifier"
}

output "database_name" {
  value = local.database_name
}

output "database_endpoint" {
  value     = local.is_aurora ? aws_rds_cluster.this[0].endpoint : aws_db_instance.this[0].address
  sensitive = true
}

output "database_master_secret_arn" {
  value = local.is_aurora ? (
    aws_rds_cluster.this[0].master_user_secret[0].secret_arn
    ) : (
    aws_db_instance.this[0].master_user_secret[0].secret_arn
  )
  sensitive = true
}

output "application_secret_arn" {
  value = try(aws_secretsmanager_secret.application[0].arn, null)
}
