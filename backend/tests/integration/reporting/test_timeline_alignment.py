from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.reporting.domain.timeline import (
    RecordingAsset,
    RecordingStatus,
    SessionEvent,
    TranscriptSegment,
)

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")


def test_timeline_models_share_an_ordered_session_clock() -> None:
    segment = TranscriptSegment(
        transcript_segment_id=UUID("00000000-0000-7000-8000-000000000003"),
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        turn_id=UUID("00000000-0000-7000-8000-000000000004"),
        speaker="applicant",
        text="최종 답변",
        confidence=0.91,
        session_start_ms=1000,
        session_end_ms=3500,
        source_audio_key="opaque/audio/1",
        version=1,
        corrected_by=None,
        created_at=NOW,
    )
    asset = RecordingAsset(
        recording_asset_id=UUID("00000000-0000-7000-8000-000000000005"),
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        asset_type="final_video",
        object_key="opaque/video/1",
        content_hash="a" * 64,
        duration_ms=10_000,
        status=RecordingStatus.PARTIAL,
        missing_ranges=((4000, 5000),),
        created_at=NOW,
    )
    event = SessionEvent(
        session_event_id=UUID("00000000-0000-7000-8000-000000000006"),
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        event_type="network_interruption",
        session_start_ms=4000,
        session_end_ms=5000,
        technical_failure=True,
        details={"code": "connection_lost"},
        created_at=NOW,
    )

    assert segment.session_end_ms <= asset.duration_ms
    assert asset.missing_ranges == ((event.session_start_ms, event.session_end_ms),)


def test_timeline_rejects_invalid_ranges_and_competency_inference() -> None:
    with pytest.raises(ValueError, match="ordered"):
        SessionEvent(
            session_event_id=UUID("00000000-0000-7000-8000-000000000006"),
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            event_type="device",
            session_start_ms=5000,
            session_end_ms=4000,
            technical_failure=True,
            details={"code": "camera_lost"},
            created_at=NOW,
        )
    with pytest.raises(ValueError, match="objective"):
        SessionEvent(
            session_event_id=UUID("00000000-0000-7000-8000-000000000007"),
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            event_type="observation",
            session_start_ms=0,
            session_end_ms=1,
            technical_failure=False,
            details={"competency_score": 0.2},
            created_at=NOW,
        )
