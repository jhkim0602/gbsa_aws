from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID

from interview_evidence.reporting.repositories.postgres import ReportingRepository
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    entry_id: UUID
    entry_type: str
    start_ms: int
    end_ms: int
    text: str | None
    technical_failure: bool
    question_rationale: QuestionRationaleProjection | None = None


@dataclass(frozen=True, slots=True)
class QuestionSourceProjection:
    source_id: UUID
    source_type: str
    locator: dict[str, object]
    excerpt: str


@dataclass(frozen=True, slots=True)
class QuestionRationaleProjection:
    criterion_id: UUID
    verification_target_type: str
    objective: str
    question_type: str
    retrieval_version: str
    generation_version: str
    policy_result: str
    source_references: tuple[QuestionSourceProjection, ...]


class QuestionRationaleProvider(Protocol):
    def list_question_rationales(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
    ) -> Sequence[Any]: ...


class QuestionSourceSnapshot(Protocol):
    source_id: UUID
    source_type: str
    locator: dict[str, object]
    excerpt: str


class QuestionRationaleSnapshot(Protocol):
    question_turn_id: UUID
    criterion_id: UUID
    verification_target_type: str
    objective: str
    question_type: str
    retrieval_version: str
    generation_version: str
    policy_result: str
    source_references: Sequence[QuestionSourceSnapshot]


class TimelineService:
    def __init__(
        self,
        repository: ReportingRepository,
        *,
        rationale_provider: QuestionRationaleProvider | None = None,
    ) -> None:
        self._repository = repository
        self._rationale_provider = rationale_provider

    # There is deliberately no free-text filter here. It used to take a `query` that
    # substring-matched the transcript, the question objective and every source excerpt --
    # applicant answer text -- and the console passed it as a URL query parameter. The
    # load balancer records one line per request including the query string, so the filter
    # made answer text land in an S3 access-log object, which the platform forbids. The
    # console filters the returned entries in the browser instead; a timeline is one
    # session, so there is nothing to page through.
    def project(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
    ) -> tuple[TimelineEntry, ...]:
        rationales = cast(
            Sequence[QuestionRationaleSnapshot],
            (
                self._rationale_provider.list_question_rationales(
                    context,
                    session_id=session_id,
                )
                if self._rationale_provider is not None
                else ()
            ),
        )
        rationale_by_turn = {
            rationale.question_turn_id: _project_rationale(rationale) for rationale in rationales
        }
        entries: list[TimelineEntry] = []
        for segment in self._repository.list_transcripts(context, session_id):
            rationale = rationale_by_turn.get(segment.turn_id)
            entries.append(
                TimelineEntry(
                    entry_id=segment.transcript_segment_id,
                    entry_type=("answer" if segment.speaker == "applicant" else "question"),
                    start_ms=segment.session_start_ms,
                    end_ms=segment.session_end_ms,
                    text=segment.text,
                    technical_failure=False,
                    question_rationale=rationale,
                )
            )
        entries.extend(
            TimelineEntry(
                entry_id=event.session_event_id,
                entry_type="event",
                start_ms=event.session_start_ms,
                end_ms=event.session_end_ms,
                text=None,
                technical_failure=event.technical_failure,
            )
            for event in self._repository.list_session_events(context, session_id)
        )
        return tuple(sorted(entries, key=lambda item: (item.start_ms, item.end_ms)))


def _project_rationale(
    rationale: QuestionRationaleSnapshot,
) -> QuestionRationaleProjection:
    return QuestionRationaleProjection(
        criterion_id=rationale.criterion_id,
        verification_target_type=rationale.verification_target_type,
        objective=rationale.objective,
        question_type=rationale.question_type,
        retrieval_version=rationale.retrieval_version,
        generation_version=rationale.generation_version,
        policy_result=rationale.policy_result,
        source_references=tuple(
            QuestionSourceProjection(
                source_id=source.source_id,
                source_type=source.source_type,
                locator=dict(source.locator),
                excerpt=source.excerpt,
            )
            for source in rationale.source_references
        ),
    )
