"""A recording asset has to point at an object that exists.

`build_manifest` computed a status from chunk arithmetic and wrote an `object_key` for a
final rendition that nothing produced, so every asset was `ready` while `head_object` on
its key returned 404. The manifest was right about the timeline and wrong about the file.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from interview_evidence.integration.interview_reporting import (
    _ranges_from_recording_segments,
)
from interview_evidence.interview_engine.application.public import (
    RecordingCheckpointSnapshot,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.workers.reporting.media import (
    RecordingAssembler,
    RecordingChunkObject,
    RecordingSourceSegment,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
NOW = datetime(2026, 8, 18, 9, 0, tzinfo=UTC)


class MediaObjects:
    """The media bucket, as far as assembly is concerned."""

    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects = dict(objects or {})
        self.reads: list[str] = []
        self.writes: list[tuple[str, int]] = []

    def read_object(self, context: TenantContext, object_key: str) -> bytes:
        context.assert_company(COMPANY_ID)
        self.reads.append(object_key)
        return self.objects[object_key]

    def write_object(
        self,
        context: TenantContext,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
    ) -> None:
        context.assert_company(COMPANY_ID)
        assert content_type == "video/webm"
        self.writes.append((object_key, len(body)))
        self.objects[object_key] = body


class CapturingRemuxer:
    def __init__(self) -> None:
        self.segments: tuple[RecordingSourceSegment, ...] = ()

    def remux(self, segments: tuple[RecordingSourceSegment, ...]) -> bytes:
        self.segments = segments
        return b"remuxed-webm"


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="trace-assembly",
    )


def chunk(sequence: int, key: str) -> RecordingChunkObject:
    return RecordingChunkObject(sequence=sequence, object_key=key)


def test_chunks_are_concatenated_in_sequence_order_into_one_object() -> None:
    key_prefix = f"tenants/{COMPANY_ID}/sessions/{SESSION_ID}/recording"
    media = MediaObjects(
        {
            f"{key_prefix}/chunks/0": b"first-",
            f"{key_prefix}/chunks/1": b"second-",
            f"{key_prefix}/chunks/2": b"third",
        }
    )

    output_key = RecordingAssembler(media).assemble(
        context(),
        session_id=SESSION_ID,
        # Deliberately out of order: the recorder's upload order is not guaranteed, and
        # a concatenation in arrival order produces a file that plays scrambled.
        chunks=(
            chunk(2, f"{key_prefix}/chunks/2"),
            chunk(0, f"{key_prefix}/chunks/0"),
            chunk(1, f"{key_prefix}/chunks/1"),
        ),
    )

    assert media.objects[output_key] == b"first-second-third"
    assert media.reads == [
        f"{key_prefix}/chunks/0",
        f"{key_prefix}/chunks/1",
        f"{key_prefix}/chunks/2",
    ]


def test_new_media_recorder_headers_are_remuxed_as_answer_segments() -> None:
    key_prefix = f"tenants/{COMPANY_ID}/sessions/{SESSION_ID}/recording"
    ebml = b"\x1a\x45\xdf\xa3"
    media = MediaObjects(
        {
            f"{key_prefix}/chunks/1": ebml + b"answer-one-a",
            f"{key_prefix}/chunks/2": b"answer-one-b",
            f"{key_prefix}/chunks/3": ebml + b"answer-two",
        }
    )
    remuxer = CapturingRemuxer()

    assembled = RecordingAssembler(media, remuxer).assemble_with_segments(
        context(),
        session_id=SESSION_ID,
        chunks=(
            RecordingChunkObject(1, f"{key_prefix}/chunks/1", 0, 2000),
            RecordingChunkObject(2, f"{key_prefix}/chunks/2", 2000, 3500),
            RecordingChunkObject(3, f"{key_prefix}/chunks/3", 3500, 6000),
        ),
    )

    assert media.objects[assembled.object_key] == b"remuxed-webm"
    assert [
        (
            segment.first_sequence,
            segment.last_sequence,
            segment.session_start_ms,
            segment.session_end_ms,
            segment.body,
        )
        for segment in remuxer.segments
    ] == [
        (1, 2, 0, 3500, ebml + b"answer-one-aanswer-one-b"),
        (3, 3, 3500, 6000, ebml + b"answer-two"),
    ]


def test_answer_segments_define_replayable_turn_ranges() -> None:
    turn_ids = [UUID(int=index) for index in range(10, 14)]
    turns = tuple(
        SimpleNamespace(turn_id=turn_id, speaker=speaker)
        for turn_id, speaker in zip(
            turn_ids,
            ("interviewer", "applicant", "interviewer", "applicant"),
            strict=True,
        )
    )
    segments = (
        RecordingSourceSegment(b"first", 1, 2, 0, 3500),
        RecordingSourceSegment(b"second", 3, 3, 3500, 6000),
    )

    ranges = _ranges_from_recording_segments(turns, segments)

    assert [(item.turn_id, item.session_start_ms, item.session_end_ms) for item in ranges] == [
        (turn_ids[0], 0, 1),
        (turn_ids[1], 0, 3500),
        (turn_ids[2], 3500, 3501),
        (turn_ids[3], 3500, 6000),
    ]


def test_checkpoints_skip_abandoned_recorder_segments() -> None:
    turn_ids = [UUID(int=index) for index in range(20, 24)]
    turns = tuple(
        SimpleNamespace(turn_id=turn_id, speaker=speaker)
        for turn_id, speaker in zip(
            turn_ids,
            ("interviewer", "applicant", "interviewer", "applicant"),
            strict=True,
        )
    )
    segments = (
        RecordingSourceSegment(b"abandoned", 1, 1, 0, 1000),
        RecordingSourceSegment(b"accepted-one", 2, 3, 1000, 4000),
        RecordingSourceSegment(b"accepted-two", 4, 5, 4000, 7000),
    )
    checkpoints = (
        RecordingCheckpointSnapshot(turn_ids[1], 3),
        RecordingCheckpointSnapshot(turn_ids[3], 5),
    )

    ranges = _ranges_from_recording_segments(
        turns,
        segments,
        checkpoints=checkpoints,
    )

    assert [(item.session_start_ms, item.session_end_ms) for item in ranges] == [
        (1000, 1001),
        (1000, 4000),
        (4000, 4001),
        (4000, 7000),
    ]


def test_assembled_key_is_tenant_scoped_and_distinct_from_the_chunks() -> None:
    key_prefix = f"tenants/{COMPANY_ID}/sessions/{SESSION_ID}/recording"
    media = MediaObjects({f"{key_prefix}/chunks/0": b"bytes"})

    output_key = RecordingAssembler(media).assemble(
        context(),
        session_id=SESSION_ID,
        chunks=(chunk(0, f"{key_prefix}/chunks/0"),),
    )

    assert output_key.startswith(f"tenants/{COMPANY_ID}/")
    assert str(SESSION_ID) in output_key
    # Writing over a chunk would destroy the verified source the manifest hashes.
    assert output_key not in {f"{key_prefix}/chunks/0"}
    assert media.writes == [(output_key, 5)]


def test_assembly_is_idempotent_for_the_same_session() -> None:
    """The media event is retried; a second key per attempt orphans the first object and
    leaves the asset row pointing at whichever attempt happened to write last."""
    key_prefix = f"tenants/{COMPANY_ID}/sessions/{SESSION_ID}/recording"
    media = MediaObjects({f"{key_prefix}/chunks/0": b"bytes"})
    assembler = RecordingAssembler(media)

    first = assembler.assemble(
        context(),
        session_id=SESSION_ID,
        chunks=(chunk(0, f"{key_prefix}/chunks/0"),),
    )
    second = assembler.assemble(
        context(),
        session_id=SESSION_ID,
        chunks=(chunk(0, f"{key_prefix}/chunks/0"),),
    )

    assert first == second


def test_assembly_refuses_a_chunk_outside_the_tenant_prefix() -> None:
    other = "tenants/00000000-0000-7000-8000-0000000000ff/interviews/s/chunks/0"
    media = MediaObjects({other: b"bytes"})

    with pytest.raises(PermissionError, match="tenant"):
        RecordingAssembler(media).assemble(
            context(),
            session_id=SESSION_ID,
            chunks=(chunk(0, other),),
        )

    assert media.reads == []
    assert media.writes == []


def test_assembly_requires_at_least_one_chunk() -> None:
    with pytest.raises(ValueError, match="chunk"):
        RecordingAssembler(MediaObjects()).assemble(
            context(),
            session_id=SESSION_ID,
            chunks=(),
        )


def test_duplicate_sequence_numbers_are_rejected_rather_than_silently_dropped() -> None:
    key_prefix = f"tenants/{COMPANY_ID}/sessions/{SESSION_ID}/recording"
    media = MediaObjects({f"{key_prefix}/chunks/0": b"a", f"{key_prefix}/chunks/0-again": b"b"})

    with pytest.raises(ValueError, match="sequence"):
        RecordingAssembler(media).assemble(
            context(),
            session_id=SESSION_ID,
            chunks=(
                chunk(0, f"{key_prefix}/chunks/0"),
                chunk(0, f"{key_prefix}/chunks/0-again"),
            ),
        )
