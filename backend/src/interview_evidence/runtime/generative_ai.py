from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from google import genai
from google.auth.credentials import Credentials
from google.genai import types

from interview_evidence.runtime.gcp_credentials import resolve_gcp_credentials
from interview_evidence.shared.aws_clients.ports import AIModel, TextEmbedder
from interview_evidence.shared.aws_clients.production import (
    AwsBedrockModel,
    AwsTitanTextEmbedder,
    BedrockClient,
)
from interview_evidence.shared.gcp_clients.generative import (
    GcpVertexModel,
    GcpVertexTextEmbedder,
    VertexClient,
)

AwsClientFactory = Callable[[str], object]
VertexClientFactory = Callable[[str, str], VertexClient]


@dataclass(frozen=True, slots=True)
class GenerativeAiDependencies:
    model: AIModel
    embedder: TextEmbedder


def create_generative_ai_dependencies(
    environment: Mapping[str, str],
    *,
    aws_client_factory: AwsClientFactory,
    vertex_client_factory: VertexClientFactory | None = None,
) -> GenerativeAiDependencies:
    model_provider = _provider(environment, "AI_PROVIDER")
    embedding_provider = _provider(environment, "EMBEDDING_PROVIDER")
    vertex_client: VertexClient | None = None
    if "gcp" in {model_provider, embedding_provider}:
        project_id = _vertex_project_id(environment)
        location = environment.get("GCP_VERTEX_AI_LOCATION", "global").strip() or "global"
        vertex_client = (
            vertex_client_factory(project_id, location)
            if vertex_client_factory is not None
            else _create_vertex_client(
                project_id,
                location,
                credentials=resolve_gcp_credentials(environment),
            )
        )

    if model_provider == "gcp":
        if vertex_client is None:
            raise RuntimeError("Vertex AI client is unavailable")
        model: AIModel = GcpVertexModel(
            vertex_client,
            model_id=environment.get("GCP_VERTEX_AI_MODEL_ID", "gemini-2.5-flash").strip(),
            thinking_budget=int(environment.get("GCP_VERTEX_AI_THINKING_BUDGET", "0")),
            timeout_seconds=float(environment.get("GCP_VERTEX_AI_TIMEOUT_SECONDS", "30")),
            max_attempts=int(environment.get("GCP_VERTEX_AI_MAX_ATTEMPTS", "2")),
        )
    else:
        model = AwsBedrockModel(
            cast(BedrockClient, aws_client_factory("bedrock-runtime")),
            model_id=_required(environment, "BEDROCK_MODEL_ID"),
            guardrail_id=environment.get("BEDROCK_GUARDRAIL_ID"),
            guardrail_version=environment.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT"),
        )

    if embedding_provider == "gcp":
        if vertex_client is None:
            raise RuntimeError("Vertex AI client is unavailable")
        embedder: TextEmbedder = GcpVertexTextEmbedder(
            vertex_client,
            model_id=environment.get(
                "GCP_VERTEX_AI_EMBEDDING_MODEL_ID",
                "gemini-embedding-001",
            ).strip(),
        )
    else:
        embedder = AwsTitanTextEmbedder(
            cast(BedrockClient, aws_client_factory("bedrock-runtime")),
            model_id=environment.get(
                "BEDROCK_EMBEDDING_MODEL_ID",
                "amazon.titan-embed-text-v2:0",
            ),
        )
    return GenerativeAiDependencies(model=model, embedder=embedder)


def _provider(environment: Mapping[str, str], name: str) -> str:
    provider = environment.get(name, "aws").strip().casefold()
    if provider not in {"aws", "gcp"}:
        raise RuntimeError(f"{name} must be aws or gcp")
    return provider


def _vertex_project_id(environment: Mapping[str, str]) -> str:
    for name in (
        "GCP_VERTEX_AI_PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT",
        "GCP_DOCUMENT_AI_PROJECT_ID",
    ):
        value = environment.get(name, "").strip()
        if value:
            return value
    raise RuntimeError("GCP_VERTEX_AI_PROJECT_ID is required for the GCP AI provider")


def _create_vertex_client(
    project_id: str,
    location: str,
    *,
    credentials: Credentials | None = None,
) -> VertexClient:
    return cast(
        VertexClient,
        genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            credentials=credentials,
            http_options=types.HttpOptions(api_version="v1"),
        ),
    )


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"required production setting is missing: {name}")
    return value.strip()
