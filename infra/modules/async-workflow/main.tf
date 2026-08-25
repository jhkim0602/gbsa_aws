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

variable "kms_key_arn" {
  type = string
}

variable "max_receive_count" {
  type    = number
  default = 5
}

variable "max_receive_count_by_workflow" {
  type = map(number)
  default = {
    reporting = 12
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  workflows = toset(["analysis", "media", "reporting", "deletion", "capacity"])
  tags = merge(var.tags, {
    Component = "async-workflow"
  })
}

resource "aws_sqs_queue" "dlq" {
  for_each = local.workflows

  name                              = "${var.name}-${each.key}-dlq"
  kms_master_key_id                 = var.kms_key_arn
  kms_data_key_reuse_period_seconds = 300
  message_retention_seconds         = 1209600
  tags                              = merge(local.tags, { Workflow = each.key })
}

resource "aws_sqs_queue" "work" {
  for_each = local.workflows

  name                              = "${var.name}-${each.key}"
  kms_master_key_id                 = var.kms_key_arn
  kms_data_key_reuse_period_seconds = 300
  visibility_timeout_seconds        = each.key == "media" ? 900 : 300
  message_retention_seconds         = 345600
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = lookup(var.max_receive_count_by_workflow, each.key, var.max_receive_count)
  })
  tags = merge(local.tags, { Workflow = each.key })
}

resource "aws_cloudwatch_event_bus" "domain" {
  name = "${var.name}-domain"
  tags = local.tags
}

resource "aws_iam_role" "eventbridge" {
  name = "${var.name}-eventbridge"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "eventbridge" {
  name = "send-workflow-messages"
  role = aws_iam_role.eventbridge.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage"]
      Resource = values(aws_sqs_queue.work)[*].arn
    }]
  })
}

resource "aws_cloudwatch_event_rule" "retention" {
  name           = "${var.name}-retention-expired"
  event_bus_name = aws_cloudwatch_event_bus.domain.name
  event_pattern = jsonencode({
    source      = ["interview-evidence.company-management"]
    detail-type = ["retention.expired"]
  })
  tags = local.tags
}

resource "aws_cloudwatch_event_target" "retention" {
  rule           = aws_cloudwatch_event_rule.retention.name
  event_bus_name = aws_cloudwatch_event_bus.domain.name
  target_id      = "deletion-queue"
  arn            = aws_sqs_queue.work["deletion"].arn
  role_arn       = aws_iam_role.eventbridge.arn
}

resource "aws_iam_role" "step_functions" {
  name = "${var.name}-step-functions"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "step_functions" {
  name = "dispatch-workflows"
  role = aws_iam_role.step_functions.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage"]
      Resource = values(aws_sqs_queue.work)[*].arn
    }]
  })
}

resource "aws_sfn_state_machine" "pipeline" {
  name     = "${var.name}-pipeline"
  role_arn = aws_iam_role.step_functions.arn
  type     = "STANDARD"

  definition = jsonencode({
    Comment = "Dispatch durable analysis, media, reporting, deletion, or capacity work"
    StartAt = "Dispatch"
    States = {
      Dispatch = {
        Type = "Choice"
        Choices = [
          for workflow in sort(tolist(local.workflows)) : {
            Variable     = "$.workflow"
            StringEquals = workflow
            Next         = "Queue${title(workflow)}"
          }
        ]
        Default = "UnsupportedWorkflow"
      }
      QueueAnalysis = {
        Type     = "Task"
        Resource = "arn:aws:states:::sqs:sendMessage"
        Parameters = {
          QueueUrl        = aws_sqs_queue.work["analysis"].url
          "MessageBody.$" = "$"
        }
        End = true
      }
      QueueMedia = {
        Type     = "Task"
        Resource = "arn:aws:states:::sqs:sendMessage"
        Parameters = {
          QueueUrl        = aws_sqs_queue.work["media"].url
          "MessageBody.$" = "$"
        }
        End = true
      }
      QueueReporting = {
        Type     = "Task"
        Resource = "arn:aws:states:::sqs:sendMessage"
        Parameters = {
          QueueUrl        = aws_sqs_queue.work["reporting"].url
          "MessageBody.$" = "$"
        }
        End = true
      }
      QueueDeletion = {
        Type     = "Task"
        Resource = "arn:aws:states:::sqs:sendMessage"
        Parameters = {
          QueueUrl        = aws_sqs_queue.work["deletion"].url
          "MessageBody.$" = "$"
        }
        End = true
      }
      QueueCapacity = {
        Type     = "Task"
        Resource = "arn:aws:states:::sqs:sendMessage"
        Parameters = {
          QueueUrl        = aws_sqs_queue.work["capacity"].url
          "MessageBody.$" = "$"
        }
        End = true
      }
      UnsupportedWorkflow = {
        Type  = "Fail"
        Error = "UnsupportedWorkflow"
      }
    }
  })

  tags = local.tags
}

output "queue_arns" {
  value = { for name, queue in aws_sqs_queue.work : name => queue.arn }
}

output "queue_urls" {
  value = { for name, queue in aws_sqs_queue.work : name => queue.url }
}

output "dlq_arns" {
  value = { for name, queue in aws_sqs_queue.dlq : name => queue.arn }
}

output "event_bus_arn" {
  value = aws_cloudwatch_event_bus.domain.arn
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.pipeline.arn
}
