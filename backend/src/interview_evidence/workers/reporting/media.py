from __future__ import annotations

import hashlib
import importlib
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from interview_evidence.reporting.domain.timeline import (
    RecordingAsset,
    RecordingStatus,
)
from interview_evidence.reporting.repositories.postgres import ReportingRepository
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.tenant import TenantContext, require_tenant_context

get_ffmpeg_exe = cast(
    Callable[[], str],
    importlib.import_module("imageio_ffmpeg").get_ffmpeg_exe,
)


@dataclass(frozen=True, slots=True)
class RecordingChunkObject:
    sequence: int
    object_key: str
    session_start_ms: int = 0
    session_end_ms: int = 1


@dataclass(frozen=True, slots=True)
class RecordingSourceSegment:
    body: bytes
    first_sequence: int
    last_sequence: int
    session_start_ms: int
    session_end_ms: int


@dataclass(frozen=True, slots=True)
class AssembledRecording:
    object_key: str
    source_segments: tuple[RecordingSourceSegment, ...]


def assembled_recording_key(*, company_id: UUID, session_id: UUID) -> str:
    """Where the single playable recording of one session lives.

    Beside the chunks it is built from, under the layout the upload path already uses.
    Derived from the session rather than the attempt, so a retried media event overwrites
    its own output instead of orphaning it. Exposed as a function because the local seed
    writes the same object without running the worker, and a second copy of this f-string
    is how the review screen ended up asking the bucket for a key nothing had written.
    """
    return f"tenants/{company_id}/sessions/{session_id}/recording/recording.webm"


class MediaObjectStore(Protocol):
    def read_object(self, context: TenantContext, object_key: str) -> bytes: ...

    def write_object(
        self,
        context: TenantContext,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
    ) -> None: ...


class RecordingRemuxer(Protocol):
    def remux(self, segments: tuple[RecordingSourceSegment, ...]) -> bytes: ...


class FfmpegWebMRemuxer:
    def __init__(self, executable: str | None = None) -> None:
        self._executable = executable or get_ffmpeg_exe()

    def remux(self, segments: tuple[RecordingSourceSegment, ...]) -> bytes:
        if not segments:
            raise ValueError("recording remux requires at least one source segment")
        with tempfile.TemporaryDirectory(prefix="iep-recording-") as directory:
            root = Path(directory)
            manifest_lines: list[str] = []
            for index, segment in enumerate(segments):
                source = root / f"source-{index:04d}.webm"
                source.write_bytes(segment.body)
                filename = f"segment-{index:04d}.webm"
                normalized = root / filename
                completed = subprocess.run(
                    (
                        self._executable,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(source),
                        # MediaRecorder may swap the WebM track order each time it
                        # restarts. The concat demuxer matches tracks by index, so
                        # normalize every answer segment to video-then-audio first.
                        "-map",
                        "0:v:0?",
                        "-map",
                        "0:a:0?",
                        "-c",
                        "copy",
                        "-y",
                        str(normalized),
                    ),
                    cwd=root,
                    capture_output=True,
                    check=False,
                )
                if completed.returncode != 0 or not normalized.exists():
                    detail = completed.stderr.decode(errors="replace").strip()[-800:]
                    raise RuntimeError(
                        f"recording segment normalization failed: {detail or 'no output'}"
                    )
                duration_seconds = (segment.session_end_ms - segment.session_start_ms) / 1000
                manifest_lines.extend(
                    (
                        f"file '{filename}'",
                        f"duration {duration_seconds:.6f}",
                    )
                )
            manifest = root / "segments.txt"
            manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
            output = root / "recording.webm"
            completed = subprocess.run(
                (
                    self._executable,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(manifest),
                    "-map",
                    "0:v:0?",
                    "-map",
                    "0:a:0?",
                    "-c",
                    "copy",
                    "-fflags",
                    "+genpts",
                    "-avoid_negative_ts",
                    "make_zero",
                    "-y",
                    str(output),
                ),
                cwd=root,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0 or not output.exists():
                detail = completed.stderr.decode(errors="replace").strip()[-800:]
                raise RuntimeError(f"recording remux failed: {detail or 'no output'}")
            body = output.read_bytes()
            if not body:
                raise RuntimeError("recording remux produced an empty output")
            return body


class RecordingAssembler:
    """Turns verified MediaRecorder chunks into one seekable WebM object."""

    def __init__(
        self,
        objects: MediaObjectStore,
        remuxer: RecordingRemuxer | None = None,
    ) -> None:
        self._objects = objects
        self._remuxer = remuxer

    def assemble(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        chunks: tuple[RecordingChunkObject, ...],
    ) -> str:
        return self.assemble_with_segments(
            context,
            session_id=session_id,
            chunks=chunks,
        ).object_key

    def assemble_with_segments(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        chunks: tuple[RecordingChunkObject, ...],
    ) -> AssembledRecording:
        tenant = require_tenant_context(context)
        if not chunks:
            raise ValueError("recording assembly requires at least one verified chunk")
        sequences = [chunk.sequence for chunk in chunks]
        if len(set(sequences)) != len(sequences):
            raise ValueError("recording chunks must have distinct sequence numbers")
        prefix = f"tenants/{tenant.company_id}/"
        # Chunks arrive under either prefix the bucket uses, matching the storage
        # adapter's own scope check; the assembled object always goes under `tenants/`.
        allowed_prefixes = (prefix, f"companies/{tenant.company_id}/")
        for chunk in chunks:
            if not chunk.object_key.startswith(allowed_prefixes):
                raise PermissionError("recording chunk is outside the tenant scope")
        ordered = sorted(chunks, key=lambda chunk: chunk.sequence)
        source_segments = _source_segments(
            tuple(
                (chunk, self._objects.read_object(context, chunk.object_key)) for chunk in ordered
            )
        )
        body = (
            self._remuxer.remux(source_segments)
            if self._remuxer is not None
            else b"".join(segment.body for segment in source_segments)
        )
        object_key = assembled_recording_key(
            company_id=tenant.company_id,
            session_id=session_id,
        )
        self._objects.write_object(
            context,
            object_key=object_key,
            body=body,
            content_type="video/webm",
        )
        return AssembledRecording(
            object_key=object_key,
            source_segments=source_segments,
        )


_EBML_HEADER = b"\x1a\x45\xdf\xa3"


def _source_segments(
    chunks: tuple[tuple[RecordingChunkObject, bytes], ...],
) -> tuple[RecordingSourceSegment, ...]:
    grouped: list[list[tuple[RecordingChunkObject, bytes]]] = []
    for chunk, body in chunks:
        if body.startswith(_EBML_HEADER) and grouped:
            grouped.append([])
        if not grouped:
            grouped.append([])
        grouped[-1].append((chunk, body))
    return tuple(
        RecordingSourceSegment(
            body=b"".join(body for _, body in group),
            first_sequence=group[0][0].sequence,
            last_sequence=group[-1][0].sequence,
            session_start_ms=group[0][0].session_start_ms,
            session_end_ms=group[-1][0].session_end_ms,
        )
        for group in grouped
    )


class MediaPostProcessor:
    def __init__(self, repository: ReportingRepository) -> None:
        self._repository = repository

    def build_manifest(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        chunks: tuple[tuple[int, int, str], ...],
        output_object_key: str,
        occurred_at: datetime,
    ) -> RecordingAsset:
        if not chunks:
            raise ValueError("recording manifest requires verified chunks")
        ordered = tuple(sorted(chunks, key=lambda item: item[0]))
        missing_ranges: list[tuple[int, int]] = []
        previous_end = ordered[0][0]
        for start_ms, end_ms, content_hash in ordered:
            if start_ms < previous_end or end_ms <= start_ms:
                raise ValueError("recording chunks must be ordered and non-overlapping")
            if len(content_hash) != 64:
                raise ValueError("recording chunk hash must be SHA-256")
            if start_ms > previous_end:
                missing_ranges.append((previous_end, start_ms))
            previous_end = end_ms
        digest = hashlib.sha256(
            "".join(chunk_hash for _, _, chunk_hash in ordered).encode()
        ).hexdigest()
        asset = RecordingAsset(
            recording_asset_id=new_uuid7(occurred_at),
            company_id=context.company_id,
            interview_session_id=session_id,
            asset_type="final_video",
            object_key=output_object_key,
            content_hash=digest,
            duration_ms=ordered[-1][1],
            status=(RecordingStatus.PARTIAL if missing_ranges else RecordingStatus.READY),
            missing_ranges=tuple(missing_ranges),
            created_at=occurred_at,
        )
        return self._repository.save_recording_asset(context, asset)
