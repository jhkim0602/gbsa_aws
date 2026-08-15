from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.reporting.domain.deletion import (
    DeletionManifest,
    DeletionStatus,
    DeletionTarget,
    TargetStatus,
)

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def test_deletion_cannot_complete_until_every_target_is_verified_absent() -> None:
    target_a = DeletionTarget.pending(
        target_id=UUID("00000000-0000-7000-8000-000000000001"),
        owner_lane="A",
        store="aurora",
        target_type="invitation",
        resource_id="invitation-1",
    )
    target_b = DeletionTarget.pending(
        target_id=UUID("00000000-0000-7000-8000-000000000002"),
        owner_lane="C",
        store="s3",
        target_type="recording_chunk",
        resource_id="chunk-1",
    )
    manifest = DeletionManifest(
        manifest_id=UUID("00000000-0000-7000-8000-000000000003"),
        deletion_request_id=UUID("00000000-0000-7000-8000-000000000004"),
        manifest_version=1,
        targets=(target_a, target_b),
    )
    assert manifest.status is DeletionStatus.DELETING

    one_done = manifest.record_result(
        target_a.target_id,
        status=TargetStatus.VERIFIED_ABSENT,
        verified_at=NOW,
    )
    assert one_done.status is DeletionStatus.VERIFYING

    failed = one_done.record_result(
        target_b.target_id,
        status=TargetStatus.RETRYING,
        error_code="OBJECT_STORE_TIMEOUT",
    )
    assert failed.status is DeletionStatus.RETRYING

    completed = failed.record_result(
        target_b.target_id,
        status=TargetStatus.VERIFIED_ABSENT,
        verified_at=NOW,
    )
    assert completed.status is DeletionStatus.COMPLETED
