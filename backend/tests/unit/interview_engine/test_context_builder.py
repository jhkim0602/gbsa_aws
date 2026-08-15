from uuid import UUID

from interview_evidence.interview_engine.application.context_builder import (
    ContextBuilder,
    ContextTurn,
)


def test_context_builder_prioritizes_recent_turns_within_budget() -> None:
    turns = tuple(
        ContextTurn(
            turn_id=UUID(f"00000000-0000-7000-8000-{index:012d}"),
            speaker="applicant" if index % 2 == 0 else "interviewer",
            text=f"{index}번째 대화 " + ("상세 내용 " * 20),
        )
        for index in range(1, 7)
    )
    result = ContextBuilder(token_budget=140).build(
        recent_turns=turns,
        older_summary="이전 대화에서는 운영 장애와 협업 경험을 다뤘습니다.",
        remaining_criterion_ids=(
            UUID("00000000-0000-7000-8000-000000000101"),
            UUID("00000000-0000-7000-8000-000000000102"),
        ),
        remaining_time_seconds=300,
        retrieved_source_ids=(UUID("00000000-0000-7000-8000-000000000201"),),
    )

    assert result.estimated_tokens <= 140
    assert result.recent_turns[-1].turn_id == turns[-1].turn_id
    assert result.remaining_time_seconds == 300
    assert result.remaining_criterion_ids
    assert result.retrieved_source_ids
