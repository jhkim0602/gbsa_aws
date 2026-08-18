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

variable "create_dns" {
  description = <<-EOT
    Whether this environment owns a domain. When false the module issues no certificate,
    writes no Route 53 record and claims no alias: each distribution answers on its own
    `*.cloudfront.net` name under CloudFront's default certificate.

    This is what makes a dev environment applyable before a domain is bought. It is not a
    downgrade of anything the platform relies on — TLS, WAF, the private origin access
    control and the disabled API cache policy are identical either way. What is lost is the
    readable hostname, and one real behaviour: without a fixed domain the SPA origin and the
    API share no parent name, so any future cookie scoped to the site domain would not work
    here. The platform sends bearer tokens, not cookies, so nothing in it depends on that.
  EOT
  type        = bool
  default     = true
}

variable "hosted_zone_id" {
  description = "Required when create_dns is true; ignored otherwise."
  type        = string
  default     = null
}

variable "company_domain" {
  description = "Alias for the company SPA. Ignored when create_dns is false."
  type        = string
  default     = null
}

variable "applicant_domain" {
  description = "Alias for the applicant SPA. Ignored when create_dns is false."
  type        = string
  default     = null
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
  dns_sites = var.create_dns ? local.sites : {}
}

# Fails at plan time rather than half way through an apply that has already created a
# distribution, which is where a null domain would otherwise surface.
resource "terraform_data" "dns_inputs" {
  count = var.create_dns ? 1 : 0

  lifecycle {
    precondition {
      condition = alltrue([
        var.hosted_zone_id != null,
        var.company_domain != null,
        var.applicant_domain != null,
      ])
      error_message = "create_dns requires hosted_zone_id, company_domain and applicant_domain."
    }
  }
}

resource "aws_acm_certificate" "sites" {
  count    = var.create_dns ? 1 : 0
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
  for_each = var.create_dns ? {
    company   = var.company_domain
    applicant = var.applicant_domain
  } : {}

  zone_id = var.hosted_zone_id
  name = one([
    for option in one(aws_acm_certificate.sites[*].domain_validation_options) :
    option.resource_record_name if option.domain_name == each.value
  ])
  type = one([
    for option in one(aws_acm_certificate.sites[*].domain_validation_options) :
    option.resource_record_type if option.domain_name == each.value
  ])
  records = [one([
    for option in one(aws_acm_certificate.sites[*].domain_validation_options) :
    option.resource_record_value if option.domain_name == each.value
  ])]
  ttl = 60
}

resource "aws_acm_certificate_validation" "sites" {
  count    = var.create_dns ? 1 : 0
  provider = aws.us_east_1

  certificate_arn         = one(aws_acm_certificate.sites[*].arn)
  validation_record_fqdns = [for record in aws_route53_record.certificate_validation : record.fqdn]
}

resource "aws_cloudfront_origin_access_control" "spa" {
  name                              = "${var.name}-spa"
  description                       = "SigV4 access to private SPA origins"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

/**
 * Turns a client-side route into the document, at the edge, before the origin is consulted.
 *
 * The alternative -- and what this replaces -- is a distribution-level
 * `custom_error_response` that rewrites 403 to `/index.html` with status 200. That switch
 * cannot tell a route from a file, and the bucket policy below grants `s3:GetObject` only,
 * so S3 answers 403 for a key that does not exist just as it does for one that is
 * forbidden. A browser holding a cached document that names a hashed asset since deleted
 * then requested `/assets/index-OLD.js`, got `index.html` with status 200 and a
 * `text/html` content type, and the module loader refused it: a blank console whose only
 * trace is a MIME type error, with every health check green. The local stack never showed
 * it -- nginx serves `/assets/` with `try_files $uri =404`.
 *
 * The extension test is the whole rule. Every application route is extension-less
 * (`/positions/<uuid>`, `/review/<uuid>`, `/access/<token>`; invitation tokens are
 * `secrets.token_urlsafe`, whose alphabet has no dot), and every emitted file has one.
 * `/v1/*` never arrives here: this is associated with the SPA behaviour only.
 */
resource "aws_cloudfront_function" "spa_router" {
  name    = "${var.name}-spa-router"
  runtime = "cloudfront-js-2.0"
  comment = "Serve the SPA document for client-side routes without masking missing files"
  publish = true

  code = <<-JS
    function handler(event) {
      var request = event.request;
      if (!/\.[0-9A-Za-z]+$/.test(request.uri)) {
        request.uri = '/index.html';
      }
      return request;
    }
  JS
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

# Every TTL zero, which CloudFront treats as caching disabled outright -- and a disabled
# policy accepts no cache-key parameters at all. Naming headers, cookies or query strings here
# is rejected at apply with `HeaderBehavior is invalid for policy with caching disabled`,
# because there is no cache key to vary when nothing is stored.
#
# Nothing is lost by their absence: a cache key decides which responses are shared, while what
# reaches the origin is decided by the origin request policy below, which forwards `allViewer`
# -- every header the browser sent, Authorization included. The `none` behaviours are
# therefore the only accepted spelling of "share nothing", not a narrowing of what the API
# receives.
resource "aws_cloudfront_cache_policy" "api" {
  name        = "${var.name}-api-disabled"
  default_ttl = 0
  max_ttl     = 0
  min_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_brotli = false
    enable_accept_encoding_gzip   = false
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

  enabled = true
  # No alias without a certificate that covers it: CloudFront rejects an alias it cannot
  # serve TLS for, so this tracks `create_dns` rather than the domain variables.
  is_ipv6_enabled     = true
  aliases             = var.create_dns ? [each.value.domain] : []
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

    # Only on this behaviour. `/v1/*` is matched by the ordered behaviour below and must
    # reach the API with its path intact.
    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_router.arn
    }
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

  # No `custom_error_response` rewriting 403 to the document. The viewer-request function
  # above already routes every extension-less path to `/index.html`, so a 403 that still
  # arrives here is a request for a file that is genuinely absent or forbidden, and it has to
  # be reported as one rather than answered with HTML and a 200.

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Still TLS either way. Without an alias the distribution is reached by its own
  # `*.cloudfront.net` name, which CloudFront's own certificate already covers; a custom
  # certificate is what an alias needs, not what encryption needs.
  viewer_certificate {
    cloudfront_default_certificate = var.create_dns ? null : true
    acm_certificate_arn            = one(aws_acm_certificate_validation.sites[*].certificate_arn)
    minimum_protocol_version       = var.create_dns ? "TLSv1.2_2021" : null
    ssl_support_method             = var.create_dns ? "sni-only" : null
  }

  tags = merge(local.tags, { Site = each.key })
}

/**
 * Read access for the distribution, and the grant that lets S3 answer "not found".
 *
 * `s3:ListBucket` carries no listing capability here -- the resource is the bucket itself,
 * CloudFront never issues a ListObjects, and no object becomes reachable that `s3:GetObject`
 * did not already reach. What it changes is the error: without permission to test a key's
 * existence, S3 answers a GET for a key that does not exist with 403, deliberately, so that
 * a caller cannot enumerate a bucket by reading status codes. A missing asset was therefore
 * indistinguishable from a forbidden one, which is what made the 403-to-index.html rewrite
 * look reasonable and turned every stale asset into an HTML document served with status 200.
 *
 * With the grant, an absent key returns 404 -- the local stack's `try_files $uri =404`
 * behaviour, which the browser e2e suite already asserts.
 */
resource "aws_s3_bucket_policy" "spa" {
  for_each = local.sites

  bucket = each.value.bucket_id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontServicePrincipalReadOnly"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = ["s3:GetObject", "s3:ListBucket"]
      Resource  = [each.value.bucket_arn, "${each.value.bucket_arn}/*"]
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.site[each.key].arn
        }
      }
    }]
  })
}

resource "aws_route53_record" "site" {
  for_each = local.dns_sites

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

# Where a browser actually reaches each SPA. Derived here rather than assembled by every
# caller, because the answer differs by `create_dns` and a caller that guesses wrong sends
# the smoke test and the e2e suite to a hostname that does not resolve.
output "site_urls" {
  value = {
    for name, distribution in aws_cloudfront_distribution.site :
    name => "https://${var.create_dns ? local.sites[name].domain : distribution.domain_name}"
  }
}
