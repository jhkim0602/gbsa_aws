from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

ALLOWED_METRIC_DIMENSIONS = frozenset(
    {
        "config_version",
        "outcome",
        "queue",
        "service",
        "stage",
        "store",
    }
)


@dataclass(frozen=True, slots=True)
class MetricRecord:
    name: str
    value: float
    unit: str
    dimensions: Mapping[str, str]


class MetricRecorder(Protocol):
    def record(
        self,
        name: str,
        value: float,
        *,
        unit: str,
        dimensions: Mapping[str, str],
    ) -> None: ...


class CloudWatchClient(Protocol):
    def put_metric_data(self, **kwargs: object) -> Mapping[str, object]: ...


def _validate_dimensions(dimensions: Mapping[str, str]) -> None:
    invalid = set(dimensions) - ALLOWED_METRIC_DIMENSIONS
    if invalid:
        raise ValueError("metric dimension is not allowed")


class InMemoryMetricRecorder:
    def __init__(self) -> None:
        self.records: list[MetricRecord] = []

    def record(
        self,
        name: str,
        value: float,
        *,
        unit: str,
        dimensions: Mapping[str, str],
    ) -> None:
        _validate_dimensions(dimensions)
        self.records.append(
            MetricRecord(
                name=name,
                value=float(value),
                unit=unit,
                dimensions=dict(dimensions),
            )
        )


class CloudWatchMetricRecorder:
    def __init__(
        self,
        client: CloudWatchClient,
        *,
        namespace: str,
    ) -> None:
        self._client = client
        self._namespace = namespace

    def record(
        self,
        name: str,
        value: float,
        *,
        unit: str,
        dimensions: Mapping[str, str],
    ) -> None:
        _validate_dimensions(dimensions)
        self._client.put_metric_data(
            Namespace=self._namespace,
            MetricData=[
                {
                    "MetricName": name,
                    "Value": float(value),
                    "Unit": unit,
                    "Dimensions": [
                        {"Name": key, "Value": dimensions[key]} for key in sorted(dimensions)
                    ],
                }
            ],
        )


class NullMetricRecorder:
    def record(
        self,
        name: str,
        value: float,
        *,
        unit: str,
        dimensions: Mapping[str, str],
    ) -> None:
        del name, value, unit, dimensions


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    status: str
    dependencies: Mapping[str, str]

    @property
    def ready(self) -> bool:
        return self.status == "ok"


class ReadinessChecker(Protocol):
    def check(self) -> ReadinessReport: ...


class DependencyReadiness:
    def __init__(self, probes: Mapping[str, Callable[[], None]]) -> None:
        self._probes = dict(probes)

    def check(self) -> ReadinessReport:
        dependencies: dict[str, str] = {}
        for name in sorted(self._probes):
            try:
                self._probes[name]()
            except Exception:
                dependencies[name] = "unavailable"
            else:
                dependencies[name] = "ok"
        return ReadinessReport(
            status=(
                "ok" if all(status == "ok" for status in dependencies.values()) else "degraded"
            ),
            dependencies=dependencies,
        )
