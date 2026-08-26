from __future__ import annotations

import json

import pytest
from botocore.config import Config
from interview_evidence.runtime import aws as aws_runtime
from interview_evidence.runtime.aws import create_aws_runtime_dependencies


class FakeClient:
    def __init__(self, service: str) -> None:
        self.service = service

    def get_secret_value(self, *, SecretId: str) -> dict[str, object]:
        assert SecretId == "secret-arn"
        return {
            "SecretString": json.dumps(
                {
                    "username": "platform",
                    "password": "p@ss word",
                    "port": 5432,
                }
            )
        }


def _environment() -> dict[str, str]:
    return {
        "AWS_REGION": "ap-northeast-2",
        "AURORA_ENDPOINT": "database.internal",
        "AURORA_DATABASE": "interview_evidence",
        "AURORA_MASTER_SECRET_ARN": "secret-arn",
        "SOURCE_BUCKET": "source-bucket",
        "MEDIA_BUCKET": "media-bucket",
        "KMS_KEY_ARN": "kms-key",
        "RETRIEVAL_BACKEND": "aurora",
        "BEDROCK_MODEL_ID": "model-id",
        "BEDROCK_GUARDRAIL_ID": "guardrail-id",
        "SES_FROM_ADDRESS": "noreply@example.com",
        "MEDIACONVERT_ROLE_ARN": "arn:aws:iam::123456789012:role/media",
        "SQS_ANALYSIS_QUEUE_URL": "https://sqs.invalid/analysis",
        "SQS_MEDIA_QUEUE_URL": "https://sqs.invalid/media",
        "SQS_REPORTING_QUEUE_URL": "https://sqs.invalid/reporting",
        "SQS_DELETION_QUEUE_URL": "https://sqs.invalid/deletion",
        "SQS_CAPACITY_QUEUE_URL": "https://sqs.invalid/capacity",
    }


def test_aws_runtime_factory_builds_all_production_dependencies() -> None:
    dependencies = create_aws_runtime_dependencies(
        _environment(),
        client_factory=lambda service: FakeClient(service),
    )
    assert dependencies.database_url.startswith("postgresql+psycopg://platform:")
    assert set(dependencies.queues) == {
        "analysis",
        "media",
        "reporting",
        "deletion",
        "capacity",
    }
    assert dependencies.application_auto_scaling is not None
    assert dependencies.object_storage is not None
    assert dependencies.media_storage is not None
    assert dependencies.search_index is None
    assert dependencies.embedder.model_id == "amazon.titan-embed-text-v2:0"


def test_aws_runtime_factory_keeps_explicit_opensearch_rollback_path() -> None:
    environment = _environment()
    environment.update(
        {
            "RETRIEVAL_BACKEND": "opensearch",
            "OPENSEARCH_ENDPOINT": "https://search.invalid",
            "OPENSEARCH_INDEX_NAME": "candidate-source-v1",
        }
    )

    dependencies = create_aws_runtime_dependencies(
        environment,
        client_factory=lambda service: FakeClient(service),
    )

    assert dependencies.search_index is not None


def test_aws_runtime_factory_fails_closed_when_configuration_is_missing() -> None:
    environment = _environment()
    environment.pop("SOURCE_BUCKET")
    with pytest.raises(
        RuntimeError,
        match="required production setting is missing: SOURCE_BUCKET",
    ):
        create_aws_runtime_dependencies(
            environment,
            client_factory=lambda service: FakeClient(service),
        )


def test_aws_client_factory_limits_global_local_endpoint_to_emulated_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, dict[str, object]] = {}

    def fake_boto_client(service_name: str, **kwargs: object) -> FakeClient:
        calls[service_name] = kwargs
        return FakeClient(service_name)

    monkeypatch.setattr(aws_runtime.boto3, "client", fake_boto_client)
    factory = aws_runtime._client_factory(
        {
            "AWS_REGION": "ap-northeast-2",
            "AWS_ENDPOINT_URL": "http://localhost:4566",
        }
    )

    factory("s3")
    factory("textract")

    assert calls["s3"]["endpoint_url"] == "http://localhost:4566"
    s3_config = calls["s3"]["config"]
    assert isinstance(s3_config, Config)
    assert s3_config.s3 == {"addressing_style": "path"}
    assert s3_config.ignore_configured_endpoint_urls is False

    assert "endpoint_url" not in calls["textract"]
    textract_config = calls["textract"]["config"]
    assert isinstance(textract_config, Config)
    assert textract_config.ignore_configured_endpoint_urls is True
