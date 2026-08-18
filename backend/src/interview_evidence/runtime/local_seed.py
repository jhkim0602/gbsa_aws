from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from importlib.resources import files
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_evidence.company_management.api import (
    ensure_company_principal,
    ensure_local_demo_recruiting,
)
from interview_evidence.interview_engine.api import ensure_local_demo_interview_session
from interview_evidence.reporting.api import (
    LocalDemoAnswerRange,
    ensure_local_demo_review_projections,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.workers.reporting.media import assembled_recording_key


class MediaUploader(Protocol):
    def write_object(
        self,
        context: TenantContext,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
    ) -> None: ...


def demo_recording_bytes() -> bytes:
    """The recording the seeded demo session plays back.

    A real WebM, because the browser decides whether it can play from the container header
    and a placeholder of the right length leaves `<video>` at ``readyState 0`` forever. It
    runs the length of the seeded timeline so every citation seeks to a frame that exists.
    """
    return (files("interview_evidence.runtime") / "demo_recording.webm").read_bytes()


def seed_local_company(
    environment: Mapping[str, str] | None = None,
    *,
    media_storage: MediaUploader | None = None,
) -> None:
    """Write the rows -- and, when the media bucket is reachable, the recording itself.

    ``media_storage`` is optional because unit and contract suites seed against SQLite with
    no bucket in reach. Without it the recording asset stays PROCESSING rather than claiming
    to be playable, so nothing offers a reviewer a URL for bytes that were never uploaded.
    """
    values = dict(os.environ if environment is None else environment)
    engine = create_engine(_required(values, "DATABASE_URL"), pool_pre_ping=True)
    with Session(engine) as session:
        company_id = UUID(_required(values, "LOCAL_COMPANY_ID"))
        company_user_id = UUID(_required(values, "LOCAL_COMPANY_USER_ID"))
        now = datetime.now(UTC)
        ensure_company_principal(
            session,
            company_id=company_id,
            company_user_id=company_user_id,
            company_name=values.get(
                "LOCAL_COMPANY_NAME",
                "Local Interview Evidence Company",
            ),
            # Whoever the token will actually carry. The local principal provider maps a
            # fixed string, so the default keeps compose unchanged; against Cognito the
            # subject is the pool's `sub` for the user, and a row written under any other
            # value authenticates a login and then answers every request with 401 --
            # `get_company_principal` looks the caller up by exactly this column.
            identity_subject=values.get(
                "LOCAL_COMPANY_IDENTITY_SUBJECT",
                "local-production-company-user",
            ),
            email_normalized=values.get(
                "LOCAL_COMPANY_EMAIL",
                "local-company@example.test",
            ),
            now=now,
        )
        if _enabled(values.get("LOCAL_DEMO_DATA_ENABLED")):
            demo = ensure_local_demo_recruiting(
                session,
                company_id=company_id,
                company_user_id=company_user_id,
                now=now,
            )
            # The reviewed applicant gets a finished interview and its review projections
            # so the local console has one row where 검토 시작 actually opens something.
            # Both helpers live in the lane that owns the tables; this only sequences them.
            recording = demo_recording_bytes()
            interview = ensure_local_demo_interview_session(
                session,
                company_id=company_id,
                company_user_id=company_user_id,
                invitation_id=demo.reviewed_invitation_id,
                applicant_id=demo.reviewed_applicant_id,
                competency_model_version_id=demo.competency_model_version_id,
                criterion_id=demo.criterion_id,
                interview_strategy_id=uuid5(
                    NAMESPACE_URL,
                    f"local-interview-demo-strategy:{demo.reviewed_invitation_id}",
                ),
                recording=recording,
                now=now,
            )
            # The key the media worker would have written, from the worker's own helper.
            # A second copy of that layout here is how the review screen ended up asking
            # the bucket for an object no code had ever produced.
            recording_object_key = assembled_recording_key(
                company_id=company_id,
                session_id=interview.interview_session_id,
            )
            if media_storage is not None:
                # One chunk, so the assembled recording is a byte-for-byte copy of it. The
                # keys differ because the citation trail and the player read different
                # objects, and deletion enumerates them separately.
                _upload_demo_recording(
                    media_storage,
                    company_id=company_id,
                    company_user_id=company_user_id,
                    session_id=interview.interview_session_id,
                    object_keys=(interview.recording_object_key, recording_object_key),
                    recording=recording,
                )
            ensure_local_demo_review_projections(
                session,
                company_id=company_id,
                company_user_id=company_user_id,
                interview_session_id=interview.interview_session_id,
                invitation_id=demo.reviewed_invitation_id,
                competency_model_version_id=demo.competency_model_version_id,
                criterion_id=demo.criterion_id,
                criterion_name=demo.criterion_name,
                answers=tuple(
                    LocalDemoAnswerRange(
                        turn_id=answer.turn_id,
                        question_turn_id=answer.question_turn_id,
                        question_text=answer.question_text,
                        answer_text=answer.answer_text,
                        session_start_ms=answer.session_start_ms,
                        session_end_ms=answer.session_end_ms,
                    )
                    for answer in interview.answers
                ),
                chunk_object_key=interview.recording_object_key,
                recording_object_key=recording_object_key,
                # What `MediaPostProcessor.build_manifest` computes: a digest over the
                # chunk digests, not over the bytes. Matching it keeps a locally seeded
                # asset comparable with one the worker produced for the same recording.
                recording_content_hash=hashlib.sha256(
                    interview.recording_content_hash.encode()
                ).hexdigest(),
                recording_duration_ms=interview.recording_duration_ms,
                recording_playable=media_storage is not None,
                now=now,
            )
        session.commit()


def _upload_demo_recording(
    media_storage: MediaUploader,
    *,
    company_id: UUID,
    company_user_id: UUID,
    session_id: UUID,
    object_keys: tuple[str, ...],
    recording: bytes,
) -> None:
    context = TenantContext(
        company_id=company_id,
        actor_type=ActorType.SYSTEM,
        actor_id=company_user_id,
        request_id=uuid5(NAMESPACE_URL, f"local-demo-recording-upload:{session_id}"),
        trace_id="local-demo-recording-upload",
    )
    for object_key in object_keys:
        media_storage.write_object(
            context,
            object_key=object_key,
            body=recording,
            content_type="video/webm",
        )


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"required local seed setting is missing: {name}")
    return value.strip()


def _enabled(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    from interview_evidence.runtime.aws import create_media_object_storage

    # The compose seed runs against LocalStack, so the recording is uploaded for real and
    # the demo review screen plays the same object a finished live interview would.
    seed_local_company(media_storage=create_media_object_storage(os.environ))


if __name__ == "__main__":
    main()
