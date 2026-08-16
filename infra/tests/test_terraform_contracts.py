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


def read(path: Path) -> str:
    assert path.is_file(), f"missing Terraform file: {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


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


def test_stage_and_prod_have_independent_state_and_production_protection() -> None:
    stage = read(ROOT / "environments" / "stage" / "main.tf")
    prod = read(ROOT / "environments" / "prod" / "main.tf")
    assert 'key          = "stage/terraform.tfstate"' in stage
    assert 'key          = "prod/terraform.tfstate"' in prod
    assert "deletion_protection = true" in prod
    assert "deletion_protection = false" in stage
    assert re.search(r"force_destroy\s*=\s*false", prod)
    assert re.search(r"nat_gateway_per_az\s*=\s*true", prod)
    assert re.search(r"enable_deletion_protection\s*=\s*true", prod)


def test_all_roots_pin_region_and_default_security_tags() -> None:
    roots = (
        ROOT / "environments" / "dev" / "foundation" / "main.tf",
        ROOT / "environments" / "dev" / "data-ai" / "main.tf",
        ROOT / "environments" / "dev" / "application" / "main.tf",
        ROOT / "environments" / "stage" / "main.tf",
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
        ROOT / "environments" / "stage" / "main.tf",
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
        ROOT / "environments" / "stage" / "main.tf",
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
