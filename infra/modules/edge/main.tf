terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = "~> 5.80"
      configuration_aliases = [aws.us_east_1]
    }
  }
}

variable "name" {
  type = string
}

variable "hosted_zone_id" {
  type = string
}

variable "company_domain" {
  type = string
}

variable "applicant_domain" {
  type = string
}

variable "company_bucket_id" {
  type = string
}

variable "company_bucket_arn" {
  type = string
}

variable "company_bucket_domain_name" {
  type = string
}

variable "applicant_bucket_id" {
  type = string
}

variable "applicant_bucket_arn" {
  type = string
}

variable "applicant_bucket_domain_name" {
  type = string
}

variable "api_origin_domain_name" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  sites = {
    company = {
      domain      = var.company_domain
      bucket_id   = var.company_bucket_id
      bucket_arn  = var.company_bucket_arn
      bucket_name = var.company_bucket_domain_name
    }
    applicant = {
      domain      = var.applicant_domain
      bucket_id   = var.applicant_bucket_id
      bucket_arn  = var.applicant_bucket_arn
      bucket_name = var.applicant_bucket_domain_name
    }
  }
  tags = merge(var.tags, {
    Component = "edge"
  })
}

resource "aws_acm_certificate" "sites" {
  provider = aws.us_east_1

  domain_name               = var.company_domain
  subject_alternative_names = [var.applicant_domain]
  validation_method         = "DNS"
  tags                      = local.tags

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "certificate_validation" {
  for_each = {
    company   = var.company_domain
    applicant = var.applicant_domain
  }

  zone_id = var.hosted_zone_id
  name = one([
    for option in aws_acm_certificate.sites.domain_validation_options :
    option.resource_record_name if option.domain_name == each.value
  ])
  type = one([
    for option in aws_acm_certificate.sites.domain_validation_options :
    option.resource_record_type if option.domain_name == each.value
  ])
  records = [one([
    for option in aws_acm_certificate.sites.domain_validation_options :
    option.resource_record_value if option.domain_name == each.value
  ])]
  ttl = 60
}

resource "aws_acm_certificate_validation" "sites" {
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.sites.arn
  validation_record_fqdns = [for record in aws_route53_record.certificate_validation : record.fqdn]
}

resource "aws_cloudfront_origin_access_control" "spa" {
  name                              = "${var.name}-spa"
  description                       = "SigV4 access to private SPA origins"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_cache_policy" "spa" {
  name        = "${var.name}-spa"
  default_ttl = 300
  max_ttl     = 86400
  min_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_brotli = true
    enable_accept_encoding_gzip   = true
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

resource "aws_cloudfront_cache_policy" "api" {
  name        = "${var.name}-api-disabled"
  default_ttl = 0
  max_ttl     = 0
  min_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_brotli = true
    enable_accept_encoding_gzip   = true
    cookies_config {
      cookie_behavior = "all"
    }
    headers_config {
      header_behavior = "whitelist"
      headers {
        items = ["Authorization", "Content-Type", "Idempotency-Key", "Origin"]
      }
    }
    query_strings_config {
      query_string_behavior = "all"
    }
  }
}

resource "aws_cloudfront_origin_request_policy" "api" {
  name    = "${var.name}-api-viewer"
  comment = "Forward authenticated REST and WebSocket viewer context to the API origin"

  cookies_config {
    cookie_behavior = "all"
  }

  headers_config {
    header_behavior = "allViewer"
  }

  query_strings_config {
    query_string_behavior = "all"
  }
}

resource "aws_wafv2_web_acl" "edge" {
  provider = aws.us_east_1

  name  = "${var.name}-edge"
  scope = "CLOUDFRONT"

  default_action {
    allow {}
  }

  rule {
    name     = "aws-common"
    priority = 10
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-common"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "rate-limit"
    priority = 20
    action {
      block {}
    }
    statement {
      rate_based_statement {
        aggregate_key_type = "IP"
        limit              = 2000
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-rate"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.name}-edge"
    sampled_requests_enabled   = true
  }

  tags = local.tags
}

resource "aws_cloudfront_distribution" "site" {
  for_each = local.sites

  enabled             = true
  is_ipv6_enabled     = true
  aliases             = [each.value.domain]
  comment             = "${var.name} ${each.key} SPA"
  default_root_object = "index.html"
  web_acl_id          = aws_wafv2_web_acl.edge.arn
  price_class         = "PriceClass_200"

  origin {
    domain_name              = each.value.bucket_name
    origin_id                = "${each.key}-spa"
    origin_access_control_id = aws_cloudfront_origin_access_control.spa.id
  }

  origin {
    domain_name = var.api_origin_domain_name
    origin_id   = "api"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "${each.key}-spa"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    compress               = true
    cache_policy_id        = aws_cloudfront_cache_policy.spa.id
  }

  ordered_cache_behavior {
    path_pattern             = "/v1/*"
    target_origin_id         = "api"
    viewer_protocol_policy   = "https-only"
    allowed_methods          = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods           = ["GET", "HEAD", "OPTIONS"]
    compress                 = true
    cache_policy_id          = aws_cloudfront_cache_policy.api.id
    origin_request_policy_id = aws_cloudfront_origin_request_policy.api.id
  }

  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.sites.certificate_arn
    minimum_protocol_version = "TLSv1.2_2021"
    ssl_support_method       = "sni-only"
  }

  tags = merge(local.tags, { Site = each.key })
}

resource "aws_s3_bucket_policy" "spa" {
  for_each = local.sites

  bucket = each.value.bucket_id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontServicePrincipalReadOnly"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${each.value.bucket_arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.site[each.key].arn
        }
      }
    }]
  })
}

resource "aws_route53_record" "site" {
  for_each = local.sites

  zone_id = var.hosted_zone_id
  name    = each.value.domain
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.site[each.key].domain_name
    zone_id                = aws_cloudfront_distribution.site[each.key].hosted_zone_id
    evaluate_target_health = false
  }
}

output "distribution_ids" {
  value = {
    for name, distribution in aws_cloudfront_distribution.site : name => distribution.id
  }
}

output "distribution_domain_names" {
  value = {
    for name, distribution in aws_cloudfront_distribution.site : name => distribution.domain_name
  }
}
