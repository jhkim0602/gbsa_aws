"""Interview level changes prompt depth without changing follow-up counts."""

from __future__ import annotations

import pytest
from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    MAX_FOLLOW_UPS,
    InterviewLevel,
)


@pytest.mark.parametrize("level", list(InterviewLevel))
def test_every_level_keeps_the_configured_follow_up_budget(level: InterviewLevel) -> None:
    assert level.follow_up_budget(2) == 2
    assert level.follow_up_budget(0) == 0
    assert level.follow_up_budget(MAX_FOLLOW_UPS) == MAX_FOLLOW_UPS


@pytest.mark.parametrize("level", list(InterviewLevel))
def test_no_level_escapes_the_verification_guide_ceiling(level: InterviewLevel) -> None:
    # A legacy row could hold a number the domain no longer accepts; clamping here
    # keeps a bad value from turning into an unbounded interview.
    assert 0 <= level.follow_up_budget(99) <= MAX_FOLLOW_UPS
    assert level.follow_up_budget(-1) == 0


def test_versions_published_before_the_toggle_read_back_as_junior() -> None:
    assert DEFAULT_INTERVIEW_LEVEL is InterviewLevel.JUNIOR
    # The migration's server default has to agree with the enum default, otherwise
    # rows written by the database and rows written by the app disagree.
    assert DEFAULT_INTERVIEW_LEVEL.value == "junior"
