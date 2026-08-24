from __future__ import annotations

import io
import json
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from uuid import UUID

import pytest
from interview_evidence.shared.aws_clients.ports import (
    CachingTextEmbedder,
    StaticTextEmbedder,
)
from interview_evidence.shared.aws_clients.production import (
    AwsBedrockModel,
    AwsCognitoPrincipalProvider,
    AwsMediaConvert,
    AwsPollyTextToSpeech,
    AwsS3ObjectStorage,
    AwsSesEmailSender,
    AwsSqsQueue,
    AwsTextract,
    AwsTitanTextEmbedder,
    AwsTranscribeSpeechToText,
)
from interview_evidence.shared.email_templates import RenderedEmail
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
ACTOR_ID = UUID("00000000-0000-7000-8000-000000000002")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=ACTOR_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000003"),
        trace_id="aws-adapter-test",
    )


class RecordingClient:
    def __init__(self, responses: Mapping[str, object] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.responses = dict(responses or {})

    def __getattr__(self, name: str):
        def call(*args: object, **kwargs: object) -> object:
            if args:
                kwargs = {"ClientMethod": args[0], **kwargs}
            self.calls.append((name, kwargs))
            return self.responses.get(name, {})

        return call


class MissingObjectError(Exception):
    def __init__(self) -> None:
        self.response = {"Error": {"Code": "404"}}


class DeletionS3Client(RecordingClient):
    def __init__(self, *, remains: bool) -> None:
        super().__init__()
        self.remains = remains

    def head_object(self, **kwargs: object) -> Mapping[str, object]:
        self.calls.append(("head_object", kwargs))
        if self.remains:
            return {"ContentLength": 1}
        raise MissingObjectError


def test_s3_sqs_and_ses_adapters_preserve_tenant_scope_without_logging_content() -> None:
    s3 = RecordingClient({"generate_presigned_url": "https://s3.invalid/upload"})
    storage = AwsS3ObjectStorage(
        s3,
        bucket="source-bucket",
        kms_key_id="kms-key",
    )
    intent = storage.create_upload_intent(
        _context(),
        "submission-original/applicant",
        12,
        "a" * 64,
    )
    assert intent.object_key.startswith(f"tenants/{COMPANY_ID}/")
    assert intent.url == "https://s3.invalid/upload"
    assert intent.required_headers["x-amz-checksum-sha256"] != "a" * 64

    sqs = RecordingClient()
    AwsSqsQueue(sqs, queue_url="https://sqs.invalid/analysis").publish(
        _context(),
        "submission.analysis_requested",
        {"submission_id": str(ACTOR_ID)},
    )
    assert sqs.calls[0][0] == "send_message"
    assert str(COMPANY_ID) in str(sqs.calls[0][1]["MessageBody"])

    ses = RecordingClient({"send_email": {"MessageId": "ses-message-1"}})
    message_id = AwsSesEmailSender(
        ses,
        from_address="noreply@example.com",
    ).send_template(
        _context(),
        "applicant-invitation-v1",
        ACTOR_ID,
        "applicant@example.com",
        {"invitation_url": "https://applicant.invalid/access"},
        RenderedEmail(
            subject="[회사] 온라인 면접 안내",
            html_body="<p>초대 본문</p>",
            text_body="초대 본문",
        ),
    )
    assert isinstance(message_id, UUID)
    assert ses.calls[0][1]["Destination"] == {"ToAddresses": ["applicant@example.com"]}
    # The rendered template is what SES delivers, not an adapter-local body.
    content = ses.calls[0][1]["Content"]
    assert isinstance(content, Mapping)
    simple = content["Simple"]
    assert isinstance(simple, Mapping)
    assert simple["Subject"]["Data"] == "[회사] 온라인 면접 안내"
    assert simple["Body"]["Html"]["Data"] == "<p>초대 본문</p>"
    assert simple["Body"]["Text"]["Data"] == "초대 본문"


def test_s3_deletion_is_verified_with_a_follow_up_head_request() -> None:
    object_key = f"tenants/{COMPANY_ID}/submission-original/object-1"
    absent_client = DeletionS3Client(remains=False)
    absent_storage = AwsS3ObjectStorage(
        absent_client,
        bucket="source-bucket",
        kms_key_id="kms-key",
    )
    assert absent_storage.delete_and_verify_object(_context(), object_key) is True
    assert [call[0] for call in absent_client.calls] == [
        "delete_object",
        "head_object",
    ]

    remaining_storage = AwsS3ObjectStorage(
        DeletionS3Client(remains=True),
        bucket="source-bucket",
        kms_key_id="kms-key",
    )
    assert remaining_storage.delete_and_verify_object(_context(), object_key) is False

    media_storage = AwsS3ObjectStorage(
        DeletionS3Client(remains=False),
        bucket="media-bucket",
        kms_key_id="kms-key",
    )
    assert (
        media_storage.delete_and_verify_object(
            _context(),
            f"companies/{COMPANY_ID}/sessions/session-1/recording/final/v1/manifest.m3u8",
        )
        is True
    )

    with pytest.raises(PermissionError, match="tenant"):
        absent_storage.delete_and_verify_object(
            _context(),
            "tenants/00000000-0000-7000-8000-000000000099/object-1",
        )


def test_playback_url_is_signed_for_the_requested_object_only() -> None:
    s3 = RecordingClient({"generate_presigned_url": "https://s3.invalid/playback?sig=x"})
    storage = AwsS3ObjectStorage(s3, bucket="media-bucket", kms_key_id="kms-key")
    object_key = f"tenants/{COMPANY_ID}/interviews/session-1/recording.webm"

    url = storage.create_playback_url(
        _context(),
        object_key=object_key,
        expires_in_seconds=300,
    )

    assert url == "https://s3.invalid/playback?sig=x"
    method, params = s3.calls[0]
    assert method == "generate_presigned_url"
    assert params["ClientMethod"] == "get_object"
    assert params["Params"] == {"Bucket": "media-bucket", "Key": object_key}
    assert params["ExpiresIn"] == 300


def test_playback_url_refuses_a_key_from_another_tenant() -> None:
    """The asset row is already tenant-scoped, but a signature is bearer authority: once
    it exists the bucket honours it regardless of which company asked."""
    s3 = RecordingClient({"generate_presigned_url": "https://s3.invalid/playback"})
    storage = AwsS3ObjectStorage(s3, bucket="media-bucket", kms_key_id="kms-key")

    with pytest.raises(PermissionError, match="tenant"):
        storage.create_playback_url(
            _context(),
            object_key="tenants/00000000-0000-7000-8000-000000000099/interviews/s/r.webm",
            expires_in_seconds=300,
        )

    assert s3.calls == []


def test_sqs_long_poll_delivery_can_be_acknowledged_or_retried() -> None:
    event_id = UUID("00000000-0000-7000-8000-000000000010")
    aggregate_id = UUID("00000000-0000-7000-8000-000000000011")
    body = json.dumps(
        {
            "company_id": str(COMPANY_ID),
            "event_type": "submission.analysis_requested",
            "trace_id": "aws-adapter-test",
            "payload": {
                "event_id": str(event_id),
                "event_version": 1,
                "idempotency_key": "analysis-request-0001",
                "occurred_at": "2026-08-15T09:00:00+00:00",
                "aggregate_type": "submission",
                "aggregate_id": str(aggregate_id),
                "aggregate_version": 1,
                "payload": {"submission_id": str(aggregate_id)},
            },
        }
    )
    client = RecordingClient(
        {"receive_message": {"Messages": [{"ReceiptHandle": "receipt-1", "Body": body}]}}
    )
    queue = AwsSqsQueue(
        client,
        queue_url="https://sqs.invalid/analysis",
        wait_time_seconds=1,
    )

    delivery = queue.receive(max_messages=1)[0]
    assert delivery.event_id == event_id
    assert delivery.aggregate_id == aggregate_id
    queue.retry(delivery.receipt_handle, delay_seconds=15)
    queue.extend_visibility(delivery.receipt_handle, 300)
    queue.acknowledge(delivery.receipt_handle)
    assert [call[0] for call in client.calls] == [
        "receive_message",
        "change_message_visibility",
        "change_message_visibility",
        "delete_message",
    ]
    assert client.calls[0][1]["WaitTimeSeconds"] == 1
    assert client.calls[0][1]["AttributeNames"] == ["ApproximateReceiveCount"]
    assert "VisibilityTimeout" not in client.calls[0][1]
    assert client.calls[1][1]["VisibilityTimeout"] == 15
    assert client.calls[2][1]["VisibilityTimeout"] == 300


def test_sqs_readiness_and_depth_use_queue_attributes() -> None:
    client = RecordingClient(
        {
            "get_queue_attributes": {
                "Attributes": {
                    "ApproximateNumberOfMessages": "7",
                    "ApproximateNumberOfMessagesNotVisible": "2",
                }
            }
        }
    )
    queue = AwsSqsQueue(client, queue_url="https://sqs.invalid/analysis")

    queue.healthcheck()

    assert queue.approximate_depth() == 9
    assert [call[0] for call in client.calls] == [
        "get_queue_attributes",
        "get_queue_attributes",
    ]


def test_cognito_bedrock_and_polly_adapters_translate_aws_responses() -> None:
    cognito = RecordingClient(
        {
            "get_user": {
                "Username": "subject-1",
                "UserAttributes": [
                    {"Name": "sub", "Value": "subject-1"},
                    {"Name": "custom:company_id", "Value": str(COMPANY_ID)},
                    {"Name": "custom:company_user_id", "Value": str(ACTOR_ID)},
                ],
            }
        }
    )
    principal = AwsCognitoPrincipalProvider(cognito).get_company_principal("token")
    assert principal.company_id == COMPANY_ID
    assert principal.company_user_id == ACTOR_ID

    bedrock = RecordingClient(
        {"invoke_model": {"body": io.BytesIO(b'{"question":"Explain the decision."}')}}
    )
    generated = AwsBedrockModel(
        bedrock,
        model_id="model-1",
    ).generate(_context(), {"criterion_id": "criterion-1"})
    assert generated["question"] == "Explain the decision."

    polly = RecordingClient({"synthesize_speech": {"AudioStream": io.BytesIO(b"audio")}})
    s3 = RecordingClient({"generate_presigned_url": "https://s3.invalid/audio"})
    speech = AwsPollyTextToSpeech(
        polly,
        s3,
        bucket="media-bucket",
        kms_key_id="kms-key",
    ).synthesize(_context(), "Next question", voice_id="Seoyeon")
    assert speech["audio_url"] == "https://s3.invalid/audio"
    assert any(call[0] == "put_object" for call in s3.calls)


def test_cognito_self_signup_principal_gets_stable_tenant_ids() -> None:
    cognito = RecordingClient(
        {
            "get_user": {
                "Username": "self-signup-subject",
                "UserAttributes": [
                    {"Name": "sub", "Value": "self-signup-subject"},
                    {"Name": "email", "Value": "recruiter@example.com"},
                ],
            }
        }
    )
    provider = AwsCognitoPrincipalProvider(cognito)

    first = provider.get_company_principal("token")
    second = provider.get_company_principal("token")

    assert first.company_id == second.company_id
    assert first.company_user_id == second.company_user_id
    assert first.company_id != first.company_user_id
    assert first.email == "recruiter@example.com"


def test_bedrock_tenant_scope_does_not_break_the_anthropic_schema() -> None:
    """A Messages body rejects unknown top-level fields, so the tenant goes in metadata."""
    bedrock = RecordingClient({"invoke_model": {"body": io.BytesIO(b'{"content":[]}')}})

    AwsBedrockModel(bedrock, model_id="model-1").generate(
        _context(),
        {
            "anthropic_version": "bedrock-2023-05-31",
            "system": "면접관입니다.",
            "max_tokens": 512,
            "messages": [{"role": "user", "content": "{}"}],
        },
    )

    body = json.loads(str(bedrock.calls[0][1]["body"], "utf-8"))
    assert "tenant_scope" not in body
    assert body["metadata"] == {"user_id": str(COMPANY_ID)}
    assert set(body) == {
        "anthropic_version",
        "system",
        "max_tokens",
        "messages",
        "metadata",
    }


def test_bedrock_keeps_tenant_scope_for_non_message_model_families() -> None:
    bedrock = RecordingClient({"invoke_model": {"body": io.BytesIO(b'{"ok":true}')}})

    AwsBedrockModel(bedrock, model_id="model-1").generate(
        _context(),
        {"task": "strategy", "criterion_ids": []},
    )

    body = json.loads(str(bedrock.calls[0][1]["body"], "utf-8"))
    assert body["tenant_scope"] == {"company_id": str(COMPANY_ID)}


def test_titan_embedder_returns_normalized_vector_without_exposing_text() -> None:
    bedrock = RecordingClient(
        {
            "invoke_model": {
                "body": io.BytesIO(json.dumps({"embedding": [0.5] * 256}).encode("utf-8"))
            }
        }
    )
    embedder = AwsTitanTextEmbedder(bedrock, model_id="amazon.titan-embed-text-v2:0")

    vector = embedder.embed(_context(), "ECS 장애 복구 경험", dimensions=256)

    assert vector == (0.5,) * 256
    request = bedrock.calls[0][1]
    assert request["modelId"] == "amazon.titan-embed-text-v2:0"
    assert json.loads(request["body"]) == {
        "inputText": "ECS 장애 복구 경험",
        "dimensions": 256,
        "normalize": True,
    }


def test_embedding_cache_deduplicates_normalized_provider_requests() -> None:
    delegate = StaticTextEmbedder((1.0,) * 1024)
    embedder = CachingTextEmbedder(delegate, max_entries=2)

    first = embedder.embed(_context(), "  같은 코드 조각  ")
    second = embedder.embed(_context(), "같은 코드 조각")

    assert first == second
    assert len(delegate.calls) == 1
    assert embedder.embedding_version == delegate.embedding_version


def test_embedding_cache_batches_only_uncached_texts() -> None:
    delegate = StaticTextEmbedder((1.0,) * 1024)
    embedder = CachingTextEmbedder(delegate, max_entries=3)

    embedder.embed(_context(), "이미 캐시된 문단")
    vectors = embedder.embed_many(
        _context(),
        ("이미 캐시된 문단", "새 문단", "새 문단"),
    )

    assert len(vectors) == 3
    assert len(delegate.calls) == 2


def test_embedding_cache_single_flights_concurrent_provider_requests() -> None:
    class ConcurrentDelegate:
        model_id = "concurrent-embedding"
        embedding_version = "concurrent-v1"

        def __init__(self) -> None:
            self.entered = Barrier(2)
            self.release = Barrier(2)
            self.call_lock = Lock()
            self.call_count = 0

        def embed(
            self,
            context: TenantContext,
            text: str,
            *,
            dimensions: int = 1024,
        ) -> tuple[float, ...]:
            with self.call_lock:
                self.call_count += 1
            self.entered.wait(timeout=2)
            self.release.wait(timeout=2)
            return (1.0,) * dimensions

    delegate = ConcurrentDelegate()
    embedder = CachingTextEmbedder(delegate, max_entries=2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(embedder.embed, _context(), "같은 질문")
        delegate.entered.wait(timeout=2)
        second = executor.submit(embedder.embed, _context(), " 같은 질문 ")
        delegate.release.wait(timeout=2)

    assert first.result() == second.result()
    assert delegate.call_count == 1


def test_titan_rejects_oversized_input_before_provider_call() -> None:
    bedrock = RecordingClient()
    embedder = AwsTitanTextEmbedder(bedrock)

    with pytest.raises(ValueError, match="exceeds 50000"):
        embedder.embed(_context(), "x" * 50_001)

    assert bedrock.calls == []


def test_textract_transcribe_and_media_convert_adapters_return_sanitized_results() -> None:
    textract = RecordingClient(
        {
            "analyze_document": {
                "Blocks": [
                    {"BlockType": "LINE", "Page": 2, "Text": "second"},
                    {"BlockType": "LINE", "Page": 1, "Text": "first"},
                ]
            }
        }
    )
    pages = AwsTextract(
        textract,
        bucket="source-bucket",
        object_key=lambda context, object_id: f"tenants/{context.company_id}/source/{object_id}",
    ).extract_pages(_context(), ACTOR_ID)
    assert [page.page_number for page in pages] == [1, 2]

    s3 = RecordingClient()
    transcribe = RecordingClient(
        {
            "start_transcription_job": {},
            "get_transcription_job": {
                "TranscriptionJob": {
                    "TranscriptionJobStatus": "COMPLETED",
                    "Transcript": {"TranscriptFileUri": "https://transcript.invalid/job"},
                }
            },
        }
    )
    result = AwsTranscribeSpeechToText(
        transcribe,
        s3,
        bucket="media-bucket",
        transcript_loader=lambda _uri: {
            "results": {
                "transcripts": [{"transcript": "final answer"}],
                "items": [{"alternatives": [{"confidence": "0.91"}]}],
            }
        },
        sleep=lambda _seconds: None,
    ).transcribe(_context(), b"audio", sample_rate_hz=16000)
    assert result == {"text": "final answer", "confidence": 0.91}

    media_convert = RecordingClient({"create_job": {"Job": {"Id": "job-1"}}})
    job_id = AwsMediaConvert(
        media_convert,
        role_arn="arn:aws:iam::123456789012:role/media",
        output_bucket="media-bucket",
    ).create_hls_job(
        _context(),
        input_key="input/session.webm",
        output_prefix="output/session",
    )
    assert job_id == "job-1"
    assert str(COMPANY_ID) in str(media_convert.calls[0][1])
