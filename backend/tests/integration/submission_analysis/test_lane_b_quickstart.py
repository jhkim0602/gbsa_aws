from datetime import UTC, datetime
from hashlib import sha256
from time import perf_counter
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.aws_clients.ports import (
    DeterministicAIModel,
    InMemoryObjectStorage,
)
from interview_evidence.shared.ids import FrozenClock, new_uuid7
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.postgres_hybrid import (
    PostgresHybridSearchIndex,
)
from interview_evidence.submission_analysis.adapters.search import (
    InMemorySearchIndex,
    SearchDocument,
)
from interview_evidence.submission_analysis.api import create_lane_b_runtime
from interview_evidence.submission_analysis.application.authorization import (
    FakeSubmissionAuthorization,
)
from interview_evidence.submission_analysis.application.deletion_targets import (
    SubmissionDeletionTargets,
)
from interview_evidence.submission_analysis.application.retrieval import (
    HybridRetrievalConfig,
    HybridRetriever,
)
from interview_evidence.submission_analysis.application.strategy_service import (
    StrategyService,
)
from interview_evidence.submission_analysis.domain.git_analysis import (
    CandidateCodeUnit,
    CommitIdentityInput,
    GitAnalysisStatus,
    GitCommitCandidate,
    GitRepositoryAnalysis,
    OwnershipClass,
)
from interview_evidence.submission_analysis.domain.source import (
    SourceReferenceCandidate,
    SubmissionChunk,
)
from interview_evidence.submission_analysis.domain.submission import (
    AnalysisStatus,
    SourceType,
    SubmissionAnalysis,
    SubmissionStatus,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    Base,
    InMemorySubmissionRepository,
)
from interview_evidence.workers.analysis.code_units import expand_python_code_units
from interview_evidence.workers.analysis.document_chunker import (
    ChunkingConfig,
    chunk_document,
)
from interview_evidence.workers.analysis.document_extract import (
    DeterministicTextract,
    DocumentExtractionAdapter,
    TextractPage,
)
from interview_evidence.workers.analysis.git_commits import (
    CommitDiff,
    analyze_candidate_commits,
)
from interview_evidence.workers.analysis.git_fetch import (
    BoundedGitFetcher,
    GitFetchLimits,
    RepositoryFile,
    RepositorySnapshot,
    StaticGitTransport,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000004")
CRITERION_VERSION_ID = UUID("00000000-0000-7000-8000-000000000005")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000006")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def system_context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000007"),
        trace_id="lane-b-quickstart",
    )


def _pilot_vector(first: float, second: float) -> tuple[float, ...]:
    return (first, second, *(0.0 for _ in range(1022)))


def test_pilot_scale_hybrid_retrieval_p95_is_below_one_second() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    query_vector = _pilot_vector(1.0, 0.0)

    with Session(engine) as session:
        index = PostgresHybridSearchIndex(session)
        for offset in range(200):
            source_id = UUID(int=1_000 + offset)
            index.add(
                SearchDocument(
                    document_id=str(source_id),
                    company_id=COMPANY_ID,
                    applicant_id=APPLICANT_ID,
                    source_id=source_id,
                    text=f"ECS 운영 장애 원인 분석과 복구 경험 {offset}",
                    vector=query_vector,
                    symbols=("ECS", "CloudWatch"),
                    locator={"page": offset + 1},
                    ownership_confidence=1.0,
                    invitation_id=INVITATION_ID,
                    competency_model_version_id=CRITERION_VERSION_ID,
                    criterion_id=CRITERION_ID,
                    embedding_model="amazon.titan-embed-text-v2:0",
                    embedding_version="titan-v2",
                )
            )
        session.commit()

        latencies: list[float] = []
        for _ in range(20):
            started_at = perf_counter()
            candidates = index.candidates(
                system_context(),
                applicant_id=APPLICANT_ID,
                invitation_id=INVITATION_ID,
                competency_model_version_id=CRITERION_VERSION_ID,
                criterion_id=CRITERION_ID,
                query="ECS 장애 복구",
                query_vector=query_vector,
                exact_symbol="ECS",
            )
            latencies.append(perf_counter() - started_at)

    p95_latency = sorted(latencies)[18]
    assert len(candidates) == 200
    assert p95_latency < 1.0


@pytest.mark.asyncio
async def test_applicant_can_register_only_one_public_github_project() -> None:
    principal = ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        session_id=SESSION_ID,
    )
    repository = InMemorySubmissionRepository()
    runtime = create_lane_b_runtime(
        principal_provider=FakePrincipalProvider(
            applicant_principals={"applicant-session": principal}
        ),
        authorization=FakeSubmissionAuthorization.allowed(principal),
        repository=repository,
        object_storage=InMemoryObjectStorage(),
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )

    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
        cookies={"iep_applicant_session": "applicant-session"},
    ) as client:
        missing_identity = await client.post(
            "/v1/applicant/submissions",
            headers={"Idempotency-Key": "project-missing-github-id"},
            json={
                "material_type": "projects",
                "source_type": "public_git",
                "public_url": "https://github.com/example/missing-identity",
                "candidate_identity_inputs": {},
            },
        )
        responses = [
            await client.post(
                "/v1/applicant/submissions",
                headers={"Idempotency-Key": f"project-submission-{index}"},
                json={
                    "material_type": "projects",
                    "source_type": "public_git",
                    "public_url": f"https://github.com/example/project-{index}",
                    "candidate_identity_inputs": {"claimed_handles": ["candidate-dev"]},
                },
            )
            for index in range(1, 3)
        ]

    assert missing_identity.status_code == 422
    assert missing_identity.json()["detail"] == (
        "exactly one candidate GitHub username is required"
    )
    assert responses[0].status_code == 202
    assert responses[0].json()["github_username"] == "candidate-dev"
    assert responses[1].status_code == 422
    assert responses[1].json()["detail"] == ("only one public GitHub project URL is allowed")
    assert len(repository.list_submissions(system_context(), APPLICANT_ID)) == 1


@pytest.mark.asyncio
async def test_failed_github_submission_is_requeued_when_submitted_again() -> None:
    principal = ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        session_id=SESSION_ID,
    )
    repository = InMemorySubmissionRepository()
    runtime = create_lane_b_runtime(
        principal_provider=FakePrincipalProvider(
            applicant_principals={"applicant-session": principal}
        ),
        authorization=FakeSubmissionAuthorization.allowed(principal),
        repository=repository,
        object_storage=InMemoryObjectStorage(),
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )
    request = {
        "material_type": "projects",
        "source_type": "public_git",
        "public_url": "https://github.com/example/retry-project",
        "candidate_identity_inputs": {"claimed_handles": ["candidate-dev"]},
    }
    headers = {"Idempotency-Key": "project-submission-retry"}

    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
        cookies={"iep_applicant_session": "applicant-session"},
    ) as client:
        created = await client.post(
            "/v1/applicant/submissions",
            headers=headers,
            json=request,
        )
        submission_id = UUID(created.json()["submission_id"])
        original_event = runtime.outbox.pending()[0]
        runtime.outbox.mark_published(original_event.outbox_event_id)
        failed = (
            repository.get_submission(system_context(), submission_id)
            .transition(SubmissionStatus.VALIDATING)
            .transition(SubmissionStatus.ANALYZING)
            .transition(
                SubmissionStatus.FAILED,
                failure_code="embedding_provider_unavailable",
                impact_summary="분석 실패",
            )
        )
        repository.save_submission(system_context(), failed)

        retried = await client.post(
            "/v1/applicant/submissions",
            headers=headers,
            json=request,
        )
        duplicate_retry = await client.post(
            "/v1/applicant/submissions",
            headers=headers,
            json=request,
        )

    assert created.status_code == 202
    assert retried.status_code == 202
    assert duplicate_retry.status_code == 202
    assert retried.json()["submission_id"] == str(submission_id)
    assert retried.json()["status"] == "validating"
    assert duplicate_retry.json()["status"] == "validating"
    retry_events = runtime.outbox.pending()
    assert len(retry_events) == 1
    assert retry_events[0].payload["analysis_version"] == 1
    assert retry_events[0].idempotency_key.startswith("analysis-retry-")


@pytest.mark.asyncio
async def test_lane_b_submission_to_traceable_strategy_journey() -> None:
    principal = ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        session_id=SESSION_ID,
    )
    repository = InMemorySubmissionRepository()
    runtime = create_lane_b_runtime(
        principal_provider=FakePrincipalProvider(
            applicant_principals={"applicant-session": principal}
        ),
        authorization=FakeSubmissionAuthorization.allowed(principal),
        repository=repository,
        object_storage=InMemoryObjectStorage(),
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )

    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
        cookies={"iep_applicant_session": "applicant-session"},
    ) as client:
        upload = await client.post(
            "/v1/applicant/submissions/upload-intents",
            headers={"Idempotency-Key": "quickstart-upload-intent"},
            json={
                "source_type": "resume",
                "filename": "resume.pdf",
                "media_type": "application/pdf",
                "byte_size": 2048,
                "sha256": "a" * 64,
            },
        )
        assert upload.status_code == 201
        registered_pdf = await client.post(
            "/v1/applicant/submissions",
            headers={"Idempotency-Key": "quickstart-register-pdf"},
            json={
                "material_type": "resume",
                "source_type": "resume",
                "upload_id": upload.json()["upload_id"],
            },
        )
        registered_git = await client.post(
            "/v1/applicant/submissions",
            headers={"Idempotency-Key": "quickstart-register-git"},
            json={
                "material_type": "projects",
                "source_type": "public_git",
                "public_url": "https://github.com/example/candidate-project",
                "candidate_identity_inputs": {
                    "claimed_names": ["홍길동"],
                    "claimed_emails": ["candidate@example.com"],
                    "claimed_handles": ["candidate-dev"],
                },
            },
        )
        assert registered_pdf.status_code == 202
        assert registered_git.status_code == 202

    submissions = repository.list_submissions(system_context(), APPLICANT_ID)
    pdf = next(item for item in submissions if item.source_type is SourceType.RESUME)
    git = next(item for item in submissions if item.source_type is SourceType.PUBLIC_GIT)
    assert git.candidate_identity_inputs == {
        "claimed_names": ("홍길동",),
        "claimed_emails": ("candidate@example.com",),
        "claimed_handles": ("candidate-dev",),
    }

    extraction = DocumentExtractionAdapter(
        DeterministicTextract(
            (
                TextractPage(
                    page_number=1,
                    lines=(
                        "경력",
                        "결제 장애율을 30% 줄이고 재처리 큐를 설계했습니다.",
                    ),
                ),
            )
        ),
        extractor_version="textract-v1",
    )
    pages = extraction.extract(system_context(), pdf.submission_id)
    drafts = chunk_document(
        pages,
        source_hash=pdf.content_hash or "",
        config=ChunkingConfig(version="chunk-v1", max_characters=200),
    )
    analysis_id = new_uuid7(NOW, random_bits=101)
    analysis = SubmissionAnalysis(
        analysis_id=analysis_id,
        company_id=COMPANY_ID,
        submission_id=pdf.submission_id,
        analysis_version=1,
        extractor_version=extraction.extractor_version,
        chunk_config_version="chunk-v1",
        status=AnalysisStatus.READY,
        created_at=NOW,
    )
    repository.save_analysis(system_context(), analysis)
    chunks = tuple(
        SubmissionChunk(
            chunk_id=new_uuid7(NOW, random_bits=200 + index),
            company_id=COMPANY_ID,
            applicant_id=APPLICANT_ID,
            submission_id=pdf.submission_id,
            analysis_id=analysis_id,
            source_location=draft.source_location,
            text_object_key=(
                f"tenants/{COMPANY_ID}/submission-derived/{pdf.submission_id}/{index}.txt"
            ),
            source_hash=draft.source_hash,
            chunk_hash=draft.chunk_hash,
            embedding_model="embed-v1",
            embedding_version="1",
            index_document_id=f"chunk-{index}",
        )
        for index, draft in enumerate(drafts, start=1)
    )
    repository.save_chunks(system_context(), chunks)
    repository.save_submission(
        system_context(),
        pdf.transition(SubmissionStatus.VALIDATING)
        .transition(SubmissionStatus.ANALYZING)
        .transition(SubmissionStatus.READY),
    )

    snapshot = BoundedGitFetcher(
        StaticGitTransport(
            RepositorySnapshot(
                repository_url=git.source_uri,
                default_branch="main",
                pinned_head_sha="b" * 40,
                files=(
                    RepositoryFile(
                        path="src/payment.py",
                        content=b"def retry_payment():\n    return True\n",
                    ),
                    RepositoryFile(
                        path="tests/test_payment.py",
                        content=(
                            b"from payment import retry_payment\n"
                            b"def test_retry_payment():\n"
                            b"    assert retry_payment()\n"
                        ),
                    ),
                    RepositoryFile(path=".env", content=b"SECRET=never-index"),
                    RepositoryFile(path="node_modules/pkg.js", content=b"ignored"),
                ),
                commit_count=12,
            )
        ),
        GitFetchLimits(),
    ).fetch(git.source_uri)
    assert [file.path for file in snapshot.files] == [
        "src/payment.py",
        "tests/test_payment.py",
    ]
    repository_analysis = GitRepositoryAnalysis(
        repository_analysis_id=new_uuid7(NOW, random_bits=301),
        company_id=COMPANY_ID,
        submission_id=git.submission_id,
        repository_url=snapshot.repository_url,
        default_branch=snapshot.default_branch,
        pinned_head_sha=snapshot.pinned_head_sha,
        candidate_identity_inputs={
            "claimed_names": ["홍길동"],
            "claimed_emails": ["candidate@example.com"],
        },
        limits_applied={"max_files": 2000, "max_commits": 500},
        status=GitAnalysisStatus.PARTIAL,
    )
    repository.save_git_repository_analysis(system_context(), repository_analysis)
    commit_analyses = analyze_candidate_commits(
        company_id=COMPANY_ID,
        repository_analysis_id=repository_analysis.repository_analysis_id,
        commits=(
            CommitDiff(
                candidate=GitCommitCandidate(
                    parent_sha="a" * 40,
                    commit_sha="b" * 40,
                    author_name="홍길동",
                    author_email="unverified@example.com",
                    changed_paths=("src/payment.py",),
                ),
                changed_line_count=2,
                summary_object_key=(f"tenants/{COMPANY_ID}/submission-derived/git/commit.json"),
            ),
        ),
        identity=CommitIdentityInput(
            claimed_names=("홍길동",),
        ),
    )
    repository.save_git_commit_analyses(system_context(), commit_analyses)
    assert commit_analyses[0].ownership_class is OwnershipClass.CONTEXT_ONLY
    assert commit_analyses[0].ownership_confidence < 0.5
    expanded_units = expand_python_code_units(
        path="src/payment.py",
        source=snapshot.files[0].content.decode(),
        changed_line_ranges=((1, 2),),
        related_files={
            snapshot.files[1].path: snapshot.files[1].content.decode(),
        },
    )
    code_units = tuple(
        CandidateCodeUnit(
            code_unit_id=new_uuid7(NOW, random_bits=400 + index),
            company_id=COMPANY_ID,
            git_commit_analysis_id=commit_analyses[0].git_commit_analysis_id,
            path=unit.path,
            language=unit.language,
            symbol=unit.symbol,
            original_line_range=unit.line_range,
            current_line_range=unit.line_range,
            authored_snapshot_key=(
                f"tenants/{COMPANY_ID}/submission-derived/git/authored-{index}.txt"
            ),
            current_snapshot_key=(
                f"tenants/{COMPANY_ID}/submission-derived/git/current-{index}.txt"
            ),
            candidate_owned_regions=unit.candidate_owned_regions,
            related_test_ids=unit.related_test_paths,
            index_document_ids=(f"code-unit-{index}",),
        )
        for index, unit in enumerate(expanded_units, start=1)
    )
    repository.save_code_units(system_context(), code_units)
    assert code_units[0].related_test_ids == ("tests/test_payment.py",)
    repository.save_submission(
        system_context(),
        git.transition(SubmissionStatus.VALIDATING)
        .transition(SubmissionStatus.ANALYZING)
        .transition(
            SubmissionStatus.PARTIAL,
            failure_code="git_history_limited",
            impact_summary="일부 커밋만 분석되어 면접에서 소유 범위를 확인합니다.",
        ),
    )

    index = InMemorySearchIndex()
    source_id = chunks[0].chunk_id
    index.add(
        SearchDocument(
            document_id=chunks[0].index_document_id,
            company_id=COMPANY_ID,
            applicant_id=APPLICANT_ID,
            source_id=source_id,
            text=drafts[0].text,
            vector=(1.0, 0.0),
            symbols=(),
            locator=chunks[0].source_location.model_dump(mode="json", exclude_none=True),
            ownership_confidence=1,
        )
    )
    index.add(
        SearchDocument(
            document_id=code_units[0].index_document_ids[0],
            company_id=COMPANY_ID,
            applicant_id=APPLICANT_ID,
            source_id=code_units[0].code_unit_id,
            text="retry_payment 결제 재시도 함수",
            vector=(0.4, 0.6),
            symbols=(code_units[0].symbol,),
            locator={
                "path": code_units[0].path,
                "symbol": code_units[0].symbol,
                "start_line": code_units[0].current_line_range[0],
                "end_line": code_units[0].current_line_range[1],
                "commit_sha": commit_analyses[0].commit_sha,
            },
            ownership_confidence=commit_analyses[0].ownership_confidence,
        )
    )
    index.add(
        SearchDocument(
            document_id="other-tenant",
            company_id=UUID("00000000-0000-7000-8000-000000000099"),
            applicant_id=APPLICANT_ID,
            source_id=UUID("00000000-0000-7000-8000-000000000098"),
            text="더 높은 관련도를 가진 다른 회사 자료",
            vector=(1.0, 0.0),
            symbols=(),
            locator={"page_number": 1},
            ownership_confidence=1,
        )
    )
    retrieved = HybridRetriever(index, HybridRetrievalConfig()).retrieve(
        system_context(),
        applicant_id=APPLICANT_ID,
        query="결제 장애 재처리",
        query_vector=(1.0, 0.0),
        limit=5,
    )
    assert retrieved[0].document_id == chunks[0].index_document_id
    assert "other-tenant" not in {result.document_id for result in retrieved}
    code_results = HybridRetriever(index, HybridRetrievalConfig()).retrieve(
        system_context(),
        applicant_id=APPLICANT_ID,
        query="retry_payment 재시도",
        query_vector=(1.0, 0.0),
        exact_symbol="retry_payment",
        limit=5,
    )
    assert code_results[0].document_id == code_units[0].index_document_ids[0]
    assert code_results[0].ownership_confidence < 0.5

    document_candidate = SourceReferenceCandidate(
        source_id=retrieved[0].source_id,
        source_type="submission_chunk",
        locator=retrieved[0].locator,
        content_hash=chunks[0].chunk_hash,
        relevance_score=retrieved[0].score,
        ownership_confidence=retrieved[0].ownership_confidence,
    )
    code_candidate = SourceReferenceCandidate(
        source_id=code_results[0].source_id,
        source_type="candidate_code_unit",
        locator=code_results[0].locator,
        content_hash=sha256(snapshot.files[0].content).hexdigest(),
        relevance_score=code_results[0].score,
        ownership_confidence=code_results[0].ownership_confidence,
    )
    strategy = StrategyService(
        DeterministicAIModel(
            {
                "common_topics": ["문제 해결"],
                "verification_points": [
                    {
                        "criterion_id": str(CRITERION_ID),
                        "prompt": "장애율 감소 방법과 대안을 확인한다.",
                        "source_ids": [
                            str(document_candidate.source_id),
                            str(code_candidate.source_id),
                        ],
                    }
                ],
                "follow_up_directions": {str(CRITERION_ID): ["재처리 큐의 트레이드오프를 묻는다."]},
                "time_budget": {"total_seconds": 1800},
                "required_evidence_plan": {str(CRITERION_ID): 1},
            }
        ),
        model_config_version="strategy-v1",
        repository=repository,
        outbox=runtime.outbox,
        clock=FrozenClock(NOW),
    ).generate(
        system_context(),
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        competency_model_version_id=CRITERION_VERSION_ID,
        criterion_ids=(CRITERION_ID,),
        source_candidates=(document_candidate, code_candidate),
        strategy_version=1,
    )
    assert repository.latest_strategy(system_context(), INVITATION_ID) == strategy
    assert runtime.outbox.pending()[-1].event_type == "strategy.ready"

    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
        cookies={"iep_applicant_session": "applicant-session"},
    ) as client:
        readiness = await client.get("/v1/applicant/analysis-status")
    assert readiness.status_code == 200
    assert readiness.json()["overall_status"] == "partial"
    assert readiness.json()["interview_ready"] is True
    assert readiness.json()["strategy_id"] == str(strategy.interview_strategy_id)

    targets = SubmissionDeletionTargets(repository).enumerate_owned_targets(
        system_context(),
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
    )
    assert {"aurora", "s3", "retrieval"} <= {target.store for target in targets}
    target_ids = {target.resource_id for target in targets}
    assert commit_analyses[0].change_summary_object_key in target_ids
    assert code_units[0].current_snapshot_key in target_ids
    assert code_units[0].index_document_ids[0] in target_ids
    assert sha256(drafts[0].text.encode("utf-8")).hexdigest() == chunks[0].chunk_hash
