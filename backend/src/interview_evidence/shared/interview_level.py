"""The 신입/주니어/시니어 interview level shared across interview modules.

The level lives here rather than inside a lane because three lanes have to speak the
same word about it: Lane A stores and publishes it with a competency version, the
integration boundary copies it onto the interview plan, and Lane C turns it into
question-depth guidance. Keeping the vocabulary in ``shared`` avoids
pointing Lane A at Lane C, which would invert the dependency direction.

What each level tells the model is prompt configuration and stays next to the prompt
in Lane C. Follow-up counts remain criterion policy and do not change by level.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

#: Absolute ceiling from ``CriterionVerificationGuide.max_follow_ups``.
MAX_FOLLOW_UPS: Final = 3


class InterviewLevel(StrEnum):
    """How deep the interview digs, chosen per position when criteria are published."""

    ENTRY = "entry"
    JUNIOR = "junior"
    SENIOR = "senior"

    def follow_up_budget(self, configured: int) -> int:
        """Return the configured follow-up budget without level-based adjustment."""
        return max(0, min(configured, MAX_FOLLOW_UPS))


#: Existing positions were published before the toggle existed and were written for
#: candidates with some experience, so they read back as 주니어.
DEFAULT_INTERVIEW_LEVEL: Final = InterviewLevel.JUNIOR
