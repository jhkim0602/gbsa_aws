import { describe, expect, it } from "vitest";

import { applyConfiguredWeights } from "../CompetencyInsights";
import type {
  CompanyApplicantInsight,
  CompanyCriterionVersion,
} from "../types";

const insight: CompanyApplicantInsight = {
  invitationId: "invitation-1",
  interviewSessionId: "session-1",
  competencyModelVersionId: "version-1",
  overallScore: 86,
  unscoredCriteriaCount: 0,
  evidenceCoverage: 100,
  summary: "summary",
  criteria: [
    {
      criterionId: "SYSTEM_DESIGN",
      criterionName: "시스템 설계",
      score: 90,
      assessmentState: "confirmed",
      evidenceCount: 2,
    },
    {
      criterionId: "OWNERSHIP",
      criterionName: "오너십",
      score: 82,
      assessmentState: "partially_confirmed",
      evidenceCount: 1,
    },
  ],
};

const version = {
  versionId: "version-1",
  criteria: [
    { code: "SYSTEM_DESIGN", name: "시스템 설계", weight: 65 },
    { code: "OWNERSHIP", name: "오너십", weight: 35 },
  ],
} as CompanyCriterionVersion;

describe("configured competency weights", () => {
  it("uses the criterion version pinned to the invitation", () => {
    const [weighted] = applyConfiguredWeights([insight], [version]);

    expect(weighted.criteria.map((criterion) => criterion.weight)).toEqual([
      65, 35,
    ]);
  });

  it("leaves the overall score to the server, which froze the weights it used", () => {
    // This used to recompute the score here (65/35 over 90/82 gives 87). The report generator
    // now does the weighting and stores the weights it used in `reports.scoring_inputs`, so
    // recomputing in the browser would undo that freeze: a company adjusting its weights would
    // change a number a reviewer already acted on.
    //
    // It would also disagree with the server whenever the join is partial. It matches on
    // `code === criterionId` -- a code against a UUID, which never matches in production -- and
    // falls through to `name === criterionName`, so a renamed criterion drops out and the
    // browser would average over a subset while the report averaged over all of it.
    const [weighted] = applyConfiguredWeights([insight], [version]);

    expect(weighted.overallScore).toBe(insight.overallScore);
  });

  it("does not rewrite scores when the pinned version is unavailable", () => {
    const [unchanged] = applyConfiguredWeights([insight], []);

    expect(unchanged).toBe(insight);
    expect(unchanged.overallScore).toBe(86);
  });
});
