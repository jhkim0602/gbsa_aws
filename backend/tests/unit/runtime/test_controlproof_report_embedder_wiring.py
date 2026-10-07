from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from interview_evidence.runtime import aws, production, worker
from interview_evidence.runtime.controlproof_model_substitute import (
    SPEC004_FIXTURE_ID,
    ControlProofFixedEmbedder,
)


def _compose_worker(monkeypatch: pytest.MonkeyPatch, environment: dict[str, str]):
    # Replace infrastructure creation, but exercise the real worker composition and handler.
    dependencies = Mock()
    dependencies.queues = {"reporting": worker.InMemoryQueue()}
    lane_b = Mock(spec=worker.LaneBRuntime)
    lane_b.repository = Mock()
    lane_d = Mock(spec=worker.LaneDRuntime)
    lane_d.repository = Mock()
    lane_d.deletion_service = Mock()
    runtime = SimpleNamespace(
        resources={
            "search_index": Mock(),
            "outbox": worker.InMemoryOutbox(),
            "clock": worker.SystemClock(),
            "metrics": worker.NullMetricRecorder(),
            "assistant_projector": Mock(spec=worker.ReportSearchProjector),
        },
        lanes={"submission_analysis": lane_b, "reporting": lane_d},
        boundaries={
            "company_management": Mock(spec=worker.CompanyManagementPublic),
            "interview_engine": Mock(spec=worker.InterviewEnginePublic),
            "interview_reporting": Mock(spec=worker.InterviewReportingBoundary),
            "submission_analysis": Mock(spec=worker.SubmissionAnalysisPublic),
        },
    )
    create_runtime = Mock(return_value=runtime)
    monkeypatch.setattr(aws, "create_aws_runtime_dependencies", Mock(return_value=dependencies))
    monkeypatch.setattr(production, "create_production_runtime", create_runtime)
    monkeypatch.setattr(worker, "RequestScopedDatabase", Mock(return_value=Mock()))
    monkeypatch.setattr(worker, "create_document_extractor", Mock(return_value=Mock()))
    composed = worker.create_production_worker_runtime(environment)
    handler = composed.consumers[0]._handlers["report.generation_requested"]
    assert isinstance(handler, worker.ReportRequestedEventHandler)
    return handler, dependencies.embedder, create_runtime.call_args.kwargs["embedder"]


def test_report_handler_uses_fixed_embedder_when_substitute_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    environment = {
        "APP_ENVIRONMENT": "test",
        "CONTROLPROOF_MODEL_SUBSTITUTE_ENABLED": "true",
        "CONTROLPROOF_MODEL_FIXTURE_ID": SPEC004_FIXTURE_ID,
        "CONTROLPROOF_EXTERNAL_AI_ALLOWED": "false",
        "AI_PROVIDER": "aws",
        "EMBEDDING_PROVIDER": "aws",
        "STT_PROVIDER": "disabled",
        "TTS_PROVIDER": "text_only",
        "BEDROCK_RUNTIME_ENDPOINT_URL": "http://127.0.0.1:4566",
        "TRANSCRIBE_ENDPOINT_URL": "http://127.0.0.1:4566",
        "POLLY_ENDPOINT_URL": "http://127.0.0.1:4566",
        "GCP_DOCUMENT_AI_API_ENDPOINT": "127.0.0.1:4566",
        "CONTROLPROOF_OBSERVER_ROOT": str(tmp_path),
        "CONTROLPROOF_WORKER_SESSION_ID": str(uuid4()),
        "CONTROLPROOF_WORKER_LAUNCHER_PID": "1",
        "CONTROLPROOF_WORKER_SLOT": "0",
    }
    handler, fallback, runtime_embedder = _compose_worker(monkeypatch, environment)

    assert isinstance(handler._embedder, ControlProofFixedEmbedder)
    assert handler._embedder is runtime_embedder
    assert handler._embedder is not fallback


def test_report_handler_preserves_aws_embedder_when_substitute_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler, fallback, runtime_embedder = _compose_worker(
        monkeypatch,
        {"APP_ENVIRONMENT": "test", "CONTROLPROOF_MODEL_SUBSTITUTE_ENABLED": "false"},
    )

    assert handler._embedder is fallback
    assert runtime_embedder is fallback
