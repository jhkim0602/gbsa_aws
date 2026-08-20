from __future__ import annotations

from collections.abc import Callable, Mapping

from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai

from interview_evidence.shared.aws_clients.ports import ObjectStorage
from interview_evidence.shared.gcp_clients.document_ai import GcpDocumentAiExtractor
from interview_evidence.shared.pdf_document_extraction import (
    HybridDocumentExtractor,
    NativePdfTextExtractor,
)
from interview_evidence.workers.analysis.document_extract import DocumentExtractor

DocumentAiClientFactory = Callable[
    [ClientOptions],
    documentai.DocumentProcessorServiceClient,
]


def create_document_extractor(
    environment: Mapping[str, str],
    *,
    object_storage: ObjectStorage,
    client_factory: DocumentAiClientFactory | None = None,
) -> DocumentExtractor:
    provider = environment.get("DOCUMENT_OCR_PROVIDER", "gcp_document_ai").strip().casefold()
    if provider != "gcp_document_ai":
        raise RuntimeError("DOCUMENT_OCR_PROVIDER must be gcp_document_ai")

    project_id = _required(environment, "GCP_DOCUMENT_AI_PROJECT_ID")
    location = environment.get("GCP_DOCUMENT_AI_LOCATION", "us").strip()
    processor_id = _required(environment, "GCP_DOCUMENT_AI_PROCESSOR_ID")
    processor_version = environment.get("GCP_DOCUMENT_AI_PROCESSOR_VERSION", "").strip()
    endpoint = environment.get(
        "GCP_DOCUMENT_AI_API_ENDPOINT",
        f"{location}-documentai.googleapis.com",
    ).strip()
    create_client = client_factory or _create_client
    client = create_client(ClientOptions(api_endpoint=endpoint))
    processor_name = (
        client.processor_version_path(
            project_id,
            location,
            processor_id,
            processor_version,
        )
        if processor_version
        else client.processor_path(project_id, location, processor_id)
    )
    ocr_extractor = GcpDocumentAiExtractor(
        client,
        object_storage=object_storage,
        processor_name=processor_name,
        timeout_seconds=float(environment.get("GCP_DOCUMENT_AI_TIMEOUT_SECONDS", "120")),
    )
    return HybridDocumentExtractor(
        object_storage=object_storage,
        native_extractor=NativePdfTextExtractor(
            minimum_document_characters=int(
                environment.get("PDF_NATIVE_TEXT_MIN_DOCUMENT_CHARACTERS", "50")
            ),
            minimum_image_page_characters=int(
                environment.get("PDF_NATIVE_TEXT_MIN_IMAGE_PAGE_CHARACTERS", "20")
            ),
        ),
        ocr_extractor=ocr_extractor,
    )


def _create_client(
    options: ClientOptions,
) -> documentai.DocumentProcessorServiceClient:
    return documentai.DocumentProcessorServiceClient(client_options=options)


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value
