from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from google.genai import types

from interview_evidence.shared.aws_clients.ports import (
    AIModel,
    EmbeddingProviderError,
    TextEmbedder,
)
from interview_evidence.shared.tenant import TenantContext, require_tenant_context


class VertexModelsClient(Protocol):
    def generate_content(
        self,
        *,
        model: str,
        contents: object,
        config: types.GenerateContentConfig,
    ) -> object: ...

    def embed_content(
        self,
        *,
        model: str,
        contents: object,
        config: types.EmbedContentConfig,
    ) -> object: ...


class VertexClient(Protocol):
    models: VertexModelsClient


class GcpGenerativeAdapterError(ConnectionError):
    pass


class GcpEmbeddingProviderError(GcpGenerativeAdapterError, EmbeddingProviderError):
    pass


class GcpVertexModel(AIModel):
    def __init__(self, client: VertexClient, *, model_id: str) -> None:
        self._client = client
        self._model_id = model_id

    def generate(
        self,
        context: TenantContext,
        model_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        tenant = require_tenant_context(context)
        try:
            response = self._client.models.generate_content(
                model=self._model_id,
                contents=_contents(model_input),
                config=types.GenerateContentConfig(
                    system_instruction=_optional_string(model_input.get("system")),
                    temperature=_optional_float(model_input.get("temperature")),
                    max_output_tokens=_optional_int(model_input.get("max_tokens")),
                    response_mime_type="application/json",
                    labels={"company_id": str(tenant.company_id)},
                ),
            )
            response_text = getattr(response, "text", None)
            if not isinstance(response_text, str) or not response_text.strip():
                raise ValueError("Vertex response text is unavailable")
            decoded = json.loads(_unwrapped(response_text.strip()))
        except Exception as error:
            raise GcpGenerativeAdapterError("model generation unavailable") from error
        if not isinstance(decoded, Mapping):
            raise GcpGenerativeAdapterError("model response shape is invalid")
        return dict(decoded)


class GcpVertexTextEmbedder(TextEmbedder):
    embedding_version = "vertex-gemini-v1"

    def __init__(self, client: VertexClient, *, model_id: str = "gemini-embedding-001") -> None:
        self._client = client
        self.model_id = model_id

    def embed(
        self,
        context: TenantContext,
        text: str,
        *,
        dimensions: int = 1024,
    ) -> tuple[float, ...]:
        require_tenant_context(context)
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("embedding text must not be blank")
        if dimensions <= 0:
            raise ValueError("embedding dimensions must be positive")
        try:
            response = self._client.models.embed_content(
                model=self.model_id,
                contents=normalized_text,
                config=types.EmbedContentConfig(
                    task_type="SEMANTIC_SIMILARITY",
                    output_dimensionality=dimensions,
                ),
            )
            embeddings = getattr(response, "embeddings", None)
            first = embeddings[0] if isinstance(embeddings, Sequence) and embeddings else None
            values = getattr(first, "values", None)
            if not isinstance(values, Sequence):
                raise ValueError("Vertex embedding values are unavailable")
            vector = tuple(float(value) for value in values)
        except Exception as error:
            raise GcpEmbeddingProviderError("text embedding unavailable") from error
        if len(vector) != dimensions or not all(math.isfinite(value) for value in vector):
            raise GcpEmbeddingProviderError("text embedding response is invalid")
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            raise GcpEmbeddingProviderError("text embedding response is invalid")
        return tuple(value / magnitude for value in vector)


def _contents(model_input: Mapping[str, Any]) -> list[types.Content]:
    messages = model_input.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("model messages are required")
    contents: list[types.Content] = []
    for message in messages:
        if not isinstance(message, Mapping):
            continue
        text = _message_text(message.get("content"))
        if not text:
            continue
        role = "model" if message.get("role") == "assistant" else "user"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=text)],
            )
        )
    if not contents:
        raise ValueError("model messages contain no text")
    return contents


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    return "".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, Mapping) and block.get("type", "text") == "text"
    ).strip()


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int) and value > 0 else None


def _unwrapped(text: str) -> str:
    if not text.startswith("```"):
        return text
    without_open = text.split("\n", 1)[1] if "\n" in text else ""
    return without_open.rsplit("```", 1)[0].strip()
