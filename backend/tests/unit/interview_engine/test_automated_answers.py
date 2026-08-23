from datetime import UTC, datetime
from typing import cast
from unittest.mock import patch
from uuid import UUID

from interview_evidence.interview_engine.api.live_handlers import LiveInterviewHandler
from interview_evidence.interview_engine.api.websocket import (
    ProtocolStreamHandler,
    ServerEnvelope,
    WebSocketEnvelope,
)
from interview_evidence.interview_engine.application.session_service import (
    SessionApplicationService,
)
from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 20, 8, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000004")
ANSWER_ID = UUID("00000000-0000-7000-8000-000000000005")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000006"),
        trace_id="trace-automated-answer",
    )


def principal() -> ApplicantPrincipal:
    return ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        session_id=SESSION_ID,
    )


def envelope() -> WebSocketEnvelope:
    return WebSocketEnvelope(
        protocol_version="1.0",
        message_type="answer.automated",
        session_id=SESSION_ID,
        sequence=3,
        idempotency_key="answer-automated-0001",
        correlation_id=UUID("00000000-0000-7000-8000-000000000007"),
        sent_at=NOW,
        payload={
            "answer_turn_id": str(ANSWER_ID),
            "text": "문제를 분석하고 해결 결과를 검증했습니다.",
            "last_recording_chunk_sequence": 4,
        },
    )


def response(message_type: str) -> ServerEnvelope:
    request = envelope()
    return ServerEnvelope(
        message_type=message_type,
        session_id=SESSION_ID,
        sequence=request.sequence,
        idempotency_key=f"server:{request.idempotency_key}",
        correlation_id=request.correlation_id,
        sent_at=NOW,
        payload={},
    )


class AutomatedHandler:
    def generate_automated_answer(
        self,
        request_context: TenantContext,
        applicant: ApplicantPrincipal,
        request: WebSocketEnvelope,
    ) -> ServerEnvelope:
        assert request_context.company_id == COMPANY_ID
        assert applicant.session_id == SESSION_ID
        return response("answer.automated.ready")

    def complete_automated_answer(
        self,
        request_context: TenantContext,
        applicant: ApplicantPrincipal,
        request: WebSocketEnvelope,
    ) -> ServerEnvelope:
        assert request_context.company_id == COMPANY_ID
        assert applicant.session_id == SESSION_ID
        assert request.payload["text"] == "문제를 분석하고 해결 결과를 검증했습니다."
        return response("session.completed")


def test_protocol_routes_local_automated_answers_to_the_opted_in_handler() -> None:
    protocol = ProtocolStreamHandler(
        session_service=cast(SessionApplicationService, object()),
        automated_answer_handler=AutomatedHandler(),
    )

    result = protocol.handle(context(), principal(), envelope())

    assert result.message_type == "session.completed"


def test_protocol_routes_local_automated_answer_generation() -> None:
    request = envelope().model_copy(
        update={
            "message_type": "answer.automated.generate",
            "payload": {
                "question_turn_id": "00000000-0000-7000-8000-000000000009",
                "include_audio": True,
            },
        }
    )
    protocol = ProtocolStreamHandler(
        session_service=cast(SessionApplicationService, object()),
        automated_answer_handler=AutomatedHandler(),
    )

    result = protocol.handle(context(), principal(), request)

    assert result.message_type == "answer.automated.ready"


def test_live_handler_records_text_before_completing_the_answer() -> None:
    handler = object.__new__(LiveInterviewHandler)
    transcript = response("transcript.final")
    completed = response("question.ready")

    with (
        patch.object(
            LiveInterviewHandler,
            "record_streaming_transcript",
            return_value=transcript,
        ) as record_transcript,
        patch.object(
            LiveInterviewHandler,
            "complete_answer",
            return_value=completed,
        ) as complete_answer,
    ):
        result = handler.complete_automated_answer(context(), principal(), envelope())

    record_transcript.assert_called_once_with(
        context(),
        principal(),
        envelope(),
        answer_turn_id=ANSWER_ID,
        text="문제를 분석하고 해결 결과를 검증했습니다.",
        confidence=1.0,
        last_chunk_sequence=0,
    )
    complete_answer.assert_called_once_with(context(), principal(), envelope())
    assert result == completed
