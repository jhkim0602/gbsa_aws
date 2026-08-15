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

variable "monthly_budget_usd" {
  type    = number
  default = 500
}

variable "alarm_email" {
  type    = string
  default = null
}

variable "queue_arns" {
  type    = map(string)
  default = {}
}

variable "dlq_arns" {
  type    = map(string)
  default = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  tags = merge(var.tags, {
    Component = "observability"
  })
}

resource "aws_cloudwatch_log_group" "application" {
  for_each = toset(["api", "worker", "audit"])

  name              = "/interview-evidence/${var.name}/${each.key}"
  retention_in_days = each.key == "audit" ? 365 : 30
  tags              = merge(local.tags, { LogType = each.key })
}

resource "aws_sns_topic" "alarms" {
  name              = "${var.name}-alarms"
  kms_master_key_id = "alias/aws/sns"
  tags              = local.tags
}

resource "aws_sns_topic_subscription" "email" {
  count = var.alarm_email == null ? 0 : 1

  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_cloudwatch_metric_alarm" "dlq_visible" {
  for_each = var.dlq_arns

  alarm_name          = "${var.name}-${each.key}-dlq-visible"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 0
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
  dimensions = {
    QueueName = element(reverse(split(":", each.value)), 0)
  }
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "queue_age" {
  for_each = var.queue_arns

  alarm_name          = "${var.name}-${each.key}-queue-age"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 600
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
  dimensions = {
    QueueName = element(reverse(split(":", each.value)), 0)
  }
  tags = local.tags
}

resource "aws_xray_sampling_rule" "interview" {
  rule_name      = "${var.name}-interview"
  priority       = 1000
  version        = 1
  reservoir_size = 1
  fixed_rate     = 0.1
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = "*"
  resource_arn   = "*"
  attributes     = {}
}

resource "aws_xray_group" "errors" {
  group_name        = "${var.name}-errors"
  filter_expression = "fault = true OR error = true"

  insights_configuration {
    insights_enabled      = true
    notifications_enabled = true
  }

  tags = local.tags
}

resource "aws_cloudwatch_dashboard" "operations" {
  dashboard_name = "${var.name}-operations"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 2
        properties = {
          markdown = "# Interview Evidence Platform\nMonitor WebSocket sessions, queue age, DLQs, Evidence rejection, and deletion residue."
        }
      }
    ]
  })
}

resource "aws_budgets_budget" "monthly" {
  name         = "${var.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = var.alarm_email == null ? [] : [var.alarm_email]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = 80
      threshold_type             = "PERCENTAGE"
      notification_type          = "FORECASTED"
      subscriber_email_addresses = [notification.value]
    }
  }
}

resource "aws_s3_bucket" "audit" {
  bucket        = "${var.name}-cloudtrail-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.name}"
  force_destroy = false
  tags          = local.tags
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "audit" {
  bucket = aws_s3_bucket.audit.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "CloudTrailAclCheck"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.audit.arn
      },
      {
        Sid       = "CloudTrailWrite"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.audit.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = { "s3:x-amz-acl" = "bucket-owner-full-control" }
        }
      }
    ]
  })
}

resource "aws_cloudtrail" "audit" {
  name                          = "${var.name}-audit"
  s3_bucket_name                = aws_s3_bucket.audit.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true
  tags                          = local.tags

  depends_on = [aws_s3_bucket_policy.audit]
}

output "alarm_topic_arn" {
  value = aws_sns_topic.alarms.arn
}

output "audit_trail_arn" {
  value = aws_cloudtrail.audit.arn
}

output "application_log_group_names" {
  value = { for name, group in aws_cloudwatch_log_group.application : name => group.name }
}
