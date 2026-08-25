from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
from google.genai import types
from interview_evidence.shared.gcp_clients.generative import (
    GcpFallbackModel,
    GcpGenerativeAdapterError,
    GcpVertexModel,
    GcpVertexTextEmbedder,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000002"),
        request_id=UUID("00000000-0000-7000-8000-000000000003"),
        trace_id="gcp-generative-test",
    )


@dataclass
class FakeEmbedding:
    values: list[float]


@dataclass
class FakeResponse:
    text: str | None = None
    embeddings: list[FakeEmbedding] | None = None


class RecordingModels:
    def __init__(self) -> None:
        self.generation_response = FakeResponse(text='```json\n{"question":"설명해 주세요"}\n```')
        self.embedding_response = FakeResponse(embeddings=[FakeEmbedding([3.0, 4.0])])
        self.generation_calls: list[dict[str, object]] = []
        self.embedding_calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> FakeResponse:
        self.generation_calls.append(kwargs)
        return self.generation_response

    def embed_content(self, **kwargs: object) -> FakeResponse:
        self.embedding_calls.append(kwargs)
        return self.embedding_response


class DynamicEmbeddingModels(RecordingModels):
    def embed_content(self, **kwargs: object) -> FakeResponse:
        self.embedding_calls.append(kwargs)
        contents = kwargs["contents"]
        assert isinstance(contents, list)
        return FakeResponse(embeddings=[FakeEmbedding([3.0, 4.0]) for _ in contents])


class FakeVertexClient:
    def __init__(self) -> None:
        self.models = RecordingModels()


class StubGcpModel:
    def __init__(self, response: dict[str, object] | None = None) -> None:
        self.response = response
        self.calls = 0

    def generate(
        self,
        _context: TenantContext,
        _model_input: dict[str, object],
    ) -> dict[str, object]:
        self.calls += 1
        if self.response is None:
            raise GcpGenerativeAdapterError("shared capacity unavailable")
        return self.response


def test_vertex_model_translates_anthropic_prompt_and_returns_structured_fields() -> None:
    client = FakeVertexClient()
    model = GcpVertexModel(
        client,
        model_id="gemini-test",
        timeout_seconds=12.5,
        max_attempts=2,
    )

    response = model.generate(
        _context(),
        {
            "system": "한국어 JSON으로 답합니다.",
            "temperature": 0,
            "max_tokens": 512,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": '{"task":"question"}'}],
                }
            ],
        },
    )

    assert response == {"question": "설명해 주세요"}
    call = client.models.generation_calls[0]
    assert call["model"] == "gemini-test"
    contents = call["contents"]
    assert isinstance(contents, list)
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == '{"task":"question"}'
    config = call["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert config.system_instruction == "한국어 JSON으로 답합니다."
    assert config.response_mime_type == "application/json"
    assert config.labels == {"company_id": str(COMPANY_ID)}
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_budget == 0
    assert config.http_options is not None
    assert config.http_options.timeout == 12_500
    assert config.http_options.retry_options is not None
    assert config.http_options.retry_options.attempts == 2


def test_vertex_model_rejects_invalid_request_limits() -> None:
    client = FakeVertexClient()

    with pytest.raises(ValueError, match="timeout must be positive"):
        GcpVertexModel(client, model_id="gemini-test", timeout_seconds=0)
    with pytest.raises(ValueError, match="attempts must be positive"):
        GcpVertexModel(client, model_id="gemini-test", max_attempts=0)


def test_vertex_embedder_returns_normalized_requested_dimensions() -> None:
    client = FakeVertexClient()
    embedder = GcpVertexTextEmbedder(client, model_id="embedding-test")

    vector = embedder.embed(_context(), "프로젝트 경험", dimensions=2)

    assert vector == pytest.approx((0.6, 0.8))
    assert embedder.embedding_version == "vertex-gemini-v1"
    call = client.models.embedding_calls[0]
    assert call["model"] == "embedding-test"
    assert call["contents"] == ["프로젝트 경험"]
    config = call["config"]
    assert isinstance(config, types.EmbedContentConfig)
    assert config.task_type == "SEMANTIC_SIMILARITY"
    assert config.output_dimensionality == 2


def test_vertex_embedder_batches_multiple_texts_in_one_request() -> None:
    client = FakeVertexClient()
    client.models.embedding_response = FakeResponse(
        embeddings=[FakeEmbedding([3.0, 4.0]), FakeEmbedding([5.0, 12.0])]
    )
    embedder = GcpVertexTextEmbedder(client, model_id="embedding-test")

    vectors = embedder.embed_many(
        _context(),
        ("첫 번째 문단", "두 번째 문단"),
        dimensions=2,
    )

    assert vectors[0] == pytest.approx((0.6, 0.8))
    assert vectors[1] == pytest.approx((5 / 13, 12 / 13))
    assert len(client.models.embedding_calls) == 1
    assert client.models.embedding_calls[0]["contents"] == [
        "첫 번째 문단",
        "두 번째 문단",
    ]


def test_vertex_embedder_splits_batches_before_the_request_size_limit() -> None:
    client = FakeVertexClient()
    client.models = DynamicEmbeddingModels()
    embedder = GcpVertexTextEmbedder(client, model_id="embedding-test")

    vectors = embedder.embed_many(
        _context(),
        ("가" * 10_000, "나" * 10_000, "작은 코드 조각"),
        dimensions=2,
    )

    assert len(vectors) == 3
    assert len(client.models.embedding_calls) == 2
    assert client.models.embedding_calls[0]["contents"] == ["가" * 10_000]
    assert client.models.embedding_calls[1]["contents"] == [
        "나" * 10_000,
        "작은 코드 조각",
    ]


def test_vertex_model_rejects_non_json_response() -> None:
    client = FakeVertexClient()
    client.models.generation_response = FakeResponse(text="not-json")

    with pytest.raises(GcpGenerativeAdapterError, match="model generation unavailable"):
        GcpVertexModel(client, model_id="gemini-test").generate(
            _context(),
            {"messages": [{"role": "user", "content": "{}"}]},
        )


def test_gcp_fallback_model_uses_the_primary_when_it_is_available() -> None:
    primary = StubGcpModel({"question": "기본 모델 질문"})
    fallback = StubGcpModel({"question": "대체 모델 질문"})

    response = GcpFallbackModel((primary, fallback)).generate(_context(), {})

    assert response == {"question": "기본 모델 질문"}
    assert primary.calls == 1
    assert fallback.calls == 0


def test_gcp_fallback_model_uses_the_next_model_after_a_provider_failure() -> None:
    primary = StubGcpModel()
    fallback = StubGcpModel({"question": "대체 모델 질문"})

    response = GcpFallbackModel((primary, fallback)).generate(_context(), {})

    assert response == {"question": "대체 모델 질문"}
    assert primary.calls == 1
    assert fallback.calls == 1


def test_gcp_fallback_model_propagates_when_every_model_is_unavailable() -> None:
    with pytest.raises(GcpGenerativeAdapterError, match="all configured GCP models"):
        GcpFallbackModel((StubGcpModel(), StubGcpModel())).generate(_context(), {})
