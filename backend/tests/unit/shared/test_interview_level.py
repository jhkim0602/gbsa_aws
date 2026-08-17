"""The 신입/주니어/시니어 toggle has to change the interview, not just label it.

Before T273 the only difficulty lever was the per-criterion ``max_follow_ups`` number,
so a recruiter reusing one competency model for an entry and a senior posting got an
identical interview. These tests pin the arithmetic half of the toggle: how far the
level is allowed to move the recruiter's configured budget.
"""

from __future__ import annotations

import pytest
from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    MAX_FOLLOW_UPS,
    InterviewLevel,
)


def test_junior_keeps_the_budget_the_recruiter_configured() -> None:
    # The configured number is the reference point; junior is the level that
    # existing versions read back as, so it must not move.
    assert InterviewLevel.JUNIOR.follow_up_budget(2) == 2
    assert InterviewLevel.JUNIOR.follow_up_budget(0) == 0


def test_entry_caps_follow_ups_at_one_so_a_first_job_candidate_is_not_drilled() -> None:
    assert InterviewLevel.ENTRY.follow_up_budget(3) == 1
    assert InterviewLevel.ENTRY.follow_up_budget(2) == 1
    # A criterion configured for no follow-up stays that way -- the level only
    # lowers the ceiling, it never invents a turn the recruiter did not ask for.
    assert InterviewLevel.ENTRY.follow_up_budget(0) == 0


def test_senior_earns_one_extra_turn_but_never_past_the_domain_limit() -> None:
    assert InterviewLevel.SENIOR.follow_up_budget(1) == 2
    assert InterviewLevel.SENIOR.follow_up_budget(MAX_FOLLOW_UPS) == MAX_FOLLOW_UPS


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
