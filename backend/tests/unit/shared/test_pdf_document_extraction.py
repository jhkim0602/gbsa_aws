from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
from interview_evidence.shared.aws_clients.ports import ObjectStorage
from interview_evidence.shared.pdf_document_extraction import (
    HybridDocumentExtractor,
    NativePdfTextExtractor,
    NativePdfTextUnavailable,
    PdfPageContent,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.workers.analysis.document_chunker import DocumentPage

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
ACTOR_ID = UUID("00000000-0000-7000-8000-000000000002")


class FakeObjectStorage:
    def __init__(self, content: bytes = b"pdf-content") -> None:
        self.content = content
        self.keys: list[str] = []

    def read_object(self, context: TenantContext, object_key: str) -> bytes:
        context.assert_company(COMPANY_ID)
        self.keys.append(object_key)
        return self.content


class StubContentExtractor:
    extractor_version = "stub-v1"

    def __init__(
        self,
        pages: tuple[DocumentPage, ...] = (),
        error: Exception | None = None,
    ) -> None:
        self.pages = pages
        self.error = error
        self.contents: list[bytes] = []

    def extract_content(self, content: bytes) -> tuple[DocumentPage, ...]:
        self.contents.append(content)
        if self.error is not None:
            raise self.error
        return self.pages


def test_native_pdf_text_is_used_when_document_contains_extractable_text() -> None:
    extractor = NativePdfTextExtractor(
        page_reader=lambda content: (
            PdfPageContent(
                text=(
                    "이력서\n경력 사항\n백엔드 개발 경력 5년입니다. "
                    "Python과 FastAPI를 사용해 채용 서비스를 개발하고 운영했습니다."
                ),
                has_images=False,
            ),
        ),
    )

    pages = extractor.extract_content(b"native-pdf")

    assert pages == (
        DocumentPage(
            page_number=1,
            text=(
                "이력서\n경력 사항\n백엔드 개발 경력 5년입니다. "
                "Python과 FastAPI를 사용해 채용 서비스를 개발하고 운영했습니다."
            ),
        ),
    )


def test_native_pdf_text_rejects_scanned_or_mixed_image_pages() -> None:
    extractor = NativePdfTextExtractor(
        page_reader=lambda content: (
            PdfPageContent(
                text="경력 사항이 충분히 포함된 첫 번째 페이지입니다.",
                has_images=False,
            ),
            PdfPageContent(text="", has_images=True),
        ),
    )

    with pytest.raises(NativePdfTextUnavailable):
        extractor.extract_content(b"mixed-pdf")


def test_hybrid_extractor_skips_ocr_for_native_text() -> None:
    storage = FakeObjectStorage()
    native = StubContentExtractor((DocumentPage(page_number=1, text="native"),))
    ocr = StubContentExtractor((DocumentPage(page_number=1, text="ocr"),))
    extractor = HybridDocumentExtractor(
        object_storage=cast(ObjectStorage, storage),
        native_extractor=native,
        ocr_extractor=ocr,
    )

    pages = extractor.extract(_context(), f"tenants/{COMPANY_ID}/file")

    assert pages == (DocumentPage(page_number=1, text="native"),)
    assert storage.keys == [f"tenants/{COMPANY_ID}/file"]
    assert native.contents == [b"pdf-content"]
    assert ocr.contents == []


def test_hybrid_extractor_uses_ocr_when_native_text_is_unavailable() -> None:
    storage = FakeObjectStorage()
    native = StubContentExtractor(error=NativePdfTextUnavailable())
    ocr = StubContentExtractor((DocumentPage(page_number=1, text="ocr"),))
    extractor = HybridDocumentExtractor(
        object_storage=cast(ObjectStorage, storage),
        native_extractor=native,
        ocr_extractor=ocr,
    )

    pages = extractor.extract(_context(), f"tenants/{COMPANY_ID}/file")

    assert pages == (DocumentPage(page_number=1, text="ocr"),)
    assert storage.keys == [f"tenants/{COMPANY_ID}/file"]
    assert native.contents == [b"pdf-content"]
    assert ocr.contents == [b"pdf-content"]


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=ACTOR_ID,
        request_id=ACTOR_ID,
        trace_id="hybrid-document-extraction-test",
    )
