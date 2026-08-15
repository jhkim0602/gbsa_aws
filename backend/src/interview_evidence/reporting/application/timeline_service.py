from __future__ import annotations

from dataclasses import dataclass
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


class TimelineService:
    def __init__(self, repository: ReportingRepository) -> None:
        self._repository = repository

    def project(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        query: str | None = None,
    ) -> tuple[TimelineEntry, ...]:
        entries = [
            TimelineEntry(
                entry_id=segment.transcript_segment_id,
                entry_type="answer" if segment.speaker == "applicant" else "question",
                start_ms=segment.session_start_ms,
                end_ms=segment.session_end_ms,
                text=segment.text,
                technical_failure=False,
            )
            for segment in self._repository.list_transcripts(context, session_id)
            if query is None or query.lower() in segment.text.lower()
        ]
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
