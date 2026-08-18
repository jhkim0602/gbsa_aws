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

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  tags = merge(var.tags, {
    Component = "ai-safety"
  })
}

resource "aws_bedrock_guardrail" "interview" {
  name                      = "${var.name}-interview"
  description               = "Secondary safety layer for the structured interview pipeline"
  blocked_input_messaging   = "요청을 안전하게 처리할 수 없습니다."
  blocked_outputs_messaging = "질문을 안전하게 생성할 수 없습니다."

  content_policy_config {
    # A prompt attack is something a caller writes, so Bedrock scores it on the way in only
    # and rejects CreateGuardrail outright unless the response strength is NONE. This is not
    # a weaker setting than the line above it: there is no such thing as a model response
    # that attacks its own prompt, and `HIGH` here fails the apply rather than filtering
    # anything. An applicant's answer reaches the model as input, which is the direction that
    # matters -- it is the one place in this pipeline where untrusted text becomes a prompt.
    filters_config {
      input_strength  = "HIGH"
      output_strength = "NONE"
      type            = "PROMPT_ATTACK"
    }
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "HATE"
    }
  }

  tags = local.tags
}

output "guardrail_id" {
  value = aws_bedrock_guardrail.interview.guardrail_id
}
