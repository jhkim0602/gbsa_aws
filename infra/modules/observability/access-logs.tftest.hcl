# The ALB request-log bucket and the database alarms.
#
# Every defect this pins is silent. A bucket policy naming the wrong principal is accepted at
# apply and then rejects every delivery, so the only symptom is an empty bucket. A KMS default
# on the bucket makes Elastic Load Balancing stop delivering, with the same symptom. An alarm
# whose dimension does not name a real cluster sits in INSUFFICIENT_DATA, which in the console
# reads as calm. None of these fail an apply and none produce an error anywhere.

# The topic ARN is given a plausible value rather than left to the mock provider's random
# string, because an alarm's schema validates that its action is a real ARN and rejects one.
mock_provider "aws" {
  mock_resource "aws_sns_topic" {
    defaults = {
      arn = "arn:aws:sns:ap-northeast-2:000000000000:iep-probe-alarms"
    }
  }
}

variables {
  name = "iep-probe"
}

run "request_logs_are_deliverable_and_expire" {
  command = apply

  override_data {
    target = data.aws_caller_identity.current
    values = { account_id = "000000000000" }
  }

  override_data {
    target = data.aws_region.current
    values = { name = "ap-northeast-2" }
  }

  override_data {
    target = data.aws_elb_service_account.current
    values = { arn = "arn:aws:iam::600734575887:root" }
  }

  # SSE-S3. Elastic Load Balancing writes these objects itself and supports only SSE-S3 for
  # them; pointed at the customer key used for applicant data it silently stops delivering.
  assert {
    condition = alltrue([
      for rule in aws_s3_bucket_server_side_encryption_configuration.access_logs.rule :
      alltrue([
        for default in rule.apply_server_side_encryption_by_default :
        default.sse_algorithm == "AES256"
      ])
    ])
    error_message = "the request-log bucket must use SSE-S3, the only algorithm ALB delivery supports"
  }

  # The grant and the balancer have to agree on one path. The module exports the prefix rather
  # than letting the caller choose so that they cannot drift.
  assert {
    condition = strcontains(
      aws_s3_bucket_policy.access_logs.policy,
      "${output.access_log_prefix}/AWSLogs/000000000000/*",
    )
    error_message = "the delivery grant must cover exactly the prefix the balancer is told to write to"
  }

  assert {
    condition     = strcontains(aws_s3_bucket_policy.access_logs.policy, "600734575887")
    error_message = "the grant must name the regional Elastic Load Balancing account the data source resolved"
  }

  # Request lines carry an applicant's opaque session id next to an IP address, so the set is
  # not kept indefinitely.
  assert {
    condition = anytrue([
      for rule in aws_s3_bucket_lifecycle_configuration.access_logs.rule :
      rule.status == "Enabled" && anytrue([
        for expiration in rule.expiration : expiration.days == 30
      ])
    ])
    error_message = "request logs must expire rather than accumulate"
  }

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.access_logs.block_public_acls,
      aws_s3_bucket_public_access_block.access_logs.block_public_policy,
      aws_s3_bucket_public_access_block.access_logs.ignore_public_acls,
      aws_s3_bucket_public_access_block.access_logs.restrict_public_buckets,
    ])
    error_message = "the request-log bucket must not be reachable publicly"
  }

  # Without a cluster identifier the alarms are absent rather than pointed at nothing, because
  # the data-ai root can be applied before the cluster exists.
  assert {
    condition = alltrue([
      length(aws_cloudwatch_metric_alarm.aurora_connections) == 0,
      length(aws_cloudwatch_metric_alarm.aurora_cpu) == 0,
    ])
    error_message = "no cluster identifier must produce no Aurora alarm, not an alarm with a null dimension"
  }
}

run "database_alarms_key_on_the_dimension_rds_metrics_carry" {
  command = apply

  variables {
    aurora_cluster_identifier = "iep-probe-aurora"
  }

  override_data {
    target = data.aws_caller_identity.current
    values = { account_id = "000000000000" }
  }

  override_data {
    target = data.aws_region.current
    values = { name = "ap-northeast-2" }
  }

  override_data {
    target = data.aws_elb_service_account.current
    values = { arn = "arn:aws:iam::600734575887:root" }
  }

  # `DBClusterIdentifier`, not the ARN and not the endpoint. A dimension name or value that is
  # subtly wrong is not an error: the alarm reports INSUFFICIENT_DATA forever.
  assert {
    condition = alltrue([
      aws_cloudwatch_metric_alarm.aurora_connections[0].dimensions["DBClusterIdentifier"] == "iep-probe-aurora",
      aws_cloudwatch_metric_alarm.aurora_cpu[0].dimensions["DBClusterIdentifier"] == "iep-probe-aurora",
    ])
    error_message = "both Aurora alarms must key on DBClusterIdentifier"
  }

  # Connection exhaustion is this platform's likeliest database failure: every interview holds a
  # WebSocket and each worker holds a pool, so the alarm has to fire below the ceiling rather
  # than at it, while there is still time to react.
  assert {
    condition     = aws_cloudwatch_metric_alarm.aurora_connections[0].threshold == 151
    error_message = "the connection alarm must fire at 80% of the ceiling, not on reaching it"
  }

  assert {
    condition = alltrue([
      aws_cloudwatch_metric_alarm.aurora_connections[0].alarm_actions == toset([aws_sns_topic.alarms.arn]),
      aws_cloudwatch_metric_alarm.aurora_cpu[0].alarm_actions == toset([aws_sns_topic.alarms.arn]),
    ])
    error_message = "an alarm with no action appears in the console as coverage while notifying nobody"
  }
}
