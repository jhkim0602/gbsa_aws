from uuid import UUID

from interview_evidence.interview_engine.application.context_builder import (
    ContextBuilder,
    ContextTurn,
    RetrievedSourceContext,
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
        interview_stage="project_deep_dive",
        interview_stage_focus="프로젝트 목표, 본인 역할, 설계와 구현, 결과와 회고",
        next_question_type="stage_opening",
        required_assessment_axis="fundamentals",
        retrieved_source_ids=(UUID("00000000-0000-7000-8000-000000000201"),),
        retrieved_sources=(
            RetrievedSourceContext(
                source_id=UUID("00000000-0000-7000-8000-000000000201"),
                source_type="submission_chunk",
                locator={"page": 2},
                excerpt="ECS 배포 경험은 있으나 장애 복구 설명은 없습니다.",
                score=0.91,
                material_type="resume",
            ),
        ),
        criterion_text="ECS 운영 장애 대응 경험을 확인한다.",
        verification_objective="원인 분석과 직접 복구 역할을 확인한다.",
        missing_dimensions=("원인 분석", "직접 수행한 복구"),
        follow_up_directions=("본인이 직접 수행한 복구 작업",),
        answer_evidence_gaps=("검증 결과",),
        stage_evidence_available=False,
    )

    assert result.estimated_tokens <= 140
    assert result.recent_turns[-1].turn_id == turns[-1].turn_id
    assert result.remaining_time_seconds == 300
    assert result.interview_stage == "project_deep_dive"
    assert result.next_question_type == "stage_opening"
    assert result.required_assessment_axis == "fundamentals"
    assert result.remaining_criterion_ids
    assert result.retrieved_source_ids
    payload = result.model_payload()
    assert payload["retrieved_sources"][0]["excerpt"].startswith("ECS 배포")
    assert payload["verification_objective"] == ("원인 분석과 직접 복구 역할을 확인한다.")
    assert payload["required_assessment_axis"] == "fundamentals"
    assert payload["follow_up_directions"] == ["본인이 직접 수행한 복구 작업"]
    assert payload["answer_evidence_gaps"] == ["검증 결과"]
    assert payload["stage_evidence_available"] is False
    assert payload["retrieved_sources"][0]["material_type"] == "resume"
