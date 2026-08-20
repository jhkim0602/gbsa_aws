from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
from interview_evidence.runtime.document_ai import create_document_extractor
from interview_evidence.shared.aws_clients.ports import ObjectStorage
from interview_evidence.shared.gcp_clients.document_ai import GcpDocumentAiExtractor
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.workers.analysis.document_extract import (
    DocumentExtractionError,
)

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


class FakeDocumentAiClient:
    def __init__(self, response: documentai.ProcessResponse) -> None:
        self.response = response
        self.requests: list[documentai.ProcessRequest] = []
        self.timeouts: list[float] = []

    def process_document(
        self,
        request: documentai.ProcessRequest,
        *,
        timeout: float,
    ) -> documentai.ProcessResponse:
        self.requests.append(request)
        self.timeouts.append(timeout)
        return self.response

    def processor_path(
        self,
        project_id: str,
        location: str,
        processor_id: str,
    ) -> str:
        return f"projects/{project_id}/locations/{location}/processors/{processor_id}"

    def processor_version_path(
        self,
        project_id: str,
        location: str,
        processor_id: str,
        processor_version: str,
    ) -> str:
        return (
            f"{self.processor_path(project_id, location, processor_id)}"
            f"/processorVersions/{processor_version}"
        )


class FailingDocumentAiClient(FakeDocumentAiClient):
    def process_document(
        self,
        request: documentai.ProcessRequest,
        *,
        timeout: float,
    ) -> documentai.ProcessResponse:
        del request, timeout
        raise RuntimeError("sensitive provider failure")


def test_gcp_document_ai_reads_pdf_and_preserves_page_lines() -> None:
    storage = FakeObjectStorage()
    client = FakeDocumentAiClient(_ocr_response())
    extractor = GcpDocumentAiExtractor(
        client,
        object_storage=cast(ObjectStorage, storage),
        processor_name="projects/project/locations/us/processors/processor",
        timeout_seconds=30,
    )

    pages = extractor.extract(
        _context(),
        f"tenants/{COMPANY_ID}/submission-original/{ACTOR_ID}/file",
    )

    assert storage.keys == [f"tenants/{COMPANY_ID}/submission-original/{ACTOR_ID}/file"]
    assert pages[0].page_number == 1
    assert pages[0].text == "이력서\n경력 5년"
    assert client.timeouts == [30]
    request = client.requests[0]
    assert request.name == "projects/project/locations/us/processors/processor"
    assert request.raw_document.content == b"pdf-content"
    assert request.raw_document.mime_type == "application/pdf"
    assert request.process_options.ocr_config.enable_native_pdf_parsing is True
    assert request.imageless_mode is True


def test_gcp_document_ai_sanitizes_provider_errors() -> None:
    extractor = GcpDocumentAiExtractor(
        FailingDocumentAiClient(_ocr_response()),
        object_storage=cast(ObjectStorage, FakeObjectStorage()),
        processor_name="projects/project/locations/us/processors/processor",
    )

    with pytest.raises(DocumentExtractionError, match="document_ocr_unavailable") as error:
        extractor.extract(_context(), f"tenants/{COMPANY_ID}/file")

    assert "sensitive provider failure" not in str(error.value)


def test_document_ai_runtime_uses_regional_endpoint_and_processor() -> None:
    storage = FakeObjectStorage()
    client = FakeDocumentAiClient(_ocr_response())
    options: list[ClientOptions] = []

    def client_factory(client_options: ClientOptions) -> documentai.DocumentProcessorServiceClient:
        options.append(client_options)
        return cast(documentai.DocumentProcessorServiceClient, client)

    extractor = create_document_extractor(
        {
            "DOCUMENT_OCR_PROVIDER": "gcp_document_ai",
            "GCP_DOCUMENT_AI_PROJECT_ID": "project-id",
            "GCP_DOCUMENT_AI_LOCATION": "us",
            "GCP_DOCUMENT_AI_PROCESSOR_ID": "processor-id",
        },
        object_storage=cast(ObjectStorage, storage),
        client_factory=client_factory,
    )

    assert extractor.extractor_version == "hybrid-pypdf-gcp-document-ai-v1"
    extractor.extract(_context(), f"tenants/{COMPANY_ID}/file")
    assert storage.keys == [f"tenants/{COMPANY_ID}/file"]
    assert options[0].api_endpoint == "us-documentai.googleapis.com"
    assert client.requests[0].name == ("projects/project-id/locations/us/processors/processor-id")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=ACTOR_ID,
        request_id=ACTOR_ID,
        trace_id="gcp-document-ai-test",
    )


def _ocr_response() -> documentai.ProcessResponse:
    text = "이력서\n경력 5년\n"
    return documentai.ProcessResponse(
        document=documentai.Document(
            text=text,
            pages=[
                documentai.Document.Page(
                    page_number=1,
                    lines=[
                        _line(0, 3),
                        _line(4, len(text) - 1),
                    ],
                )
            ],
        )
    )


def _line(start_index: int, end_index: int) -> documentai.Document.Page.Line:
    return documentai.Document.Page.Line(
        layout=documentai.Document.Page.Layout(
            text_anchor=documentai.Document.TextAnchor(
                text_segments=[
                    documentai.Document.TextAnchor.TextSegment(
                        start_index=start_index,
                        end_index=end_index,
                    )
                ]
            )
        )
    )
