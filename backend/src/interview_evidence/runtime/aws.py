from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, cast

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from sqlalchemy import URL

from interview_evidence.capacity_management.scaling import ApplicationAutoScalingClient
from interview_evidence.interview_engine.adapters.recent_context import (
    DynamoClient,
    DynamoRecentContext,
    RecentContextPort,
)
from interview_evidence.runtime.generative_ai import create_generative_ai_dependencies
from interview_evidence.runtime.queue_topology import (
    WORKFLOW_QUEUE_NAMES,
    queue_visibility_timeout_seconds,
)
from interview_evidence.shared.aws_clients.ports import (
    AIModel,
    CachingTextEmbedder,
    ConsumableQueue,
    EmailSender,
    ObjectStorage,
    SpeechToText,
    TextEmbedder,
    TextToSpeech,
)
from interview_evidence.shared.aws_clients.production import (
    AwsCognitoPrincipalProvider,
    AwsMediaConvert,
    AwsPollyTextToSpeech,
    AwsS3ObjectStorage,
    AwsSesEmailSender,
    AwsSqsQueue,
    AwsTranscribeSpeechToText,
    CognitoClient,
    MediaConvertClient,
    PollyClient,
    S3Client,
    SesClient,
    SqsClient,
    TranscribeClient,
)
from interview_evidence.shared.operations import (
    CloudWatchClient,
    CloudWatchMetricRecorder,
    MetricRecorder,
    NullMetricRecorder,
)
from interview_evidence.shared.security.principals import PrincipalProvider
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.adapters.opensearch import (
    AwsOpenSearchIndex,
)
from interview_evidence.submission_analysis.adapters.search import SearchIndex


class SecretsManagerClient(Protocol):
    def get_secret_value(self, *, SecretId: str) -> Mapping[str, object]: ...


ClientFactory = Callable[[str], object]


class MediaConvertPort(Protocol):
    def create_hls_job(
        self,
        context: TenantContext,
        *,
        input_key: str,
        output_prefix: str,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class AwsRuntimeDependencies:
    database_url: str
    principal_provider: PrincipalProvider
    object_storage: ObjectStorage
    media_storage: ObjectStorage
    email_sender: EmailSender
    recent_context: RecentContextPort
    search_index: SearchIndex | None
    queues: Mapping[str, ConsumableQueue]
    model: AIModel
    embedder: TextEmbedder
    speech_to_text: SpeechToText
    text_to_speech: TextToSpeech
    media_convert: MediaConvertPort
    metrics: MetricRecorder
    application_auto_scaling: ApplicationAutoScalingClient


def create_aws_runtime_dependencies(
    environment: Mapping[str, str],
    *,
    client_factory: ClientFactory | None = None,
) -> AwsRuntimeDependencies:
    region = _required(environment, "AWS_REGION")
    factory = client_factory or _client_factory(environment)
    s3 = cast(S3Client, factory("s3"))
    presign_s3 = (
        cast(
            S3Client,
            _boto_client(
                "s3",
                region=region,
                endpoint_url=environment["S3_PUBLIC_ENDPOINT_URL"],
            ),
        )
        if environment.get("S3_PUBLIC_ENDPOINT_URL")
        else s3
    )
    source_bucket = _required(environment, "SOURCE_BUCKET")
    media_bucket = _required(environment, "MEDIA_BUCKET")
    kms_key_id = _required(environment, "KMS_KEY_ARN")
    database_url = _database_url(
        environment,
        cast(SecretsManagerClient, factory("secretsmanager")),
    )
    sqs_wait_time_seconds = int(environment.get("SQS_WAIT_TIME_SECONDS", "2"))
    queues = {
        name: AwsSqsQueue(
            cast(SqsClient, factory("sqs")),
            queue_url=_required(environment, f"SQS_{name.upper()}_QUEUE_URL"),
            wait_time_seconds=sqs_wait_time_seconds,
            visibility_timeout_seconds=queue_visibility_timeout_seconds(name, environment),
        )
        for name in WORKFLOW_QUEUE_NAMES
    }
    principal_provider = AwsCognitoPrincipalProvider(cast(CognitoClient, factory("cognito-idp")))
    object_storage = AwsS3ObjectStorage(
        s3,
        bucket=source_bucket,
        kms_key_id=kms_key_id,
        presign_client=presign_s3,
    )
    media_storage = AwsS3ObjectStorage(
        s3,
        bucket=media_bucket,
        kms_key_id=kms_key_id,
        presign_client=presign_s3,
    )
    email_sender = AwsSesEmailSender(
        cast(SesClient, factory("sesv2")),
        from_address=_required(environment, "SES_FROM_ADDRESS"),
        configuration_set_name=environment.get("SES_CONFIGURATION_SET"),
    )
    recent_context = DynamoRecentContext(
        cast(DynamoClient, factory("dynamodb")),
        table_name=_required(environment, "DYNAMODB_TABLE_NAME"),
    )
    retrieval_backend = (
        environment.get(
            "RETRIEVAL_BACKEND",
            "aurora",
        )
        .strip()
        .casefold()
    )
    if retrieval_backend not in {"aurora", "opensearch"}:
        raise RuntimeError("RETRIEVAL_BACKEND must be aurora or opensearch")
    search_index = (
        AwsOpenSearchIndex(
            endpoint=_required(environment, "OPENSEARCH_ENDPOINT"),
            index_name=_required(environment, "OPENSEARCH_INDEX_NAME"),
            region=region,
            signer=(
                (lambda _method, _url, _body: {})
                if environment.get(
                    "OPENSEARCH_SIGN_REQUESTS",
                    "true",
                ).casefold()
                == "false"
                else None
            ),
        )
        if retrieval_backend == "opensearch"
        else None
    )
    generative_ai = create_generative_ai_dependencies(
        environment,
        aws_client_factory=factory,
    )
    embedder = CachingTextEmbedder(
        generative_ai.embedder,
        max_entries=int(environment.get("BEDROCK_EMBEDDING_CACHE_ENTRIES", "2048")),
    )
    speech_to_text = AwsTranscribeSpeechToText(
        cast(TranscribeClient, factory("transcribe")),
        s3,
        bucket=media_bucket,
    )
    text_to_speech = AwsPollyTextToSpeech(
        cast(PollyClient, factory("polly")),
        s3,
        bucket=media_bucket,
        kms_key_id=kms_key_id,
    )
    media_convert = AwsMediaConvert(
        cast(MediaConvertClient, factory("mediaconvert")),
        role_arn=_required(environment, "MEDIACONVERT_ROLE_ARN"),
        output_bucket=media_bucket,
    )
    metrics: MetricRecorder
    if environment.get("AWS_ENDPOINT_URL"):
        metrics = NullMetricRecorder()
    else:
        metrics = CloudWatchMetricRecorder(
            cast(CloudWatchClient, factory("cloudwatch")),
            namespace=environment.get(
                "METRIC_NAMESPACE",
                "InterviewEvidencePlatform",
            ),
        )
    return AwsRuntimeDependencies(
        database_url=database_url,
        principal_provider=principal_provider,
        object_storage=object_storage,
        media_storage=media_storage,
        email_sender=email_sender,
        recent_context=recent_context,
        search_index=search_index,
        queues=queues,
        model=generative_ai.model,
        embedder=embedder,
        speech_to_text=speech_to_text,
        text_to_speech=text_to_speech,
        media_convert=media_convert,
        metrics=metrics,
        application_auto_scaling=cast(
            ApplicationAutoScalingClient,
            factory("application-autoscaling"),
        ),
    )


def resolve_database_url(
    environment: Mapping[str, str],
    *,
    client_factory: ClientFactory | None = None,
) -> str:
    """The database URL a task would connect with, without building the whole runtime.

    For one-off tasks that need the database and nothing else -- the seed does -- so that the
    credential is read from Secrets Manager inside the container rather than passed in as a
    plaintext override, which `ecs run-task` records in the task description and in CloudTrail.

    An explicit `DATABASE_URL` short-circuits before any client is built, because compose sets
    one and has no Secrets Manager to reach: constructing the client first would make this
    fail locally on credentials it never needed to read.
    """
    explicit = environment.get("DATABASE_URL", "").strip()
    if explicit:
        return explicit
    factory = client_factory or _client_factory(environment)
    return _database_url(environment, cast(SecretsManagerClient, factory("secretsmanager")))


def _database_url(
    environment: Mapping[str, str],
    secrets: SecretsManagerClient,
) -> str:
    explicit = environment.get("DATABASE_URL", "").strip()
    if explicit:
        return explicit
    response = secrets.get_secret_value(SecretId=_required(environment, "AURORA_MASTER_SECRET_ARN"))
    secret_string = response.get("SecretString")
    if not isinstance(secret_string, str):
        raise RuntimeError("database secret string is unavailable")
    try:
        secret = json.loads(secret_string)
    except json.JSONDecodeError as error:
        raise RuntimeError("database secret is invalid") from error
    if not isinstance(secret, dict):
        raise RuntimeError("database secret is invalid")
    username = secret.get("username")
    password = secret.get("password")
    port = secret.get("port", 5432)
    if not isinstance(username, str) or not isinstance(password, str):
        raise RuntimeError("database secret is incomplete")
    if not isinstance(port, int | str):
        raise RuntimeError("database secret port is invalid")
    try:
        parsed_port = int(port)
    except ValueError as error:
        raise RuntimeError("database secret port is invalid") from error
    return URL.create(
        drivername="postgresql+psycopg",
        username=username,
        password=password,
        host=_required(environment, "AURORA_ENDPOINT"),
        port=parsed_port,
        database=_required(environment, "AURORA_DATABASE"),
    ).render_as_string(hide_password=False)


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"required production setting is missing: {name}")
    return value.strip()


def create_media_object_storage(environment: Mapping[str, str]) -> AwsS3ObjectStorage:
    """The media bucket adapter on its own, for a caller that only needs the recording.

    The local seed uploads the demo recording without building the rest of the runtime;
    routing it through here keeps the bucket and key settings in one place. No presign
    client: this writes objects, and the URLs a reviewer follows are signed by the API.
    """
    factory = _client_factory(environment)
    return AwsS3ObjectStorage(
        cast(S3Client, factory("s3")),
        bucket=_required(environment, "MEDIA_BUCKET"),
        kms_key_id=_required(environment, "KMS_KEY_ARN"),
    )


def _client_factory(environment: Mapping[str, str]) -> ClientFactory:
    region = _required(environment, "AWS_REGION")

    def create(service_name: str) -> object:
        service_key = service_name.upper().replace("-", "_")
        endpoint_url = environment.get(f"{service_key}_ENDPOINT_URL")
        if endpoint_url is None and service_name in {
            "cloudwatch",
            "s3",
            "secretsmanager",
            "sesv2",
            "sqs",
        }:
            endpoint_url = environment.get("AWS_ENDPOINT_URL")
        if service_name == "dynamodb":
            endpoint_url = environment.get("DYNAMODB_ENDPOINT_URL", endpoint_url)
        return _boto_client(
            service_name,
            region=region,
            endpoint_url=endpoint_url,
        )

    return create


def _boto_client(
    service_name: str,
    *,
    region: str,
    endpoint_url: str | None,
) -> object:
    config = Config(ignore_configured_endpoint_urls=endpoint_url is None)
    if service_name == "s3":
        config = config.merge(Config(s3={"addressing_style": "path"}))
    kwargs: dict[str, object] = {
        "region_name": region,
        "config": config,
    }
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client(service_name, **kwargs)
