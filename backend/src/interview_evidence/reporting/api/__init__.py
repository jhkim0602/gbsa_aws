from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.orm import Session

from interview_evidence.reporting.api.company_routes import (
    LaneDRuntime,
    create_lane_d_app,
    create_lane_d_runtime,
)
from interview_evidence.reporting.domain.report import (
    AssessmentState,
    AxisAssessment,
    Evidence,
    Report,
    ReportItem,
    ReportKind,
    ReportStatus,
    Sufficiency,
)
from interview_evidence.reporting.domain.timeline import (
    RecordingAsset,
    RecordingStatus,
    TranscriptSegment,
)
from interview_evidence.reporting.repositories.postgres import (
    ReportingRepository,
    SQLAlchemyReportingRepository,
)
from interview_evidence.shared.tenant import ActorType, TenantContext


def create_sql_repository(session: Session) -> ReportingRepository:
    return SQLAlchemyReportingRepository(session)


@dataclass(frozen=True, slots=True)
class LocalDemoAnswerRange:
    """One seeded final answer as Lane C recorded it, in session-clock milliseconds."""

    turn_id: UUID
    #: The Turn the question was spoken on, as Lane C wrote it. The timeline attaches a
    #: question's rationale by this id, so a segment derived from anything else would show
    #: the question with no trace of the submitted material behind it.
    question_turn_id: UUID
    question_text: str
    answer_text: str
    session_start_ms: int
    session_end_ms: int


#: What the seeded report says about the one criterion the demo interview covered. The
#: scores are a plausible reading of the seeded answers rather than a flattering one: the
#: candidate hedged on measuring the index's write cost, so 본인 기여 lands mid-band and
#: CS 기본기 is left unjudged because the interview never went there. Written out rather
#: than generated so the local review screen shows the same thing on every machine.
_DEMO_AXES: tuple[tuple[str, str, int | None, str], ...] = (
    (
        "correctness",
        "정확성",
        64,
        "커넥션 풀 고갈과 p99 지연을 연결한 진단은 맞고, 풀 확대가 근본 원인이 아니라는 "
        "점도 스스로 구분했습니다. 다만 인덱스 추가가 쓰기 경로에 주는 비용을 '알고 있었다' "
        "수준에서 멈춰 정확성을 더 올리지는 못했습니다.",
    ),
    (
        "depth",
        "깊이",
        52,
        "왜 풀을 먼저 늘렸는지는 트래픽 시간대라는 근거로 설명했지만, 대안(타임아웃 조정, "
        "쿼리 차단)을 검토한 흔적은 없습니다. 한 겹 더 물었을 때 설명이 이어지긴 했으나 "
        "두 겹째에서 측정하지 못했다는 답으로 끝났습니다.",
    ),
    (
        "fundamentals",
        "CS 기본기",
        None,
        "커넥션 풀과 인덱스가 언급되었을 뿐, 자료구조·동시성·트랜잭션 같은 기반 지식을 "
        "확인할 질문이 면접에서 나오지 않았습니다. 다루지 않은 주제를 근거 없이 판단하지 "
        "않습니다.",
    ),
    (
        "ownership",
        "본인 기여",
        71,
        "지표 확인, 풀 조정, 실행 계획 재검토를 모두 1인칭으로 말했고, 쓰기 지연을 직접 "
        "측정하지 못했다는 한계도 먼저 밝혔습니다. 기여를 부풀린 흔적은 보이지 않습니다.",
    ),
    (
        "communication",
        "설명력",
        68,
        "증상에서 진단, 임시 조치, 근본 조치 순으로 따라갈 수 있게 설명했습니다. 모르는 "
        "부분을 모른다고 말한 점도 전달에 도움이 됩니다.",
    ),
)


def ensure_local_demo_review_projections(
    session: Session,
    *,
    company_id: UUID,
    company_user_id: UUID,
    interview_session_id: UUID,
    invitation_id: UUID,
    competency_model_version_id: UUID,
    criterion_id: UUID,
    criterion_name: str,
    answers: tuple[LocalDemoAnswerRange, ...],
    recording_object_key: str,
    recording_duration_ms: int,
    now: datetime,
) -> UUID:
    """Seed the transcript, recording and report a finished local demo session would have.

    The worker cascade that normally writes these needs a real media file and a model
    call, neither of which a seed can produce, so the projections are written directly.
    Every axis score cites the Evidence it rests on, the same rule the generated path is
    held to -- a seeded score a reviewer cannot play back would teach them to trust the
    number instead of the answer.
    """
    context = TenantContext(
        company_id=company_id,
        actor_type=ActorType.COMPANY_USER,
        actor_id=company_user_id,
        request_id=uuid5(NAMESPACE_URL, f"local-review-demo:{interview_session_id}"),
        trace_id="local-review-demo",
    )
    repository = SQLAlchemyReportingRepository(session)
    report_id = uuid5(NAMESPACE_URL, f"local-review-demo-report:{interview_session_id}")
    existing = repository.get_report_for_session(context, interview_session_id)
    if existing is not None:
        return existing.report_id

    completed_at = now - timedelta(hours=1)
    for answer in answers:
        repository.save_transcript(
            context,
            TranscriptSegment(
                transcript_segment_id=uuid5(NAMESPACE_URL, f"{answer.turn_id}:question-segment"),
                company_id=company_id,
                interview_session_id=interview_session_id,
                turn_id=answer.question_turn_id,
                speaker="interviewer",
                text=answer.question_text,
                confidence=1.0,
                # The question is spoken in the ten seconds before the answer window, so
                # the timeline reads question-then-answer instead of interleaving them.
                session_start_ms=max(answer.session_start_ms - 10_000, 0),
                session_end_ms=answer.session_start_ms,
                source_audio_key=recording_object_key,
                version=1,
                corrected_by=None,
                created_at=completed_at,
            ),
        )
        repository.save_transcript(
            context,
            TranscriptSegment(
                transcript_segment_id=_answer_segment_id(answer.turn_id),
                company_id=company_id,
                interview_session_id=interview_session_id,
                turn_id=answer.turn_id,
                speaker="applicant",
                text=answer.answer_text,
                confidence=0.94,
                session_start_ms=answer.session_start_ms,
                session_end_ms=answer.session_end_ms,
                source_audio_key=recording_object_key,
                version=1,
                corrected_by=None,
                created_at=completed_at,
            ),
        )
    repository.save_recording_asset(
        context,
        RecordingAsset(
            recording_asset_id=uuid5(
                NAMESPACE_URL, f"local-review-demo-asset:{interview_session_id}"
            ),
            company_id=company_id,
            interview_session_id=interview_session_id,
            asset_type="final_video",
            object_key=recording_object_key,
            content_hash=sha256(f"local-demo-asset:{interview_session_id}".encode()).hexdigest(),
            duration_ms=recording_duration_ms,
            status=RecordingStatus.READY,
            missing_ranges=(),
            created_at=completed_at,
        ),
    )

    report_item_id = uuid5(NAMESPACE_URL, f"{report_id}:item")
    evidence = tuple(
        Evidence(
            evidence_id=uuid5(NAMESPACE_URL, f"{report_item_id}:evidence:{index}"),
            company_id=company_id,
            report_item_id=report_item_id,
            criterion_id=criterion_id,
            competency_model_version_id=competency_model_version_id,
            answer_turn_id=answer.turn_id,
            transcript_segment_id=_answer_segment_id(answer.turn_id),
            video_start_ms=answer.session_start_ms,
            video_end_ms=answer.session_end_ms,
            observation=observation,
            rationale=rationale,
            sufficiency=sufficiency,
            generation_version="local-demo-seed",
            created_at=completed_at,
        )
        for index, (answer, (observation, rationale, sufficiency)) in enumerate(
            zip(answers, _DEMO_EVIDENCE, strict=True), start=1
        )
    )
    evidence_ids = tuple(item.evidence_id for item in evidence)
    repository.save_report(
        context,
        Report(
            report_id=report_id,
            company_id=company_id,
            interview_session_id=interview_session_id,
            invitation_id=invitation_id,
            version=1,
            kind=ReportKind.AI_ORIGINAL,
            model_version="local-demo-seed",
            prompt_version="local-demo-seed",
            config_version="local-demo-seed",
            status=ReportStatus.READY,
            summary=(
                "장애를 스스로 진단하고 임시 조치와 근본 조치를 구분한 점이 확인됩니다. "
                "다만 조치의 부작용을 직접 측정하지 못했다고 답해, 검증까지 책임지는 "
                "범위는 답변만으로 확인되지 않았습니다. 인용된 구간을 재생해 판단해 "
                "주세요."
            ),
            created_at=completed_at,
            items=(
                ReportItem(
                    report_item_id=report_item_id,
                    company_id=company_id,
                    report_id=report_id,
                    criterion_id=criterion_id,
                    criterion_name=criterion_name,
                    competency_model_version_id=competency_model_version_id,
                    assessment_state=AssessmentState.PARTIALLY_CONFIRMED,
                    observation=(
                        "결제 API 지연을 커넥션 풀 고갈로 진단하고 풀 확대로 급히 막은 뒤 "
                        "인덱스를 추가해 근본 원인을 처리했다고 설명했습니다."
                    ),
                    rationale=(
                        "문제 인지부터 조치까지의 순서와 각 판단의 이유가 본인 시점으로 "
                        "이어졌습니다. 조치의 부작용 측정은 수행하지 못했다고 밝혀 부분 "
                        "확인으로 둡니다."
                    ),
                    sufficiency=Sufficiency.DIRECT.value,
                    uncertainty=(
                        "인덱스 추가 후 쓰기 경로 영향은 지원자가 직접 측정하지 않아 "
                        "답변만으로는 확인할 수 없습니다."
                    ),
                    evidence=evidence,
                    follow_up_question=(
                        "인덱스를 추가한 뒤 쓰기 지연을 어떤 지표로 확인하겠습니까?"
                    ),
                    axis_assessments=tuple(
                        AxisAssessment(
                            axis=axis,
                            label=label,
                            score=score,
                            rationale=rationale,
                            # An unjudged axis cites nothing: there is no answer to point
                            # at, and the domain only requires citations behind a score.
                            quoted_evidence_ids=(() if score is None else evidence_ids),
                        )
                        for axis, label, score, rationale in _DEMO_AXES
                    ),
                ),
            ),
        ),
    )
    return report_id


def _answer_segment_id(turn_id: UUID) -> UUID:
    """The transcript segment an Evidence range points at, derived once so both agree."""
    return uuid5(NAMESPACE_URL, f"{turn_id}:answer-segment")


#: Observation, rationale and sufficiency per seeded answer, in the order the answers were
#: given. Kept beside the axes so a reviewer can check that every score's citation leads
#: to a real quoted range.
_DEMO_EVIDENCE: tuple[tuple[str, str, Sufficiency], ...] = (
    (
        "대시보드의 p99 지연 상승을 보고 커넥션 풀 대기를 먼저 확인했다고 말했습니다.",
        "증상에서 원인 가설로 넘어가는 경로를 본인이 밟았음을 보여주는 구간입니다.",
        Sufficiency.DIRECT,
    ),
    (
        "트래픽 시간대라 응답 회복이 급했다는 이유로 풀 확대를 먼저 선택했다고 말했습니다.",
        "임시 조치와 근본 조치를 구분해 판단한 근거가 직접 드러납니다.",
        Sufficiency.DIRECT,
    ),
    (
        "인덱스 추가 후 쓰기 지연을 직접 측정하지 못했고 전체 지표만 확인했다고 말했습니다.",
        "조치의 부작용 검증 범위가 어디서 멈췄는지 지원자 스스로 밝힌 구간입니다.",
        Sufficiency.SUPPORTING,
    ),
)


__all__ = [
    "LaneDRuntime",
    "LocalDemoAnswerRange",
    "create_lane_d_app",
    "create_lane_d_runtime",
    "create_sql_repository",
    "ensure_local_demo_review_projections",
]
