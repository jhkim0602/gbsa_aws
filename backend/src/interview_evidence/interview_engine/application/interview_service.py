from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from interview_evidence.interview_engine.adapters.polly import (
    SpeechOutput,
    SpeechSynthesisAdapter,
)
from interview_evidence.interview_engine.adapters.retrieval_client import (
    RetrievalClient,
    RetrievedContext,
)
from interview_evidence.interview_engine.application.answer_evidence import (
    missing_answer_evidence,
)
from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.context_builder import (
    ContextBuilder,
    ContextTurn,
    RetrievedSourceContext,
)
from interview_evidence.interview_engine.application.idempotency import IdempotencyStore
from interview_evidence.interview_engine.application.interview_plan import (
    INTERVIEW_STAGE_FOCUS,
    InterviewStage,
    VerificationTargetPlan,
    is_follow_up_question_type,
    stage_verification_objective,
)
from interview_evidence.interview_engine.application.question_generator import (
    QuestionGenerationUnavailable,
    QuestionGenerator,
)
from interview_evidence.interview_engine.application.question_policy import (
    QuestionDraft,
    QuestionPolicy,
    stage_fallback_question,
)
from interview_evidence.interview_engine.application.recovery_service import (
    RecoveryMessage,
    RecoveryService,
)
from interview_evidence.interview_engine.application.state_machine import SessionStateMachine
from interview_evidence.interview_engine.domain.session import InterviewSessionState
from interview_evidence.interview_engine.domain.turn import (
    HotViewSyncStatus,
    InterviewTurn,
    QuestionRationale,
    QuestionSourceReference,
    TurnSpeaker,
    TurnStatus,
    VerificationProgress,
    VerificationProgressState,
)
from interview_evidence.interview_engine.repositories.postgres import InterviewRepository
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    MAX_FOLLOW_UPS,
    InterviewLevel,
)
from interview_evidence.shared.messaging.outbox import Outbox, OutboxEvent
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class InterviewPipelineResult:
    answer: RecoveryMessage
    question_turn: InterviewTurn
    source_references: tuple[QuestionSourceReference, ...]
    speech: SpeechOutput
    policy_reason_codes: tuple[str, ...]


class InterviewService:
    def __init__(
        self,
        *,
        repository: InterviewRepository,
        idempotency: IdempotencyStore,
        recovery: RecoveryService,
        checkpoints: CheckpointService,
        context_builder: ContextBuilder,
        retrieval: RetrievalClient,
        generator: QuestionGenerator,
        policy: QuestionPolicy,
        speech: SpeechSynthesisAdapter,
        outbox: Outbox | None = None,
    ) -> None:
        self._repository = repository
        self._idempotency = idempotency
        self._recovery = recovery
        self._checkpoints = checkpoints
        self._context_builder = context_builder
        self._retrieval = retrieval
        self._generator = generator
        self._policy = policy
        self._speech = speech
        self._outbox = outbox
        self._state_machine = SessionStateMachine()

    def finalize_answer_and_generate(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        expected_sequence: int,
        answer_turn_id: UUID,
        answer_text: str,
        last_recording_chunk_sequence: int,
        idempotency_key: str,
        target_criterion_id: UUID,
        allowed_criterion_ids: frozenset[UUID],
        prohibited_topics: tuple[str, ...],
        previous_questions: tuple[str, ...],
        fallback_question: str,
        remaining_criterion_ids: tuple[UUID, ...],
        remaining_time_seconds: int,
        query_vector: tuple[float, ...] | None,
        model_config_version: str,
        retrieval_config_version: str,
        voice_id: str,
        occurred_at: datetime,
        interview_level: InterviewLevel = DEFAULT_INTERVIEW_LEVEL,
        interview_stage: InterviewStage = InterviewStage.TECHNICAL,
        question_type: str = "adaptive",
        answered_stage: InterviewStage | None = None,
        answered_target: VerificationTargetPlan | None = None,
        question_target: VerificationTargetPlan | None = None,
        existing_progress: VerificationProgress | None = None,
    ) -> InterviewPipelineResult:
        return self._idempotency.execute(
            context,
            session_id=session_id,
            operation="answer.pipeline",
            idempotency_key=idempotency_key,
            request_payload={
                "answer_turn_id": str(answer_turn_id),
                "answer_sha256": sha256(answer_text.encode("utf-8")).hexdigest(),
                "expected_sequence": expected_sequence,
                "last_recording_chunk_sequence": last_recording_chunk_sequence,
                "target_criterion_id": str(target_criterion_id),
                "model_config_version": model_config_version,
                "retrieval_config_version": retrieval_config_version,
                "interview_stage": interview_stage.value,
                "question_type": question_type,
            },
            execute=lambda: self._run_pipeline(
                context,
                session_id=session_id,
                expected_sequence=expected_sequence,
                answer_turn_id=answer_turn_id,
                answer_text=answer_text,
                last_recording_chunk_sequence=last_recording_chunk_sequence,
                idempotency_key=idempotency_key,
                target_criterion_id=target_criterion_id,
                allowed_criterion_ids=allowed_criterion_ids,
                prohibited_topics=prohibited_topics,
                previous_questions=previous_questions,
                fallback_question=fallback_question,
                remaining_criterion_ids=remaining_criterion_ids,
                remaining_time_seconds=remaining_time_seconds,
                query_vector=query_vector,
                model_config_version=model_config_version,
                retrieval_config_version=retrieval_config_version,
                voice_id=voice_id,
                occurred_at=occurred_at,
                interview_level=interview_level,
                interview_stage=interview_stage,
                question_type=question_type,
                answered_stage=answered_stage,
                answered_target=answered_target,
                question_target=question_target,
                existing_progress=existing_progress,
            ),
            occurred_at=occurred_at,
        )

    def _run_pipeline(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        expected_sequence: int,
        answer_turn_id: UUID,
        answer_text: str,
        last_recording_chunk_sequence: int,
        idempotency_key: str,
        target_criterion_id: UUID,
        allowed_criterion_ids: frozenset[UUID],
        prohibited_topics: tuple[str, ...],
        previous_questions: tuple[str, ...],
        fallback_question: str,
        remaining_criterion_ids: tuple[UUID, ...],
        remaining_time_seconds: int,
        query_vector: tuple[float, ...] | None,
        model_config_version: str,
        retrieval_config_version: str,
        voice_id: str,
        occurred_at: datetime,
        interview_level: InterviewLevel,
        interview_stage: InterviewStage,
        question_type: str,
        answered_stage: InterviewStage | None,
        answered_target: VerificationTargetPlan | None,
        question_target: VerificationTargetPlan | None,
        existing_progress: VerificationProgress | None,
    ) -> InterviewPipelineResult:
        answer = self._recovery.finalize_answer(
            context,
            session_id=session_id,
            expected_sequence=expected_sequence,
            answer_turn_id=answer_turn_id,
            text=answer_text,
            last_recording_chunk_sequence=last_recording_chunk_sequence,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
        )
        if answer.message_type != "answer.accepted":
            raise ValueError("stale answer cannot generate a new question")

        session = self._repository.get_session(context, session_id)
        self._record_answer_progress(
            context,
            session_id=session_id,
            applicant_id=session.applicant_id,
            answer_turn_id=answer_turn_id,
            answered_stage=answered_stage,
            question_stage=interview_stage,
            answered_target=answered_target,
            question_target=question_target,
            existing_progress=existing_progress,
            next_question_type=question_type,
            occurred_at=occurred_at,
        )
        retrieval = self._retrieval.retrieve(
            context,
            applicant_id=session.applicant_id,
            invitation_id=session.invitation_id,
            competency_model_version_id=session.competency_model_version_id,
            session_id=session_id,
            query=_retrieval_query(
                answer_text=answer_text,
                interview_stage=interview_stage,
                question_target=question_target,
            ),
            query_vector=query_vector,
            criterion_id=target_criterion_id,
            config_version=retrieval_config_version,
            interview_stage=interview_stage,
        )
        project_reference_ids = {
            reference_id
            for rationale in self._repository.list_question_rationales(context, session_id)
            if rationale.interview_stage == InterviewStage.PROJECT_DEEP_DIVE.value
            for reference_id in rationale.source_reference_ids
        }
        requires_git_question = interview_stage is InterviewStage.PROJECT_DEEP_DIVE and not any(
            reference.source_reference_id in project_reference_ids
            and reference.source_type in {"candidate_code_unit", "repository_overview"}
            for reference in self._repository.list_session_source_references(
                context,
                session_id,
            )
        )
        git_hit = next(
            (hit for hit in retrieval.hits if hit.source_type == "repository_overview"),
            None,
        ) or next(
            (hit for hit in retrieval.hits if hit.source_type == "candidate_code_unit"),
            None,
        )
        turns = self._repository.list_final_turns(context, session_id)
        company_required_question = (
            question_target is not None
            and question_target.target_type == "company_required_question"
        )
        effective_question_type = "company_required" if company_required_question else question_type
        verification_objective = (
            question_target.objective
            if company_required_question and question_target is not None
            else (
                stage_verification_objective(interview_stage, question_target)
                if question_target
                else ""
            )
        )
        answer_evidence_gaps = (
            missing_answer_evidence(answer_text, interview_stage.value)
            if question_type == "follow_up" and answered_stage is interview_stage
            else ()
        )
        # Requirements are assessed in the report; only explicit company questions are
        # copied verbatim into the interview question stream.
        required_assessment_axis = None
        built_context = self._context_builder.build(
            recent_turns=tuple(
                ContextTurn(
                    turn_id=turn.turn_id,
                    speaker=turn.speaker.value,
                    text=turn.text or "",
                )
                for turn in turns
            ),
            older_summary="",
            remaining_criterion_ids=remaining_criterion_ids,
            remaining_time_seconds=remaining_time_seconds,
            interview_stage=interview_stage.value,
            interview_stage_focus=INTERVIEW_STAGE_FOCUS[interview_stage],
            next_question_type=effective_question_type,
            required_assessment_axis=required_assessment_axis,
            retrieved_source_ids=tuple(hit.source_id for hit in retrieval.hits),
            retrieved_sources=tuple(
                RetrievedSourceContext(
                    source_id=hit.source_id,
                    source_type=hit.source_type,
                    locator=hit.locator,
                    excerpt=hit.excerpt,
                    score=hit.score,
                    material_type=hit.material_type,
                )
                for hit in retrieval.hits
            ),
            criterion_text=(question_target.criterion_text if question_target else ""),
            verification_objective=verification_objective,
            missing_dimensions=(question_target.missing_dimensions if question_target else ()),
            follow_up_directions=(question_target.follow_up_directions if question_target else ()),
            answer_evidence_gaps=answer_evidence_gaps,
            stage_evidence_available=_stage_evidence_available(
                interview_stage,
                answer_text=answer_text,
                retrieval_hits=retrieval.hits,
            ),
        )
        try:
            draft = (
                QuestionDraft(
                    text=question_target.common_question,
                    target_criterion_id=target_criterion_id,
                    source_reference_ids=(),
                    model_config_version=model_config_version,
                    retrieval_config_version=retrieval_config_version,
                )
                if company_required_question and question_target is not None
                else self._generator.generate(
                    context,
                    target_criterion_id=target_criterion_id,
                    context_payload=built_context.model_payload(),
                    model_config_version=model_config_version,
                    retrieval_config_version=retrieval_config_version,
                    interview_level=interview_level,
                )
            )
        except QuestionGenerationUnavailable:
            current = self._repository.get_session(context, session_id)
            degraded = current.model_copy(
                update={
                    "degraded_modes": tuple(
                        dict.fromkeys((*current.degraded_modes, "question_generation"))
                    )
                }
            )
            self._repository.save_session(context, degraded)
            draft = QuestionDraft(
                text=stage_fallback_question(
                    interview_stage.value,
                    previous_questions=previous_questions,
                    default=fallback_question,
                    required_assessment_axis=required_assessment_axis,
                ),
                target_criterion_id=target_criterion_id,
                source_reference_ids=(),
                model_config_version=model_config_version,
                retrieval_config_version=retrieval_config_version,
            )
        retrieved_by_id = {hit.source_id: hit for hit in retrieval.hits}
        draft = draft.model_copy(
            update={
                "source_reference_ids": tuple(
                    source_id
                    for source_id in draft.source_reference_ids
                    if source_id in retrieved_by_id
                )
            }
        )
        if (
            not company_required_question
            and requires_git_question
            and git_hit is not None
            and git_hit.source_id not in draft.source_reference_ids
        ):
            draft = _git_project_question(
                hit=git_hit,
                target_criterion_id=target_criterion_id,
                model_config_version=model_config_version,
                retrieval_config_version=retrieval_config_version,
            )
        policy_result = self._policy.evaluate(
            draft,
            allowed_criterion_ids=allowed_criterion_ids,
            prohibited_topics=prohibited_topics,
            previous_questions=previous_questions,
            fallback_question=fallback_question,
            fallback_criterion_id=target_criterion_id,
            interview_stage=interview_stage.value,
            question_type=effective_question_type,
            required_assessment_axis=required_assessment_axis,
        )
        if {
            "stage_mismatch",
            "assessment_axis_mismatch",
            "code_level_question",
        }.intersection(policy_result.reason_codes):
            retry_payload = built_context.model_payload()
            retry_payload["stage_alignment_retry"] = {
                "interview_stage": interview_stage.value,
                "rejected_question": draft.text,
                "reason_codes": list(policy_result.reason_codes),
            }
            try:
                retried = self._generator.generate(
                    context,
                    target_criterion_id=target_criterion_id,
                    context_payload=retry_payload,
                    model_config_version=model_config_version,
                    retrieval_config_version=retrieval_config_version,
                    interview_level=interview_level,
                )
            except QuestionGenerationUnavailable:
                pass
            else:
                retried = retried.model_copy(
                    update={
                        "source_reference_ids": tuple(
                            source_id
                            for source_id in retried.source_reference_ids
                            if source_id in retrieved_by_id
                        )
                    }
                )
                policy_result = self._policy.evaluate(
                    retried,
                    allowed_criterion_ids=allowed_criterion_ids,
                    prohibited_topics=prohibited_topics,
                    previous_questions=previous_questions,
                    fallback_question=fallback_question,
                    fallback_criterion_id=target_criterion_id,
                    interview_stage=interview_stage.value,
                    question_type=effective_question_type,
                    required_assessment_axis=required_assessment_axis,
                )
        question = policy_result.question
        if not policy_result.accepted:
            question = question.model_copy(update={"source_reference_ids": ()})

        question_turn = self._repository.save_turn(
            context,
            InterviewTurn(
                turn_id=new_uuid7(occurred_at),
                company_id=session.company_id,
                interview_session_id=session_id,
                sequence=max((turn.sequence for turn in turns), default=0) + 1,
                speaker=TurnSpeaker.INTERVIEWER,
                status=TurnStatus.FINAL,
                text=question.text,
                target_criterion_id=question.target_criterion_id,
                idempotency_key=f"{idempotency_key}:question",
                model_config_version=question.model_config_version,
                finalized_at=occurred_at,
            ),
        )
        references = tuple(
            QuestionSourceReference(
                source_reference_id=new_uuid7(occurred_at),
                company_id=session.company_id,
                interview_session_id=session_id,
                question_turn_id=question_turn.turn_id,
                source_id=source_id,
                source_type=retrieved_by_id[source_id].source_type,
                locator=retrieved_by_id[source_id].locator,
                excerpt=retrieved_by_id[source_id].excerpt[:2000],
                relevance_score=retrieved_by_id[source_id].score,
                ownership_confidence=retrieved_by_id[source_id].ownership_confidence,
                retrieval_config_version=question.retrieval_config_version,
                model_config_version=question.model_config_version,
                created_at=occurred_at,
            )
            for source_id in question.source_reference_ids
        )
        self._repository.save_question_source_references(context, references)
        if question_target is not None:
            self._repository.save_question_rationale(
                context,
                QuestionRationale(
                    question_rationale_id=new_uuid7(occurred_at),
                    company_id=session.company_id,
                    interview_session_id=session_id,
                    question_turn_id=question_turn.turn_id,
                    applicant_id=session.applicant_id,
                    competency_model_version_id=(session.competency_model_version_id),
                    criterion_id=question_target.criterion_id,
                    verification_target_id=(question_target.verification_target_id),
                    verification_target_type=question_target.target_type,
                    objective=verification_objective,
                    question_type=effective_question_type,
                    interview_stage=interview_stage.value,
                    retrieval_version=retrieval_config_version,
                    generation_version=model_config_version,
                    policy_result=(
                        "accepted"
                        if policy_result.accepted
                        else ",".join(policy_result.reason_codes)
                    ),
                    source_reference_ids=tuple(
                        reference.source_reference_id for reference in references
                    ),
                    created_at=occurred_at,
                ),
            )
        speech = self._speech.synthesize(
            context,
            text=question.text,
            voice_id=voice_id,
        )
        current = self._repository.get_session(context, session_id)
        in_progress = self._state_machine.transition(
            current,
            expected_sequence=current.session_sequence,
            target=InterviewSessionState.IN_PROGRESS,
        )
        transitioned = self._state_machine.transition(
            in_progress,
            expected_sequence=in_progress.session_sequence,
            target=InterviewSessionState.AWAITING_ANSWER,
        )
        active_degraded_modes = tuple(
            mode for mode in (retrieval.degraded_mode, speech.degraded_mode) if mode is not None
        )
        if active_degraded_modes:
            transitioned = transitioned.model_copy(
                update={
                    "degraded_modes": tuple(
                        dict.fromkeys((*transitioned.degraded_modes, *active_degraded_modes))
                    )
                }
            )
        self._repository.save_session(context, transitioned)
        self._checkpoints.create(
            context,
            session_id=session_id,
            last_final_turn_id=question_turn.turn_id,
            last_media_chunk_sequence=last_recording_chunk_sequence,
            pending_turn_id=question_turn.turn_id,
            hot_view_sync_status=HotViewSyncStatus.PENDING,
            occurred_at=occurred_at,
        )
        return InterviewPipelineResult(
            answer=answer,
            question_turn=question_turn,
            source_references=references,
            speech=speech,
            policy_reason_codes=policy_result.reason_codes,
        )

    def finalize_answer_and_complete(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        expected_sequence: int,
        answer_turn_id: UUID,
        answer_text: str,
        last_recording_chunk_sequence: int,
        idempotency_key: str,
        answered_target: VerificationTargetPlan | None,
        answered_stage: InterviewStage | None,
        existing_progress: VerificationProgress | None,
        occurred_at: datetime,
    ) -> RecoveryMessage:
        answer = self._recovery.finalize_answer(
            context,
            session_id=session_id,
            expected_sequence=expected_sequence,
            answer_turn_id=answer_turn_id,
            text=answer_text,
            last_recording_chunk_sequence=last_recording_chunk_sequence,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
        )
        if answer.message_type != "answer.accepted":
            return answer
        session = self._repository.get_session(context, session_id)
        self._record_answer_progress(
            context,
            session_id=session_id,
            applicant_id=session.applicant_id,
            answer_turn_id=answer_turn_id,
            answered_stage=answered_stage,
            question_stage=None,
            answered_target=answered_target,
            question_target=None,
            existing_progress=existing_progress,
            next_question_type=None,
            occurred_at=occurred_at,
        )
        in_progress = self._state_machine.transition(
            session,
            expected_sequence=session.session_sequence,
            target=InterviewSessionState.IN_PROGRESS,
        )
        completed = self._state_machine.transition(
            in_progress,
            expected_sequence=in_progress.session_sequence,
            target=InterviewSessionState.COMPLETED,
        ).model_copy(update={"completed_at": occurred_at})
        self._repository.save_session(context, completed)
        self._checkpoints.create(
            context,
            session_id=session_id,
            last_final_turn_id=answer_turn_id,
            last_media_chunk_sequence=last_recording_chunk_sequence,
            pending_turn_id=None,
            hot_view_sync_status=HotViewSyncStatus.PENDING,
            occurred_at=occurred_at,
        )
        if self._outbox is not None:
            self._outbox.append(
                OutboxEvent(
                    outbox_event_id=new_uuid7(occurred_at),
                    company_id=session.company_id,
                    aggregate_type="interview_session",
                    aggregate_id=session_id,
                    aggregate_version=completed.session_sequence,
                    event_type="interview.completed",
                    event_version=1,
                    payload={
                        "interview_session_id": str(session_id),
                        "invitation_id": str(session.invitation_id),
                        "last_turn_id": str(answer_turn_id),
                        "completed_at": occurred_at.isoformat(),
                        "media_status": "pending",
                    },
                    idempotency_key=f"interview-completed-{session_id}",
                    trace_id=context.trace_id,
                    occurred_at=occurred_at,
                )
            )
        return answer

    def _record_answer_progress(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        applicant_id: UUID,
        answer_turn_id: UUID,
        answered_stage: InterviewStage | None,
        question_stage: InterviewStage | None,
        answered_target: VerificationTargetPlan | None,
        question_target: VerificationTargetPlan | None,
        existing_progress: VerificationProgress | None,
        next_question_type: str | None,
        occurred_at: datetime,
    ) -> None:
        if answered_target is None:
            return
        if existing_progress is not None and existing_progress.state in {
            VerificationProgressState.COMPLETED,
            VerificationProgressState.EXHAUSTED,
        }:
            return
        follows_same_target = (
            next_question_type is not None
            and is_follow_up_question_type(next_question_type)
            and question_target is not None
            and question_target.verification_target_id == answered_target.verification_target_id
            and answered_stage is not None
            and answered_stage is question_stage
        )
        previous_follow_up_count = (
            existing_progress.follow_up_count if existing_progress is not None else 0
        )
        next_follow_up_count = min(
            MAX_FOLLOW_UPS,
            previous_follow_up_count + (1 if follows_same_target else 0),
        )
        progress_state = (
            VerificationProgressState.EXHAUSTED
            if follows_same_target and previous_follow_up_count >= MAX_FOLLOW_UPS
            else (
                VerificationProgressState.IN_PROGRESS
                if follows_same_target
                else VerificationProgressState.COMPLETED
            )
        )
        self._repository.save_verification_progress(
            context,
            VerificationProgress(
                verification_progress_id=(
                    existing_progress.verification_progress_id
                    if existing_progress is not None
                    else new_uuid7(occurred_at)
                ),
                company_id=context.company_id,
                interview_session_id=session_id,
                applicant_id=applicant_id,
                verification_target_id=(answered_target.verification_target_id),
                criterion_id=answered_target.criterion_id,
                state=progress_state,
                follow_up_count=next_follow_up_count,
                final_answer_turn_ids=tuple(
                    dict.fromkeys(
                        (
                            *(existing_progress.final_answer_turn_ids if existing_progress else ()),
                            answer_turn_id,
                        )
                    )
                ),
                updated_at=occurred_at,
            ),
        )


def _retrieval_query(
    *,
    answer_text: str,
    interview_stage: InterviewStage,
    question_target: VerificationTargetPlan | None,
) -> str:
    target_parts = (
        (
            stage_verification_objective(interview_stage, question_target),
            *question_target.missing_dimensions,
        )
        if question_target is not None
        else ()
    )
    return " ".join(
        part.strip()
        for part in (
            INTERVIEW_STAGE_FOCUS[interview_stage],
            *target_parts,
            answer_text,
        )
        if part.strip()
    )


_BEHAVIORAL_CONTEXT_TERMS = (
    "팀",
    "팀원",
    "동료",
    "협업",
    "조율",
    "소통",
    "피드백",
    "합의",
    "설득",
    "갈등",
    "역할",
    "책임",
)


def _stage_evidence_available(
    interview_stage: InterviewStage,
    *,
    answer_text: str,
    retrieval_hits: tuple[RetrievedContext, ...],
) -> bool:
    if interview_stage is not InterviewStage.BEHAVIORAL:
        return True
    combined = " ".join((answer_text, *(hit.excerpt for hit in retrieval_hits))).casefold()
    return any(term.casefold() in combined for term in _BEHAVIORAL_CONTEXT_TERMS)


def _git_project_question(
    *,
    hit: RetrievedContext,
    target_criterion_id: UUID,
    model_config_version: str,
    retrieval_config_version: str,
) -> QuestionDraft:
    return QuestionDraft(
        text=(
            "이번에는 GitHub 프로젝트를 바탕으로 여쭤보겠습니다. 이 프로젝트의 주요 구성 요소와 "
            "각각의 책임을 어떻게 나누었고, 그 구조를 선택한 이유를 설명해 주세요."
        ),
        target_criterion_id=target_criterion_id,
        source_reference_ids=(hit.source_id,),
        model_config_version=model_config_version,
        retrieval_config_version=retrieval_config_version,
    )
