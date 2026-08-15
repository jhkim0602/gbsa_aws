from hashlib import sha256

from interview_evidence.workers.analysis.document_chunker import (
    ChunkingConfig,
    DocumentPage,
    chunk_document,
)


def test_document_chunks_preserve_page_section_locator_and_hashes() -> None:
    source = (
        DocumentPage(
            page_number=1,
            text="경력\n결제 시스템의 장애율을 30% 줄였습니다.\n기술 선택\nSQS를 사용했습니다.",
        ),
        DocumentPage(
            page_number=2,
            text="성과\n재처리 큐를 도입해 복구 시간을 줄였습니다.",
        ),
    )
    source_hash = sha256(b"source-pdf").hexdigest()

    chunks = chunk_document(
        source,
        source_hash=source_hash,
        config=ChunkingConfig(version="chunk-v1", max_characters=45),
    )

    assert len(chunks) >= 2
    assert chunks[0].source_location.page_number == 1
    assert chunks[0].source_location.section == "경력"
    assert chunks[-1].source_location.page_number == 2
    assert all(chunk.source_hash == source_hash for chunk in chunks)
    assert all(
        chunk.chunk_hash == sha256(chunk.text.encode("utf-8")).hexdigest() for chunk in chunks
    )
    assert all(chunk.chunk_config_version == "chunk-v1" for chunk in chunks)


def test_chunk_hash_is_reproducible_for_the_same_source() -> None:
    page = DocumentPage(page_number=1, text="경력\n동일한 입력은 동일한 해시를 만든다.")
    config = ChunkingConfig(version="chunk-v1", max_characters=200)

    first = chunk_document((page,), source_hash="a" * 64, config=config)
    second = chunk_document((page,), source_hash="a" * 64, config=config)

    assert [chunk.chunk_hash for chunk in first] == [chunk.chunk_hash for chunk in second]
