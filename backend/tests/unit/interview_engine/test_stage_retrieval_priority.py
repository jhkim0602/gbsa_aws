from dataclasses import dataclass, field
from uuid import UUID

from interview_evidence.interview_engine.adapters.retrieval_client import (
    RetrievalClient,
    RetrievedContext,
)
from interview_evidence.interview_engine.application.interview_plan import (
    InterviewStage,
    VerificationTargetPlan,
)
from interview_evidence.interview_engine.application.interview_service import (
    _git_project_question,
    _retrieval_query,
)
from interview_evidence.interview_engine.application.question_policy import QuestionPolicy
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
MODEL_VERSION_ID = UUID("00000000-0000-7000-8000-000000000004")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000005")


@dataclass(frozen=True, slots=True)
class Record:
    source_id: UUID
    source_type: str
    material_type: str | None
    excerpt: str
    score: float = 0.7
    locator: dict[str, object] = field(default_factory=dict)
    ownership_confidence: float = 1.0


class FixedRetrieval:
    def __init__(self, records: tuple[Record, ...]) -> None:
        self.records = records
        self.requested_limit = 0
        self.requested_source_types: list[frozenset[str] | None] = []

    def retrieve_context(self, *args: object, **kwargs: object) -> tuple[Record, ...]:
        del args
        self.requested_limit = int(kwargs["limit"])
        source_types = kwargs.get("source_types")
        assert source_types is None or isinstance(source_types, frozenset)
        self.requested_source_types.append(source_types)
        matching = (
            self.records
            if source_types is None
            else tuple(record for record in self.records if record.source_type in source_types)
        )
        return matching[: self.requested_limit]


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000006"),
        trace_id="stage-retrieval-priority",
    )


def _retrieve(stage: InterviewStage) -> tuple[str, ...]:
    provider = FixedRetrieval(
        (
            Record(
                source_id=UUID("00000000-0000-7000-8000-000000000010"),
                source_type="submission_chunk",
                material_type="resume",
                excerpt="기술 경험과 경력",
            ),
            Record(
                source_id=UUID("00000000-0000-7000-8000-000000000011"),
                source_type="submission_chunk",
                material_type="cover_letter",
                excerpt="팀 갈등을 조율한 경험",
            ),
            Record(
                source_id=UUID("00000000-0000-7000-8000-000000000012"),
                source_type="candidate_code_unit",
                material_type=None,
                excerpt="class PaymentService",
            ),
            Record(
                source_id=UUID("00000000-0000-7000-8000-000000000013"),
                source_type="repository_overview",
                material_type="projects",
                excerpt="API, worker, database로 구성된 저장소 구조",
                locator={"section": "repository_overview:repository_structure"},
            ),
        )
    )
    outcome = RetrievalClient(provider, limit=3).retrieve(
        _context(),
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=MODEL_VERSION_ID,
        session_id=UUID("00000000-0000-7000-8000-000000000020"),
        query="지원자가 설명한 경험",
        query_vector=(1.0,),
        criterion_id=CRITERION_ID,
        config_version="stage-aware-v1",
        interview_stage=stage,
    )
    assert provider.requested_limit == 9
    return tuple(hit.material_type or hit.source_type for hit in outcome.hits)


def test_project_stage_prioritizes_repository_architecture_before_code() -> None:
    assert _retrieve(InterviewStage.PROJECT_DEEP_DIVE)[0] == "projects"


def test_project_stage_fetches_github_when_general_shortlist_has_only_documents() -> None:
    documents = tuple(
        Record(
            source_id=UUID(int=100 + index),
            source_type="submission_chunk",
            material_type="portfolio",
            excerpt=f"프로젝트 설명 {index}",
            score=0.9,
        )
        for index in range(12)
    )
    github = Record(
        source_id=UUID("00000000-0000-7000-8000-000000000099"),
        source_type="candidate_code_unit",
        material_type=None,
        excerpt="class PaymentService",
        score=0.1,
        locator={"path": "src/payment.py", "symbol": "PaymentService"},
    )
    provider = FixedRetrieval((*documents, github))

    outcome = RetrievalClient(provider, limit=3).retrieve(
        _context(),
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=MODEL_VERSION_ID,
        session_id=UUID("00000000-0000-7000-8000-000000000020"),
        query="결제 프로젝트",
        query_vector=(1.0,),
        criterion_id=CRITERION_ID,
        config_version="stage-aware-v1",
        interview_stage=InterviewStage.PROJECT_DEEP_DIVE,
    )

    assert any(hit.source_type == "candidate_code_unit" for hit in outcome.hits)
    assert provider.requested_source_types == [
        None,
        frozenset({"candidate_code_unit", "repository_overview"}),
    ]


def test_behavioral_stage_prioritizes_narrative_materials() -> None:
    ranked = _retrieve(InterviewStage.BEHAVIORAL)

    assert ranked[0] == "cover_letter"
    assert "candidate_code_unit" not in ranked


def test_technical_stage_uses_resume_before_supporting_code() -> None:
    ranked = _retrieve(InterviewStage.TECHNICAL)

    assert ranked[:2] == ("resume", "candidate_code_unit")


def test_retrieval_query_combines_stage_target_and_latest_answer() -> None:
    target = VerificationTargetPlan(
        verification_target_id=UUID("00000000-0000-7000-8000-000000000030"),
        criterion_id=CRITERION_ID,
        criterion_text="프로젝트에서 맡은 역할",
        target_type="detail_missing",
        objective="지원자가 직접 설계하고 구현한 범위를 확인한다.",
        missing_dimensions=("설계 근거", "직접 구현 범위"),
        follow_up_directions=(),
        max_follow_ups=1,
        common_question="프로젝트 경험을 설명해 주세요?",
    )

    query = _retrieval_query(
        answer_text="결제 서비스를 개발했습니다.",
        interview_stage=InterviewStage.PROJECT_DEEP_DIVE,
        question_target=target,
    )

    assert "하나의 실제 프로젝트" in query
    assert target.objective in query
    assert "직접 구현 범위" in query
    assert query.endswith("결제 서비스를 개발했습니다.")


def test_required_github_question_is_policy_safe_and_keeps_code_source() -> None:
    draft = _git_project_question(
        hit=RetrievedContext(
            source_id=UUID("00000000-0000-7000-8000-000000000040"),
            score=1.1,
            locator={"path": "src/payment.py", "symbol": "PaymentService"},
            ownership_confidence=1,
            excerpt="class PaymentService",
            source_type="candidate_code_unit",
        ),
        target_criterion_id=CRITERION_ID,
        model_config_version="question-v1",
        retrieval_config_version="stage-aware-v1",
    )

    result = QuestionPolicy().evaluate(
        draft,
        allowed_criterion_ids=frozenset({CRITERION_ID}),
        prohibited_topics=(),
        previous_questions=(),
        fallback_question="프로젝트 경험을 설명해 주시겠습니까?",
        fallback_criterion_id=CRITERION_ID,
        interview_stage="project_deep_dive",
    )

    assert result.accepted
    assert result.question.source_reference_ids == draft.source_reference_ids
    assert "주요 구성 요소" in result.question.text
    assert "구조를 선택한 이유" in result.question.text
    assert "PaymentService" not in result.question.text
    assert "payment.py" not in result.question.text
