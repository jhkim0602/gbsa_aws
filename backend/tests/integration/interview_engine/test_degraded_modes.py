from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from interview_evidence.interview_engine.adapters.polly import SpeechSynthesisAdapter
from interview_evidence.interview_engine.adapters.retrieval_client import RetrievalClient
from interview_evidence.interview_engine.application.question_generator import (
    QuestionGenerationUnavailable,
    QuestionGenerator,
)
from interview_evidence.interview_engine.application.recording_service import (
    RecordingService,
    RecordingUploadUnavailable,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000003")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=UUID("00000000-0000-7000-8000-000000000004"),
        request_id=UUID("00000000-0000-7000-8000-000000000005"),
        trace_id="trace-lane-c-degraded",
    )


class FailingRetrieval:
    def retrieve_context(self, *_args: object, **_kwargs: object) -> tuple[object, ...]:
        raise RuntimeError("search unavailable")


class FailingModel:
    def generate(
        self, _context: TenantContext, _model_input: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        raise RuntimeError("model unavailable")


class FailingSpeech:
    def synthesize(
        self,
        _context: TenantContext,
        _text: str,
        *,
        voice_id: str,
    ) -> Mapping[str, Any]:
        del voice_id
        raise RuntimeError("speech unavailable")


class FailingStorage:
    def create_upload_intent(
        self,
        _context: TenantContext,
        _namespace: str,
        _byte_size: int,
        _sha256: str,
    ) -> object:
        raise RuntimeError("object storage unavailable")


def test_search_failure_returns_common_criterion_fallback_context() -> None:
    outcome = RetrievalClient(FailingRetrieval()).retrieve(
        context(),
        applicant_id=context().actor_id,
        session_id=SESSION_ID,
        query="장애 대응",
        query_vector=(0.1, 0.2),
        criterion_id=CRITERION_ID,
        config_version="hybrid-v1",
    )

    assert outcome.hits == ()
    assert outcome.degraded_mode == "search_fallback"
    assert outcome.user_message == "관련 자료를 불러오지 못해 공통 평가 질문으로 진행합니다."


def test_model_failure_is_retryable_and_does_not_fabricate_question() -> None:
    generator = QuestionGenerator(FailingModel())

    with pytest.raises(QuestionGenerationUnavailable) as error:
        generator.generate(
            context(),
            target_criterion_id=CRITERION_ID,
            context_payload={"remaining_time_seconds": 300},
            model_config_version="question-model-v1",
            retrieval_config_version="hybrid-v1",
        )

    assert error.value.retryable is True


def test_speech_failure_returns_text_only_question() -> None:
    output = SpeechSynthesisAdapter(FailingSpeech()).synthesize(
        context(),
        text="문제를 해결한 과정을 설명해 주세요?",
        voice_id="Seoyeon",
    )

    assert output.text_only is True
    assert output.audio_url is None
    assert output.speech_marks_url is None
    assert output.degraded_mode == "text_only"


def test_upload_failure_is_retryable_and_does_not_create_chunk() -> None:
    service = RecordingService(FailingStorage())

    with pytest.raises(RecordingUploadUnavailable) as error:
        service.issue_upload_intent(
            context(),
            session_id=SESSION_ID,
            sequence=1,
            byte_size=1024,
            content_hash="a" * 64,
            session_start_ms=0,
            session_end_ms=2000,
            idempotency_key="recording-upload-0001",
            occurred_at=NOW,
        )

    assert error.value.retryable is True
