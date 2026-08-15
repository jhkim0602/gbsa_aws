from __future__ import annotations

import io
from collections.abc import Mapping
from uuid import UUID

from interview_evidence.shared.aws_clients.production import (
    AwsBedrockModel,
    AwsCognitoPrincipalProvider,
    AwsMediaConvert,
    AwsPollyTextToSpeech,
    AwsS3ObjectStorage,
    AwsSesEmailSender,
    AwsSqsQueue,
    AwsTextract,
    AwsTranscribeSpeechToText,
)
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
    )
    assert isinstance(message_id, UUID)
    assert ses.calls[0][1]["Destination"] == {"ToAddresses": ["applicant@example.com"]}


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
