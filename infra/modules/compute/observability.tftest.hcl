# Request logging, the trace collector, and the alarms that answer "is the product working".
#
# These live in this module rather than in observability because they watch resources this
# module creates, and observability is applied from an earlier root whose state cannot see
# them. What is asserted here is mostly about absence being total: an alarm with no action, a
# sidecar marked essential, or an `access_logs` block pointing at a null bucket all apply
# cleanly and read in a review as though monitoring were configured.

# The mock provider invents a random string for every computed attribute, and several schemas
# here validate that theirs is a real ARN or dimension value, so those are given plausible
# shapes rather than overridden per run.
mock_provider "aws" {
  mock_resource "aws_lb" {
    defaults = {
      arn        = "arn:aws:elasticloadbalancing:ap-northeast-2:000000000000:loadbalancer/app/iep-probe-api/aaaaaaaaaaaaaaaa"
      arn_suffix = "app/iep-probe-api/aaaaaaaaaaaaaaaa"
    }
  }
  mock_resource "aws_lb_target_group" {
    defaults = {
      arn        = "arn:aws:elasticloadbalancing:ap-northeast-2:000000000000:targetgroup/iep-probe-api/bbbbbbbbbbbbbbbb"
      arn_suffix = "targetgroup/iep-probe-api/bbbbbbbbbbbbbbbb"
    }
  }
  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::000000000000:role/iep-probe"
    }
  }
}

variables {
  name                          = "iep-probe"
  vpc_id                        = "vpc-00000000000000000"
  private_subnet_ids            = ["subnet-00000000000000001"]
  alb_subnet_ids                = ["subnet-00000000000000002"]
  alb_security_group_id         = "sg-00000000000000001"
  application_security_group_id = "sg-00000000000000002"
}

run "an_environment_without_observability_wiring_creates_no_half_configured_monitoring" {
  command = apply

  override_data {
    target = data.aws_region.current
    values = { name = "ap-northeast-2" }
  }

  # No bucket means the block is absent, not present and disabled: `enabled = false` with a
  # null bucket is rejected at apply, and a block pointing at a bucket that rejects every
  # delivery has an empty bucket as its only symptom.
  assert {
    condition     = length(aws_lb.api.access_logs) == 0
    error_message = "without a bucket the load balancer must have no access_logs block at all"
  }

  # An alarm that fires into nothing is worse than no alarm, because it appears in the console
  # as coverage.
  assert {
    condition = alltrue([
      length(aws_cloudwatch_metric_alarm.api_5xx) == 0,
      length(aws_cloudwatch_metric_alarm.alb_5xx) == 0,
      length(aws_cloudwatch_metric_alarm.target_health) == 0,
      length(aws_cloudwatch_metric_alarm.service_tasks) == 0,
    ])
    error_message = "without a topic no alarm may be created rather than an alarm with no action"
  }

  # A collector that cannot reach X-Ray would retry every span; an exporter pointed at a
  # collector that is not running fills the log with connection errors that read as a
  # networking fault.
  assert {
    condition = alltrue([
      length(jsondecode(aws_ecs_task_definition.api.container_definitions)) == 1,
      length(jsondecode(aws_ecs_task_definition.worker.container_definitions)) == 1,
      length(aws_cloudwatch_log_group.otel) == 0,
    ])
    error_message = "tracing off must add no sidecar and no log group"
  }

  assert {
    condition = length([
      for entry in jsondecode(aws_ecs_task_definition.api.container_definitions)[0].environment :
      entry if startswith(entry.name, "OTEL_")
    ]) == 0
    error_message = "no OTLP endpoint may be set when there is no collector to receive spans"
  }
}

run "a_wired_environment_logs_requests_traces_and_alarms" {
  command = apply

  variables {
    access_log_bucket = "iep-probe-alb-logs-000000000000-ap-northeast-2"
    alarm_topic_arn   = "arn:aws:sns:ap-northeast-2:000000000000:iep-probe-alarms"
    # Both, because they are separate switches: the gate cannot read the ARN, whose value is
    # unknown at plan time in the root that creates the topic.
    create_alarms  = true
    enable_tracing = true
  }

  override_data {
    target = data.aws_region.current
    values = { name = "ap-northeast-2" }
  }

  # The prefix the observability module's bucket policy grants writes to. A balancer writing
  # anywhere else is denied on every delivery.
  assert {
    condition = anytrue([
      for block in aws_lb.api.access_logs :
      block.enabled
      && block.bucket == "iep-probe-alb-logs-000000000000-ap-northeast-2"
      && block.prefix == "alb"
    ])
    error_message = "the balancer must log into the granted bucket and prefix"
  }

  # `essential = false` is the important field. Traces are diagnostic; marked essential a
  # collector that fails to start would take the whole task down and turn an observability gap
  # into an outage.
  assert {
    condition = alltrue([
      for definition in [
        aws_ecs_task_definition.api.container_definitions,
        aws_ecs_task_definition.worker.container_definitions,
      ] :
      length([
        for container in jsondecode(definition) :
        container if container.name == "otel-collector" && container.essential == false
      ]) == 1
    ])
    error_message = "both tasks must run a non-essential collector sidecar"
  }

  # The application container is still first and still essential -- the sidecar is appended, so
  # a mistake here would silently reorder the containers the service load balancer names.
  assert {
    condition = alltrue([
      jsondecode(aws_ecs_task_definition.api.container_definitions)[0].name == "api",
      jsondecode(aws_ecs_task_definition.api.container_definitions)[0].essential,
      jsondecode(aws_ecs_task_definition.worker.container_definitions)[0].name == "worker",
    ])
    error_message = "the application container must remain the first, essential container"
  }

  # localhost, because in awsvpc mode the sidecar is inside the task: nothing traverses the
  # network and no security group rule or VPC endpoint is involved.
  assert {
    condition = length([
      for entry in jsondecode(aws_ecs_task_definition.api.container_definitions)[0].environment :
      entry
      if entry.name == "OTEL_EXPORTER_OTLP_ENDPOINT" && entry.value == "http://localhost:4317"
    ]) == 1
    error_message = "the application must export spans to the sidecar on localhost"
  }

  # X-Ray requires its own id format; the W3C default produces ids the service rejects, and the
  # only symptom is an empty console.
  assert {
    condition = length([
      for entry in jsondecode(aws_ecs_task_definition.api.container_definitions)[0].environment :
      entry if entry.name == "OTEL_PROPAGATORS" && entry.value == "xray"
    ]) == 1
    error_message = "the propagator must be xray, not the W3C default"
  }

  # A count of good things: no data is exactly what a total outage looks like, so missing data
  # has to breach. `notBreaching` here would go silent precisely when everything is down.
  assert {
    condition = alltrue([
      aws_cloudwatch_metric_alarm.target_health[0].treat_missing_data == "breaching",
      alltrue([
        for alarm in aws_cloudwatch_metric_alarm.service_tasks :
        alarm.treat_missing_data == "breaching"
      ]),
    ])
    error_message = "absence of a healthy-host or running-task datapoint must breach, not go quiet"
  }

  # A count of bad things: no data means none happened.
  assert {
    condition = alltrue([
      aws_cloudwatch_metric_alarm.api_5xx[0].treat_missing_data == "notBreaching",
      aws_cloudwatch_metric_alarm.alb_5xx[0].treat_missing_data == "notBreaching",
    ])
    error_message = "absence of a 5xx datapoint means no errors, so it must not breach"
  }

  # The worker has no load balancer, so a crash-looping worker is invisible to every other
  # alarm here: the analysis queue would simply stop draining.
  assert {
    condition = alltrue([
      length(aws_cloudwatch_metric_alarm.service_tasks) == 2,
      contains(keys(aws_cloudwatch_metric_alarm.service_tasks), "worker"),
      aws_cloudwatch_metric_alarm.service_tasks["worker"].dimensions["ClusterName"] == "iep-probe",
    ])
    error_message = "both services must be alarmed on running task count, the worker included"
  }

  # The CloudWatch dimension form is the ARN tail, not the ARN. A subtly wrong value is not an
  # error: the alarm reports INSUFFICIENT_DATA indefinitely, which reads as nothing wrong.
  assert {
    condition = alltrue([
      aws_cloudwatch_metric_alarm.api_5xx[0].dimensions["LoadBalancer"] == aws_lb.api.arn_suffix,
      aws_cloudwatch_metric_alarm.target_health[0].dimensions["TargetGroup"] == aws_lb_target_group.api.arn_suffix,
      output.alb_arn_suffix == aws_lb.api.arn_suffix,
    ])
    error_message = "alarms must key on the arn_suffix dimension form the module exports"
  }
}

# The two switches are separate on purpose, and this is the half a module test can prove: the
# alarms follow `create_alarms` and never the ARN. It cannot reproduce the failure that forced
# the split -- the prod root creates the topic in the same apply, so the ARN is unknown while
# planning, and a `count` derived from it failed the whole prod plan with "depends on resource
# attributes that cannot be determined until apply". Any value written here is a known literal,
# so that failure only appears from a root. `prod/local-plan.tftest.hcl` is what covers it.
run "the_alarm_count_never_depends_on_the_topic_arn" {
  command = apply

  variables {
    alarm_topic_arn = "arn:aws:sns:ap-northeast-2:000000000000:iep-probe-alarms"
    create_alarms   = false
  }

  override_data {
    target = data.aws_region.current
    values = { name = "ap-northeast-2" }
  }

  assert {
    condition = alltrue([
      length(aws_cloudwatch_metric_alarm.api_5xx) == 0,
      length(aws_cloudwatch_metric_alarm.alb_5xx) == 0,
      length(aws_cloudwatch_metric_alarm.target_health) == 0,
      length(aws_cloudwatch_metric_alarm.service_tasks) == 0,
    ])
    error_message = "a topic ARN alone must not create alarms: the switch is create_alarms"
  }
}

# The other half of the split, and the combination it makes possible. Because the gate cannot
# read the ARN, alarms turned on with no topic produce `alarm_actions = [null]`, which plans and
# applies cleanly -- verified by removing the validation, at which point this run passes. The
# result is alarms that notify nobody while appearing in the console as coverage.
run "turning_alarms_on_without_a_topic_is_refused" {
  command = plan

  variables {
    create_alarms = true
  }

  override_data {
    target = data.aws_region.current
    values = { name = "ap-northeast-2" }
  }

  expect_failures = [var.create_alarms]
}
