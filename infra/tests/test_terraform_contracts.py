import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODULE_RESOURCES = {
    "network": {
        "aws_vpc",
        "aws_subnet",
        "aws_vpc_endpoint",
        "aws_security_group",
    },
    "edge": {
        "aws_cloudfront_distribution",
        "aws_cloudfront_origin_access_control",
        "aws_wafv2_web_acl",
        "aws_route53_record",
        "aws_acm_certificate",
    },
    "compute": {
        "aws_ecr_repository",
        "aws_lb",
        "aws_ecs_cluster",
        "aws_ecs_service",
        "aws_appautoscaling_target",
    },
    "data": {
        "aws_rds_cluster",
        "aws_rds_cluster_instance",
        "aws_dynamodb_table",
        "aws_s3_bucket",
        "aws_kms_key",
        "aws_secretsmanager_secret",
    },
    "async-workflow": {
        "aws_sqs_queue",
        "aws_sfn_state_machine",
        "aws_cloudwatch_event_bus",
    },
    "ai-search": {
        "aws_bedrock_guardrail",
    },
    "identity": {
        "aws_cognito_user_pool",
        "aws_cognito_user_pool_client",
        "aws_sesv2_email_identity",
        "aws_iam_role",
    },
    "observability": {
        "aws_cloudwatch_log_group",
        "aws_cloudwatch_metric_alarm",
        "aws_xray_sampling_rule",
        "aws_budgets_budget",
        "aws_cloudtrail",
    },
}


APPLICATION_ROOTS = (
    ROOT / "environments" / "dev" / "application" / "main.tf",
    ROOT / "environments" / "prod" / "main.tf",
)


def read(path: Path) -> str:
    assert path.is_file(), f"missing Terraform file: {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def container_commands(compute: str) -> list[list[str]]:
    """The application containers' `command`, as the words the container would exec.

    Scoped to the `aws_ecs_task_definition` resources rather than the whole module. The
    collector sidecar is built in `locals` and its command is a config flag, not a Python
    launcher, so a module-wide scrape reported it as a container running bare `python`.
    """
    return [
        re.findall(r'"([^"]+)"', body)
        for block in re.findall(
            r'^resource "aws_ecs_task_definition".*?^}$', compute, re.DOTALL | re.MULTILINE
        )
        for body in re.findall(r"command\s*=\s*\[(.*?)\]", block, re.DOTALL)
    ]


def assignment_body(source: str, label: str) -> str:
    """The body of a `label = { ... }` argument passed to a module at two-space indent."""
    start = source.index(f"{label} = {{")
    return source[start : source.index("\n  }", start)]


def test_modules_define_required_aws_resources_without_provisioners() -> None:
    for module, resources in MODULE_RESOURCES.items():
        source = read(ROOT / "modules" / module / "main.tf")
        for resource in resources:
            assert f'resource "{resource}"' in source, f"{module} missing {resource}"
        assert "provisioner " not in source
        assert "local-exec" not in source
        assert "remote-exec" not in source


def test_dev_roots_use_distinct_native_lockfile_state_keys() -> None:
    roots = ("foundation", "data-ai", "application")
    sources = {root: read(ROOT / "environments" / "dev" / root / "main.tf") for root in roots}
    for root, source in sources.items():
        assert 'backend "s3"' in source
        assert "use_lockfile = true" in source
        assert f'key          = "dev/{root}/terraform.tfstate"' in source
    assert len(set(sources.values())) == len(roots)


def test_dev_and_prod_have_independent_state_and_production_protection() -> None:
    dev_foundation = read(ROOT / "environments" / "dev" / "foundation" / "main.tf")
    dev_data = read(ROOT / "environments" / "dev" / "data-ai" / "main.tf")
    prod = read(ROOT / "environments" / "prod" / "main.tf")
    assert 'key          = "prod/terraform.tfstate"' in prod
    # Matched with flexible whitespace rather than a literal, because `terraform fmt` aligns
    # `=` to the longest argument name in the block: adding one longer argument silently
    # rewrites the spacing of every other line and broke this assertion once, reporting a
    # missing protection that had never been removed.
    # Anchored to the line start so `enable_deletion_protection` -- the ALB's separate
    # setting, asserted below -- cannot satisfy a check about the pool and the database.
    assert re.search(r"^\s*deletion_protection\s*=\s*true", prod, re.MULTILINE)
    assert re.search(r"^\s*deletion_protection\s*=\s*false", dev_foundation, re.MULTILINE)
    assert re.search(r"^\s*deletion_protection\s*=\s*false", dev_data, re.MULTILINE)
    assert re.search(r"force_destroy\s*=\s*false", prod)
    assert re.search(r"nat_gateway_per_az\s*=\s*true", prod)
    assert re.search(r"enable_deletion_protection\s*=\s*true", prod)


def test_all_roots_pin_region_and_default_security_tags() -> None:
    roots = (
        ROOT / "environments" / "dev" / "foundation" / "main.tf",
        ROOT / "environments" / "dev" / "data-ai" / "main.tf",
        ROOT / "environments" / "dev" / "application" / "main.tf",
        ROOT / "environments" / "prod" / "main.tf",
    )
    for path in roots:
        source = read(path)
        assert 'default = "ap-northeast-2"' in source
        assert "default_tags" in source
        assert 'ManagedBy   = "Terraform"' in source


def test_network_and_edge_keep_application_origins_private() -> None:
    network = read(ROOT / "modules" / "network" / "main.tf")
    edge = read(ROOT / "modules" / "edge" / "main.tf")

    assert "com.amazonaws.global.cloudfront.origin-facing" in network
    assert "prefix_list_id" in network
    assert "referenced_security_group_id = aws_security_group.alb.id" in network
    assert "map_public_ip_on_launch = false" in network
    assert 'origin_access_control_origin_type = "s3"' in edge
    assert 'signing_behavior                  = "always"' in edge
    assert '"AWS:SourceArn"' in edge
    assert 'header_behavior = "allViewer"' in edge
    assert 'scope = "CLOUDFRONT"' in edge


def test_compute_and_data_define_durable_private_runtime_boundaries() -> None:
    compute = read(ROOT / "modules" / "compute" / "main.tf")
    data = read(ROOT / "modules" / "data" / "main.tf")

    assert 'image_tag_mutability = "IMMUTABLE"' in compute
    assert "assign_public_ip = false" in compute
    assert "deployment_circuit_breaker" in compute
    assert "ignore_changes = [desired_count, task_definition]" in compute
    assert "enable_deletion_protection = var.enable_deletion_protection" in compute
    assert "count = var.create_task_role ? 1 : 0" in compute
    assert '"uvicorn",' in compute
    assert '"interview_evidence.main:app",' in compute
    assert '"--port",' in compute
    assert '"8000",' in compute
    assert 'command     = ["python", "-m", "interview_evidence.main"]' not in compute
    assert compute.count('"secretsmanager:GetSecretValue"') == 2
    assert "block_public_policy     = true" in data
    assert 'sse_algorithm     = "aws:kms"' in data
    assert "point_in_time_recovery" in data
    assert "manage_master_user_password" in data
    assert "deletion_protection             = var.deletion_protection" in data


def test_application_roots_pass_secret_identifiers_without_secret_values() -> None:
    roots = (
        ROOT / "environments" / "dev" / "application" / "main.tf",
        ROOT / "environments" / "prod" / "main.tf",
    )
    for root in roots:
        source = read(root)
        assert "AURORA_ENDPOINT" in source
        assert "AURORA_MASTER_SECRET_ARN" in source
        assert "AURORA_DATABASE" in source
        assert "MIGRATION_DATABASE_URL" not in source


def test_application_roots_pass_complete_production_adapter_configuration() -> None:
    roots = (
        ROOT / "environments" / "dev" / "application" / "main.tf",
        ROOT / "environments" / "prod" / "main.tf",
    )
    required = {
        "AWS_REGION",
        "SOURCE_BUCKET",
        "MEDIA_BUCKET",
        "KMS_KEY_ARN",
        "DYNAMODB_TABLE_NAME",
        "RETRIEVAL_BACKEND",
        "BEDROCK_EMBEDDING_MODEL_ID",
        "BEDROCK_MODEL_ID",
        "BEDROCK_GUARDRAIL_ID",
        "SES_FROM_ADDRESS",
        "SQS_ANALYSIS_QUEUE_URL",
        "SQS_MEDIA_QUEUE_URL",
        "SQS_REPORTING_QUEUE_URL",
        "SQS_DELETION_QUEUE_URL",
        "APPLICANT_ACCESS_BASE_URL",
    }
    for root in roots:
        source = read(root)
        for name in required:
            assert name in source, f"{root.parent.name} missing {name}"

    compute = read(ROOT / "modules" / "compute" / "main.tf")
    assert 'Principal = { Service = "mediaconvert.amazonaws.com" }' in compute
    assert '"mediaconvert:CreateJob"' in compute
    assert '"iam:PassRole"' in compute
    assert '"transcribe:StartTranscriptionJob"' in compute
    assert '"transcribe:GetTranscriptionJob"' in compute
    assert '"cognito-idp:GetUser"' in compute
    assert '"ses:SendEmail"' in compute
    assert "MEDIACONVERT_ROLE_ARN" in compute


def test_every_task_command_runs_python_through_the_image_virtualenv() -> None:
    """The image installs the package with `uv sync --no-editable`, into a virtualenv.

    A container told to run a bare `python -m interview_evidence...` therefore starts the
    interpreter outside that virtualenv and dies on ModuleNotFoundError before any code
    of ours runs -- the ECS worker shipped that way, crash-looping while the api beside it
    was fine. Asserting the module name is right is not enough; the launcher has to be.
    """
    compute = read(ROOT / "modules" / "compute" / "main.tf")
    commands = container_commands(compute)
    assert commands, "the compute module defines container commands"
    for command in commands:
        assert command[:3] == ["uv", "run", "--no-sync"], command
        assert any(word.startswith("interview_evidence") for word in command), command

    # The sidecar is not one of the above -- it is a prebuilt AWS image with no virtualenv of
    # ours -- but it must stay non-essential. Marked essential, a collector that fails to start
    # takes the task down with it and turns a missing trace into an outage.
    #
    # Anchored to the line start, because a plain substring check was satisfied by the doc
    # comment above the block that explains why the field is false: flipping the actual field
    # to `true` left the test passing.
    assert re.search(r"^\s*image\s*=\s*var\.otel_image", compute, re.MULTILINE)
    assert re.search(r"^\s*essential\s*=\s*false", compute, re.MULTILINE)


def test_application_roots_deliver_the_github_credential_by_reference_only() -> None:
    """The analysis worker needs a GitHub token, and a token is not configuration.

    Anonymous GitHub allows 60 API requests an hour, which one real repository analysis
    can spend by itself, so without the token the submission analysis a reviewer is
    reading stops mid-fetch. It still must never be a plaintext environment value: the
    task definition, every saved plan and every deploy log would carry it.
    """
    for root in APPLICATION_ROOTS:
        source = read(root)
        environment = assignment_body(source, "task_environment")
        secrets = assignment_body(source, "task_secrets")
        assert "GITHUB_TOKEN" not in environment, f"{root.parent.name} exposes the token"
        assert "GITHUB_TOKEN" in secrets, f"{root.parent.name} never delivers the token"
        assert "application_secret_arn" in secrets

    compute = read(ROOT / "modules" / "compute" / "main.tf")
    assert "valueFrom = value_from" in compute
    assert compute.count("secrets     = local.secrets") == 2, "api and worker both need it"
    # The execution role, not the task role, resolves `secrets`, and the application
    # secret is encrypted with the customer key -- so it needs its own decrypt grant.
    assert 'Action   = ["kms:Decrypt"]' in compute


def test_async_ai_identity_and_audit_resources_enforce_safety_controls() -> None:
    async_workflow = read(ROOT / "modules" / "async-workflow" / "main.tf")
    ai_search = read(ROOT / "modules" / "ai-search" / "main.tf")
    identity = read(ROOT / "modules" / "identity" / "main.tf")
    observability = read(ROOT / "modules" / "observability" / "main.tf")

    assert "redrive_policy" in async_workflow
    assert "deadLetterTargetArn" in async_workflow
    assert "message_retention_seconds         = 1209600" in async_workflow
    assert "aws_bedrock_guardrail" in ai_search
    assert "aws_opensearchserverless" not in ai_search
    assert "aws_bedrockagent_knowledge_base" not in ai_search
    assert "minimum_length                   = 14" in identity
    assert "prevent_user_existence_errors" in identity
    assert '"ses:FromAddress"' in identity
    assert '"cloudwatch:PutMetricData"' in identity
    assert "enable_log_file_validation    = true" in observability
    assert "is_multi_region_trail         = true" in observability
    assert "block_public_policy     = true" in observability
    assert "aws_budgets_budget" in observability
