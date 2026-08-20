"""The five axes a technical answer is scored on, as a vocabulary two lanes share.

The axes themselves belong to Lane D: what separates a 40 from an 80 on 깊이 is prose that
lives next to the prompt it is rendered into (``reporting/application/assessment_prompt.py``).
But the *key set* is now needed on both sides of the boundary — Lane A validates the
per-company axis weights a recruiter publishes, and Lane D validates the axis a model
returns — and a company weighting an axis that no prompt scores is a silently wrong score
rather than an error.

So the keys live here for the same reason ``InterviewLevel`` does: putting them in Lane D
and importing them from Lane A would point the upstream lane at the downstream one and
invert the dependency direction. Only the vocabulary is here. The guidance each axis is
scored by stays in Lane D, because that is prompt configuration.

Adding or removing a key is a scoring-behaviour change, not a configuration one: a
company cannot do it. Companies adjust the weights, and express what *they* value by
choosing which criteria to ask about — of which there is no limit.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final


class AssessmentAxisKey(StrEnum):
    """How an engineering answer is read, independent of what it is about."""

    CORRECTNESS = "correctness"
    DEPTH = "depth"
    FUNDAMENTALS = "fundamentals"
    OWNERSHIP = "ownership"
    COMMUNICATION = "communication"


#: Declaration order, which is the order a reviewer reads them in and the order the
#: weight sliders are rendered in. Kept as a tuple so callers cannot reorder it in place.
ASSESSMENT_AXIS_KEYS: Final[tuple[str, ...]] = tuple(axis.value for axis in AssessmentAxisKey)

#: Every key, for the membership checks both lanes perform.
ASSESSMENT_AXIS_KEY_SET: Final[frozenset[str]] = frozenset(ASSESSMENT_AXIS_KEYS)

#: The Korean label shown to a recruiter setting weights and to a reviewer reading scores.
#: Here rather than beside the guidance because both lanes render it; the guidance does not
#: leave Lane D.
ASSESSMENT_AXIS_LABELS: Final[Mapping[str, str]] = {
    AssessmentAxisKey.CORRECTNESS.value: "정확성",
    AssessmentAxisKey.DEPTH.value: "깊이",
    AssessmentAxisKey.FUNDAMENTALS.value: "CS 기본기",
    AssessmentAxisKey.OWNERSHIP.value: "본인 기여",
    AssessmentAxisKey.COMMUNICATION.value: "설명력",
}
