from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from unicodedata import category

from pypdf import PdfReader

from interview_evidence.shared.aws_clients.ports import ObjectStorage
from interview_evidence.shared.tenant import TenantContext, require_tenant_context
from interview_evidence.workers.analysis.document_chunker import DocumentPage
from interview_evidence.workers.analysis.document_extract import (
    DocumentContentExtractor,
    DocumentExtractionError,
)


@dataclass(frozen=True, slots=True)
class PdfPageContent:
    text: str
    has_images: bool


PdfPageReader = Callable[[bytes], tuple[PdfPageContent, ...]]


class NativePdfTextUnavailable(RuntimeError):
    pass


class NativePdfTextExtractor:
    extractor_version = "pypdf-native-text-v1"

    def __init__(
        self,
        *,
        minimum_document_characters: int = 50,
        minimum_image_page_characters: int = 20,
        page_reader: PdfPageReader | None = None,
    ) -> None:
        if minimum_document_characters < 1:
            raise ValueError("minimum_document_characters must be positive")
        if minimum_image_page_characters < 1:
            raise ValueError("minimum_image_page_characters must be positive")
        self._minimum_document_characters = minimum_document_characters
        self._minimum_image_page_characters = minimum_image_page_characters
        self._page_reader = page_reader or _read_pdf_pages

    def extract_content(self, content: bytes) -> tuple[DocumentPage, ...]:
        try:
            source_pages = self._page_reader(content)
        except Exception as error:
            raise NativePdfTextUnavailable from error

        pages: list[DocumentPage] = []
        total_characters = 0
        for page_number, source_page in enumerate(source_pages, start=1):
            text = _normalize_text(source_page.text)
            meaningful_characters = _meaningful_character_count(text)
            if _looks_corrupted(text):
                raise NativePdfTextUnavailable
            if (
                source_page.has_images
                and meaningful_characters < self._minimum_image_page_characters
            ):
                raise NativePdfTextUnavailable
            total_characters += meaningful_characters
            if text:
                pages.append(DocumentPage(page_number=page_number, text=text))

        if total_characters < self._minimum_document_characters or not pages:
            raise NativePdfTextUnavailable
        return tuple(pages)


class HybridDocumentExtractor:
    extractor_version = "hybrid-pypdf-gcp-document-ai-v1"

    def __init__(
        self,
        *,
        object_storage: ObjectStorage,
        native_extractor: DocumentContentExtractor,
        ocr_extractor: DocumentContentExtractor,
    ) -> None:
        self._object_storage = object_storage
        self._native_extractor = native_extractor
        self._ocr_extractor = ocr_extractor

    def extract(
        self,
        context: TenantContext,
        source_uri: str,
    ) -> tuple[DocumentPage, ...]:
        require_tenant_context(context)
        try:
            content = self._object_storage.read_object(context, source_uri)
        except Exception as error:
            raise DocumentExtractionError("document_source_unavailable") from error

        try:
            return self._native_extractor.extract_content(content)
        except NativePdfTextUnavailable:
            return self._ocr_extractor.extract_content(content)


def _read_pdf_pages(content: bytes) -> tuple[PdfPageContent, ...]:
    reader = PdfReader(BytesIO(content), strict=False)
    return tuple(
        PdfPageContent(
            text=page.extract_text() or "",
            has_images=len(page.images) > 0,
        )
        for page in reader.pages
    )


def _normalize_text(text: str) -> str:
    return "\n".join(
        line
        for raw_line in text.replace("\x00", "").splitlines()
        if (line := " ".join(raw_line.split()))
    )


def _meaningful_character_count(text: str) -> int:
    return sum(category(character).startswith(("L", "N")) for character in text)


def _looks_corrupted(text: str) -> bool:
    visible_characters = [character for character in text if not character.isspace()]
    if not visible_characters:
        return False
    invalid_characters = sum(
        character == "\ufffd" or category(character) in {"Cc", "Cs", "Co"}
        for character in visible_characters
    )
    return invalid_characters / len(visible_characters) > 0.05
