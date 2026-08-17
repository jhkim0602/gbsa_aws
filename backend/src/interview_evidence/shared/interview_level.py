"""The 신입/주니어/시니어 interview level and the follow-up budget it implies.

The level lives here rather than inside a lane because three lanes have to speak the
same word about it: Lane A stores and publishes it with a competency version, the
integration boundary copies it onto the interview plan, and Lane C turns it into
question depth and a follow-up budget. Keeping the vocabulary in ``shared`` avoids
pointing Lane A at Lane C, which would invert the dependency direction.

Only the scalar policy lives here. What each level tells the model is prompt
configuration and stays next to the prompt in Lane C.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

#: Absolute ceiling from ``CriterionVerificationGuide.max_follow_ups``. A level may
#: shrink or grow the configured budget but never past the domain limit.
MAX_FOLLOW_UPS: Final = 3


class InterviewLevel(StrEnum):
    """How deep the interview digs, chosen per position when criteria are published."""

    ENTRY = "entry"
    JUNIOR = "junior"
    SENIOR = "senior"

    def follow_up_budget(self, configured: int) -> int:
        """Adjust a criterion's configured follow-up budget for this level.

        The recruiter's per-criterion number stays the reference point; the level only
        moves it. An entry-level interview is capped at a single follow-up so a first
        job candidate is not drilled three deep on one criterion, while a senior
        interview earns one extra turn to push past the first plausible answer.

        A criterion configured for no follow-up is the recruiter saying the common
        question is enough, so no level adds a turn to it.
        """
        bounded = max(0, min(configured, MAX_FOLLOW_UPS))
        if bounded == 0:
            return 0
        if self is InterviewLevel.ENTRY:
            return 1
        if self is InterviewLevel.SENIOR:
            return min(bounded + 1, MAX_FOLLOW_UPS)
        return bounded


#: Existing positions were published before the toggle existed and were written for
#: candidates with some experience, so they read back as 주니어.
DEFAULT_INTERVIEW_LEVEL: Final = InterviewLevel.JUNIOR
