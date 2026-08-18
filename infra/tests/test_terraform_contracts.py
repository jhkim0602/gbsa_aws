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


def test_the_api_cache_policy_names_no_cache_key_parameters() -> None:
    """A zero-TTL CloudFront cache policy accepts no cache-key parameters.

    All three TTLs at zero means caching disabled, and CloudFront then rejects
    CreateCachePolicy for any named header, cookie, query string or accept-encoding flag:
    with nothing stored there is no key to vary. The rejection happens at apply, after the
    load balancer and its listener are already up.

    The tempting version of this resource whitelists `Authorization` and reads as the careful
    choice. It is inert -- what reaches the origin is the origin request policy's `allViewer`,
    asserted above -- so the two must not drift back together.
    """
    edge = read(ROOT / "modules" / "edge" / "main.tf")

    policy = edge.split('resource "aws_cloudfront_cache_policy" "api"')[1]
    policy = policy.split("resource ")[0]
    assert 'cookie_behavior = "none"' in policy
    assert 'header_behavior = "none"' in policy
    assert 'query_string_behavior = "none"' in policy
    assert "headers {" not in policy
    assert "enable_accept_encoding_brotli = false" in policy
    assert "enable_accept_encoding_gzip   = false" in policy


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
    # The customer key still encrypts the buckets holding applicant material. This read
    # `sse_algorithm     = "aws:kms"` until the algorithm became conditional per bucket --
    # see `test_the_spa_origins_are_not_encrypted_with_the_customer_key` for why.
    assert 'contains(local.spa_bucket_names, each.key) ? "AES256" : "aws:kms"' in data
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


def test_the_spa_origins_are_not_encrypted_with_the_customer_key() -> None:
    """CloudFront holds no grant on the customer key, so it cannot read what that key sealed.

    Every bucket in this module shared one `aws_kms_key`, which made the deployed SPAs answer
    `403 AccessDenied` from `server: AmazonS3` for `/index.html` -- while a key that did not
    exist still returned 404 and `/v1/*` still reached the API. Nothing failed on the way
    there: terraform applied, both bundles published, nine of ten deploy jobs were green.

    The fix has to stay on the SPA side. Granting `cloudfront.amazonaws.com` decrypt on that
    key is the other way to make a public JavaScript bundle readable, and the same key
    encrypts Aurora, the media bucket holding interview recordings and the audit trail.
    """
    data = read(ROOT / "modules" / "data" / "main.tf")

    assert 'spa_bucket_names = toset(["company-spa", "applicant-spa"])' in data
    rule = data.split('resource "aws_s3_bucket_server_side_encryption_configuration"')[1]
    rule = rule.split("\nresource ")[0]
    # Conditional on the bucket, not a blanket setting either way: the applicant material
    # buckets must keep the customer key, and SSE-S3 everywhere would be the opposite defect.
    assert "contains(local.spa_bucket_names, each.key) ? null : aws_kms_key.data.arn" in rule
    assert 'contains(local.spa_bucket_names, each.key) ? "AES256" : "aws:kms"' in rule
    # S3 rejects a bucket key on an SSE-S3 rule, which would fail the apply.
    assert "bucket_key_enabled = !contains(local.spa_bucket_names, each.key)" in rule

    # And the existing objects have to be rewritten, because an object keeps the encryption it
    # was written with: the buckets are full of objects sealed under the customer key, and
    # changing the bucket's encryption does not re-encrypt one of them. `sync` skips a
    # same-sized source that is not newer and `index.html` keeps its name, so an unconditional
    # `cp --recursive` has to precede it. `--exact-timestamps` looks like the fix and is not --
    # the CLI applies it only when syncing S3 to local, so it was inert on an upload.
    workflow = read(ROOT.parent / ".github" / "workflows" / "deploy.yml")
    publish = workflow.split("Publish private SPA origins")[1].split("\n      - name:")[0]
    # Comments dropped before matching: they name these flags while saying nothing about
    # whether the commands pass them, and a match against the raw step body passed on the
    # comment alone.
    script = "\n".join(
        line.strip() for line in publish.splitlines() if not line.lstrip().startswith("#")
    )
    for dist, bucket in (
        ("apps/company-console/dist", "$COMPANY_SPA_BUCKET"),
        ("apps/applicant-interview/dist", "$APPLICANT_SPA_BUCKET"),
    ):
        copy = f'aws s3 cp {dist} "s3://{bucket}" --recursive'
        sync = f'aws s3 sync {dist} "s3://{bucket}" --delete'
        assert copy in script, copy
        assert sync in script, sync
        # The copy first, so nothing is deleted before it has been replaced.
        assert script.index(copy) < script.index(sync)
    assert "--exact-timestamps" not in script


def test_the_deploy_role_trusts_the_numeric_repository_subject() -> None:
    """GitHub signs OIDC subjects naming the repository by numeric id, and it cannot decline.

    `repo:owner/name:environment:dev-plan` is the documented form and the only one this
    trust policy listed. The deploy run failed with `Not authorized to perform
    sts:AssumeRoleWithWebIdentity` and nothing more: the subject AWS rejected is in no
    workflow log, and the repository reported `use_default: true` -- so the configuration
    looked correct from both sides. It took a CloudTrail lookup to read
    `userIdentity.userName` and see `repo:jhkim0602@104820436/gbsa_aws@1337672097`.

    Pinned because deleting the numeric entry is a one-line tidy that reads like removing a
    duplicate, and the whole pipeline stops the next time a job assumes the role.
    """
    bootstrap = read(ROOT / "environments" / "bootstrap" / "main.tf")
    tfvars = read(ROOT / "environments" / "bootstrap" / "terraform.tfvars")

    trust = bootstrap.split('data "aws_iam_policy_document" "deploy_trust"')[1]
    trust = trust.split("\nresource ")[0]
    # Both spellings, built from one list so a new environment cannot be trusted under one
    # form and not the other -- which would fail only for whichever form GitHub signs next.
    assert "var.github_immutable_repository" in trust
    assert "compact([var.github_repository, var.github_immutable_repository])" in trust
    assert "repo:${repository}:environment:${name}" in trust
    assert "repo:${var.github_repository}:environment:" not in trust
    # The variable defaults to null, so the value is what actually reaches the policy.
    assert re.search(
        r"^github_immutable_repository\s*=\s*\"[^/\"]+@[0-9]+/[^/\"]+@[0-9]+\"",
        tfvars,
        re.MULTILINE,
    )


def test_the_prompt_attack_filter_scores_input_only() -> None:
    """Bedrock refuses any response strength but NONE for PROMPT_ATTACK.

    A symmetrical `HIGH`/`HIGH` block reads like the strictest possible setting and passes
    plan, validate and every check in this file. It fails at apply, with a
    ValidationException naming a field rather than the resource -- and it failed there after
    Aurora had already taken ten minutes to come up, which is the expensive place to find out.

    Pinned as a contract because the mistake is invisible: `HATE` beside it is legitimately
    bidirectional, so the two lines differ for a reason that is not apparent from the shape.
    """
    ai_search = read(ROOT / "modules" / "ai-search" / "main.tf")

    prompt_attack = ai_search.split('type            = "PROMPT_ATTACK"')[0]
    block = prompt_attack.rsplit("filters_config {", 1)[1]
    assert 'output_strength = "NONE"' in block
    # Input is still scored: the applicant's answer becomes a prompt, and NONE on both sides
    # would satisfy the assertion above while filtering nothing at all.
    assert 'input_strength  = "HIGH"' in block
