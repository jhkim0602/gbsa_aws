# The shape dev actually applies: no hosted zone, no certificate, no alias.
#
# Every prior edge assertion supplied a domain, so nothing covered the path the only
# deployed environment uses. The two failures this pins are both apply-time and both
# opaque: CloudFront rejects `aliases` it holds no certificate for, and a
# `viewer_certificate` that sets neither `cloudfront_default_certificate` nor an ACM ARN is
# an invalid argument combination. Rendering the distribution is what proves the switch is
# coherent -- `terraform validate` accepts all three of those.

# The function ARN is given a real shape here rather than per run, because the distribution
# schema validates that `function_association.function_arn` is an ARN and that validation runs
# before a run's `override_resource` is applied -- the mock provider's random string fails it.
mock_provider "aws" {
  mock_resource "aws_cloudfront_function" {
    defaults = {
      arn = "arn:aws:cloudfront::000000000000:function/iep-probe-spa-router"
    }
  }
}

mock_provider "aws" {
  alias = "us_east_1"
}

variables {
  name                         = "iep-probe"
  company_bucket_id            = "iep-probe-company-spa"
  company_bucket_arn           = "arn:aws:s3:::iep-probe-company-spa"
  company_bucket_domain_name   = "iep-probe-company-spa.s3.ap-northeast-2.amazonaws.com"
  applicant_bucket_id          = "iep-probe-applicant-spa"
  applicant_bucket_arn         = "arn:aws:s3:::iep-probe-applicant-spa"
  applicant_bucket_domain_name = "iep-probe-applicant-spa.s3.ap-northeast-2.amazonaws.com"
  api_origin_domain_name       = "iep-probe-api-000000000.ap-northeast-2.elb.amazonaws.com"
}

run "domainless_edge_serves_both_spas_on_cloudfront_names" {
  command = apply

  variables {
    create_dns = false
  }

  override_resource {
    target = aws_cloudfront_distribution.site
    values = {
      domain_name    = "d111111abcdef8.cloudfront.net"
      hosted_zone_id = "Z2FDTNDATAQYW2"
      arn            = "arn:aws:cloudfront::000000000000:distribution/EDFDVBD6EXAMPLE"
    }
  }

  assert {
    condition     = length(aws_acm_certificate.sites) == 0
    error_message = "a domainless environment must not request a certificate it cannot validate"
  }

  assert {
    condition     = length(aws_route53_record.certificate_validation) == 0
    error_message = "a domainless environment has no zone to write validation records into"
  }

  assert {
    condition     = length(aws_route53_record.site) == 0
    error_message = "a domainless environment has no zone to write site records into"
  }

  assert {
    condition = alltrue([
      for distribution in values(aws_cloudfront_distribution.site) :
      length(distribution.aliases) == 0
    ])
    error_message = "CloudFront rejects an alias with no certificate covering it"
  }

  # Still TLS. The default certificate is what covers a `*.cloudfront.net` name, so the
  # assertion is that it is switched on -- not that encryption was traded away.
  assert {
    condition = alltrue([
      for distribution in values(aws_cloudfront_distribution.site) :
      distribution.viewer_certificate[0].cloudfront_default_certificate == true
      && distribution.viewer_certificate[0].acm_certificate_arn == null
    ])
    error_message = "domainless distributions must serve CloudFront's own certificate"
  }

  # What the invitation email and the deploy smoke test are pointed at. A `site_urls` that
  # fell back to `https://` plus a null domain would read as a valid string here and send
  # every applicant to a host that does not resolve.
  assert {
    condition = alltrue([
      for url in values(output.site_urls) :
      startswith(url, "https://") && strcontains(url, ".cloudfront.net")
    ])
    error_message = "site_urls must name the CloudFront hostname when there is no domain"
  }

  assert {
    condition     = length(keys(output.site_urls)) == 2
    error_message = "both the company and applicant SPA need a reachable URL"
  }
}

# A client-side route and a missing file are different answers, and the distribution used to
# give both the same one.
#
# The replaced arrangement was a `custom_error_response` mapping 403 to `/index.html` with
# status 200. S3 returns 403 -- not 404 -- for a key that does not exist when the policy
# grants only `s3:GetObject`, which is what the OAC policy here grants, so a browser holding
# a cached document that named a since-deleted hashed asset received `index.html` with a
# `text/html` content type in place of its JavaScript. The module loader refuses that, and
# the symptom is a blank console with every health check green. Nothing local reproduces it:
# nginx serves `/assets/` with `try_files $uri =404`.
run "spa_routing_does_not_turn_a_missing_file_into_the_document" {
  command = apply

  variables {
    create_dns = false
  }

  override_resource {
    target = aws_cloudfront_distribution.site
    values = {
      domain_name    = "d111111abcdef8.cloudfront.net"
      hosted_zone_id = "Z2FDTNDATAQYW2"
      arn            = "arn:aws:cloudfront::000000000000:distribution/EDFDVBD6EXAMPLE"
    }
  }

  assert {
    condition = alltrue([
      for distribution in values(aws_cloudfront_distribution.site) :
      length(distribution.custom_error_response) == 0
    ])
    error_message = "no error response may rewrite a 403 into the document with status 200"
  }

  # The routing has to happen somewhere, so absence above is only half the assertion: the
  # function must be attached, on the SPA behaviour, at viewer-request.
  assert {
    condition = alltrue([
      for distribution in values(aws_cloudfront_distribution.site) :
      length(distribution.default_cache_behavior[0].function_association) == 1
      && one(distribution.default_cache_behavior[0].function_association).event_type == "viewer-request"
      && one(distribution.default_cache_behavior[0].function_association).function_arn == aws_cloudfront_function.spa_router.arn
    ])
    error_message = "the SPA behaviour must route client-side paths in a viewer-request function"
  }

  # And not on `/v1/*`: rewriting an API path to `/index.html` would answer every request
  # the console makes with the console.
  assert {
    condition = alltrue([
      for distribution in values(aws_cloudfront_distribution.site) :
      alltrue([
        for behavior in distribution.ordered_cache_behavior :
        length(behavior.function_association) == 0
      ])
    ])
    error_message = "the API behaviour must reach the origin with its path unmodified"
  }

  # The distinction the function draws, asserted on the published code rather than trusted
  # from the comment: an extension test, and the document as the rewrite target.
  assert {
    condition = alltrue([
      strcontains(aws_cloudfront_function.spa_router.code, "/\\.[0-9A-Za-z]+$/"),
      strcontains(aws_cloudfront_function.spa_router.code, "'/index.html'"),
      aws_cloudfront_function.spa_router.publish == true,
    ])
    error_message = "the router must rewrite only extension-less paths, and must be published"
  }
}

# The other half of the same defect, one layer down.
#
# S3 answers a GET for a key that does not exist with 403 rather than 404 unless the caller
# is also allowed `s3:ListBucket` -- it will not confirm a key's absence to a principal that
# cannot test for it. So "missing" and "forbidden" arrived at CloudFront as the same status,
# which is what made rewriting 403 to the document look like SPA routing. The grant adds no
# reach: CloudFront issues no ListObjects, and every object was already readable.
run "the_origin_grant_lets_s3_distinguish_missing_from_forbidden" {
  command = apply

  variables {
    create_dns = false
  }

  override_resource {
    target = aws_cloudfront_distribution.site
    values = {
      domain_name    = "d111111abcdef8.cloudfront.net"
      hosted_zone_id = "Z2FDTNDATAQYW2"
      arn            = "arn:aws:cloudfront::000000000000:distribution/EDFDVBD6EXAMPLE"
    }
  }

  assert {
    condition = alltrue([
      for policy in values(aws_s3_bucket_policy.spa) :
      alltrue([
        for action in jsondecode(policy.policy).Statement[0].Action :
        contains(["s3:GetObject", "s3:ListBucket"], action)
      ])
      && length(jsondecode(policy.policy).Statement[0].Action) == 2
    ])
    error_message = "the origin grant needs ListBucket so a missing key returns 404, not 403"
  }

  # ListBucket is evaluated against the bucket ARN, not the object ARN, so a policy that
  # names only `bucket/*` grants it nothing and the 403 remains.
  assert {
    condition = alltrue([
      for name, policy in aws_s3_bucket_policy.spa :
      contains(jsondecode(policy.policy).Statement[0].Resource, local.sites[name].bucket_arn)
      && contains(jsondecode(policy.policy).Statement[0].Resource, "${local.sites[name].bucket_arn}/*")
    ])
    error_message = "the grant must name both the bucket and its objects"
  }

  # Still only this distribution. Widening the actions must not widen who may call them --
  # without the condition the bucket is readable by any CloudFront distribution in any account.
  assert {
    condition = alltrue([
      for name, policy in aws_s3_bucket_policy.spa :
      jsondecode(policy.policy).Statement[0].Condition.StringEquals["AWS:SourceArn"] == aws_cloudfront_distribution.site[name].arn
    ])
    error_message = "the grant must stay scoped to this distribution"
  }
}
