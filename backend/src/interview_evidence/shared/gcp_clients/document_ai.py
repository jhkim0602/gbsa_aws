from __future__ import annotations

from typing import Protocol

from google.cloud import documentai_v1 as documentai

from interview_evidence.shared.aws_clients.ports import ObjectStorage
from interview_evidence.shared.tenant import TenantContext, require_tenant_context
from interview_evidence.workers.analysis.document_chunker import DocumentPage
from interview_evidence.workers.analysis.document_extract import DocumentExtractionError


class DocumentAiClient(Protocol):
    def process_document(
        self,
        request: documentai.ProcessRequest,
        *,
        timeout: float,
    ) -> documentai.ProcessResponse: ...


class GcpDocumentAiExtractor:
    extractor_version = "gcp-document-ai-ocr-v1"

    def __init__(
        self,
        client: DocumentAiClient,
        *,
        object_storage: ObjectStorage,
        processor_name: str,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._client = client
        self._object_storage = object_storage
        self._processor_name = processor_name
        self._timeout_seconds = timeout_seconds

    def extract(
        self,
        context: TenantContext,
        source_uri: str,
    ) -> tuple[DocumentPage, ...]:
        require_tenant_context(context)
        try:
            content = self._object_storage.read_object(context, source_uri)
        except Exception as error:
            raise DocumentExtractionError("document_ocr_unavailable") from error
        return self.extract_content(content)

    def extract_content(self, content: bytes) -> tuple[DocumentPage, ...]:
        try:
            response = self._client.process_document(
                request=documentai.ProcessRequest(
                    name=self._processor_name,
                    raw_document=documentai.RawDocument(
                        content=content,
                        mime_type="application/pdf",
                    ),
                    process_options=documentai.ProcessOptions(
                        ocr_config=documentai.OcrConfig(
                            enable_native_pdf_parsing=True,
                        )
                    ),
                    skip_human_review=True,
                    imageless_mode=True,
                ),
                timeout=self._timeout_seconds,
            )
        except Exception as error:
            raise DocumentExtractionError("document_ocr_unavailable") from error

        pages = _document_pages(response.document)
        if not pages:
            raise DocumentExtractionError("document_contains_no_extractable_text")
        return pages


def _document_pages(document: documentai.Document) -> tuple[DocumentPage, ...]:
    pages: list[DocumentPage] = []
    for index, page in enumerate(document.pages, start=1):
        lines = tuple(
            text
            for line in page.lines
            if (text := _layout_text(document.text, line.layout.text_anchor))
        )
        if not lines:
            page_text = _layout_text(document.text, page.layout.text_anchor)
            lines = tuple(line.strip() for line in page_text.splitlines() if line.strip())
        if not lines:
            continue
        pages.append(
            DocumentPage(
                page_number=int(page.page_number or index),
                text="\n".join(lines),
            )
        )
    return tuple(pages)


def _layout_text(text: str, anchor: documentai.Document.TextAnchor) -> str:
    fragments = [
        text[int(segment.start_index) : int(segment.end_index)]
        for segment in anchor.text_segments
        if int(segment.end_index) > int(segment.start_index)
    ]
    return "".join(fragments).strip()
