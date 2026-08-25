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

variable "force_destroy_buckets" {
  description = "Delete operational log buckets with their objects in disposable environments."
  type        = bool
  default     = false
}

variable "queue_arns" {
  type    = map(string)
  default = {}
}

variable "dlq_arns" {
  type    = map(string)
  default = {}
}

/**
 * The database this environment's alarms watch.
 *
 * Optional so that an environment can be applied before the cluster exists; absent, the two
 * Aurora alarms are simply not created, which a plan shows -- unlike an alarm whose dimension
 * names a cluster that is not there, which sits in INSUFFICIENT_DATA looking calm.
 *
 * The load balancer and the services are alarmed in the compute module instead, not here. This
 * module is applied from the dev `data-ai` root, which runs before the `application` root that
 * creates them and whose state it cannot read without a cycle -- and an alarm belongs with the
 * resource it watches in any case.
 */
variable "database_identifier" {
  type    = string
  default = null
}

variable "database_metric_dimension_name" {
  description = "CloudWatch dimension used by the selected RDS database implementation."
  type        = string
  default     = "DBClusterIdentifier"

  validation {
    condition = contains(
      ["DBClusterIdentifier", "DBInstanceIdentifier"],
      var.database_metric_dimension_name,
    )
    error_message = "database_metric_dimension_name must be DBClusterIdentifier or DBInstanceIdentifier."
  }
}

variable "database_max_connections" {
  description = <<-EOT
    The connection ceiling the alarm is a fraction of.

    Aurora Serverless v2 derives `max_connections` from the current ACU, so there is no single
    true number to read at plan time; this is the floor the cluster is scaled to, and the
    alarm fires at 80% of it. A wrong value here makes the alarm early or late, never absent.
  EOT
  type        = number
  default     = 189
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
  # Fixed rather than a variable: the bucket policy grants writes to exactly this prefix, so
  # the balancer and the grant have to agree, and one string they both read is the only way
  # that agreement cannot drift.
  access_log_prefix = "alb"
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

/**
 * Where the load balancer writes one line per request.
 *
 * This is the only record of what a browser actually asked for and what it got back. Without
 * it, a report of "the console showed an error" has nothing behind it: the application log
 * says what the API decided, not which requests never reached it, were rejected by WAF, or
 * timed out at the balancer. Latency percentiles and 4xx-by-path also live only here.
 *
 * Created in this module rather than beside the load balancer because the bucket must exist
 * before the balancer that logs into it, and the two are in different roots. The bucket name
 * is what the application root passes to `aws_lb.access_logs`.
 *
 * A request line contains the query string, so what the API accepts as a query parameter is
 * part of this bucket's threat model -- see the note on the timeline endpoint in
 * `reporting/api/company_routes.py`, whose free-text search over answer transcripts was
 * removed rather than logged.
 */
resource "aws_s3_bucket" "access_logs" {
  bucket        = "${var.name}-alb-logs-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.name}"
  force_destroy = var.force_destroy_buckets
  tags          = local.tags
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket                  = aws_s3_bucket.access_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# AES256, not the customer key used for applicant data. Elastic Load Balancing writes these
# objects itself and supports only SSE-S3 for them; pointed at a KMS key the balancer silently
# stops delivering logs, and the only symptom is an empty bucket.
resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Request lines are an operational record, not evidence, and they are the one place an
# applicant's opaque session id appears next to an IP address. Thirty days is long enough to
# investigate an incident and short enough that the set does not accumulate indefinitely.
resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    id     = "expire-request-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = 30
    }
  }
}

# The regional Elastic Load Balancing account, not a service principal. Seoul predates the
# August 2022 region cutover after which ALB delivery switched to
# `logdelivery.elasticloadbalancing.amazonaws.com`; in an older region only the account
# principal is authorised, and a policy naming the wrong one is accepted at apply and then
# rejects every delivery. The data source resolves whichever is correct for the region.
data "aws_elb_service_account" "current" {}

resource "aws_s3_bucket_policy" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AlbAccessLogDelivery"
      Effect    = "Allow"
      Principal = { AWS = data.aws_elb_service_account.current.arn }
      Action    = "s3:PutObject"
      Resource  = "${aws_s3_bucket.access_logs.arn}/${local.access_log_prefix}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
    }]
  })
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

resource "aws_cloudwatch_metric_alarm" "aurora_connections" {
  count = var.database_identifier == null ? 0 : 1

  alarm_name          = "${var.name}-database-connections"
  alarm_description   = "The database is near its connection ceiling."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Maximum"
  threshold           = floor(var.database_max_connections * 0.8)
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
  dimensions = {
    (var.database_metric_dimension_name) = var.database_identifier
  }
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "aurora_cpu" {
  count = var.database_identifier == null ? 0 : 1

  alarm_name          = "${var.name}-database-cpu"
  alarm_description   = "The database is CPU-saturated; queries will be slow before they fail."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
  dimensions = {
    (var.database_metric_dimension_name) = var.database_identifier
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

resource "aws_cloudwatch_metric_alarm" "capacity_saturated" {
  for_each = toset(["api", "worker"])

  alarm_name          = "${var.name}-${each.value}-scheduled-capacity-saturated"
  alarm_description   = "A reservation requires more ${each.value} tasks than the configured ECS maximum."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "scheduled_capacity_saturated"
  namespace           = "InterviewEvidencePlatform"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
  dimensions = {
    service = each.value
  }
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "task_protection_error" {
  for_each = toset(["api", "worker"])

  alarm_name          = "${var.name}-${each.value}-task-protection-error"
  alarm_description   = "The ${each.value} task could not protect active interview work from ECS scale-in."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ecs_task_protection_change"
  namespace           = "InterviewEvidencePlatform"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
  dimensions = {
    service = each.value
    outcome = "error"
  }
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "assessment_citation_withheld" {
  alarm_name          = "${var.name}-assessment-citation-withheld"
  alarm_description   = "AI assessment citations did not resolve, so one or more scores were withheld."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ai_assessment_axis_count"
  namespace           = "InterviewEvidencePlatform"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
  dimensions = {
    outcome = "citation_withheld"
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
          markdown = "# Interview Evidence Platform\n예약 용량, Worker 적체, ECS 작업 보호, Evidence 인용 검증을 한 화면에서 확인합니다."
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 2
        width  = 12
        height = 6
        properties = {
          title  = "예약으로 보장한 ECS 최소 작업 수"
          view   = "timeSeries"
          region = data.aws_region.current.name
          stat   = "Maximum"
          period = 60
          metrics = [
            ["InterviewEvidencePlatform", "scheduled_capacity_minimum", "service", "api"],
            [".", ".", ".", "worker"],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 2
        width  = 12
        height = 6
        properties = {
          title  = "SQS 대기 작업 및 DLQ"
          view   = "timeSeries"
          region = data.aws_region.current.name
          stat   = "Maximum"
          period = 60
          metrics = concat(
            [for name, arn in var.queue_arns : ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", element(reverse(split(":", arn)), 0), { label = "${name} 대기" }]],
            [for name, arn in var.dlq_arns : ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", element(reverse(split(":", arn)), 0), { label = "${name} DLQ" }]],
          )
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 8
        width  = 12
        height = 6
        properties = {
          title  = "AI 평가 Evidence 인용 검증"
          view   = "timeSeries"
          region = data.aws_region.current.name
          stat   = "Sum"
          period = 300
          metrics = [
            ["InterviewEvidencePlatform", "ai_assessment_axis_count", "outcome", "evidence_verified"],
            [".", ".", ".", "citation_withheld"],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 8
        width  = 12
        height = 6
        properties = {
          title  = "ECS 작업 보호 변경"
          view   = "timeSeries"
          region = data.aws_region.current.name
          stat   = "Sum"
          period = 300
          metrics = [
            ["InterviewEvidencePlatform", "ecs_task_protection_change", "service", "api", "outcome", "error"],
            [".", ".", ".", "worker", ".", "."],
          ]
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
  force_destroy = var.force_destroy_buckets
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

# Both halves, because `aws_lb.access_logs` needs the bucket and the prefix and the prefix is
# not free to choose -- the bucket policy above grants writes to this one path.
output "access_log_bucket" {
  value = aws_s3_bucket.access_logs.id
}

output "access_log_prefix" {
  value = local.access_log_prefix
}
