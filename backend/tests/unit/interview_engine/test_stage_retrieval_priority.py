from dataclasses import dataclass, field
from uuid import UUID

from interview_evidence.interview_engine.adapters.retrieval_client import RetrievalClient
from interview_evidence.interview_engine.application.interview_plan import (
    InterviewStage,
    VerificationTargetPlan,
)
from interview_evidence.interview_engine.application.interview_service import (
    _retrieval_query,
)
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

    def retrieve_context(self, *args: object, **kwargs: object) -> tuple[Record, ...]:
        del args
        self.requested_limit = int(kwargs["limit"])
        return self.records


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


def test_project_stage_prioritizes_github_code() -> None:
    assert _retrieve(InterviewStage.PROJECT_DEEP_DIVE)[0] == "candidate_code_unit"


def test_behavioral_stage_prioritizes_narrative_materials() -> None:
    ranked = _retrieve(InterviewStage.BEHAVIORAL)

    assert ranked[0] == "cover_letter"
    assert ranked[-1] == "candidate_code_unit"


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

    assert "프로젝트 목표" in query
    assert target.objective in query
    assert "직접 구현 범위" in query
    assert query.endswith("결제 서비스를 개발했습니다.")
