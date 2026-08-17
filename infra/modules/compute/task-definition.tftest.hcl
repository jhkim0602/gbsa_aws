# What the two ECS containers are actually told to run, checked against the rendered
# task definition rather than the file text. Both defects this pins shipped and neither
# was visible to a text assertion: the worker launched a bare `python`, which cannot
# import a package installed into the image's uv virtualenv, and the GitHub credential
# the analysis worker needs reached no container at all.

mock_provider "aws" {}

variables {
  name                          = "iep-probe"
  vpc_id                        = "vpc-00000000000000000"
  private_subnet_ids            = ["subnet-00000000000000001"]
  alb_subnet_ids                = ["subnet-00000000000000002"]
  alb_security_group_id         = "sg-00000000000000001"
  application_security_group_id = "sg-00000000000000002"
  api_image                     = "000000000000.dkr.ecr.ap-northeast-2.amazonaws.com/iep/api:probe"
  worker_image                  = "000000000000.dkr.ecr.ap-northeast-2.amazonaws.com/iep/worker:probe"
  secret_arns                   = ["arn:aws:secretsmanager:ap-northeast-2:000000000000:secret:iep-probe/application/config-aaaaaa"]
  kms_key_arns                  = ["arn:aws:kms:ap-northeast-2:000000000000:key/00000000-0000-0000-0000-000000000000"]
  task_environment              = { AWS_REGION = "ap-northeast-2" }
  task_secrets = {
    GITHUB_TOKEN = "arn:aws:secretsmanager:ap-northeast-2:000000000000:secret:iep-probe/application/config-aaaaaa:github_token::"
  }
}

run "containers_render_the_credential_by_reference_and_launch_through_uv" {
  command = apply

  override_data {
    target = data.aws_region.current
    values = { name = "ap-northeast-2" }
  }

  override_resource {
    target = aws_iam_role.execution
    values = { arn = "arn:aws:iam::000000000000:role/iep-probe-ecs-execution" }
  }

  override_resource {
    target = aws_iam_role.task
    values = { arn = "arn:aws:iam::000000000000:role/iep-probe-ecs-task", name = "iep-probe-ecs-task" }
  }

  override_resource {
    target = aws_iam_role.media_convert
    values = { arn = "arn:aws:iam::000000000000:role/iep-probe-media-convert" }
  }

  override_resource {
    target = aws_lb.api
    values = { arn = "arn:aws:elasticloadbalancing:ap-northeast-2:000000000000:loadbalancer/app/iep-probe-api/aaaaaaaaaaaaaaaa" }
  }

  override_resource {
    target = aws_lb_target_group.api
    values = { arn = "arn:aws:elasticloadbalancing:ap-northeast-2:000000000000:targetgroup/iep-probe-api/aaaaaaaaaaaaaaaa" }
  }

  assert {
    condition = alltrue([
      for definition in [
        aws_ecs_task_definition.api.container_definitions,
        aws_ecs_task_definition.worker.container_definitions,
      ] :
      length([
        for secret in jsondecode(definition)[0].secrets :
        secret
        if secret.name == "GITHUB_TOKEN"
        && endswith(secret.valueFrom, ":github_token::")
        && startswith(secret.valueFrom, "arn:aws:secretsmanager:")
      ]) == 1
    ])
    error_message = "both containers must resolve GITHUB_TOKEN from the application secret"
  }

  assert {
    condition = alltrue([
      for definition in [
        aws_ecs_task_definition.api.container_definitions,
        aws_ecs_task_definition.worker.container_definitions,
      ] :
      length([
        for entry in jsondecode(definition)[0].environment :
        entry if entry.name == "GITHUB_TOKEN"
      ]) == 0
    ])
    error_message = "GITHUB_TOKEN must never be rendered as a plaintext environment entry"
  }

  assert {
    condition = jsondecode(aws_ecs_task_definition.worker.container_definitions)[0].command == [
      "uv", "run", "--no-sync", "python", "-m", "interview_evidence.worker"
    ]
    error_message = "the worker must launch python through the image virtualenv"
  }
}
