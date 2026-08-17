mock_provider "aws" {}

mock_provider "aws" {
  alias = "us_east_1"
}

run "production_equivalent_local_plan" {
  command = plan

  override_data {
    target = module.network.data.aws_availability_zones.available
    values = {
      names = ["ap-northeast-2a", "ap-northeast-2c"]
    }
  }

  override_data {
    target = module.network.data.aws_region.current
    values = {
      name = "ap-northeast-2"
    }
  }

  override_data {
    target = module.compute.data.aws_region.current
    values = {
      name = "ap-northeast-2"
    }
  }

  variables {
    hosted_zone_id     = "Z0000000000000000000"
    company_domain     = "company.prod.example.com"
    applicant_domain   = "applicant.prod.example.com"
    api_image          = "000000000000.dkr.ecr.ap-northeast-2.amazonaws.com/iep-api:local"
    worker_image       = "000000000000.dkr.ecr.ap-northeast-2.amazonaws.com/iep-worker:local"
    interview_model_id = "local-model-id"
  }

  assert {
    condition     = contains(keys(module.data.bucket_arns), "source")
    error_message = "source bucket must be part of the local plan"
  }

  assert {
    condition     = module.compute.api_service_name != ""
    error_message = "API service must be part of the local plan"
  }

  assert {
    condition     = contains(keys(module.edge.distribution_ids), "company")
    error_message = "company CloudFront distribution must be part of the local plan"
  }
}
