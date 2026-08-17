import json
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from hashlib import sha256
from typing import Literal, Protocol
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.interview_engine.application.session_service import (
    SessionApplicationService,
)
from interview_evidence.interview_engine.domain.session import InterviewSession
from interview_evidence.shared.database import RequestScopedDatabase
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    PrincipalNotFoundError,
    PrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext


class WebSocketEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: Literal["1.0"]
    message_type: str = Field(pattern=r"^[a-z]+(?:\.[a-z_]+)*$")
    session_id: UUID
    sequence: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)
    correlation_id: UUID
    sent_at: datetime
    payload: dict[str, object]


class ServerEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: Literal["1.0"] = "1.0"
    message_type: str = Field(pattern=r"^[a-z]+(?:\.[a-z_]+)*$")
    session_id: UUID
    sequence: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)
    correlation_id: UUID
    sent_at: datetime
    payload: dict[str, object]


class AudioChunkMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer_turn_id: UUID
    chunk_sequence: int = Field(ge=0)
    codec: Literal["pcm_s16le"]
    sample_rate_hz: int = Field(ge=8000, le=48000)
    channel_count: Literal[1]
    byte_length: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class AnswerCompletionHandler(Protocol):
    def complete_answer(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
    ) -> ServerEnvelope: ...


class AudioFrameHandler(Protocol):
    def handle_audio(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
        metadata: AudioChunkMetadata,
        audio: bytes,
    ) -> tuple[ServerEnvelope, ...]: ...


class SessionStartHandler(Protocol):
    def initial_question(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
        started: InterviewSession,
    ) -> ServerEnvelope: ...


class ProtocolStreamHandler:
    def __init__(
        self,
        *,
        session_service: SessionApplicationService,
        start_handler: SessionStartHandler | None = None,
        answer_handler: AnswerCompletionHandler | None = None,
        audio_handler: AudioFrameHandler | None = None,
    ) -> None:
        self._session_service = session_service
        self._start_handler = start_handler
        self._answer_handler = answer_handler
        self._audio_handler = audio_handler

    def authorize_connection(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        session_id: UUID,
    ) -> None:
        self._session_service.resume(context, principal, session_id=session_id)

    def handle(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
    ) -> ServerEnvelope:
        if envelope.message_type == "session.start":
            started = self._session_service.start_session(
                context,
                principal,
                session_id=envelope.session_id,
                expected_sequence=envelope.sequence,
                idempotency_key=envelope.idempotency_key,
            )
            if self._start_handler is not None:
                return self._start_handler.initial_question(
                    context,
                    principal,
                    envelope,
                    started,
                )
            return self._server_message(
                envelope,
                message_type="session.state_changed",
                sequence=started.session_sequence,
                payload={
                    "previous_state": "preparing",
                    "state": started.state.value,
                    "reason_code": "session_started",
                    "checkpoint_id": None,
                },
            )
        if envelope.message_type == "session.resume":
            snapshot = self._session_service.resume(
                context,
                principal,
                session_id=envelope.session_id,
            )
            return self._server_message(
                envelope,
                message_type="resume.snapshot",
                sequence=snapshot.server_sequence,
                payload={
                    "state": snapshot.state,
                    "server_sequence": snapshot.server_sequence,
                    "last_final_turn_id": snapshot.last_final_turn_id,
                    "pending_turn": snapshot.pending_turn,
                    "last_verified_recording_chunk_sequence": (
                        snapshot.last_verified_recording_chunk_sequence
                    ),
                    "allowed_client_messages": ["session.resume"],
                    "degraded_modes": list(snapshot.degraded_modes),
                },
            )
        if envelope.message_type == "heartbeat.ping":
            snapshot = self._session_service.resume(
                context,
                principal,
                session_id=envelope.session_id,
            )
            return self._server_message(
                envelope,
                message_type="heartbeat.pong",
                sequence=snapshot.server_sequence,
                payload={"client_monotonic": envelope.payload.get("client_monotonic")},
            )
        if envelope.message_type == "question.repeat":
            question_turn_id = UUID(str(envelope.payload.get("question_turn_id", "")))
            turn = self._session_service.repeat_question(
                context,
                principal,
                session_id=envelope.session_id,
                question_turn_id=question_turn_id,
            )
            return self._server_message(
                envelope,
                message_type="question.ready",
                sequence=envelope.sequence,
                payload={
                    "question_turn_id": str(turn.turn_id),
                    "text": turn.text,
                    "target_criterion_id": str(turn.target_criterion_id),
                    "audio_url": None,
                    "audio_expires_at": None,
                    "speech_marks_url": None,
                    "source_reference_count": 0,
                    "text_only": True,
                },
            )
        if envelope.message_type == "answer.complete" and self._answer_handler is not None:
            return self._answer_handler.complete_answer(context, principal, envelope)
        if envelope.message_type == "answer.complete":
            return self._server_message(
                envelope,
                message_type="error",
                sequence=envelope.sequence,
                payload={
                    "code": "ANSWER_TRANSCRIPT_NOT_READY",
                    "message": "확정 자막을 준비하고 있습니다. 잠시 후 다시 시도해 주세요.",
                    "retryable": True,
                    "current_sequence": envelope.sequence,
                },
            )
        return self._server_message(
            envelope,
            message_type="error",
            sequence=envelope.sequence,
            payload={
                "code": "UNSUPPORTED_MESSAGE",
                "message": "지원하지 않는 메시지입니다.",
                "retryable": False,
                "current_sequence": envelope.sequence,
            },
        )

    def handle_audio(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
        metadata: AudioChunkMetadata,
        audio: bytes,
    ) -> tuple[ServerEnvelope, ...]:
        validate_audio_frame(metadata, audio)
        if self._audio_handler is not None:
            return self._audio_handler.handle_audio(
                context,
                principal,
                envelope,
                metadata,
                audio,
            )
        return (
            self._server_message(
                envelope,
                message_type="error",
                sequence=envelope.sequence,
                payload={
                    "code": "TRANSCRIPTION_UNAVAILABLE",
                    "message": "음성 인식을 준비하고 있습니다. 연결을 유지해 주세요.",
                    "retryable": True,
                    "current_sequence": envelope.sequence,
                },
            ),
        )

    @staticmethod
    def _server_message(
        envelope: WebSocketEnvelope,
        *,
        message_type: str,
        sequence: int,
        payload: dict[str, object],
    ) -> ServerEnvelope:
        return ServerEnvelope(
            message_type=message_type,
            session_id=envelope.session_id,
            sequence=sequence,
            idempotency_key=f"server:{envelope.idempotency_key}",
            correlation_id=envelope.correlation_id,
            sent_at=datetime.now(UTC),
            payload=payload,
        )


def create_interview_websocket_router(
    *,
    principal_provider: PrincipalProvider,
    handler: ProtocolStreamHandler,
    database: RequestScopedDatabase | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/v1")

    @router.websocket("/applicant/interview-sessions/{session_id}/stream")
    async def interview_stream(websocket: WebSocket, session_id: UUID) -> None:
        session_cookie = websocket.cookies.get("iep_applicant_session")
        if session_cookie is None:
            await websocket.close(code=4001)
            return
        try:
            principal = _execute_transaction(
                database,
                partial(principal_provider.get_applicant_principal, session_cookie),
            )
        except PrincipalNotFoundError:
            await websocket.close(code=4001)
            return
        request_id = new_uuid7()
        context = TenantContext(
            company_id=principal.company_id,
            actor_type=ActorType.APPLICANT,
            actor_id=principal.applicant_id,
            request_id=request_id,
            trace_id=websocket.headers.get("x-trace-id") or str(request_id),
        )
        try:
            _execute_transaction(
                database,
                lambda: handler.authorize_connection(
                    context,
                    principal,
                    session_id=session_id,
                ),
            )
        except (LookupError, PermissionError):
            await websocket.close(code=4003)
            return
        await websocket.accept()
        pending_audio: tuple[WebSocketEnvelope, AudioChunkMetadata] | None = None
        try:
            while True:
                incoming = await websocket.receive()
                if incoming["type"] == "websocket.disconnect":
                    return
                binary = incoming.get("bytes")
                if binary is not None:
                    if pending_audio is None:
                        await websocket.send_json(
                            _invalid_message(session_id).model_dump(mode="json")
                        )
                        continue
                    envelope, metadata = pending_audio
                    pending_audio = None
                    try:
                        responses = _execute_transaction(
                            database,
                            partial(
                                handler.handle_audio,
                                context,
                                principal,
                                envelope,
                                metadata,
                                binary,
                            ),
                        )
                    except ValueError:
                        responses = (_invalid_message(session_id),)
                    for response in responses:
                        await websocket.send_json(response.model_dump(mode="json"))
                    continue
                try:
                    text = incoming.get("text")
                    if text is None:
                        raise ValueError("message body is missing")
                    raw = json.loads(text)
                    envelope = WebSocketEnvelope.model_validate(raw)
                    if envelope.session_id != session_id:
                        raise ValueError("session id mismatch")
                    if envelope.message_type == "audio.chunk.begin":
                        pending_audio = (
                            envelope,
                            AudioChunkMetadata.model_validate(envelope.payload),
                        )
                        continue
                    response = _execute_transaction(
                        database,
                        partial(handler.handle, context, principal, envelope),
                    )
                except (ValueError, TypeError):
                    response = _invalid_message(session_id)
                await websocket.send_json(response.model_dump(mode="json"))
        except WebSocketDisconnect:
            return

    return router


def _execute_transaction[ResultT](
    database: RequestScopedDatabase | None,
    execute: Callable[[], ResultT],
) -> ResultT:
    if database is None:
        return execute()
    token = database.begin_scope()
    try:
        result = execute()
        database.session.commit()
        return result
    except BaseException:
        database.session.rollback()
        raise
    finally:
        database.end_scope(token)


def validate_audio_frame(metadata: AudioChunkMetadata, audio: bytes) -> None:
    if len(audio) != metadata.byte_length:
        raise ValueError("audio frame size does not match declaration")
    if sha256(audio).hexdigest() != metadata.sha256:
        raise ValueError("audio frame digest does not match declaration")


def _invalid_message(session_id: UUID) -> ServerEnvelope:
    return ServerEnvelope(
        message_type="error",
        session_id=session_id,
        sequence=0,
        idempotency_key="server:invalid-message",
        correlation_id=new_uuid7(),
        sent_at=datetime.now(UTC),
        payload={
            "code": "INVALID_MESSAGE",
            "message": "메시지 형식이 올바르지 않습니다.",
            "retryable": False,
            "current_sequence": 0,
        },
    )
