"""The seeded demo asset has to name an object that holds playable bytes.

The seed wrote a recording chunk and a ``ready`` asset but never uploaded anything, so the
review screen asked the bucket for a key that returned 404 -- a green suite and a video
element that never leaves ``readyState 0``. These drive the upload the seed now performs.
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from interview_evidence.company_management.api import ensure_local_demo_recruiting
from interview_evidence.company_management.repositories.postgres import Base as CompanyBase
from interview_evidence.interview_engine.repositories.postgres import (
    Base as InterviewBase,
)
from interview_evidence.interview_engine.repositories.postgres import RecordingChunkRow
from interview_evidence.reporting.repositories.postgres import Base as ReportingBase
from interview_evidence.reporting.repositories.postgres import (
    RecordingAssetRow,
    TranscriptSegmentRow,
)
from interview_evidence.runtime.local_seed import seed_local_company
from interview_evidence.shared.tenant import ActorType, TenantContext
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
NOW = datetime(2026, 8, 18, 9, 0, tzinfo=UTC)
#: The first four bytes of any WebM file. A truncated or text placeholder fails this.
EBML_MAGIC = b"\x1a\x45\xdf\xa3"


class MediaObjects:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}

    def write_object(
        self,
        context: TenantContext,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
    ) -> None:
        context.assert_company(COMPANY_ID)
        self.objects[object_key] = body
        self.content_types[object_key] = content_type


@pytest.fixture
def seeded(tmp_path: Path) -> tuple[Session, MediaObjects, UUID]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'recording.db'}"
    engine = create_engine(database_url)
    for metadata in (CompanyBase.metadata, InterviewBase.metadata, ReportingBase.metadata):
        metadata.create_all(engine)
    media = MediaObjects()
    environment = {
        "DATABASE_URL": database_url,
        "LOCAL_COMPANY_ID": str(COMPANY_ID),
        "LOCAL_COMPANY_USER_ID": str(COMPANY_USER_ID),
        "LOCAL_DEMO_DATA_ENABLED": "true",
    }
    # Twice: the local stack re-seeds on every boot, and a bucket that already holds the
    # recording must not end up with a second copy under a different key.
    seed_local_company(environment, media_storage=media)
    seed_local_company(environment, media_storage=media)
    session = Session(engine)
    return session, media, COMPANY_ID


def test_the_seeded_asset_key_holds_a_playable_recording(
    seeded: tuple[Session, MediaObjects, UUID],
) -> None:
    session, media, _ = seeded
    with session:
        asset = session.scalars(select(RecordingAssetRow)).one()
        assert asset.object_key in media.objects
        body = media.objects[asset.object_key]
        # The browser decides whether it can play this from the container header, so the
        # bytes have to be a real WebM rather than any placeholder of the right length.
        assert body.startswith(EBML_MAGIC)
        assert len(body) > 1024
        assert media.content_types[asset.object_key] == "video/webm"


def test_the_asset_key_has_the_shape_the_worker_writes() -> None:
    """The seed and the media worker have to agree on where a recording lives.

    A seed that invents its own layout hides the production key from every local run, so a
    change to the worker's output key is only ever discovered after deployment.
    """
    from interview_evidence.workers.reporting.media import (
        RecordingAssembler,
        RecordingChunkObject,
    )

    written: dict[str, bytes] = {}

    class Objects:
        def read_object(self, context: TenantContext, object_key: str) -> bytes:
            return b"bytes"

        def write_object(
            self,
            context: TenantContext,
            *,
            object_key: str,
            body: bytes,
            content_type: str,
        ) -> None:
            written[object_key] = body

    session_id = UUID("00000000-0000-7000-8000-00000000000a")
    context = TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=COMPANY_USER_ID,
        request_id=UUID("00000000-0000-7000-8000-00000000000b"),
        trace_id="demo-recording-shape",
    )
    prefix = f"tenants/{COMPANY_ID}/sessions/{session_id}/recording"
    produced = RecordingAssembler(Objects()).assemble(
        context,
        session_id=session_id,
        chunks=(RecordingChunkObject(sequence=0, object_key=f"{prefix}/chunks/000000"),),
    )

    assert produced == f"{prefix}/recording.webm"
    assert written[produced] == b"bytes"


def test_the_chunk_the_transcripts_cite_is_uploaded_too(
    seeded: tuple[Session, MediaObjects, UUID],
) -> None:
    """Evidence points at the chunk, not only the assembled file.

    A citation whose source object is absent cannot be re-verified, which is the whole
    reason the chunk key is recorded on the transcript in the first place.
    """
    session, media, _ = seeded
    with session:
        chunk = session.scalars(select(RecordingChunkRow)).one()
        assert chunk.object_key in media.objects
        assert media.objects[chunk.object_key].startswith(EBML_MAGIC)
        # Byte size was previously a made-up constant; a mismatch makes
        # `verify_uploaded_object` reject the very chunk the seed just wrote.
        assert chunk.byte_size == len(media.objects[chunk.object_key])

        sources = set(session.scalars(select(TranscriptSegmentRow.source_audio_key)))
        assert sources == {chunk.object_key}


def test_reseeding_does_not_multiply_recording_objects(
    seeded: tuple[Session, MediaObjects, UUID],
) -> None:
    session, media, _ = seeded
    with session:
        asset = session.scalars(select(RecordingAssetRow)).one()
        chunk = session.scalars(select(RecordingChunkRow)).one()
    assert set(media.objects) == {asset.object_key, chunk.object_key}


def test_the_seed_runs_without_a_bucket_but_records_no_playable_asset(tmp_path: Path) -> None:
    """Unit and contract suites seed against SQLite with no bucket in reach.

    They get the rows without an upload; what they must not get is an asset claiming to be
    playable, because that is exactly the state this task exists to remove.
    """
    database_url = f"sqlite+pysqlite:///{tmp_path / 'no-bucket.db'}"
    engine = create_engine(database_url)
    for metadata in (CompanyBase.metadata, InterviewBase.metadata, ReportingBase.metadata):
        metadata.create_all(engine)
    environment = {
        "DATABASE_URL": database_url,
        "LOCAL_COMPANY_ID": str(COMPANY_ID),
        "LOCAL_COMPANY_USER_ID": str(COMPANY_USER_ID),
        "LOCAL_DEMO_DATA_ENABLED": "true",
    }

    seed_local_company(environment)

    with Session(engine) as session:
        demo = ensure_local_demo_recruiting(
            session,
            company_id=COMPANY_ID,
            company_user_id=COMPANY_USER_ID,
            now=NOW,
        )
        assert demo.reviewed_invitation_id
        asset = session.scalars(select(RecordingAssetRow)).one()
        assert asset.status == "processing"
