from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from interview_evidence.interview_engine.adapters.polly import (
    SpeechOutput,
    SpeechSynthesisAdapter,
)
from interview_evidence.interview_engine.api.websocket import (
    AudioChunkMetadata,
    ServerEnvelope,
    WebSocketEnvelope,
)
from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.idempotency import IdempotencyStore
from interview_evidence.interview_engine.application.interview_plan import (
    InterviewPlan,
    InterviewPlanProvider,
)
from interview_evidence.interview_engine.application.interview_service import InterviewService
from interview_evidence.interview_engine.application.session_service import (
    SessionApplicationService,
)
from interview_evidence.interview_engine.application.state_machine import SessionStateMachine
from interview_evidence.interview_engine.domain.session import (
    InterviewSession,
    InterviewSessionState,
)
from interview_evidence.interview_engine.domain.turn import (
    HotViewSyncStatus,
    InterviewTurn,
    QuestionRationale,
    TurnSpeaker,
    TurnStatus,
    VerificationProgress,
    VerificationProgressState,
)
from interview_evidence.interview_engine.repositories.postgres import InterviewRepository
from interview_evidence.shared.aws_clients.ports import SpeechToText
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import TenantContext


class LiveInterviewHandler:
    def __init__(
        self,
        *,
        repository: InterviewRepository,
        session_service: SessionApplicationService,
        interview_service: InterviewService,
        plan_provider: InterviewPlanProvider,
        speech_to_text: SpeechToText | None,
        speech: SpeechSynthesisAdapter,
        idempotency: IdempotencyStore,
        checkpoints: CheckpointService,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._session_service = session_service
        self._interview_service = interview_service
        self._plan_provider = plan_provider
        self._speech_to_text = speech_to_text
        self._speech = speech
        self._idempotency = idempotency
        self._checkpoints = checkpoints
        self._clock = clock
        self._state_machine = SessionStateMachine()

    def initial_question(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
        started: InterviewSession,
    ) -> ServerEnvelope:
        del principal
        return self._idempotency.execute(
            context,
            session_id=started.interview_session_id,
            operation="session.initial_question",
            idempotency_key=envelope.idempotency_key,
            request_payload={
                "strategy_id": str(started.interview_strategy_id),
                "server_sequence": started.session_sequence,
            },
            execute=lambda: self._create_initial_question(
                context,
                envelope=envelope,
                started=started,
            ),
            occurred_at=self._clock.now(),
        )

    def _create_initial_question(
        self,
        context: TenantContext,
        *,
        envelope: WebSocketEnvelope,
        started: InterviewSession,
    ) -> ServerEnvelope:
        plan = self._plan(started, context)
        initial_target = plan.initial_target()
        question_turn = self._repository.save_turn(
            context,
            InterviewTurn(
                turn_id=new_uuid7(self._clock.now()),
                company_id=started.company_id,
                interview_session_id=started.interview_session_id,
                sequence=self._next_turn_sequence(context, started.interview_session_id),
                speaker=TurnSpeaker.INTERVIEWER,
                status=TurnStatus.FINAL,
                text=plan.initial_question,
                target_criterion_id=(
                    initial_target.criterion_id
                    if initial_target is not None
                    else plan.criterion_ids[0]
                ),
                idempotency_key=f"{envelope.idempotency_key}:question",
                model_config_version=plan.model_config_version,
                finalized_at=self._clock.now(),
            ),
        )
        if initial_target is not None:
            self._repository.save_verification_progress(
                context,
                VerificationProgress(
                    verification_progress_id=new_uuid7(self._clock.now()),
                    company_id=started.company_id,
                    interview_session_id=started.interview_session_id,
                    applicant_id=started.applicant_id,
                    verification_target_id=(initial_target.verification_target_id),
                    criterion_id=initial_target.criterion_id,
                    state=VerificationProgressState.PENDING,
                    follow_up_count=0,
                    final_answer_turn_ids=(),
                    updated_at=self._clock.now(),
                ),
            )
            self._repository.save_question_rationale(
                context,
                QuestionRationale(
                    question_rationale_id=new_uuid7(self._clock.now()),
                    company_id=started.company_id,
                    interview_session_id=started.interview_session_id,
                    question_turn_id=question_turn.turn_id,
                    applicant_id=started.applicant_id,
                    competency_model_version_id=(started.competency_model_version_id),
                    criterion_id=initial_target.criterion_id,
                    verification_target_id=(initial_target.verification_target_id),
                    verification_target_type=initial_target.target_type,
                    objective=initial_target.objective,
                    question_type="common",
                    retrieval_version=plan.retrieval_config_version,
                    generation_version=plan.model_config_version,
                    policy_result="configured_common_question",
                    source_reference_ids=(),
                    created_at=self._clock.now(),
                ),
            )
        awaiting = self._state_machine.transition(
            started,
            expected_sequence=started.session_sequence,
            target=InterviewSessionState.AWAITING_ANSWER,
        )
        self._repository.save_session(context, awaiting)
        self._checkpoints.create(
            context,
            session_id=started.interview_session_id,
            last_final_turn_id=question_turn.turn_id,
            last_media_chunk_sequence=0,
            pending_turn_id=question_turn.turn_id,
            hot_view_sync_status=HotViewSyncStatus.PENDING,
            occurred_at=self._clock.now(),
        )
        speech = self._speech.synthesize(
            context,
            text=plan.initial_question,
            voice_id=plan.voice_id,
        )
        return self._question_message(
            envelope,
            sequence=awaiting.session_sequence,
            question_turn=question_turn,
            source_reference_count=0,
            speech=speech,
            voice_id=plan.voice_id,
        )

    def handle_audio(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
        metadata: AudioChunkMetadata,
        audio: bytes,
    ) -> tuple[ServerEnvelope, ...]:
        self._session_service.resume(context, principal, session_id=envelope.session_id)
        return self._idempotency.execute(
            context,
            session_id=envelope.session_id,
            operation="audio.chunk",
            idempotency_key=envelope.idempotency_key,
            request_payload={
                "answer_turn_id": str(metadata.answer_turn_id),
                "chunk_sequence": metadata.chunk_sequence,
                "sha256": metadata.sha256,
                "sample_rate_hz": metadata.sample_rate_hz,
            },
            execute=lambda: self._transcribe_once(
                context,
                envelope=envelope,
                metadata=metadata,
                audio=audio,
            ),
            occurred_at=self._clock.now(),
        )

    def _transcribe_once(
        self,
        context: TenantContext,
        *,
        envelope: WebSocketEnvelope,
        metadata: AudioChunkMetadata,
        audio: bytes,
    ) -> tuple[ServerEnvelope, ...]:
        if self._speech_to_text is None:
            return (
                self._error(
                    envelope,
                    code="TRANSCRIPTION_UNAVAILABLE",
                    message="음성 인식을 준비하고 있습니다. 연결을 유지해 주세요.",
                    retryable=True,
                ),
            )
        response = self._speech_to_text.transcribe(
            context,
            audio,
            sample_rate_hz=metadata.sample_rate_hz,
        )
        text = str(response.get("text", "")).strip()
        confidence = _bounded_confidence(response.get("confidence"))
        if not text:
            return (
                self._message(
                    envelope,
                    message_type="transcript.partial",
                    sequence=envelope.sequence,
                    payload={
                        "answer_turn_id": str(metadata.answer_turn_id),
                        "chunk_sequence": metadata.chunk_sequence,
                        "text": "",
                        "display_only": True,
                    },
                ),
            )
        draft = self._save_transcript_draft(
            context,
            session_id=envelope.session_id,
            answer_turn_id=metadata.answer_turn_id,
            text=text,
            idempotency_key=envelope.idempotency_key,
        )
        return (
            self._message(
                envelope,
                message_type="transcript.final",
                sequence=envelope.sequence,
                payload={
                    "answer_turn_id": str(draft.turn_id),
                    "chunk_sequence": metadata.chunk_sequence,
                    "text": text,
                    "confidence": confidence,
                    "review_required": confidence < 0.75,
                },
            ),
        )

    def record_streaming_transcript(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
        *,
        answer_turn_id: UUID,
        text: str,
        confidence: float,
        last_chunk_sequence: int,
    ) -> ServerEnvelope:
        self._session_service.resume(context, principal, session_id=envelope.session_id)
        return self._idempotency.execute(
            context,
            session_id=envelope.session_id,
            operation="transcript.streaming.final",
            idempotency_key=f"{envelope.idempotency_key}:transcript",
            request_payload={
                "answer_turn_id": str(answer_turn_id),
                "transcript_sha256": sha256(text.encode("utf-8")).hexdigest(),
                "last_chunk_sequence": last_chunk_sequence,
            },
            execute=lambda: self._record_streaming_transcript_once(
                context,
                envelope=envelope,
                answer_turn_id=answer_turn_id,
                text=text,
                confidence=confidence,
                last_chunk_sequence=last_chunk_sequence,
            ),
            occurred_at=self._clock.now(),
        )

    def _record_streaming_transcript_once(
        self,
        context: TenantContext,
        *,
        envelope: WebSocketEnvelope,
        answer_turn_id: UUID,
        text: str,
        confidence: float,
        last_chunk_sequence: int,
    ) -> ServerEnvelope:
        draft = self._save_transcript_draft(
            context,
            session_id=envelope.session_id,
            answer_turn_id=answer_turn_id,
            text=text,
            idempotency_key=f"{envelope.idempotency_key}:transcript",
            replace_existing=True,
        )
        return self._message(
            envelope,
            message_type="transcript.final",
            sequence=envelope.sequence,
            payload={
                "answer_turn_id": str(draft.turn_id),
                "chunk_sequence": last_chunk_sequence,
                "text": text,
                "confidence": confidence,
                "review_required": confidence < 0.75,
            },
        )

    def complete_answer(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
    ) -> ServerEnvelope:
        return self._idempotency.execute(
            context,
            session_id=envelope.session_id,
            operation="answer.websocket",
            idempotency_key=envelope.idempotency_key,
            request_payload={
                "answer_turn_id": str(envelope.payload.get("answer_turn_id", "")),
                "expected_sequence": envelope.sequence,
                "last_recording_chunk_sequence": _non_negative_int(
                    envelope.payload.get("last_recording_chunk_sequence")
                ),
            },
            execute=lambda: self._complete_answer_once(context, principal, envelope),
            occurred_at=self._clock.now(),
        )

    def complete_automated_answer(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
    ) -> ServerEnvelope:
        try:
            answer_turn_id = UUID(str(envelope.payload["answer_turn_id"]))
        except (KeyError, TypeError, ValueError):
            return self._error(
                envelope,
                code="AUTOMATED_ANSWER_INVALID",
                message="자동 답변 식별자가 올바르지 않습니다.",
                retryable=False,
            )
        text = str(envelope.payload.get("text", "")).strip()
        if not text or len(text) > 12_000:
            return self._error(
                envelope,
                code="AUTOMATED_ANSWER_INVALID",
                message="자동 답변 내용이 비어 있거나 너무 깁니다.",
                retryable=False,
            )
        self.record_streaming_transcript(
            context,
            principal,
            envelope,
            answer_turn_id=answer_turn_id,
            text=text,
            confidence=1.0,
            last_chunk_sequence=0,
        )
        return self.complete_answer(context, principal, envelope)

    def _complete_answer_once(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        envelope: WebSocketEnvelope,
    ) -> ServerEnvelope:
        self._session_service.resume(
            context,
            principal,
            session_id=envelope.session_id,
        )
        session = self._repository.get_session(context, envelope.session_id)
        try:
            answer_turn_id = UUID(str(envelope.payload["answer_turn_id"]))
            answer = self._repository.get_turn(context, answer_turn_id)
        except (KeyError, TypeError, ValueError, LookupError):
            return self._error(
                envelope,
                code="ANSWER_TRANSCRIPT_NOT_READY",
                message="확정 자막을 준비하고 있습니다. 잠시 후 다시 시도해 주세요.",
                retryable=True,
            )
        if (
            answer.interview_session_id != envelope.session_id
            or answer.speaker is not TurnSpeaker.APPLICANT
            or answer.status is not TurnStatus.RECORDING
            or not answer.text
        ):
            return self._error(
                envelope,
                code="ANSWER_TRANSCRIPT_NOT_READY",
                message="확정 자막을 준비하고 있습니다. 잠시 후 다시 시도해 주세요.",
                retryable=True,
            )
        plan = self._plan(session, context)
        final_turns = self._repository.list_final_turns(
            context,
            envelope.session_id,
        )
        previous_questions = tuple(
            turn.text or "" for turn in final_turns if turn.speaker is TurnSpeaker.INTERVIEWER
        )
        previous_question = next(
            (turn for turn in reversed(final_turns) if turn.speaker is TurnSpeaker.INTERVIEWER),
            None,
        )
        rationale = (
            self._repository.get_question_rationale(
                context,
                question_turn_id=previous_question.turn_id,
            )
            if previous_question is not None
            else None
        )
        progress_rows = self._repository.list_verification_progress(
            context,
            envelope.session_id,
        )
        progress_by_target = {
            progress.verification_target_id: progress for progress in progress_rows
        }
        answered_target = None
        question_target = None
        existing_progress = None
        if rationale is not None and plan.verification_targets:
            answered_target = plan.target(rationale.verification_target_id)
            existing_progress = progress_by_target.get(answered_target.verification_target_id)
            question_target = plan.next_target_after_answer(
                answered_target_id=answered_target.verification_target_id,
                follow_up_count=(
                    existing_progress.follow_up_count if existing_progress is not None else 0
                ),
                completed_target_ids=frozenset(
                    progress.verification_target_id
                    for progress in progress_rows
                    if progress.state
                    in {
                        VerificationProgressState.COMPLETED,
                        VerificationProgressState.EXHAUSTED,
                    }
                ),
                elapsed_seconds=self._elapsed_seconds(session),
            )
            if question_target is None:
                self._interview_service.finalize_answer_and_complete(
                    context,
                    session_id=envelope.session_id,
                    expected_sequence=envelope.sequence,
                    answer_turn_id=answer_turn_id,
                    answer_text=answer.text,
                    last_recording_chunk_sequence=_non_negative_int(
                        envelope.payload.get("last_recording_chunk_sequence")
                    ),
                    idempotency_key=envelope.idempotency_key,
                    answered_target=answered_target,
                    existing_progress=existing_progress,
                    occurred_at=self._clock.now(),
                )
                completed = self._repository.get_session(
                    context,
                    envelope.session_id,
                )
                return self._message(
                    envelope,
                    message_type="session.completed",
                    sequence=completed.session_sequence,
                    payload={
                        "state": completed.state.value,
                        "completed_at": (
                            completed.completed_at.isoformat()
                            if completed.completed_at is not None
                            else self._clock.now().isoformat()
                        ),
                        "last_turn_id": str(answer_turn_id),
                        "post_processing_status": "queued",
                    },
                )
        target = (
            question_target.criterion_id
            if question_target is not None
            else (
                previous_question.target_criterion_id
                if previous_question is not None
                and previous_question.target_criterion_id is not None
                else plan.criterion_ids[0]
            )
        )
        result = self._interview_service.finalize_answer_and_generate(
            context,
            session_id=envelope.session_id,
            expected_sequence=envelope.sequence,
            answer_turn_id=answer_turn_id,
            answer_text=answer.text,
            last_recording_chunk_sequence=_non_negative_int(
                envelope.payload.get("last_recording_chunk_sequence")
            ),
            idempotency_key=envelope.idempotency_key,
            target_criterion_id=target,
            allowed_criterion_ids=frozenset(plan.criterion_ids),
            prohibited_topics=plan.prohibited_topics,
            previous_questions=previous_questions,
            fallback_question=plan.fallback_question,
            remaining_criterion_ids=plan.criterion_ids,
            # What the model is told is the time actually left, not the slot length, so
            # it can wrap up instead of opening a topic the clock cannot finish.
            remaining_time_seconds=max(
                0, plan.remaining_time_seconds - self._elapsed_seconds(session)
            ),
            query_vector=None,
            model_config_version=plan.model_config_version,
            retrieval_config_version=plan.retrieval_config_version,
            voice_id=plan.voice_id,
            occurred_at=self._clock.now(),
            interview_level=plan.interview_level,
            answered_target=answered_target,
            question_target=question_target,
            existing_progress=existing_progress,
        )
        current = self._repository.get_session(context, envelope.session_id)
        return self._question_message(
            envelope,
            sequence=current.session_sequence,
            question_turn=result.question_turn,
            source_reference_count=len(result.source_references),
            speech=result.speech,
            voice_id=plan.voice_id,
        )

    def _save_transcript_draft(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        answer_turn_id: UUID,
        text: str,
        idempotency_key: str,
        replace_existing: bool = False,
    ) -> InterviewTurn:
        session = self._repository.get_session(context, session_id)
        try:
            existing = self._repository.get_turn(context, answer_turn_id)
        except LookupError:
            existing = None
        combined = text
        if existing is not None:
            if (
                existing.interview_session_id != session_id
                or existing.speaker is not TurnSpeaker.APPLICANT
                or existing.status is TurnStatus.FINAL
            ):
                raise ValueError("audio answer turn is outside the active answer")
            if not replace_existing:
                combined = f"{existing.text or ''} {text}".strip()
        return self._repository.save_turn(
            context,
            InterviewTurn(
                turn_id=answer_turn_id,
                company_id=session.company_id,
                interview_session_id=session_id,
                sequence=(
                    existing.sequence
                    if existing is not None
                    else self._next_turn_sequence(context, session_id)
                ),
                speaker=TurnSpeaker.APPLICANT,
                status=TurnStatus.RECORDING,
                text=combined,
                idempotency_key=(
                    existing.idempotency_key if existing is not None else idempotency_key
                ),
            ),
        )

    def _plan(
        self,
        session: InterviewSession,
        context: TenantContext,
    ) -> InterviewPlan:
        return self._plan_provider.get_interview_plan(
            context,
            strategy_id=session.interview_strategy_id,
            competency_model_version_id=session.competency_model_version_id,
        )

    def _elapsed_seconds(self, session: InterviewSession) -> int:
        """Wall-clock seconds since the applicant started answering.

        A session that has not started yet has consumed nothing. Resuming after a pause
        keeps counting, which matches what the applicant experiences: the recruiter
        bought a 30 minute slot, not 30 minutes of model time.
        """
        if session.started_at is None:
            return 0
        return max(0, int((self._clock.now() - session.started_at).total_seconds()))

    def _next_turn_sequence(self, context: TenantContext, session_id: UUID) -> int:
        turns = self._repository.list_turns(context, session_id)
        return max((turn.sequence for turn in turns), default=0) + 1

    @classmethod
    def _question_message(
        cls,
        envelope: WebSocketEnvelope,
        *,
        sequence: int,
        question_turn: InterviewTurn,
        source_reference_count: int,
        speech: SpeechOutput,
        voice_id: str,
    ) -> ServerEnvelope:
        return cls._message(
            envelope,
            message_type="question.ready",
            sequence=sequence,
            payload={
                "question_turn_id": str(question_turn.turn_id),
                "text": question_turn.text,
                "target_criterion_id": str(question_turn.target_criterion_id),
                "audio_url": speech.audio_url,
                "audio_expires_at": speech.audio_expires_at,
                "speech_marks_url": speech.speech_marks_url,
                "source_reference_count": source_reference_count,
                "text_only": speech.text_only,
                "voice_id": voice_id,
            },
        )

    @classmethod
    def _error(
        cls,
        envelope: WebSocketEnvelope,
        *,
        code: str,
        message: str,
        retryable: bool,
    ) -> ServerEnvelope:
        return cls._message(
            envelope,
            message_type="error",
            sequence=envelope.sequence,
            payload={
                "code": code,
                "message": message,
                "retryable": retryable,
                "current_sequence": envelope.sequence,
            },
        )

    @staticmethod
    def _message(
        envelope: WebSocketEnvelope,
        *,
        message_type: str,
        sequence: int,
        payload: dict[str, object],
    ) -> ServerEnvelope:
        return ServerEnvelope(
            message_type=message_type,
            session_id=envelope.session_id,
            sequence=sequence,
            idempotency_key=f"server:{envelope.idempotency_key}",
            correlation_id=envelope.correlation_id,
            sent_at=envelope.sent_at,
            payload=payload,
        )


def _bounded_confidence(value: object) -> float:
    if isinstance(value, int | float):
        return min(1.0, max(0.0, float(value)))
    return 0.0


def _non_negative_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0
