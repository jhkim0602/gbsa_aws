from uuid import UUID

from interview_evidence.shared.aws_clients.ports import (
    DeterministicAIModel,
    DeterministicSpeechToText,
    DeterministicTextToSpeech,
    InMemoryEmailSender,
    InMemoryObjectStorage,
    InMemoryQueue,
    SearchHit,
    StaticSearch,
)
from interview_evidence.shared.tenant import ActorType, TenantContext


def tenant_context() -> TenantContext:
    return TenantContext(
        company_id=UUID("00000000-0000-7000-8000-000000000001"),
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000002"),
        request_id=UUID("00000000-0000-7000-8000-000000000003"),
        trace_id="trace-ports",
    )


def test_deterministic_ports_keep_tenant_scope_and_record_calls() -> None:
    context = tenant_context()
    storage = InMemoryObjectStorage()
    queue = InMemoryQueue()
    search = StaticSearch(
        [
            SearchHit(
                company_id=context.company_id,
                source_id=UUID("00000000-0000-7000-8000-000000000004"),
                score=0.9,
                locator={"page": 1},
            )
        ]
    )
    model = DeterministicAIModel({"question": "설계 선택을 설명해 주세요."})

    upload = storage.create_upload_intent(context, "submissions", 10, "a" * 64)
    queue.publish(
        context,
        "submission.analysis_requested",
        {"submission_id": str(upload.object_id)},
    )
    hits = search.search(context, "설계", limit=5)
    result = model.generate(context, {"criterion_id": "criterion-1"})

    assert upload.company_id == context.company_id
    assert queue.messages[0].company_id == context.company_id
    assert hits[0].company_id == context.company_id
    assert result == {"question": "설계 선택을 설명해 주세요."}


def test_speech_and_email_fakes_are_deterministic_and_tenant_scoped() -> None:
    context = tenant_context()
    speech_to_text = DeterministicSpeechToText({"text": "최종 답변", "confidence": 0.98})
    text_to_speech = DeterministicTextToSpeech(
        {"object_id": "00000000-0000-7000-8000-000000000010"}
    )
    email = InMemoryEmailSender()

    transcript = speech_to_text.transcribe(context, b"audio", sample_rate_hz=16000)
    audio = text_to_speech.synthesize(context, "다음 질문입니다.", voice_id="Seoyeon")
    message_id = email.send_template(
        context,
        "invitation-v1",
        UUID("00000000-0000-7000-8000-000000000011"),
        {"invitation_id": "00000000-0000-7000-8000-000000000012"},
    )

    assert transcript == {"text": "최종 답변", "confidence": 0.98}
    assert audio == {"object_id": "00000000-0000-7000-8000-000000000010"}
    assert speech_to_text.calls[0].company_id == context.company_id
    assert text_to_speech.calls[0].company_id == context.company_id
    assert email.messages[0].company_id == context.company_id
    assert message_id == email.messages[0].message_id
