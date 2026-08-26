from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.shared.aws_clients.ports import StaticTextEmbedder
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import (
    InMemorySearchIndex,
    SearchDocument,
)
from interview_evidence.submission_analysis.application.retrieval import (
    HybridRetrievalConfig,
    HybridRetriever,
)
from interview_evidence.submission_analysis.application.verification_map import (
    CriterionVerificationInput,
    RequirementVerificationInput,
    VerificationMapBuilder,
)
from interview_evidence.submission_analysis.domain.retrieval import (
    VerificationTargetType,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    InMemorySubmissionRepository,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000004")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000005")
SOURCE_ID = UUID("00000000-0000-7000-8000-000000000006")
SECOND_CRITERION_ID = UUID("00000000-0000-7000-8000-000000000008")
NOW = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000007"),
        trace_id="verification-map",
    )


def _vector() -> tuple[float, ...]:
    return (1.0, *(0.0 for _ in range(1023)))


def test_ecs_deployment_without_incident_details_creates_missing_detail_target() -> None:
    index = InMemorySearchIndex()
    index.add(
        SearchDocument(
            document_id=str(SOURCE_ID),
            company_id=COMPANY_ID,
            applicant_id=APPLICANT_ID,
            source_id=SOURCE_ID,
            text="ECS 기반 서비스를 배포하고 GitHub Actions 자동화를 구성했습니다.",
            vector=_vector(),
            symbols=("ECS",),
            locator={"page": 2},
            ownership_confidence=1.0,
            embedding_model="test-static-embedding",
            embedding_version="test-static-v1",
            invitation_id=INVITATION_ID,
            competency_model_version_id=VERSION_ID,
        )
    )
    repository = InMemorySubmissionRepository()
    verification_map = VerificationMapBuilder(
        repository=repository,
        retriever=HybridRetriever(index, HybridRetrievalConfig()),
        embedder=StaticTextEmbedder(_vector()),
        clock=FrozenClock(NOW),
    ).build(
        _context(),
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=VERSION_ID,
        criterion_version=1,
        criteria=(
            CriterionVerificationInput(
                criterion_id=CRITERION_ID,
                code="INCIDENT_RESPONSE",
                name="운영 문제 해결",
                description="ECS 장애 원인을 분석하고 복구한다.",
                required=False,
                weight=30,
                observable_dimensions=(
                    "실제 장애 상황",
                    "원인 분석",
                    "직접 수행한 복구",
                    "재발 방지",
                ),
                follow_up_directions=("본인 역할",),
                max_follow_ups=2,
                time_budget_seconds=300,
            ),
        ),
        requirements=(
            RequirementVerificationInput(
                statement="ECS 운영 장애 대응 경험",
                criterion_code="INCIDENT_RESPONSE",
                required=False,
                priority=2,
            ),
        ),
        material_version="analysis-1",
    )

    targets = repository.list_verification_targets(_context(), verification_map)
    assert len(targets) == 1
    assert targets[0].target_type is VerificationTargetType.DETAIL_MISSING
    assert targets[0].missing_dimensions == (
        "실제 장애 상황",
        "원인 분석",
        "직접 수행한 복구",
        "재발 방지",
    )
    assert targets[0].source_reference_candidates == (SOURCE_ID,)
    assert "확인되지 않은" in targets[0].objective
    claims = repository.list_candidate_claims(
        _context(),
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
    )
    assert len(claims) == 1
    assert claims[0].source_id == SOURCE_ID
    assert "언급되어 있습니다" in claims[0].neutral_text


def test_material_difference_creates_neutral_conflict_target() -> None:
    index = InMemorySearchIndex()
    for source_id, text in (
        (
            UUID("00000000-0000-7000-8000-000000000010"),
            "ECS 운영에서 자동 롤백을 사용했습니다.",
        ),
        (
            UUID("00000000-0000-7000-8000-000000000011"),
            "ECS 운영에서 자동 롤백을 사용하지 않았습니다.",
        ),
    ):
        index.add(
            SearchDocument(
                document_id=str(source_id),
                company_id=COMPANY_ID,
                applicant_id=APPLICANT_ID,
                source_id=source_id,
                text=text,
                vector=_vector(),
                symbols=("ECS",),
                locator={"page": 3},
                ownership_confidence=1.0,
                embedding_model="test-static-embedding",
                embedding_version="test-static-v1",
                invitation_id=INVITATION_ID,
                competency_model_version_id=VERSION_ID,
                criterion_id=CRITERION_ID,
            )
        )
    repository = InMemorySubmissionRepository()
    verification_map = VerificationMapBuilder(
        repository=repository,
        retriever=HybridRetriever(index, HybridRetrievalConfig()),
        embedder=StaticTextEmbedder(_vector()),
        clock=FrozenClock(NOW),
    ).build(
        _context(),
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=VERSION_ID,
        criterion_version=1,
        criteria=(
            CriterionVerificationInput(
                criterion_id=CRITERION_ID,
                code="INCIDENT_RESPONSE",
                name="운영 문제 해결",
                description="ECS 장애 원인을 분석하고 복구한다.",
                required=True,
                weight=30,
                observable_dimensions=("롤백 방식",),
                follow_up_directions=("선택한 롤백 방식을 확인",),
                max_follow_ups=1,
                time_budget_seconds=300,
            ),
        ),
        requirements=(),
        material_version="analysis-2",
    )

    targets = repository.list_verification_targets(_context(), verification_map)
    conflicts = repository.list_claim_conflicts(
        _context(),
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
    )

    assert targets[0].target_type is VerificationTargetType.SOURCE_CONFLICT
    assert len(conflicts) == 1
    assert "차이" in conflicts[0].verification_objective
    assert "허위" not in conflicts[0].verification_objective


def test_requirement_only_boosts_priority_when_related_material_exists() -> None:
    context = _context()
    requirement = RequirementVerificationInput(
        statement="Java 기반 서비스 개발 경험",
        criterion_code="PROJECT_EXECUTION",
        required=True,
        priority=1,
    )
    criteria = (
        CriterionVerificationInput(
            criterion_id=CRITERION_ID,
            code="TECHNICAL_COMPETENCY",
            name="기술 역량",
            description="기술 선택과 구현 방식을 확인한다.",
            required=True,
            weight=30,
            observable_dimensions=("기술 선택 이유",),
            follow_up_directions=("구현 방식",),
            max_follow_ups=1,
            time_budget_seconds=300,
        ),
        CriterionVerificationInput(
            criterion_id=SECOND_CRITERION_ID,
            code="PROJECT_EXECUTION",
            name="프로젝트 실행 역량",
            description="프로젝트 목표와 본인 역할을 확인한다.",
            required=True,
            weight=40,
            observable_dimensions=("본인 역할",),
            follow_up_directions=("직접 수행한 작업",),
            max_follow_ups=1,
            time_budget_seconds=300,
        ),
    )

    empty_repository = InMemorySubmissionRepository()
    empty_map = VerificationMapBuilder(
        repository=empty_repository,
        retriever=HybridRetriever(InMemorySearchIndex(), HybridRetrievalConfig()),
        embedder=StaticTextEmbedder(_vector()),
        clock=FrozenClock(NOW),
    ).build(
        context,
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=VERSION_ID,
        criterion_version=1,
        criteria=criteria,
        requirements=(requirement,),
        material_version="analysis-empty",
    )
    empty_targets = empty_repository.list_verification_targets(context, empty_map)
    assert [target.criterion_id for target in empty_targets] == [
        CRITERION_ID,
        SECOND_CRITERION_ID,
    ]
    assert [target.priority for target in empty_targets] == [20, 21]

    index = InMemorySearchIndex()
    index.add(
        SearchDocument(
            document_id=str(SOURCE_ID),
            company_id=COMPANY_ID,
            applicant_id=APPLICANT_ID,
            source_id=SOURCE_ID,
            text="Java와 Spring Boot로 주문 서비스 API를 직접 개발했습니다.",
            vector=_vector(),
            symbols=("Java", "Spring"),
            locator={"page": 1},
            ownership_confidence=1.0,
            embedding_model="test-static-embedding",
            embedding_version="test-static-v1",
            invitation_id=INVITATION_ID,
            competency_model_version_id=VERSION_ID,
            criterion_id=SECOND_CRITERION_ID,
        )
    )
    matched_repository = InMemorySubmissionRepository()
    matched_map = VerificationMapBuilder(
        repository=matched_repository,
        retriever=HybridRetriever(index, HybridRetrievalConfig()),
        embedder=StaticTextEmbedder(_vector()),
        clock=FrozenClock(NOW),
    ).build(
        context,
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=VERSION_ID,
        criterion_version=2,
        criteria=criteria,
        requirements=(requirement,),
        material_version="analysis-matched",
    )
    matched_targets = matched_repository.list_verification_targets(context, matched_map)
    assert matched_targets[0].criterion_id == SECOND_CRITERION_ID
    assert matched_targets[0].priority == 1
