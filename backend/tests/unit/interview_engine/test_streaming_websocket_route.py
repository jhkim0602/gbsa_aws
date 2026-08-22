from __future__ import annotations

import asyncio
import warnings
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from starlette.exceptions import StarletteDeprecationWarning

with warnings.catch_warnings():
    warnings.simplefilter("ignore", StarletteDeprecationWarning)
    from starlette.testclient import TestClient

from interview_evidence.interview_engine.api.streaming_speech import WebSocketSpeechRuntime
from interview_evidence.interview_engine.api.websocket import (
    ServerEnvelope,
    WebSocketEnvelope,
    create_interview_websocket_router,
)
from interview_evidence.interview_engine.application.question_generator import (
    QuestionGenerationUnavailable,
)
from interview_evidence.main import create_app
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    CompanyPrincipal,
)
from interview_evidence.shared.speech.ports import (
    SpeechRecognitionConfig,
    SpeechRecognitionSession,
    TranscriptEvent,
)
from interview_evidence.shared.tenant import TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000011")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000012")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000013")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000014")
ANSWER_ID = UUID("00000000-0000-7000-8000-000000000015")
NOW = datetime(2026, 8, 20, 9, 0, tzinfo=UTC)


class FakePrincipalProvider:
    def get_applicant_principal(self, credential: str) -> ApplicantPrincipal:
        assert credential == "applicant-session"
        return ApplicantPrincipal(
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            session_id=SESSION_ID,
        )

    def get_company_principal(self, credential: str) -> CompanyPrincipal:
        raise AssertionError(credential)


class FakeProtocolHandler:
    def __init__(self) -> None:
        self.saved_transcript: str | None = None

    def authorize_connection(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        session_id: UUID,
    ) -> None:
        assert context.company_id == COMPANY_ID
        assert principal.applicant_id == APPLICANT_ID
        assert session_id == SESSION_ID

    def handle(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
    ) -> ServerEnvelope:
        del context, principal
        message_type = (
            "answer.started" if envelope.message_type == "answer.start" else "question.ready"
        )
        return _response(envelope, message_type=message_type, payload={})

    def record_streaming_transcript(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
        *,
        answer_turn_id: UUID,
        text: str,
        confidence: float,
        last_chunk_sequence: int,
    ) -> ServerEnvelope:
        del context, principal
        assert answer_turn_id == ANSWER_ID
        assert confidence == 0.96
        assert last_chunk_sequence == 0
        self.saved_transcript = text
        return _response(
            envelope,
            message_type="transcript.final",
            payload={"answer_turn_id": str(answer_turn_id), "text": text},
        )


class TemporarilyUnavailableProtocolHandler(FakeProtocolHandler):
    def handle(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
    ) -> ServerEnvelope:
        if envelope.message_type == "answer.automated":
            raise QuestionGenerationUnavailable(
                "question generation is temporarily unavailable",
                retryable=True,
            )
        return super().handle(context, principal, envelope)


class FakeRecognitionSession(SpeechRecognitionSession):
    def __init__(self) -> None:
        self.events: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()

    async def send_audio(self, chunk: bytes) -> None:
        assert chunk == b"pcm"
        await self.events.put(TranscriptEvent("안녕", False, 0.4, 0.7))
        await self.events.put(TranscriptEvent("안녕하세요", True, 0.92, 1.0))

    def results(self) -> AsyncIterator[TranscriptEvent]:
        return self._results()

    async def _results(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            event = await self.events.get()
            if event is None:
                return
            yield event

    async def end_input(self) -> None:
        await self.events.put(TranscriptEvent("반갑습니다", True, 0.96, 1.0))
        await self.events.put(None)

    async def abort(self) -> None:
        await self.events.put(None)


class FakeStreamingSpeechToText:
    def __init__(self) -> None:
        self.session = FakeRecognitionSession()

    async def open_stream(
        self,
        context: TenantContext,
        config: SpeechRecognitionConfig,
    ) -> SpeechRecognitionSession:
        assert context.company_id == COMPANY_ID
        assert config.sample_rate_hz == 16000
        return self.session


class RecordingTaskProtection:
    def __init__(self) -> None:
        self.acquired: list[UUID] = []
        self.released: list[UUID] = []

    def acquire(self, workload_id: UUID) -> bool:
        self.acquired.append(workload_id)
        return True

    def release(self, workload_id: UUID) -> bool:
        self.released.append(workload_id)
        return True


def test_websocket_streams_partial_caption_then_persists_final_transcript() -> None:
    handler = FakeProtocolHandler()
    task_protection = RecordingTaskProtection()
    router = create_interview_websocket_router(
        principal_provider=FakePrincipalProvider(),
        handler=handler,  # type: ignore[arg-type]
        speech=WebSocketSpeechRuntime(
            speech_to_text=FakeStreamingSpeechToText(),
        ),
        task_protection=task_protection,
    )
    app = create_app([router])

    with TestClient(app) as client:
        client.cookies.set("iep_applicant_session", "applicant-session")
        with client.websocket_connect(
            f"/v1/applicant/interview-sessions/{SESSION_ID}/stream"
        ) as websocket:
            websocket.send_json(_envelope("answer.start", "answer-start-0001"))
            assert websocket.receive_json()["message_type"] == "answer.started"

            audio = b"pcm"
            websocket.send_json(
                _envelope(
                    "audio.chunk.begin",
                    "audio-chunk-0001",
                    payload={
                        "answer_turn_id": str(ANSWER_ID),
                        "chunk_sequence": 0,
                        "codec": "pcm_s16le",
                        "sample_rate_hz": 16000,
                        "channel_count": 1,
                        "byte_length": len(audio),
                        "sha256": sha256(audio).hexdigest(),
                    },
                )
            )
            websocket.send_bytes(audio)
            assert websocket.receive_json()["payload"]["text"] == "안녕"
            assert websocket.receive_json()["payload"]["text"] == "안녕하세요"

            websocket.send_json(_envelope("answer.complete", "answer-complete-0001"))
            assert websocket.receive_json()["payload"]["text"] == "안녕하세요 반갑습니다"
            assert websocket.receive_json()["message_type"] == "transcript.final"
            assert websocket.receive_json()["message_type"] == "question.ready"

    assert handler.saved_transcript == "안녕하세요 반갑습니다"
    assert task_protection.acquired == [SESSION_ID]
    assert task_protection.released == [SESSION_ID]


def test_question_generation_failure_keeps_websocket_available_for_retry() -> None:
    handler = TemporarilyUnavailableProtocolHandler()
    router = create_interview_websocket_router(
        principal_provider=FakePrincipalProvider(),
        handler=handler,  # type: ignore[arg-type]
    )
    app = create_app([router])

    with TestClient(app) as client:
        client.cookies.set("iep_applicant_session", "applicant-session")
        with client.websocket_connect(
            f"/v1/applicant/interview-sessions/{SESSION_ID}/stream"
        ) as websocket:
            websocket.send_json(
                _envelope(
                    "answer.automated",
                    "answer-automated-0001",
                    payload={
                        "answer_turn_id": str(ANSWER_ID),
                        "text": "자동 답변입니다.",
                    },
                )
            )
            failure = websocket.receive_json()
            assert failure["message_type"] == "error"
            assert failure["payload"]["code"] == "QUESTION_GENERATION_UNAVAILABLE"
            assert failure["payload"]["retryable"] is True

            websocket.send_json(_envelope("answer.start", "answer-start-0002"))
            assert websocket.receive_json()["message_type"] == "answer.started"


def _envelope(
    message_type: str,
    idempotency_key: str,
    *,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "protocol_version": "1.0",
        "message_type": message_type,
        "session_id": str(SESSION_ID),
        "sequence": 3,
        "idempotency_key": idempotency_key,
        "correlation_id": "00000000-0000-7000-8000-000000000016",
        "sent_at": NOW.isoformat(),
        "payload": payload or {"answer_turn_id": str(ANSWER_ID)},
    }


def _response(
    envelope: WebSocketEnvelope,
    *,
    message_type: str,
    payload: dict[str, object],
) -> ServerEnvelope:
    return ServerEnvelope(
        message_type=message_type,
        session_id=envelope.session_id,
        sequence=envelope.sequence,
        idempotency_key=f"server:{envelope.idempotency_key}",
        correlation_id=envelope.correlation_id,
        sent_at=envelope.sent_at,
        payload=payload,
    )
