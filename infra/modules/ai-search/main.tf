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

variable "security_group_ids" {
  type = list(string)
}

variable "source_bucket_arn" {
  type = string
}

variable "application_role_arn" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "embedding_model_arn" {
  type = string
}

variable "vector_index_name" {
  type    = string
  default = "candidate-materials-v1"
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  collection_name        = substr(replace("${var.name}-candidate-materials", "_", "-"), 0, 32)
  encryption_policy_name = substr("${local.collection_name}-enc", 0, 32)
  network_policy_name    = substr("${local.collection_name}-net", 0, 32)
  data_policy_name       = substr("${local.collection_name}-data", 0, 32)
  vpc_endpoint_name      = substr("${local.collection_name}-vpce", 0, 32)
  index_mapping = {
    settings = {
      index = {
        knn = true
      }
    }
    mappings = {
      properties = {
        company_id   = { type = "keyword" }
        applicant_id = { type = "keyword" }
        source_type  = { type = "keyword" }
        path         = { type = "keyword" }
        symbol       = { type = "keyword" }
        text         = { type = "text" }
        metadata     = { type = "text", index = false }
        vector       = { type = "knn_vector", dimension = 1024 }
      }
    }
  }
  tags = merge(var.tags, {
    Component = "ai-search"
  })
}

resource "aws_opensearchserverless_vpc_endpoint" "this" {
  name               = local.vpc_endpoint_name
  vpc_id             = var.vpc_id
  subnet_ids         = var.private_subnet_ids
  security_group_ids = var.security_group_ids
}

resource "aws_opensearchserverless_security_policy" "encryption" {
  name = local.encryption_policy_name
  type = "encryption"
  policy = jsonencode({
    Rules = [{
      ResourceType = "collection"
      Resource     = ["collection/${local.collection_name}"]
    }]
    AWSOwnedKey = false
    KmsARN      = var.kms_key_arn
  })
}

resource "aws_opensearchserverless_security_policy" "network" {
  name = local.network_policy_name
  type = "network"
  policy = jsonencode([{
    Rules = [
      {
        ResourceType = "collection"
        Resource     = ["collection/${local.collection_name}"]
      },
      {
        ResourceType = "dashboard"
        Resource     = ["collection/${local.collection_name}"]
      }
    ]
    AllowFromPublic = false
    SourceVPCEs     = [aws_opensearchserverless_vpc_endpoint.this.id]
  }])
}

resource "aws_opensearchserverless_collection" "this" {
  name = local.collection_name
  type = "VECTORSEARCH"
  tags = local.tags

  depends_on = [
    aws_opensearchserverless_security_policy.encryption,
    aws_opensearchserverless_security_policy.network,
  ]
}

resource "aws_iam_role" "knowledge_base" {
  name = "${var.name}-bedrock-kb"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "knowledge_base" {
  name = "knowledge-base-data"
  role = aws_iam_role.knowledge_base.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = var.embedding_model_arn
      },
      {
        Effect   = "Allow"
        Action   = ["aoss:APIAccessAll"]
        Resource = aws_opensearchserverless_collection.this.arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = [var.source_bucket_arn, "${var.source_bucket_arn}/*"]
      }
    ]
  })
}

resource "aws_opensearchserverless_access_policy" "data" {
  name = local.data_policy_name
  type = "data"
  policy = jsonencode([{
    Rules = [
      {
        ResourceType = "collection"
        Resource     = ["collection/${local.collection_name}"]
        Permission   = ["aoss:DescribeCollectionItems", "aoss:CreateCollectionItems"]
      },
      {
        ResourceType = "index"
        Resource     = ["index/${local.collection_name}/*"]
        Permission   = ["aoss:*"]
      }
    ]
    Principal = [var.application_role_arn, aws_iam_role.knowledge_base.arn]
  }])
}

resource "aws_ssm_parameter" "index_mapping" {
  name        = "/${var.name}/search/${var.vector_index_name}/mapping"
  description = "Versioned index mapping consumed by the deployment pipeline"
  type        = "String"
  value       = jsonencode(local.index_mapping)
  tags        = local.tags
}

resource "aws_bedrockagent_knowledge_base" "this" {
  name     = "${var.name}-candidate-materials"
  role_arn = aws_iam_role.knowledge_base.arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = var.embedding_model_arn
    }
  }

  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"
    opensearch_serverless_configuration {
      collection_arn    = aws_opensearchserverless_collection.this.arn
      vector_index_name = var.vector_index_name
      field_mapping {
        metadata_field = "metadata"
        text_field     = "text"
        vector_field   = "vector"
      }
    }
  }

  depends_on = [aws_opensearchserverless_access_policy.data]
  tags       = local.tags
}

resource "aws_bedrockagent_data_source" "source" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.this.id
  name              = "${var.name}-candidate-source"

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn         = var.source_bucket_arn
      inclusion_prefixes = ["companies/"]
    }
  }

  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"
      fixed_size_chunking_configuration {
        max_tokens         = 500
        overlap_percentage = 15
      }
    }
  }
}

resource "aws_bedrock_guardrail" "interview" {
  name                      = "${var.name}-interview"
  description               = "Secondary safety layer for the structured interview pipeline"
  blocked_input_messaging   = "요청을 안전하게 처리할 수 없습니다."
  blocked_outputs_messaging = "질문을 안전하게 생성할 수 없습니다."

  content_policy_config {
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
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

output "collection_arn" {
  value = aws_opensearchserverless_collection.this.arn
}

output "collection_endpoint" {
  value = aws_opensearchserverless_collection.this.collection_endpoint
}

output "knowledge_base_id" {
  value = aws_bedrockagent_knowledge_base.this.id
}

output "guardrail_id" {
  value = aws_bedrock_guardrail.interview.guardrail_id
}

output "index_mapping_parameter_arn" {
  value = aws_ssm_parameter.index_mapping.arn
}

output "vector_index_name" {
  value = var.vector_index_name
}
