"""Ask the model to score one criterion, then refuse what it cannot back up.

This is the seam between judgement and verification. The model decides the numbers --
Python has no way to tell a shallow answer from a deep one, and a formula that tried would
be measuring answer length. Python decides whether a number is allowed to be shown: every
axis must cite Evidence that actually exists, and the citation is resolved before the score
is stored. A score whose support does not resolve is withheld, because a reviewer cannot
overrule reasoning they are unable to check.

Scoring is deliberately non-fatal. If the model is unavailable the report is still
generated, just without axis scores, because the transcript, the video intervals and the
Evidence trail are the part a reviewer cannot reconstruct themselves -- losing those to a
model outage would be the worse failure.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError

from interview_evidence.reporting.application.assessment_prompt import (
    ASSESSMENT_AXES,
    AnswerForAssessment,
    AssessmentPromptTemplate,
    AssessmentVerdict,
    assessment_prompt_for,
    build_assessment_prompt,
    parse_assessment_response,
)
from interview_evidence.reporting.domain.report import (
    AssessmentState,
    AxisAssessment,
)
from interview_evidence.shared.aws_clients.ports import AIModel
from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    InterviewLevel,
)
from interview_evidence.shared.operations import MetricRecorder, NullMetricRecorder
from interview_evidence.shared.tenant import TenantContext

#: The Korean label a reviewer reads for each axis key. Snapshotted onto every stored
#: assessment so an old report keeps its wording after the axis list changes.
_AXIS_LABELS = {axis.key: axis.label for axis in ASSESSMENT_AXES}


@dataclass(frozen=True, slots=True)
class CriterionAssessment:
    """What the model concluded about one criterion, after verification."""

    axis_assessments: tuple[AxisAssessment, ...]
    assessment_state: AssessmentState
    summary: str
    follow_up_question: str | None


class CriterionAssessor:
    def __init__(
        self,
        model: AIModel,
        *,
        prompt: AssessmentPromptTemplate | None = None,
        metrics: MetricRecorder | None = None,
    ) -> None:
        self._model = model
        # An explicit template pins every level to it, which is what a scoring-calibration
        # experiment wants. Left unset, the interview's level chooses.
        self._prompt = prompt
        self._metrics = metrics or NullMetricRecorder()

    def prompt_for(self, level: InterviewLevel) -> AssessmentPromptTemplate:
        return self._prompt or assessment_prompt_for(level)

    def assess(
        self,
        context: TenantContext,
        *,
        criterion_id: UUID,
        criterion_name: str,
        criterion_text: str,
        answers: Sequence[AnswerForAssessment],
        model_config_version: str,
        interview_level: InterviewLevel = DEFAULT_INTERVIEW_LEVEL,
    ) -> CriterionAssessment | None:
        """Score a criterion, or return None when the model could not be used.

        None is not "the candidate failed" -- it is "we have no judgement", which the
        caller renders as a report item without scores rather than as a zero.
        """
        if not answers:
            self._record_criterion_outcome("no_answers")
            return None
        try:
            response = self._model.generate(
                context,
                build_assessment_prompt(
                    self.prompt_for(interview_level),
                    criterion_id=criterion_id,
                    criterion_name=criterion_name,
                    criterion_text=criterion_text,
                    answers=answers,
                    model_config_version=model_config_version,
                ),
            )
            verdict = parse_assessment_response(response)
        except (RuntimeError, ValidationError, TypeError, ValueError, KeyError):
            # Deliberately swallowed: see the module docstring. A scoring failure must not
            # cost the reviewer the Evidence trail.
            self._record_criterion_outcome("model_unavailable")
            return None
        verified = verdict.verified_against(frozenset(answer.evidence_id for answer in answers))
        accepted_axes = sum(score.score is not None for score in verified.axis_scores)
        withheld_axes = sum(
            original.score is not None and checked.score is None
            for original, checked in zip(verdict.axis_scores, verified.axis_scores, strict=True)
        )
        if accepted_axes:
            self._metrics.record(
                "ai_assessment_axis_count",
                float(accepted_axes),
                unit="Count",
                dimensions={"outcome": "evidence_verified"},
            )
        if withheld_axes:
            self._metrics.record(
                "ai_assessment_axis_count",
                float(withheld_axes),
                unit="Count",
                dimensions={"outcome": "citation_withheld"},
            )
        self._record_criterion_outcome(
            "citation_withheld"
            if withheld_axes and not accepted_axes
            else "partially_verified"
            if withheld_axes
            else "evidence_verified"
        )
        return CriterionAssessment(
            axis_assessments=tuple(
                AxisAssessment(
                    axis=score.axis,
                    label=_AXIS_LABELS.get(score.axis, score.axis),
                    score=score.score,
                    rationale=score.rationale,
                    quoted_evidence_ids=score.quoted_evidence_ids,
                )
                for score in verified.axis_scores
            ),
            assessment_state=_state_of(verified),
            summary=verified.summary,
            follow_up_question=verified.follow_up_question,
        )

    def _record_criterion_outcome(self, outcome: str) -> None:
        self._metrics.record(
            "ai_assessment_criterion_count",
            1,
            unit="Count",
            dimensions={"outcome": outcome},
        )


def _state_of(verdict: AssessmentVerdict) -> AssessmentState:
    """Read the model's evidence state, defaulting to the one that asks for a human.

    An unrecognised state is treated as needing follow-up rather than as confirmed: the
    failure mode of over-confirming is a reviewer who skips an answer they should have
    watched, which is worse than one extra prompt to look.
    """
    try:
        return AssessmentState(verdict.assessment_state)
    except ValueError:
        return AssessmentState.NEEDS_FOLLOW_UP
