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

variable "aurora_min_capacity" {
  type    = number
  default = 0.5
}

variable "aurora_max_capacity" {
  type    = number
  default = 8
}

variable "tags" {
  type    = map(string)
  default = {}
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  bucket_names = toset([
    "source",
    "media",
    "artifacts",
    "audit",
    "company-spa",
    "applicant-spa",
  ])
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
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.data.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
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

resource "aws_dynamodb_table" "interview_context" {
  name         = "${var.name}-interview-context"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.data.arn
  }

  tags = local.tags
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-aurora"
  subnet_ids = var.private_subnet_ids
  tags       = local.tags
}

resource "aws_rds_cluster" "this" {
  cluster_identifier              = "${var.name}-aurora"
  engine                          = "aurora-postgresql"
  database_name                   = "interview_evidence"
  master_username                 = "platform_admin"
  manage_master_user_password     = true
  master_user_secret_kms_key_id   = aws_kms_key.data.arn
  db_subnet_group_name            = aws_db_subnet_group.this.name
  vpc_security_group_ids          = [var.database_security_group_id]
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.data.arn
  backup_retention_period         = var.deletion_protection ? 35 : 7
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
  count = 2

  identifier         = "${var.name}-aurora-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.this.engine
  engine_version     = aws_rds_cluster.this.engine_version
  tags               = local.tags
}

resource "aws_secretsmanager_secret" "application" {
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

output "aurora_cluster_arn" {
  value = aws_rds_cluster.this.arn
}

output "aurora_database_name" {
  value = aws_rds_cluster.this.database_name
}

output "aurora_endpoint" {
  value     = aws_rds_cluster.this.endpoint
  sensitive = true
}

output "aurora_master_secret_arn" {
  value     = aws_rds_cluster.this.master_user_secret[0].secret_arn
  sensitive = true
}

output "application_secret_arn" {
  value = aws_secretsmanager_secret.application.arn
}

output "dynamodb_table_arn" {
  value = aws_dynamodb_table.interview_context.arn
}
