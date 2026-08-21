"""Weighted aggregation of scores, and the divisor it used.

Two things are aggregated with the same arithmetic: a criterion's score from its five axes,
and a report's score from its criteria. Both have to skip what could not be judged -- an axis
the answers gave no basis for, a criterion the interview never reached -- and both have to say
what they skipped.

**Returning the divisor is the reason this module exists.** "No evidence, so no score" and
"fixed weights" do not compose unless the divisor is visible. If criterion A carries 30% and is
dropped for lack of evidence, the remaining weights add to 0.70 and the score is
``numerator / 0.70``. A screen showing only "78" cannot tell a reviewer whether that is 78 out
of 100% or 78 out of 70% of the interview -- so the work meant to create traceability would
destroy it. Every caller therefore gets ``numerator``, ``denominator`` and the list of what was
excluded, not just a number.

No model is involved here. The scores arriving as input are the model's judgements; turning
them into one figure is arithmetic a reviewer can redo by hand, which is the point.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


class Weighted(Protocol):
    """One thing being aggregated: a score that may be absent, and what it counts for."""

    @property
    def key(self) -> str: ...

    @property
    def score(self) -> int | None: ...

    @property
    def weight(self) -> float: ...


@dataclass(frozen=True, slots=True)
class Entry:
    """A concrete :class:`Weighted`, for callers that do not already have one."""

    key: str
    score: int | None
    weight: float


@dataclass(frozen=True, slots=True)
class Contribution:
    """One scored entry's arithmetic, in the form a calculator renders it.

    ``normalized_weight`` is the share of the *whole* configuration, not of what survived, so
    the numbers on screen add up to ``numerator`` and the reader can see the shortfall against
    1.0 that ``denominator`` reports.
    """

    key: str
    score: int
    weight: float
    normalized_weight: float
    contribution: float


@dataclass(frozen=True, slots=True)
class Exclusion:
    """An entry that carried weight but could not be scored."""

    key: str
    weight: float
    normalized_weight: float


@dataclass(frozen=True, slots=True)
class Aggregate:
    """A weighted mean together with everything needed to re-derive it.

    ``score`` is ``round(numerator / denominator)``, or ``None`` when nothing could be scored --
    never zero. Zero would say every answer was wrong, and treating "never asked" as wrong
    would reject candidates for gaps in our own interview.
    """

    score: int | None
    numerator: float
    denominator: float
    contributions: tuple[Contribution, ...]
    exclusions: tuple[Exclusion, ...]

    @property
    def scored_count(self) -> int:
        return len(self.contributions)

    @property
    def excluded_count(self) -> int:
        return len(self.exclusions)


def aggregate(entries: Sequence[Weighted]) -> Aggregate:
    """Combine scored entries into a weighted mean, reporting what was left out.

    An entry whose ``score`` is ``None`` is excluded from both the numerator and the
    denominator. Dropping it from the numerator alone would silently mark it zero.

    A total weight of zero -- which the domain refuses on a published version but which older
    reports carry as an empty weight mapping -- is read as equal weight. That reproduces the
    plain mean those reports were actually scored with, rather than restating their history.

    No entries at all is a criterion with no axis scores: a report generated before scoring
    existed, or one the interview never reached. It has no score, which is different from
    scoring zero.
    """
    if not entries:
        return Aggregate(
            score=None,
            numerator=0.0,
            denominator=0.0,
            contributions=(),
            exclusions=(),
        )

    total_weight = sum(max(0.0, entry.weight) for entry in entries)
    if total_weight <= 0:
        # Substituted rather than recursed: an equal-weight retry on an empty sequence would
        # recurse forever, and the guard above is easy to lose sight of from in here.
        weights = [1.0] * len(entries)
        total_weight = float(len(entries))
    else:
        weights = [max(0.0, entry.weight) for entry in entries]

    contributions: list[Contribution] = []
    exclusions: list[Exclusion] = []
    numerator = 0.0
    denominator = 0.0
    for entry, weight in zip(entries, weights, strict=True):
        normalized = weight / total_weight
        if entry.score is None:
            exclusions.append(Exclusion(key=entry.key, weight=weight, normalized_weight=normalized))
            continue
        contribution = normalized * entry.score
        contributions.append(
            Contribution(
                key=entry.key,
                score=entry.score,
                weight=weight,
                normalized_weight=normalized,
                contribution=contribution,
            )
        )
        numerator += contribution
        denominator += normalized

    return Aggregate(
        # `denominator` can be zero two ways: nothing was scored, or everything scored carried
        # zero weight. Both mean there is no basis for a number, and both must not divide.
        score=round(numerator / denominator) if denominator > 0 else None,
        numerator=numerator,
        denominator=denominator,
        contributions=tuple(contributions),
        exclusions=tuple(exclusions),
    )


def weights_for(keys: Sequence[str], weights: Mapping[str, float]) -> tuple[float, ...]:
    """Line a weight mapping up with the keys being scored.

    A key the mapping does not name gets ``1.0`` rather than ``0.0``. Zero would drop that
    entry out of the score entirely, and an absent key means "not configured" -- which for a
    report frozen before weights existed is every key. The published version cannot reach here
    with a partial mapping; ``CompetencyModelVersion`` refuses one.
    """
    return tuple(float(weights.get(key, 1.0)) for key in keys)
