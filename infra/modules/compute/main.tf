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

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "alb_subnet_ids" {
  type = list(string)
}

variable "alb_security_group_id" {
  type = string
}

variable "application_security_group_id" {
  type = string
}

variable "api_image" {
  type    = string
  default = "public.ecr.aws/docker/library/python:3.12-slim"
}

variable "worker_image" {
  type    = string
  default = "public.ecr.aws/docker/library/python:3.12-slim"
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "worker_desired_count" {
  type    = number
  default = 1
}

variable "worker_queue_names" {
  description = "SQS queues whose visible backlog should add Worker tasks before CPU rises."
  type        = set(string)
  default     = []
}

variable "enable_deletion_protection" {
  type    = bool
  default = false
}

variable "force_delete_repositories" {
  description = "Delete ECR repositories with their images when an ephemeral environment is destroyed."
  type        = bool
  default     = false
}

variable "task_environment" {
  type    = map(string)
  default = {}
}

variable "secret_arns" {
  type    = list(string)
  default = []
}

variable "task_secrets" {
  type    = map(string)
  default = {}
}

variable "kms_key_arns" {
  type    = list(string)
  default = []
}

variable "data_resource_arns" {
  type    = list(string)
  default = []
}

variable "task_role_arn" {
  type    = string
  default = null
}

variable "create_task_role" {
  type    = bool
  default = true
}

variable "task_role_name" {
  type    = string
  default = null
}

/**
 * Where the load balancer writes one request line per browser request.
 *
 * Optional, because the bucket is created in the observability module in a different root, and
 * an environment applied before it exists should still get a working load balancer rather than
 * a failed apply. When absent, `access_logs` is disabled -- which a plan shows -- instead of
 * enabled and pointed at a bucket that rejects every delivery, whose only symptom is an empty
 * bucket nobody thinks to check.
 */
variable "access_log_bucket" {
  type    = string
  default = null
}

variable "access_log_prefix" {
  description = "Must match the prefix the bucket policy grants writes to."
  type        = string
  default     = "alb"
}

variable "alarm_topic_arn" {
  description = <<-EOT
    Where the load balancer and service alarms publish. Comes from the observability module,
    which is applied in an earlier root.

    Optional, and when absent no alarms are created rather than alarms with no action -- an
    alarm that fires into nothing is worse than none, because it appears in the console as
    coverage.
  EOT
  type        = string
  default     = null
}

variable "create_alarms" {
  description = <<-EOT
    Whether to create the load balancer and service alarms. Requires `alarm_topic_arn`.

    Separate from `alarm_topic_arn` being set, because whether a resource exists has to be
    decidable at plan time. In the prod root the topic is created in the same apply, so its ARN
    is an unknown value during the plan, and counting the alarms on `arn != null` failed the
    plan outright with "the count value depends on resource attributes that cannot be
    determined until apply" -- prod's first apply would have created nothing at all. Dev did
    not show this: there the ARN arrives from an already-applied root's state, so it is known.

    Off by default, so that a caller who passes no topic still gets no alarms rather than
    alarms whose only action is null.
  EOT
  type        = bool
  default     = false

  # Nothing else stops the combination the split makes possible: alarms on with no topic
  # produces `alarm_actions = [null]`, which plans and applies cleanly and leaves alarms that
  # notify nobody while appearing in the console as coverage.
  #
  # A cross-variable validation rather than a `check` block, which is the other way to span two
  # variables: a check has to evaluate its condition, and reading the unknown ARN made it report
  # "assertion known after apply" and fail the prod plan -- the same class of failure this
  # variable exists to fix. A validation only rejects, so it never has to resolve the value.
  validation {
    condition     = !var.create_alarms || var.alarm_topic_arn != null
    error_message = "create_alarms requires alarm_topic_arn: the alarms would notify nobody."
  }
}

variable "enable_tracing" {
  description = <<-EOT
    Run an ADOT collector alongside each application container and let it publish spans to
    X-Ray.

    Off by default because a sidecar that cannot reach X-Ray -- no task-role grant, no
    endpoint -- would make every task fail its health check and take the service down. On, it
    is what turns the existing sampling rule and error group from empty dashboards into
    traces: without a collector nothing emits, and the X-Ray console shows "no data" in a way
    that is indistinguishable from no traffic.
  EOT
  type        = bool
  default     = false
}

variable "otel_image" {
  description = <<-EOT
    The AWS Distro for OpenTelemetry collector image.

    Pinned to a version rather than `latest`: the task definition is a deployment artifact,
    and a floating tag makes a redeploy of unchanged code able to change the collector.
  EOT
  type        = string
  default     = "public.ecr.aws/aws-observability/aws-otel-collector:v0.43.0"
}

variable "tags" {
  type    = map(string)
  default = {}
}

data "aws_region" "current" {}

locals {
  tags = merge(var.tags, {
    Component = "compute"
  })
  environment = concat([
    for key, value in merge(var.task_environment, local.tracing_environment) : {
      name  = key
      value = value
    }
    ], [{
      name  = "MEDIACONVERT_ROLE_ARN"
      value = aws_iam_role.media_convert.arn
  }])
  # Credentials arrive as Secrets Manager references the execution role resolves at task
  # start, so the value never appears in the task definition, a plan, or a log line.
  secrets = [
    for key, value_from in var.task_secrets : {
      name      = key
      valueFrom = value_from
    }
  ]
  effective_task_role_arn = (
    var.create_task_role ? aws_iam_role.task[0].arn : var.task_role_arn
  )
  effective_task_role_name = (
    var.create_task_role ? aws_iam_role.task[0].name : var.task_role_name
  )

  /**
   * The ADOT collector that turns the application's spans into X-Ray traces.
   *
   * A sidecar rather than a separate service: it receives OTLP on localhost, which in `awsvpc`
   * mode is inside the task, so nothing traverses the network and no security group rule or
   * endpoint is involved. One collector per task also means its spans are already scoped to
   * the task that produced them.
   *
   * `essential = false` is the important field. Traces are diagnostic; a collector that fails
   * to start must not stop the API from serving, and marked essential it would take the whole
   * task down and turn an observability gap into an outage.
   */
  otel_container = var.enable_tracing ? [{
    name      = "otel-collector"
    image     = var.otel_image
    essential = false
    command   = ["--config=/etc/ecs/ecs-xray.yaml"]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = one(aws_cloudwatch_log_group.otel[*].name)
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = "otel"
      }
    }
  }] : []

  # Deliberately does not mention `alarm_topic_arn`. Any expression that reads it inherits its
  # unknown-ness -- `create_alarms && arn != null` fails the prod plan exactly as `arn != null`
  # did -- so the switch has to stand alone. See the variable.
  alarms_enabled = var.create_alarms

  # Both services, because the worker has no load balancer and so is invisible to every other
  # alarm here. Named by role rather than by service name so the alarm name reads
  # `iep-dev-worker-no-running-tasks` and not the full service identifier twice.
  alarmed_services = {
    api    = aws_ecs_service.api.name
    worker = aws_ecs_service.worker.name
  }

  # Points the application's OTLP exporter at the sidecar. Only set when a sidecar exists:
  # an exporter configured against a collector that is not running retries on every span and
  # fills the log with connection errors that look like a networking fault.
  tracing_environment = var.enable_tracing ? {
    OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4317"
    OTEL_TRACES_EXPORTER        = "otlp"
    # X-Ray requires its own id format; the W3C default produces ids the service rejects.
    OTEL_PROPAGATORS = "xray"
  } : {}
}

resource "aws_ecr_repository" "api" {
  name                 = "${var.name}/api"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.force_delete_repositories

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

resource "aws_ecr_repository" "worker" {
  name                 = "${var.name}/worker"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.force_delete_repositories

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.name}/api"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.name}/worker"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "otel" {
  count = var.enable_tracing ? 1 : 0

  name              = "/ecs/${var.name}/otel"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_iam_role" "execution" {
  name = "${var.name}-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  count = length(var.secret_arns) > 0 ? 1 : 0
  name  = "read-runtime-secrets"
  role  = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = var.secret_arns
      }],
      # The execution role, not the task role, resolves the container `secrets` block,
      # and the application secret is encrypted with the customer key -- without this the
      # task fails to start with an AccessDeniedException before any code runs.
      length(var.task_secrets) > 0 ? [{
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = var.kms_key_arns
      }] : [],
    )
  })
}

resource "aws_iam_role" "task" {
  count = var.create_task_role ? 1 : 0

  name = "${var.name}-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role" "media_convert" {
  name = "${var.name}-media-convert"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "mediaconvert.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "media_convert" {
  name = "tenant-media-read-write"
  role = aws_iam_role.media_convert.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = var.data_resource_arns
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = var.kms_key_arns
      },
    ]
  })
}

resource "aws_iam_role_policy" "task" {
  name = "application-boundaries"
  role = local.effective_task_role_name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DataAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:DeleteItem",
          # The readiness probe, not a data path: `DynamoRecentContext.healthcheck` calls
          # DescribeTable and treats any exception as `unavailable`. Without this action the
          # probe raised AccessDenied on every poll, so `/health/ready` answered 503 forever,
          # the ALB marked both targets unhealthy and the deployment circuit breaker opened --
          # while the API itself was serving requests correctly the whole time. Nothing in the
          # request path failed, which is why the symptom looked like a broken deploy.
          "dynamodb:DescribeTable",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem",
          "s3:AbortMultipartUpload",
          "s3:DeleteObject",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject",
          "sqs:ChangeMessageVisibility",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ReceiveMessage",
          "sqs:SendMessage",
        ]
        Resource = var.data_resource_arns
      },
      {
        Sid    = "ApprovedAI"
        Effect = "Allow"
        Action = [
          "bedrock:ApplyGuardrail",
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "cognito-idp:GetUser",
          "mediaconvert:CreateJob",
          "polly:SynthesizeSpeech",
          "ses:SendEmail",
          "textract:AnalyzeDocument",
          "transcribe:GetTranscriptionJob",
          "transcribe:StartTranscriptionJob",
          "transcribe:StartStreamTranscription",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:RequestedRegion" = data.aws_region.current.name
          }
        }
      },
      {
        Sid    = "ManageScheduledCapacity"
        Effect = "Allow"
        Action = [
          "application-autoscaling:DeleteScheduledAction",
          "application-autoscaling:PutScheduledAction",
          "application-autoscaling:RegisterScalableTarget",
          "ecs:UpdateTaskProtection",
        ]
        Resource = "*"
      },
      {
        Sid      = "PassMediaConvertRole"
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = aws_iam_role.media_convert.arn
      },
      # Its own statement rather than folded into ApprovedAI above: the collector reads the
      # sampling rules the observability module defines, and the `aws:RequestedRegion`
      # condition on that statement would be wrong here anyway -- these calls are regional but
      # the grant is about a service with no resource-level permissions, so a narrower
      # Resource is not available to give.
      {
        Sid    = "PublishTraces"
        Effect = "Allow"
        Action = [
          "xray:GetSamplingRules",
          "xray:GetSamplingStatisticSummaries",
          "xray:GetSamplingTargets",
          "xray:PutTelemetryRecords",
          "xray:PutTraceSegments",
        ]
        Resource = "*"
      },
      {
        Sid      = "DecryptRuntimeData"
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = var.kms_key_arns
      },
      {
        Sid    = "ReadRuntimeSecrets"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = length(var.secret_arns) > 0 ? var.secret_arns : [
          "arn:aws:secretsmanager:${data.aws_region.current.name}:*:secret:${var.name}/disabled-*"
        ]
      }
    ]
  })
}

resource "aws_ecs_cluster" "this" {
  name = var.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.tags
}

resource "aws_lb" "api" {
  name                       = substr("${var.name}-api", 0, 32)
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [var.alb_security_group_id]
  subnets                    = var.alb_subnet_ids
  drop_invalid_header_fields = true
  enable_deletion_protection = var.enable_deletion_protection

  # One line per request: the only record of what a browser asked for and what the balancer
  # returned, including the requests that never reached a task. `dynamic` rather than a
  # conditional bucket name because the block itself has to be absent when there is no bucket
  # -- `enabled = false` with a null bucket is rejected at apply.
  dynamic "access_logs" {
    for_each = var.access_log_bucket == null ? [] : [var.access_log_bucket]
    content {
      bucket  = access_logs.value
      prefix  = var.access_log_prefix
      enabled = true
    }
  }

  tags = local.tags
}

resource "aws_lb_target_group" "api" {
  name                 = substr("${var.name}-api", 0, 32)
  port                 = 8000
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = var.vpc_id
  deregistration_delay = 120

  health_check {
    path                = "/health/ready"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = local.tags
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = local.effective_task_role_arn

  container_definitions = jsonencode(concat([{
    name        = "api"
    image       = var.api_image
    essential   = true
    stopTimeout = 120
    command = [
      "uv",
      "run",
      "--no-sync",
      "uvicorn",
      "interview_evidence.main:app",
      "--host",
      "0.0.0.0",
      "--port",
      "8000",
    ]
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]
    environment = local.environment
    secrets     = local.secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = "api"
      }
    }
  }], local.otel_container))

  tags = local.tags
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = local.effective_task_role_arn

  container_definitions = jsonencode(concat([{
    name        = "worker"
    image       = var.worker_image
    essential   = true
    stopTimeout = 120
    # The image installs the package into a uv virtualenv, so a bare `python` cannot
    # import it -- the task would crash-loop on ModuleNotFoundError. Matches the api
    # command above and the worker CMD in backend/Containerfile.
    command = [
      "uv",
      "run",
      "--no-sync",
      "python",
      "-m",
      "interview_evidence.worker",
    ]
    environment = local.environment
    secrets     = local.secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.worker.name
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = "worker"
      }
    }
  }], local.otel_container))

  tags = local.tags
}

resource "aws_ecs_service" "api" {
  name            = "${var.name}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    assign_public_ip = false
    subnets          = var.private_subnet_ids
    security_groups  = [var.application_security_group_id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  lifecycle {
    ignore_changes = [desired_count, task_definition]
  }

  depends_on = [aws_lb_listener.api]
  tags       = local.tags
}

resource "aws_ecs_service" "worker" {
  name            = "${var.name}-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    assign_public_ip = false
    subnets          = var.private_subnet_ids
    security_groups  = [var.application_security_group_id]
  }

  lifecycle {
    ignore_changes = [desired_count, task_definition]
  }

  tags = local.tags
}

resource "aws_appautoscaling_target" "api" {
  max_capacity       = 20
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"

  lifecycle {
    # Runtime scheduled actions own the reservation floor; Terraform owns its initial value.
    ignore_changes = [min_capacity]
  }
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${var.name}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 60
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

resource "aws_appautoscaling_target" "worker" {
  max_capacity       = 30
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"

  lifecycle {
    # Queue pressure and reservation windows must survive an unrelated Terraform apply.
    ignore_changes = [min_capacity]
  }
}

resource "aws_appautoscaling_policy" "worker_cpu" {
  name               = "${var.name}-worker-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 65
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

resource "aws_appautoscaling_policy" "worker_queue_pressure" {
  name               = "${var.name}-worker-queue-pressure"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 60
    metric_aggregation_type = "Maximum"

    step_adjustment {
      metric_interval_lower_bound = 0
      metric_interval_upper_bound = 15
      scaling_adjustment          = 1
    }

    step_adjustment {
      metric_interval_lower_bound = 15
      metric_interval_upper_bound = 90
      scaling_adjustment          = 3
    }

    step_adjustment {
      metric_interval_lower_bound = 90
      scaling_adjustment          = 6
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "worker_queue_pressure" {
  for_each = var.worker_queue_names

  alarm_name          = "${var.name}-${each.value}-worker-scale-out"
  alarm_description   = "Visible work is waiting; add Worker tasks before CPU target tracking reacts."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 10
  alarm_actions = concat(
    [aws_appautoscaling_policy.worker_queue_pressure.arn],
    var.alarm_topic_arn == null ? [] : [var.alarm_topic_arn],
  )
  treat_missing_data = "notBreaching"
  dimensions = {
    QueueName = each.value
  }
  tags = local.tags
}

/**
 * The alarms that answer "is the product working", as opposed to "is a queue backing up".
 *
 * Before these, an environment could serve 500s to every applicant, run zero API tasks, or
 * exhaust its database connections without anything firing: the only alarms were on SQS depth
 * and message age, which stay quiet when the failure is upstream of the queue. Each one below
 * is a distinct failure this platform can actually have, and all of them are gated on
 * `create_alarms` so that a root which has not created the topic yet simply gets no alarm
 * rather than one pointed at nothing.
 *
 * `treat_missing_data` differs per alarm on purpose and is the easiest thing to get wrong.
 * For a count of bad things -- 5xx responses -- no data means none happened, so `notBreaching`
 * is right. For a count of good things -- healthy hosts, running tasks -- no data is exactly
 * what a total outage looks like, so `breaching` is right; `notBreaching` there would go
 * silent precisely when everything is down.
 */
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  count = local.alarms_enabled ? 1 : 0

  alarm_name          = "${var.name}-api-5xx"
  alarm_description   = "The API is returning server errors to browsers."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_actions       = [var.alarm_topic_arn]
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = aws_lb.api.arn_suffix
  }
  tags = local.tags
}

# Separate from the target 5xx above, and not redundant: this one counts errors the load
# balancer produced itself, which is what a client sees when no task is reachable to return
# a 5xx of its own. A deployment that fails to start every task shows up only here.
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  count = local.alarms_enabled ? 1 : 0

  alarm_name          = "${var.name}-alb-5xx"
  alarm_description   = "The load balancer could not reach the API at all."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_ELB_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_actions       = [var.alarm_topic_arn]
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = aws_lb.api.arn_suffix
  }
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "target_health" {
  count = local.alarms_enabled ? 1 : 0

  alarm_name          = "${var.name}-api-no-healthy-targets"
  alarm_description   = "No API task is passing the /health/ready check."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  alarm_actions       = [var.alarm_topic_arn]
  treat_missing_data  = "breaching"
  dimensions = {
    LoadBalancer = aws_lb.api.arn_suffix
    TargetGroup  = aws_lb_target_group.api.arn_suffix
  }
  tags = local.tags
}

# The worker has no load balancer, so a crash-looping worker is invisible to every alarm
# above: the analysis queue would drain no messages and only the age alarm would notice, ten
# minutes later. This notices the tasks themselves being gone.
resource "aws_cloudwatch_metric_alarm" "service_tasks" {
  for_each = local.alarms_enabled ? local.alarmed_services : {}

  alarm_name          = "${var.name}-${each.key}-no-running-tasks"
  alarm_description   = "The ${each.key} service has no running task."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  alarm_actions       = [var.alarm_topic_arn]
  treat_missing_data  = "breaching"
  dimensions = {
    ClusterName = aws_ecs_cluster.this.name
    ServiceName = each.value
  }
  tags = local.tags
}

output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "worker_service_name" {
  value = aws_ecs_service.worker.name
}

output "alb_dns_name" {
  value = aws_lb.api.dns_name
}

output "alb_zone_id" {
  value = aws_lb.api.zone_id
}

# The CloudWatch dimension form, which is the ARN tail and not the ARN. Exported rather than
# reassembled by the caller because an alarm whose dimension value is subtly wrong is not an
# error -- it reports INSUFFICIENT_DATA indefinitely, which reads as "nothing wrong".
output "alb_arn_suffix" {
  value = aws_lb.api.arn_suffix
}

output "target_group_arn_suffix" {
  value = aws_lb_target_group.api.arn_suffix
}

output "api_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "worker_repository_url" {
  value = aws_ecr_repository.worker.repository_url
}

output "task_role_arn" {
  value = local.effective_task_role_arn
}

output "media_convert_role_arn" {
  value = aws_iam_role.media_convert.arn
}
