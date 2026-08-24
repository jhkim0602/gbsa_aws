from __future__ import annotations

import pytest
from interview_evidence.runtime.generative_ai import create_generative_ai_dependencies
from interview_evidence.shared.aws_clients.production import AwsTitanTextEmbedder
from interview_evidence.shared.gcp_clients.generative import (
    GcpVertexModel,
    GcpVertexTextEmbedder,
)


class FakeVertexClient:
    models = object()


def test_gcp_providers_share_one_vertex_client_and_skip_bedrock() -> None:
    vertex_calls: list[tuple[str, str]] = []
    aws_calls: list[str] = []
    client = FakeVertexClient()

    dependencies = create_generative_ai_dependencies(
        {
            "AI_PROVIDER": "gcp",
            "EMBEDDING_PROVIDER": "gcp",
            "GCP_DOCUMENT_AI_PROJECT_ID": "project-from-document-ai",
            "GCP_VERTEX_AI_LOCATION": "global",
            "GCP_VERTEX_AI_MODEL_ID": "gemini-test",
            "GCP_VERTEX_AI_EMBEDDING_MODEL_ID": "embedding-test",
        },
        aws_client_factory=lambda service: aws_calls.append(service),
        vertex_client_factory=lambda project, location: (
            vertex_calls.append((project, location)) or client
        ),
    )

    assert isinstance(dependencies.model, GcpVertexModel)
    assert isinstance(dependencies.embedder, GcpVertexTextEmbedder)
    assert dependencies.embedder.model_id == "embedding-test"
    assert vertex_calls == [("project-from-document-ai", "global")]
    assert aws_calls == []


def test_unknown_provider_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="AI_PROVIDER must be aws or gcp"):
        create_generative_ai_dependencies(
            {"AI_PROVIDER": "other"},
            aws_client_factory=lambda _service: object(),
        )


def test_gcp_generation_can_share_an_aws_titan_embedding_space() -> None:
    aws_calls: list[str] = []
    client = FakeVertexClient()

    dependencies = create_generative_ai_dependencies(
        {
            "AI_PROVIDER": "gcp",
            "EMBEDDING_PROVIDER": "aws",
            "GCP_DOCUMENT_AI_PROJECT_ID": "project-id",
            "BEDROCK_EMBEDDING_MODEL_ID": "amazon.titan-embed-text-v2:0",
        },
        aws_client_factory=lambda service: aws_calls.append(service) or object(),
        vertex_client_factory=lambda _project, _location: client,
    )

    assert isinstance(dependencies.model, GcpVertexModel)
    assert isinstance(dependencies.embedder, AwsTitanTextEmbedder)
    assert aws_calls == ["bedrock-runtime"]
