from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import cast
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from interview_evidence.company_management.api import LaneARuntime
from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.integration.interview_reporting import (
    FinalTurnRange,
    InterviewReportingBoundary,
)
from interview_evidence.integration.reporting_company import ReportingCompanyBoundary
from interview_evidence.integration.submission_interview import (
    SubmissionInterviewBoundary,
)
from interview_evidence.interview_engine.adapters.polly import SpeechSynthesisAdapter
from interview_evidence.interview_engine.adapters.retrieval_client import RetrievalClient
from interview_evidence.interview_engine.api import LaneCRuntime
from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.context_builder import ContextBuilder
from interview_evidence.interview_engine.application.context_reconciliation import (
    ContextReconciler,
)
from interview_evidence.interview_engine.application.interview_service import InterviewService
from interview_evidence.interview_engine.application.question_generator import QuestionGenerator
from interview_evidence.interview_engine.application.question_policy import QuestionPolicy
from interview_evidence.interview_engine.application.recovery_service import RecoveryService
from interview_evidence.interview_engine.application.state_machine import SessionStateMachine
from interview_evidence.interview_engine.domain.session import InterviewSessionState
from interview_evidence.interview_engine.domain.turn import (
    RecordingChunk,
    RecordingUploadStatus,
)
from interview_evidence.main import LocalRuntime, create_local_runtime
from interview_evidence.reporting.api.company_routes import LaneDRuntime
from interview_evidence.shared.aws_clients.ports import (
    DeterministicAIModel,
    DeterministicTextToSpeech,
    InMemoryEmailSender,
)
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import (
    InMemorySearchIndex,
    SearchDocument,
)
from interview_evidence.submission_analysis.api import LaneBRuntime
from interview_evidence.submission_analysis.application.strategy_service import (
    StrategyService,
)
from interview_evidence.submission_analysis.domain.source import (
    SourceLocation,
    SourceReferenceCandidate,
    SubmissionChunk,
)
from interview_evidence.submission_analysis.domain.submission import (
    AnalysisStatus,
    SubmissionAnalysis,
    SubmissionStatus,
)
from interview_evidence.workers.reporting.report import CriterionInput, ReportGenerator

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
COMPANY_TOKEN = "company-e2e-token"
SECOND_COMPANY_ID = UUID("00000000-0000-7000-8000-000000000099")
SECOND_COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000098")
SECOND_COMPANY_TOKEN = "company-e2e-token-second"


@dataclass(frozen=True, slots=True)
class ThinJourneyResult:
    runtime: LocalRuntime
    company_context: TenantContext
    applicant_context: TenantContext
    invitation_id: UUID
    applicant_id: UUID
    upload_id: UUID
    session_id: UUID
    report_id: UUID
    analysis_ready: bool
    answer_turn_id: UUID
    question_turn_id: UUID
    question_source_reference_count: int
    evidence_answer_turn_id: UUID
    human_decision: str
    campaign_criterion_version_id: UUID
    strategy_criterion_version_id: UUID
    session_criterion_version_id: UUID
    report_criterion_version_id: UUID


def run_thin_journey() -> ThinJourneyResult:
    return asyncio.run(_run_thin_journey())


async def run_thin_journey_async() -> ThinJourneyResult:
    return await _run_thin_journey()


async def _run_thin_journey() -> ThinJourneyResult:
    principals = FakePrincipalProvider(
        company_principals={
            COMPANY_TOKEN: CompanyPrincipal(
                company_id=COMPANY_ID,
                company_user_id=COMPANY_USER_ID,
                identity_subject="local|company-reviewer",
            ),
            SECOND_COMPANY_TOKEN: CompanyPrincipal(
                company_id=SECOND_COMPANY_ID,
                company_user_id=SECOND_COMPANY_USER_ID,
                identity_subject="local|other-company-reviewer",
            ),
        }
    )
    runtime = create_local_runtime(company_principal_provider=principals)
    lane_a = cast(LaneARuntime, runtime.lanes["company_management"])
    lane_b = cast(LaneBRuntime, runtime.lanes["submission_analysis"])
    lane_c = cast(LaneCRuntime, runtime.lanes["interview_engine"])
    lane_d = cast(LaneDRuntime, runtime.lanes["reporting"])
    company_public = cast(
        CompanyManagementPublic,
        runtime.boundaries["company_management"],
    )
    submission_interview = cast(
        SubmissionInterviewBoundary,
        runtime.boundaries["submission_interview"],
    )
    interview_reporting = cast(
        InterviewReportingBoundary,
        runtime.boundaries["interview_reporting"],
    )
    reporting_company = cast(
        ReportingCompanyBoundary,
        runtime.boundaries["reporting_company"],
    )
    search_index = cast(InMemorySearchIndex, runtime.resources["search_index"])
    clock = cast(Clock, runtime.resources["clock"])

    company_headers = {"Authorization": f"Bearer {COMPANY_TOKEN}"}
    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
    ) as client:
        position = await client.post(
            "/v1/positions",
            headers={**company_headers, "Idempotency-Key": "e2e-position-0001"},
            json={
                "title": "백엔드 개발자",
                "description": "AWS 기반 면접 증거 플랫폼을 개발합니다.",
            },
        )
        assert position.status_code == 201
        position_id = UUID(position.json()["position_id"])

        criteria = await client.post(
            f"/v1/positions/{position_id}/competency-model-versions",
            headers={**company_headers, "Idempotency-Key": "e2e-criteria-0001"},
            json={
                "criteria": [
                    {
                        "code": "PROBLEM_SOLVING",
                        "name": "문제 해결",
                        "description": "대안과 근거를 설명한다.",
                        "weight": 1,
                        "good_evidence": {"signal": "tradeoff"},
                        "weak_evidence": {"signal": "unsupported"},
                        "abstain_guidance": "최종 답변 근거가 없으면 판단을 유보한다.",
                        "common_questions": ["어떤 대안을 비교했나요?"],
                        "required": True,
                    }
                ],
                "prohibited_topics": ["가족", "외모"],
                "interview_duration_minutes": 30,
                "persona_definition": {"name": "GBSA AI", "tone": "차분함"},
            },
        )
        assert criteria.status_code == 201
        criterion_version_id = UUID(criteria.json()["competency_model_version_id"])
        published = await client.post(
            f"/v1/competency-model-versions/{criterion_version_id}/publish",
            headers={
                **company_headers,
                "Idempotency-Key": "e2e-criteria-publish-0001",
                "If-Match-Version": "1",
            },
        )
        assert published.status_code == 200

        campaign = await client.post(
            "/v1/campaigns",
            headers={**company_headers, "Idempotency-Key": "e2e-campaign-0001"},
            json={
                "position_id": str(position_id),
                "competency_model_version_id": str(criterion_version_id),
                "name": "2026 백엔드 채용",
                "candidate_instructions": "조용한 환경에서 진행해 주세요.",
            },
        )
        assert campaign.status_code == 201
        campaign_id = UUID(campaign.json()["campaign_id"])
        campaign_publish = await client.post(
            f"/v1/campaigns/{campaign_id}/publish",
            headers={
                **company_headers,
                "Idempotency-Key": "e2e-campaign-publish-0001",
                "If-Match-Version": "1",
            },
        )
        assert campaign_publish.status_code == 200

        invitation = await client.post(
            f"/v1/campaigns/{campaign_id}/invitations",
            headers={**company_headers, "Idempotency-Key": "e2e-invitation-0001"},
            json={
                "applicants": [
                    {
                        "email": "applicant@example.com",
                        "display_name": "홍길동",
                    }
                ],
                "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            },
        )
        assert invitation.status_code == 202
        invitation_id = UUID(invitation.json()["invitations"][0]["invitation_id"])
        email_sender = cast(InMemoryEmailSender, lane_a.email_sender)
        invitation_url = str(email_sender.messages[-1].template_data["invitation_url"])
        raw_token = parse_qs(urlparse(invitation_url).query)["token"][0]

        exchange = await client.post(
            "/v1/applicant/access/exchange",
            headers={"Idempotency-Key": "e2e-token-exchange-0001"},
            json={"invitation_token": raw_token},
        )
        assert exchange.status_code == 204
        verified = await client.post(
            "/v1/applicant/identity-verifications",
            headers={"Idempotency-Key": "e2e-identity-verify-0001"},
            json={"display_name": "홍길동", "verification_value": "1234"},
        )
        assert verified.status_code == 200
        consent = await client.post(
            "/v1/applicant/consents",
            headers={"Idempotency-Key": "e2e-consent-record-0001"},
            json={
                "policy_version": "2026-08-v1",
                "accepted_purposes": [
                    "document_analysis",
                    "recording",
                    "ai_assessment",
                ],
                "consent_content_digest": "a" * 64,
            },
        )
        assert consent.status_code == 201

        session_cookie = client.cookies["iep_applicant_session"]
        applicant = lane_a.sessions.get_applicant_principal(session_cookie)
        company_context = TenantContext(
            company_id=COMPANY_ID,
            actor_type=ActorType.COMPANY_USER,
            actor_id=COMPANY_USER_ID,
            request_id=new_uuid7(),
            trace_id="e2e-company",
        )
        applicant_context = TenantContext(
            company_id=COMPANY_ID,
            actor_type=ActorType.APPLICANT,
            actor_id=applicant.applicant_id,
            request_id=applicant.session_id,
            trace_id="e2e-applicant",
        )

        upload = await client.post(
            "/v1/applicant/submissions/upload-intents",
            headers={"Idempotency-Key": "e2e-upload-intent-0001"},
            json={
                "source_type": "resume",
                "filename": "resume.pdf",
                "media_type": "application/pdf",
                "byte_size": 2048,
                "sha256": "b" * 64,
            },
        )
        assert upload.status_code == 201
        registered = await client.post(
            "/v1/applicant/submissions",
            headers={"Idempotency-Key": "e2e-register-file-0001"},
            json={
                "source_type": "resume",
                "upload_id": upload.json()["upload_id"],
            },
        )
        assert registered.status_code == 202
        submission_id = UUID(registered.json()["submission_id"])

        submission = lane_b.repository.get_submission(applicant_context, submission_id)
        analysis_id = new_uuid7()
        source_text = "결제 장애에서 캐시와 재처리 큐를 비교하고 큐를 선택했습니다."
        chunk_hash = sha256(source_text.encode()).hexdigest()
        lane_b.repository.save_analysis(
            applicant_context,
            SubmissionAnalysis(
                analysis_id=analysis_id,
                company_id=COMPANY_ID,
                submission_id=submission_id,
                analysis_version=1,
                extractor_version="local-textract-v1",
                chunk_config_version="local-chunk-v1",
                status=AnalysisStatus.READY,
                created_at=clock.now(),
            ),
        )
        chunk = SubmissionChunk(
            chunk_id=new_uuid7(),
            company_id=COMPANY_ID,
            applicant_id=applicant.applicant_id,
            submission_id=submission_id,
            analysis_id=analysis_id,
            source_location=SourceLocation(page_number=1, section="경력"),
            text_object_key=f"local/{submission_id}/chunk-1.txt",
            source_hash=submission.content_hash or "b" * 64,
            chunk_hash=chunk_hash,
            embedding_model="local-embedding",
            embedding_version="1",
            index_document_id=f"chunk-{submission_id}",
        )
        lane_b.repository.save_chunks(applicant_context, (chunk,))
        lane_b.repository.save_submission(
            applicant_context,
            submission.transition(SubmissionStatus.VALIDATING)
            .transition(SubmissionStatus.ANALYZING)
            .transition(SubmissionStatus.READY),
        )
        search_index.add(
            SearchDocument(
                document_id=chunk.index_document_id,
                company_id=COMPANY_ID,
                applicant_id=applicant.applicant_id,
                source_id=chunk.chunk_id,
                text=source_text,
                vector=(1.0, 0.0),
                symbols=(),
                locator=chunk.source_location.model_dump(mode="json", exclude_none=True),
                ownership_confidence=1,
            )
        )

        invitation_snapshot = company_public.authorize_invitation(
            company_context,
            invitation_id,
            required_state="consented",
        )
        campaign_snapshot = company_public.get_campaign_snapshot(
            company_context,
            invitation_snapshot.campaign_id,
        )
        criterion_snapshot = company_public.get_criterion_version(
            company_context,
            campaign_snapshot.competency_model_version_id,
        )
        criterion_id = criterion_snapshot.criteria[0].criterion_id
        source_candidate = SourceReferenceCandidate(
            source_id=chunk.chunk_id,
            source_type="submission_chunk",
            locator=chunk.source_location.model_dump(mode="json", exclude_none=True),
            content_hash=chunk.chunk_hash,
            relevance_score=1,
            ownership_confidence=1,
        )
        strategy = StrategyService(
            DeterministicAIModel(
                {
                    "verification_points": [
                        {
                            "criterion_id": str(criterion_id),
                            "prompt": "장애 대응 대안을 검증한다.",
                            "source_ids": [str(chunk.chunk_id)],
                        }
                    ],
                    "common_topics": ["문제 해결"],
                    "follow_up_directions": {str(criterion_id): ["대안 비교", "결과 검증"]},
                    "time_budget": {"total_seconds": 1800},
                    "required_evidence_plan": {str(criterion_id): 1},
                }
            ),
            model_config_version="local-strategy-v1",
            repository=lane_b.repository,
            outbox=lane_b.outbox,
            clock=clock,
        ).generate(
            applicant_context,
            invitation_id=invitation_id,
            applicant_id=applicant.applicant_id,
            competency_model_version_id=campaign_snapshot.competency_model_version_id,
            criterion_ids=(criterion_id,),
            source_candidates=(source_candidate,),
            strategy_version=1,
        )
        readiness = await client.get("/v1/applicant/analysis-status")
        assert readiness.status_code == 200
        assert readiness.json()["interview_ready"] is True

        equipment = await client.post(
            "/v1/applicant/equipment-checks",
            headers={"Idempotency-Key": "e2e-equipment-check-0001"},
            json={
                "camera": {"status": "ready", "sanitized_code": None},
                "microphone": {"status": "ready", "sanitized_code": None},
                "network": {"status": "ready", "sanitized_code": None},
            },
        )
        assert equipment.status_code == 201
        session_response = await client.post(
            "/v1/applicant/interview-sessions",
            headers={"Idempotency-Key": "e2e-interview-session-0001"},
            json={
                "equipment_check_id": equipment.json()["equipment_check_id"],
                "strategy_id": str(strategy.interview_strategy_id),
                "acknowledged_partial_analysis": False,
            },
        )
        assert session_response.status_code == 201
        session_id = UUID(session_response.json()["interview_session_id"])

        started = lane_c.service.start_session(
            applicant_context,
            applicant,
            session_id=session_id,
            expected_sequence=0,
            idempotency_key="e2e-session-start-0001",
        )
        awaiting = SessionStateMachine().transition(
            started,
            expected_sequence=started.session_sequence,
            target=InterviewSessionState.AWAITING_ANSWER,
        )
        lane_c.repository.save_session(applicant_context, awaiting)
        recording = RecordingChunk(
            recording_chunk_id=new_uuid7(),
            company_id=COMPANY_ID,
            interview_session_id=session_id,
            sequence=1,
            object_key=f"local/{session_id}/recording-1.webm",
            content_hash="c" * 64,
            byte_size=4096,
            session_start_ms=0,
            session_end_ms=10_000,
            upload_status=RecordingUploadStatus.VERIFIED,
            idempotency_key="e2e-recording-verify-0001",
            created_at=clock.now(),
        )
        lane_c.repository.save_recording_chunk(applicant_context, recording)

        checkpoints = CheckpointService(lane_c.repository, lane_c.outbox)
        recovery = RecoveryService(
            repository=lane_c.repository,
            idempotency=lane_c.idempotency,
            checkpoints=checkpoints,
            reconciler=ContextReconciler(lane_c.repository, lane_c.hot_view),
        )
        pipeline = InterviewService(
            repository=lane_c.repository,
            idempotency=lane_c.idempotency,
            recovery=recovery,
            checkpoints=checkpoints,
            context_builder=ContextBuilder(token_budget=600),
            retrieval=RetrievalClient(submission_interview),
            generator=QuestionGenerator(
                DeterministicAIModel(
                    {
                        "text": "캐시 대신 재처리 큐를 선택한 기준은 무엇인가요?",
                        "target_criterion_id": str(criterion_id),
                        "source_reference_ids": [str(chunk.chunk_id)],
                    }
                )
            ),
            policy=QuestionPolicy(),
            speech=SpeechSynthesisAdapter(
                DeterministicTextToSpeech(
                    {
                        "audio_url": "https://local.invalid/question.mp3",
                        "audio_expires_at": "2026-08-15T10:00:00Z",
                        "speech_marks_url": None,
                    }
                )
            ),
        )
        answer_turn_id = new_uuid7()
        pipeline_result = pipeline.finalize_answer_and_generate(
            applicant_context,
            session_id=session_id,
            expected_sequence=awaiting.session_sequence,
            answer_turn_id=answer_turn_id,
            answer_text="캐시는 유실 가능성이 있어 내구성 있는 큐와 멱등 재처리를 선택했습니다.",
            last_recording_chunk_sequence=1,
            idempotency_key="e2e-answer-complete-0001",
            target_criterion_id=criterion_id,
            allowed_criterion_ids=frozenset({criterion_id}),
            prohibited_topics=campaign_snapshot.prohibited_topics,
            previous_questions=(),
            fallback_question=criterion_snapshot.criteria[0].common_questions[0],
            remaining_criterion_ids=(criterion_id,),
            remaining_time_seconds=900,
            query_vector=(1.0, 0.0),
            model_config_version="local-question-v1",
            retrieval_config_version="local-hybrid-v1",
            voice_id="Seoyeon",
            occurred_at=clock.now(),
        )
        current_session = lane_c.repository.get_session(applicant_context, session_id)
        completed = current_session.transition(
            InterviewSessionState.COMPLETED,
            occurred_at=clock.now(),
        )
        lane_c.repository.save_session(applicant_context, completed)

        turn_ranges = (
            FinalTurnRange(
                turn_id=answer_turn_id,
                session_start_ms=1_000,
                session_end_ms=4_000,
                confidence=0.96,
            ),
            FinalTurnRange(
                turn_id=pipeline_result.question_turn.turn_id,
                session_start_ms=5_000,
                session_end_ms=7_000,
                confidence=0.99,
            ),
        )
        interview_reporting.project_completed_session(
            company_context,
            session_id=session_id,
            turn_ranges=turn_ranges,
            output_object_key=f"local/{session_id}/final.m3u8",
            occurred_at=clock.now(),
        )
        transcripts = lane_d.repository.list_transcripts(company_context, session_id)
        answer_transcript = next(item for item in transcripts if item.turn_id == answer_turn_id)
        recording_asset = lane_d.repository.list_recording_assets(
            company_context,
            session_id,
        )[-1]
        report = cast(
            ReportGenerator,
            runtime.worker_handlers["report_generation"],
        ).generate(
            company_context,
            session_id=session_id,
            invitation_id=invitation_id,
            competency_model_version_id=criterion_version_id,
            criteria=(
                CriterionInput(
                    criterion_id=criterion_id,
                    observation="대안과 내구성 기준을 설명함",
                    answer_turn_id=answer_turn_id,
                    transcript=answer_transcript,
                    video_start_ms=1_000,
                    video_end_ms=4_000,
                ),
            ),
            recording=recording_asset,
            events=(),
            occurred_at=clock.now(),
        )
        report_response = await client.get(
            f"/v1/interview-sessions/{session_id}/report",
            headers=company_headers,
        )
        assert report_response.status_code == 200
        decision = await client.post(
            f"/v1/invitations/{invitation_id}/final-decisions",
            headers={
                **company_headers,
                "Idempotency-Key": "e2e-human-decision-0001",
            },
            json={
                "decision": "hold",
                "reason": "사람 면접에서 운영 규모를 추가 확인한다.",
            },
        )
        assert decision.status_code == 201

    review_projection = reporting_company.get_invitation_review(
        company_context,
        invitation_id=invitation_id,
    )
    assert review_projection is not None
    evidence = report.items[0].evidence[0]
    return ThinJourneyResult(
        runtime=runtime,
        company_context=company_context,
        applicant_context=applicant_context,
        invitation_id=invitation_id,
        applicant_id=applicant.applicant_id,
        upload_id=UUID(upload.json()["upload_id"]),
        session_id=session_id,
        report_id=report.report_id,
        analysis_ready=readiness.json()["interview_ready"],
        answer_turn_id=answer_turn_id,
        question_turn_id=pipeline_result.question_turn.turn_id,
        question_source_reference_count=len(pipeline_result.source_references),
        evidence_answer_turn_id=evidence.answer_turn_id,
        human_decision=review_projection.human_decision_status or "",
        campaign_criterion_version_id=campaign_snapshot.competency_model_version_id,
        strategy_criterion_version_id=strategy.competency_model_version_id,
        session_criterion_version_id=completed.competency_model_version_id,
        report_criterion_version_id=report.items[0].competency_model_version_id,
    )
