from __future__ import annotations

import base64
import io
import json
import math
import time
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, BinaryIO, Protocol, cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from interview_evidence.shared.aws_clients.ports import (
    AIModel,
    ConsumableQueue,
    EmailSender,
    ObjectStorage,
    QueueDelivery,
    SpeechToText,
    TextEmbedder,
    TextToSpeech,
    UploadIntent,
)
from interview_evidence.shared.email_templates import RenderedEmail
from interview_evidence.shared.messaging.outbox import _assert_safe_payload
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    CompanyPrincipal,
    PrincipalNotFoundError,
)
from interview_evidence.shared.tenant import TenantContext, require_tenant_context
from interview_evidence.workers.analysis.document_extract import TextractPage


class AwsAdapterError(RuntimeError):
    """Sanitized managed-service failure."""


class ResponseBody(Protocol):
    def read(self) -> bytes: ...


class S3Client(Protocol):
    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: Mapping[str, object],
        ExpiresIn: int,
    ) -> str: ...

    def put_object(self, **kwargs: object) -> Mapping[str, object]: ...

    def get_object(self, **kwargs: object) -> Mapping[str, object]: ...

    def delete_object(self, **kwargs: object) -> Mapping[str, object]: ...

    def head_object(self, **kwargs: object) -> Mapping[str, object]: ...

    def head_bucket(self, **kwargs: object) -> Mapping[str, object]: ...


class SqsClient(Protocol):
    def send_message(self, **kwargs: object) -> Mapping[str, object]: ...

    def receive_message(self, **kwargs: object) -> Mapping[str, object]: ...

    def delete_message(self, **kwargs: object) -> Mapping[str, object]: ...

    def change_message_visibility(self, **kwargs: object) -> Mapping[str, object]: ...

    def get_queue_attributes(self, **kwargs: object) -> Mapping[str, object]: ...


class SesClient(Protocol):
    def send_email(self, **kwargs: object) -> Mapping[str, object]: ...


class CognitoClient(Protocol):
    def get_user(self, *, AccessToken: str) -> Mapping[str, object]: ...


class BedrockClient(Protocol):
    def invoke_model(self, **kwargs: object) -> Mapping[str, object]: ...


class PollyClient(Protocol):
    def synthesize_speech(self, **kwargs: object) -> Mapping[str, object]: ...


class TextractClient(Protocol):
    def analyze_document(self, **kwargs: object) -> Mapping[str, object]: ...


class TranscribeClient(Protocol):
    def start_transcription_job(self, **kwargs: object) -> Mapping[str, object]: ...

    def get_transcription_job(self, **kwargs: object) -> Mapping[str, object]: ...


class MediaConvertClient(Protocol):
    def create_job(self, **kwargs: object) -> Mapping[str, object]: ...


class AwsS3ObjectStorage(ObjectStorage):
    def __init__(
        self,
        client: S3Client,
        *,
        bucket: str,
        kms_key_id: str,
        presign_client: S3Client | None = None,
        expires_in_seconds: int = 900,
    ) -> None:
        self._client = client
        self._presign_client = presign_client or client
        self._bucket = bucket
        self._kms_key_id = kms_key_id
        self._expires_in_seconds = expires_in_seconds

    def _assert_tenant_key(
        self,
        context: TenantContext,
        object_key: str,
    ) -> TenantContext:
        """Both prefixes are in use: chunks are written under `tenants/`, and the media
        pipeline's own outputs under `companies/`."""
        tenant = require_tenant_context(context)
        allowed_prefixes = (
            f"tenants/{tenant.company_id}/",
            f"companies/{tenant.company_id}/",
        )
        if not object_key.startswith(allowed_prefixes):
            raise PermissionError("object key is outside the tenant scope")
        return tenant

    def create_upload_intent(
        self,
        context: TenantContext,
        namespace: str,
        byte_size: int,
        sha256: str,
    ) -> UploadIntent:
        tenant = require_tenant_context(context)
        if byte_size < 0 or len(sha256) != 64:
            raise ValueError("invalid upload metadata")
        try:
            checksum = base64.b64encode(bytes.fromhex(sha256)).decode("ascii")
        except ValueError as error:
            raise ValueError("invalid upload checksum") from error
        object_id = uuid4()
        object_key = f"tenants/{tenant.company_id}/{namespace.strip('/')}/{object_id}"
        params: dict[str, object] = {
            "Bucket": self._bucket,
            "Key": object_key,
            "ChecksumSHA256": checksum,
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": self._kms_key_id,
            "Metadata": {"company-id": str(tenant.company_id)},
        }
        try:
            url = self._presign_client.generate_presigned_url(
                "put_object",
                Params=params,
                ExpiresIn=self._expires_in_seconds,
            )
        except Exception as error:
            raise AwsAdapterError("object upload intent unavailable") from error
        return UploadIntent(
            object_id=object_id,
            company_id=tenant.company_id,
            namespace=namespace,
            byte_size=byte_size,
            sha256=sha256,
            object_key=object_key,
            url=url,
            required_headers={
                "x-amz-checksum-sha256": checksum,
                "x-amz-server-side-encryption": "aws:kms",
                "x-amz-server-side-encryption-aws-kms-key-id": self._kms_key_id,
                "x-amz-meta-company-id": str(tenant.company_id),
            },
        )

    def read_object(self, context: TenantContext, object_key: str) -> bytes:
        self._assert_tenant_key(context, object_key)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            return cast(ResponseBody, response["Body"]).read()
        except Exception as error:
            raise AwsAdapterError("object read unavailable") from error

    def write_object(
        self,
        context: TenantContext,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
    ) -> None:
        tenant = self._assert_tenant_key(context, object_key)
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=object_key,
                Body=body,
                ContentType=content_type,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=self._kms_key_id,
                Metadata={"company-id": str(tenant.company_id)},
            )
        except Exception as error:
            raise AwsAdapterError("object write unavailable") from error

    def create_playback_url(
        self,
        context: TenantContext,
        *,
        object_key: str,
        expires_in_seconds: int,
    ) -> str:
        """A short-lived read of one recording object, for a reviewer's `<video src>`.

        Signed through the presign client rather than the internal one, because the
        browser resolves this host and the container's endpoint is not reachable from it.
        """
        self._assert_tenant_key(context, object_key)
        if expires_in_seconds < 1:
            raise ValueError("playback URL lifetime must be positive")
        try:
            return self._presign_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": object_key},
                ExpiresIn=expires_in_seconds,
            )
        except Exception as error:
            raise AwsAdapterError("recording playback unavailable") from error

    def verify_uploaded_object(
        self,
        context: TenantContext,
        *,
        object_key: str,
        expected_byte_size: int,
        expected_sha256: str,
    ) -> bool:
        """Whether the object the applicant PUT matches the intent that authorized it.

        The presigned URL already pins the checksum, so S3 rejects a body that does not
        match. This confirms the object arrived and is the size that was declared, which
        is what stops an empty or truncated chunk from being recorded as verified.
        """
        tenant = require_tenant_context(context)
        if not object_key.startswith(f"tenants/{tenant.company_id}/"):
            raise PermissionError("object key is outside the tenant scope")
        try:
            head = self._client.head_object(Bucket=self._bucket, Key=object_key)
        except Exception as error:
            if _aws_error_code(error) in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise AwsAdapterError("object verification unavailable") from error
        if int(cast(int, head.get("ContentLength", -1))) != expected_byte_size:
            return False
        checksum = head.get("ChecksumSHA256")
        if checksum is None:
            # Buckets that do not return the checksum still gave us existence and size,
            # which the presigned checksum condition has already had to satisfy.
            return True
        try:
            return base64.b64decode(str(checksum)).hex() == expected_sha256
        except ValueError:
            return False

    def delete_and_verify_object(
        self,
        context: TenantContext,
        object_key: str,
    ) -> bool:
        self._assert_tenant_key(context, object_key)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=object_key)
            self._client.head_object(Bucket=self._bucket, Key=object_key)
        except Exception as error:
            if _aws_error_code(error) in {"404", "NoSuchKey", "NotFound"}:
                return True
            raise AwsAdapterError("object deletion verification unavailable") from error
        return False

    def healthcheck(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception as error:
            raise AwsAdapterError("object storage unavailable") from error


class AwsSqsQueue(ConsumableQueue):
    def __init__(
        self,
        client: SqsClient,
        *,
        queue_url: str,
        wait_time_seconds: int = 2,
    ) -> None:
        if not 0 <= wait_time_seconds <= 20:
            raise ValueError("SQS wait time must be between 0 and 20 seconds")
        self._client = client
        self._queue_url = queue_url
        self._wait_time_seconds = wait_time_seconds

    def publish(
        self,
        context: TenantContext,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> None:
        tenant = require_tenant_context(context)
        _assert_safe_payload(payload)
        body = {
            "company_id": str(tenant.company_id),
            "event_type": event_type,
            "payload": dict(payload),
            "trace_id": tenant.trace_id,
        }
        try:
            self._client.send_message(
                QueueUrl=self._queue_url,
                MessageBody=json.dumps(
                    body,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
        except Exception as error:
            raise AwsAdapterError("queue publish unavailable") from error

    def receive(self, *, max_messages: int) -> tuple[QueueDelivery, ...]:
        try:
            response = self._client.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=max(1, min(max_messages, 10)),
                WaitTimeSeconds=self._wait_time_seconds,
                # Repository analysis and OCR can take several minutes. A one-minute lease made
                # an in-progress delivery visible again, so another worker repeated the same job.
                VisibilityTimeout=900,
            )
        except Exception as error:
            raise AwsAdapterError("queue receive unavailable") from error
        raw_messages = response.get("Messages", ())
        if not isinstance(raw_messages, list):
            return ()
        deliveries: list[QueueDelivery] = []
        for raw in raw_messages:
            if not isinstance(raw, Mapping):
                continue
            receipt_handle = raw.get("ReceiptHandle")
            body = raw.get("Body")
            if not isinstance(receipt_handle, str) or not isinstance(body, str):
                continue
            try:
                envelope = json.loads(body)
                event = envelope["payload"]
                payload = event["payload"]
                deliveries.append(
                    QueueDelivery(
                        receipt_handle=receipt_handle,
                        event_id=UUID(str(event["event_id"])),
                        event_version=int(event["event_version"]),
                        idempotency_key=str(event["idempotency_key"]),
                        company_id=UUID(str(envelope["company_id"])),
                        aggregate_type=str(event["aggregate_type"]),
                        aggregate_id=UUID(str(event["aggregate_id"])),
                        aggregate_version=int(event["aggregate_version"]),
                        event_type=str(envelope["event_type"]),
                        payload=dict(cast(Mapping[str, object], payload)),
                        trace_id=str(envelope["trace_id"]),
                        occurred_at=datetime.fromisoformat(str(event["occurred_at"])),
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise AwsAdapterError("queue message envelope is invalid") from error
        return tuple(deliveries)

    def acknowledge(self, receipt_handle: str) -> None:
        try:
            self._client.delete_message(
                QueueUrl=self._queue_url,
                ReceiptHandle=receipt_handle,
            )
        except Exception as error:
            raise AwsAdapterError("queue acknowledgement unavailable") from error

    def retry(self, receipt_handle: str) -> None:
        try:
            self._client.change_message_visibility(
                QueueUrl=self._queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=0,
            )
        except Exception as error:
            raise AwsAdapterError("queue retry unavailable") from error

    def healthcheck(self) -> None:
        self._attributes()

    def approximate_depth(self) -> int:
        attributes = self._attributes()
        try:
            visible = _queue_count(attributes.get("ApproximateNumberOfMessages", "0"))
            inflight = _queue_count(attributes.get("ApproximateNumberOfMessagesNotVisible", "0"))
        except (TypeError, ValueError) as error:
            raise AwsAdapterError("queue attributes are invalid") from error
        return visible + inflight

    def _attributes(self) -> Mapping[str, object]:
        try:
            response = self._client.get_queue_attributes(
                QueueUrl=self._queue_url,
                AttributeNames=[
                    "ApproximateNumberOfMessages",
                    "ApproximateNumberOfMessagesNotVisible",
                ],
            )
        except Exception as error:
            raise AwsAdapterError("queue attributes unavailable") from error
        attributes = response.get("Attributes")
        if not isinstance(attributes, Mapping):
            raise AwsAdapterError("queue attributes are invalid")
        return cast(Mapping[str, object], attributes)


class AwsSesEmailSender(EmailSender):
    def __init__(
        self,
        client: SesClient,
        *,
        from_address: str,
        configuration_set_name: str | None = None,
    ) -> None:
        self._client = client
        self._from_address = from_address
        self._configuration_set_name = configuration_set_name

    def send_template(
        self,
        context: TenantContext,
        template_id: str,
        recipient_ref: UUID,
        recipient_address: str,
        template_data: Mapping[str, Any],
        rendered: RenderedEmail,
    ) -> UUID:
        require_tenant_context(context)
        request: dict[str, object] = {
            "FromEmailAddress": self._from_address,
            "Destination": {"ToAddresses": [recipient_address]},
            "Content": {
                "Simple": {
                    "Subject": {
                        "Data": rendered.subject,
                        "Charset": "UTF-8",
                    },
                    "Body": {
                        "Html": {"Data": rendered.html_body, "Charset": "UTF-8"},
                        "Text": {"Data": rendered.text_body, "Charset": "UTF-8"},
                    },
                }
            },
            "EmailTags": [
                {"Name": "company", "Value": str(context.company_id)},
                {"Name": "recipient_ref", "Value": str(recipient_ref)},
                {"Name": "template", "Value": template_id},
            ],
        }
        if self._configuration_set_name is not None:
            request["ConfigurationSetName"] = self._configuration_set_name
        try:
            response = self._client.send_email(**request)
        except Exception as error:
            raise AwsAdapterError("email delivery unavailable") from error
        message_id = response.get("MessageId")
        if not isinstance(message_id, str) or not message_id:
            raise AwsAdapterError("email delivery returned no receipt")
        return uuid5(NAMESPACE_URL, message_id)


class AwsCognitoPrincipalProvider:
    def __init__(self, client: CognitoClient) -> None:
        self._client = client

    def get_company_principal(self, credential: str) -> CompanyPrincipal:
        try:
            response = self._client.get_user(AccessToken=credential)
            attributes = _cognito_attributes(response.get("UserAttributes"))
            subject = attributes.get("sub") or response.get("Username")
            if not isinstance(subject, str):
                raise KeyError("subject")
            return CompanyPrincipal(
                company_id=_cognito_principal_id(
                    attributes,
                    attribute="custom:company_id",
                    subject=subject,
                    kind="company",
                ),
                company_user_id=_cognito_principal_id(
                    attributes,
                    attribute="custom:company_user_id",
                    subject=subject,
                    kind="company-user",
                ),
                identity_subject=subject,
                email=attributes.get("email"),
            )
        except Exception as error:
            raise PrincipalNotFoundError("company principal not found") from error

    def get_applicant_principal(self, credential: str) -> ApplicantPrincipal:
        del credential
        raise PrincipalNotFoundError("applicant principal not found")


def _cognito_principal_id(
    attributes: Mapping[str, str],
    *,
    attribute: str,
    subject: str,
    kind: str,
) -> UUID:
    existing = attributes.get(attribute)
    if existing is not None:
        return UUID(existing)
    return uuid5(NAMESPACE_URL, f"interview-evidence:{kind}:{subject}")


def _tenant_scoped_body(
    body: dict[str, Any],
    *,
    company_id: UUID,
) -> dict[str, Any]:
    """Attach the calling tenant to a model request without breaking its schema.

    An Anthropic Messages body rejects unknown top-level fields, so the tenant goes
    in ``metadata.user_id``, which is the field the schema reserves for an opaque
    caller identifier. Bodies for other model families keep the previous
    ``tenant_scope`` key.
    """
    if "messages" in body:
        metadata = body.get("metadata")
        merged = dict(metadata) if isinstance(metadata, Mapping) else {}
        merged["user_id"] = str(company_id)
        return {**body, "metadata": merged}
    return {**body, "tenant_scope": {"company_id": str(company_id)}}


class AwsBedrockModel(AIModel):
    def __init__(
        self,
        client: BedrockClient,
        *,
        model_id: str,
        guardrail_id: str | None = None,
        guardrail_version: str = "DRAFT",
    ) -> None:
        self._client = client
        self._model_id = model_id
        self._guardrail_id = guardrail_id
        self._guardrail_version = guardrail_version

    def generate(
        self,
        context: TenantContext,
        model_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        tenant = require_tenant_context(context)
        request: dict[str, object] = {
            "modelId": self._model_id,
            "contentType": "application/json",
            "accept": "application/json",
            "body": json.dumps(
                _tenant_scoped_body(dict(model_input), company_id=tenant.company_id),
                ensure_ascii=False,
            ).encode("utf-8"),
        }
        if self._guardrail_id is not None:
            request.update(
                {
                    "guardrailIdentifier": self._guardrail_id,
                    "guardrailVersion": self._guardrail_version,
                }
            )
        try:
            response = self._client.invoke_model(**request)
            body = cast(ResponseBody, response["body"]).read()
            decoded = json.loads(body)
        except Exception as error:
            raise AwsAdapterError("model generation unavailable") from error
        if not isinstance(decoded, dict):
            raise AwsAdapterError("model response shape is invalid")
        return cast(dict[str, Any], decoded)


class AwsTitanTextEmbedder(TextEmbedder):
    def __init__(
        self,
        client: BedrockClient,
        *,
        model_id: str = "amazon.titan-embed-text-v2:0",
    ) -> None:
        self._client = client
        self.model_id = model_id

    def embed(
        self,
        context: TenantContext,
        text: str,
        *,
        dimensions: int = 1024,
    ) -> tuple[float, ...]:
        require_tenant_context(context)
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("embedding text must not be blank")
        if dimensions not in {256, 512, 1024}:
            raise ValueError("Titan embedding dimensions must be 256, 512, or 1024")
        request = {
            "modelId": self.model_id,
            "contentType": "application/json",
            "accept": "application/json",
            "body": json.dumps(
                {
                    "inputText": normalized_text,
                    "dimensions": dimensions,
                    "normalize": True,
                },
                ensure_ascii=False,
            ).encode("utf-8"),
        }
        try:
            response = self._client.invoke_model(**request)
            body = cast(ResponseBody, response["body"]).read()
            decoded = json.loads(body)
            raw_embedding = decoded["embedding"]
            vector = tuple(float(value) for value in raw_embedding)
        except Exception as error:
            raise AwsAdapterError("text embedding unavailable") from error
        if len(vector) != dimensions or not all(math.isfinite(value) for value in vector):
            raise AwsAdapterError("text embedding response is invalid")
        return vector


class AwsPollyTextToSpeech(TextToSpeech):
    def __init__(
        self,
        polly: PollyClient,
        s3: S3Client,
        *,
        bucket: str,
        kms_key_id: str,
        expires_in_seconds: int = 900,
    ) -> None:
        self._polly = polly
        self._s3 = s3
        self._bucket = bucket
        self._kms_key_id = kms_key_id
        self._expires_in_seconds = expires_in_seconds

    def synthesize(
        self,
        context: TenantContext,
        text: str,
        *,
        voice_id: str,
    ) -> Mapping[str, Any]:
        tenant = require_tenant_context(context)
        object_key = f"tenants/{tenant.company_id}/speech/{uuid4()}.mp3"
        try:
            response = self._polly.synthesize_speech(
                Text=text,
                OutputFormat="mp3",
                VoiceId=voice_id,
                Engine="neural",
            )
            audio_stream = cast(BinaryIO, response["AudioStream"])
            self._s3.put_object(
                Bucket=self._bucket,
                Key=object_key,
                Body=audio_stream.read(),
                ContentType="audio/mpeg",
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=self._kms_key_id,
                Metadata={"company-id": str(tenant.company_id)},
            )
            url = self._s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": object_key},
                ExpiresIn=self._expires_in_seconds,
            )
        except Exception as error:
            raise AwsAdapterError("speech synthesis unavailable") from error
        return {
            "audio_url": url,
            "audio_expires_at": (
                datetime.now(UTC) + timedelta(seconds=self._expires_in_seconds)
            ).isoformat(),
            "speech_marks_url": None,
        }


class AwsTextract:
    def __init__(
        self,
        client: TextractClient,
        *,
        bucket: str,
        object_key: Callable[[TenantContext, UUID], str],
    ) -> None:
        self._client = client
        self._bucket = bucket
        self._object_key = object_key

    def extract_pages(
        self,
        context: TenantContext,
        object_id: UUID,
    ) -> tuple[TextractPage, ...]:
        require_tenant_context(context)
        try:
            response = self._client.analyze_document(
                Document={
                    "S3Object": {
                        "Bucket": self._bucket,
                        "Name": self._object_key(context, object_id),
                    }
                },
                FeatureTypes=["LAYOUT"],
            )
        except Exception as error:
            raise AwsAdapterError("document extraction unavailable") from error
        lines: dict[int, list[str]] = {}
        raw_blocks = response.get("Blocks", ())
        if not isinstance(raw_blocks, list):
            raise AwsAdapterError("document extraction response is invalid")
        for raw in raw_blocks:
            if not isinstance(raw, dict) or raw.get("BlockType") != "LINE":
                continue
            page = raw.get("Page")
            text = raw.get("Text")
            if isinstance(page, int) and isinstance(text, str):
                lines.setdefault(page, []).append(text)
        return tuple(
            TextractPage(page_number=page, lines=tuple(lines[page])) for page in sorted(lines)
        )


class AwsTranscribeSpeechToText(SpeechToText):
    def __init__(
        self,
        transcribe: TranscribeClient,
        s3: S3Client,
        *,
        bucket: str,
        transcript_loader: Callable[[str], Mapping[str, Any]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        poll_interval_seconds: float = 1,
        max_polls: int = 120,
    ) -> None:
        self._transcribe = transcribe
        self._s3 = s3
        self._bucket = bucket
        self._transcript_loader = transcript_loader or _load_json
        self._sleep = sleep
        self._poll_interval_seconds = poll_interval_seconds
        self._max_polls = max_polls

    def transcribe(
        self,
        context: TenantContext,
        audio: bytes,
        *,
        sample_rate_hz: int,
    ) -> Mapping[str, Any]:
        tenant = require_tenant_context(context)
        job_id = f"interview-{tenant.company_id}-{uuid4()}"
        object_key = f"tenants/{tenant.company_id}/transcribe/{job_id}.webm"
        try:
            self._s3.put_object(
                Bucket=self._bucket,
                Key=object_key,
                Body=audio,
                ContentType="audio/webm",
                Metadata={"company-id": str(tenant.company_id)},
            )
            self._transcribe.start_transcription_job(
                TranscriptionJobName=job_id,
                Media={"MediaFileUri": f"s3://{self._bucket}/{object_key}"},
                MediaFormat="webm",
                MediaSampleRateHertz=sample_rate_hz,
                LanguageCode="ko-KR",
                Settings={"ShowSpeakerLabels": False},
            )
            transcript_uri = self._wait_for_transcript(job_id)
            transcript = self._transcript_loader(transcript_uri)
        except AwsAdapterError:
            raise
        except Exception as error:
            raise AwsAdapterError("transcription unavailable") from error
        results = transcript.get("results")
        if not isinstance(results, dict):
            raise AwsAdapterError("transcription response is invalid")
        transcripts = results.get("transcripts")
        items = results.get("items")
        text = ""
        if isinstance(transcripts, list) and transcripts:
            first = transcripts[0]
            if isinstance(first, dict) and isinstance(first.get("transcript"), str):
                text = first["transcript"]
        confidences = _transcript_confidences(items)
        return {
            "text": text,
            "confidence": (sum(confidences) / len(confidences) if confidences else 0.0),
        }

    def _wait_for_transcript(self, job_id: str) -> str:
        for _ in range(self._max_polls):
            response = self._transcribe.get_transcription_job(TranscriptionJobName=job_id)
            job = response.get("TranscriptionJob")
            if not isinstance(job, dict):
                raise AwsAdapterError("transcription status is invalid")
            status = job.get("TranscriptionJobStatus")
            if status == "COMPLETED":
                transcript = job.get("Transcript")
                if isinstance(transcript, dict):
                    transcript_uri = transcript.get("TranscriptFileUri")
                    if isinstance(transcript_uri, str):
                        return transcript_uri
                raise AwsAdapterError("transcription receipt is missing")
            if status == "FAILED":
                raise AwsAdapterError("transcription failed")
            self._sleep(self._poll_interval_seconds)
        raise AwsAdapterError("transcription timed out")


class AwsMediaConvert:
    def __init__(
        self,
        client: MediaConvertClient,
        *,
        role_arn: str,
        output_bucket: str,
    ) -> None:
        self._client = client
        self._role_arn = role_arn
        self._output_bucket = output_bucket

    def create_hls_job(
        self,
        context: TenantContext,
        *,
        input_key: str,
        output_prefix: str,
    ) -> str:
        tenant = require_tenant_context(context)
        destination = (
            f"s3://{self._output_bucket}/tenants/{tenant.company_id}/{output_prefix.strip('/')}/"
        )
        try:
            response = self._client.create_job(
                Role=self._role_arn,
                UserMetadata={"company_id": str(tenant.company_id)},
                Settings={
                    "Inputs": [{"FileInput": f"s3://{self._output_bucket}/{input_key}"}],
                    "OutputGroups": [
                        {
                            "Name": "HLS",
                            "OutputGroupSettings": {
                                "Type": "HLS_GROUP_SETTINGS",
                                "HlsGroupSettings": {
                                    "Destination": destination,
                                    "SegmentLength": 2,
                                },
                            },
                            "Outputs": [
                                {
                                    "ContainerSettings": {
                                        "Container": "M3U8",
                                    }
                                }
                            ],
                        }
                    ],
                },
            )
        except Exception as error:
            raise AwsAdapterError("media conversion unavailable") from error
        job = response.get("Job")
        if not isinstance(job, dict):
            raise AwsAdapterError("media conversion returned no receipt")
        job_id = job.get("Id")
        if not isinstance(job_id, str):
            raise AwsAdapterError("media conversion returned no receipt")
        return job_id


def _cognito_attributes(raw: object) -> dict[str, str]:
    if not isinstance(raw, list):
        raise KeyError("attributes")
    attributes: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("Name")
        value = item.get("Value")
        if isinstance(name, str) and isinstance(value, str):
            attributes[name] = value
    return attributes


def _aws_error_code(error: Exception) -> str | None:
    response = getattr(error, "response", None)
    if not isinstance(response, Mapping):
        return None
    details = response.get("Error")
    if not isinstance(details, Mapping):
        return None
    code = details.get("Code")
    return str(code) if code is not None else None


def _queue_count(value: object) -> int:
    if not isinstance(value, int | str):
        raise TypeError("queue count is not numeric")
    return int(value)


def _transcript_confidences(raw: object) -> list[float]:
    if not isinstance(raw, list):
        return []
    values: list[float] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        alternatives = item.get("alternatives")
        if not isinstance(alternatives, list) or not alternatives:
            continue
        first = alternatives[0]
        if not isinstance(first, dict):
            continue
        confidence = first.get("confidence")
        if isinstance(confidence, str):
            try:
                values.append(float(confidence))
            except ValueError:
                continue
    return values


def _load_json(uri: str) -> Mapping[str, Any]:
    with urllib.request.urlopen(uri, timeout=10) as response:  # noqa: S310
        return cast(dict[str, Any], json.load(io.BytesIO(response.read())))
