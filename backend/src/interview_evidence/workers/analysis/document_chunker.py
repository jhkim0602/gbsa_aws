from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from interview_evidence.submission_analysis.domain.source import SourceLocation


@dataclass(frozen=True, slots=True)
class DocumentPage:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    version: str
    max_characters: int


@dataclass(frozen=True, slots=True)
class DocumentChunkDraft:
    text: str
    source_location: SourceLocation
    source_hash: str
    chunk_hash: str
    chunk_config_version: str


def chunk_document(
    pages: tuple[DocumentPage, ...],
    *,
    source_hash: str,
    config: ChunkingConfig,
) -> tuple[DocumentChunkDraft, ...]:
    if config.max_characters < 20:
        raise ValueError("max_characters must be at least 20")
    chunks: list[DocumentChunkDraft] = []
    for page in pages:
        section = "본문"
        buffer: list[str] = []
        buffer_length = 0
        start_line = 1
        for line_number, raw_line in enumerate(page.text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            if _looks_like_heading(line):
                if buffer:
                    chunks.append(
                        _draft(
                            buffer,
                            page.page_number,
                            section,
                            start_line,
                            line_number - 1,
                            source_hash,
                            config.version,
                        )
                    )
                    buffer = []
                    buffer_length = 0
                section = line
                start_line = line_number + 1
                continue
            if buffer and buffer_length + len(line) + 1 > config.max_characters:
                chunks.append(
                    _draft(
                        buffer,
                        page.page_number,
                        section,
                        start_line,
                        line_number - 1,
                        source_hash,
                        config.version,
                    )
                )
                buffer = []
                buffer_length = 0
                start_line = line_number
            buffer.append(line)
            buffer_length += len(line) + 1
        if buffer:
            chunks.append(
                _draft(
                    buffer,
                    page.page_number,
                    section,
                    start_line,
                    max(start_line, len(page.text.splitlines())),
                    source_hash,
                    config.version,
                )
            )
    return tuple(chunks)


def _looks_like_heading(line: str) -> bool:
    return len(line) <= 20 and not any(character in line for character in ".。?!")


def _draft(
    lines: list[str],
    page_number: int,
    section: str,
    start_line: int,
    end_line: int,
    source_hash: str,
    config_version: str,
) -> DocumentChunkDraft:
    text = "\n".join(lines)
    return DocumentChunkDraft(
        text=text,
        source_location=SourceLocation(
            page_number=page_number,
            section=section,
            start_line=start_line,
            end_line=end_line,
        ),
        source_hash=source_hash,
        chunk_hash=sha256(text.encode("utf-8")).hexdigest(),
        chunk_config_version=config_version,
    )
