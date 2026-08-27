export type AssessmentState =
  | "confirmed"
  | "partially_confirmed"
  | "insufficient_evidence"
  | "needs_follow_up";

export type RequirementAssessmentStatus =
  "met" | "partially_met" | "not_met" | "unknown";

export type RequirementEvidence = {
  evidenceId: string;
  sourceKind: "submission" | "interview";
  sourceType: string;
  excerpt: string;
  locator: Record<string, unknown>;
  relation: "supports" | "partially_supports" | "contradicts";
  explanation: string;
};

export type RequirementAssessment = {
  requirementAssessmentId: string;
  jobRequirementId: string;
  requirementType: "required" | "preferred";
  statement: string;
  status: RequirementAssessmentStatus;
  rationale: string;
  confidence: number;
  evidence: RequirementEvidence[];
  humanOverride: {
    status: RequirementAssessmentStatus;
    reason: string | null;
    createdAt: string;
  } | null;
};

export type InterviewStage = "technical" | "project_deep_dive" | "behavioral";

export type InterviewStageSummary = {
  stage: InterviewStage;
  label: string;
  questionCount: number;
  evidenceCount: number;
};

/** How far the quoted answer carries the criterion, as the AI graded the citation. */
export type EvidenceSufficiency = "direct" | "supporting" | "weak";

/**
 * One quoted answer span, with the prose the AI wrote about it.
 *
 * `transcriptSegmentId` is the same id the timeline uses for its entries, so a reviewer
 * can be shown the sentence the AI quoted without a second request.
 */
export type EvidenceRange = {
  evidenceId: string;
  answerTurnId: string;
  transcriptSegmentId: string;
  startMs: number;
  endMs: number;
  observation: string;
  rationale: string;
  sufficiency: EvidenceSufficiency;
};

/** A submission excerpt the interview used to build a question. Never an answer. */
export type ReviewQuestionSource = {
  sourceId: string;
  sourceType: string;
  locator: Record<string, unknown>;
  excerpt: string;
};

/**
 * One evaluation axis as the AI judged it.
 *
 * `score` is null when the answers gave no basis to judge the axis, or when the AI's
 * citations did not resolve to real Evidence. It is never 0 for those cases, so the UI
 * must never render null as a zero or fold it into an average.
 */
export type AxisAssessment = {
  axis: string;
  label: string;
  score: number | null;
  rationale: string;
  quotedEvidenceIds: string[];
  /** What this axis counted for. Null on reports scored before weights existed. */
  weight: number | null;
};

/** One scored row of a calculator: `score × normalizedWeight = contribution`. */
export type ScoreContribution = {
  /** Criterion id at report level, axis key at criterion level. */
  key: string;
  score: number;
  weight: number;
  normalizedWeight: number;
  contribution: number;
  criterionName: string | null;
  assessmentState: AssessmentState | null;
  reason: string | null;
};

/**
 * Something that carried weight but could not be scored.
 *
 * Rendered, never hidden: it is the difference between the denominator and 1.0, and without it
 * on screen the divisor appears from nowhere.
 */
export type ScoreExclusion = {
  key: string;
  weight: number;
  normalizedWeight: number;
  criterionName: string | null;
  assessmentState: AssessmentState | null;
  reason: string | null;
};

/**
 * The arithmetic behind a score.
 *
 * `denominator` is the field that cannot be inferred from the score alone: 82 out of the whole
 * interview and 82 out of the 70% of it that could be judged are different claims, and the
 * calculator has to show which one it is.
 */
export type ScoreBreakdown = {
  numerator: number;
  denominator: number;
  contributions: ScoreContribution[];
  exclusions: ScoreExclusion[];
};

export type ReviewReportItem = {
  reportItemId: string;
  /** Links the criterion to the questions the interview asked for it. */
  criterionId: string;
  criterionName: string;
  assessmentState: AssessmentState;
  observation: string;
  followUpQuestion: string | null;
  averageScore: number | null;
  axisAssessments: AxisAssessment[];
  evidence: EvidenceRange[];
  /** What this criterion counted for in the report score. 1 when nothing was weighted. */
  criterionWeight: number;
  /** How `averageScore` was reached from the axes, with the axes it could not judge. */
  axisBreakdown: ScoreBreakdown | null;
};

export type ReviewReport = {
  summary: string;
  status: string;
  /** Weighted mean across the criteria that could be scored. Never a hiring verdict. */
  overallScore: number | null;
  /** Answer delivery score, kept separate from technical and role competency scores. */
  communicationScore?: number | null;
  communicationScoredCriteriaCount?: number;
  /** Read beside `overallScore` so the number is not mistaken for the whole interview. */
  unscoredCriteriaCount: number;
  /** How `overallScore` was reached, and what it leaves out. Null on pre-scoring reports. */
  scoringBreakdown: ScoreBreakdown | null;
  items: ReviewReportItem[];
  /** The sole score source for requirement-only reports; unknown entries stay unscored. */
  requirementAssessments: RequirementAssessment[];
};

export type ReviewTimelineEntry = {
  entryId: string;
  type: "question" | "answer" | "event" | "evidence";
  startMs: number;
  endMs: number;
  text: string | null;
  questionRationale?: {
    criterionId: string;
    interviewStage?: InterviewStage;
    verificationTargetType:
      | "not_mentioned"
      | "claim_found"
      | "detail_missing"
      | "source_conflict"
      | "ownership_uncertain"
      | "company_required_question"
      | "criterion_baseline";
    objective: string;
    questionType: string;
    policyResult: string;
    sourceReferences: ReviewQuestionSource[];
  } | null;
};

/** The answer a citation points at, resolved from the transcript already on screen. */
export type ReviewAnswerQuote = {
  text: string;
  startMs: number;
  endMs: number;
};

/**
 * What the report needs from the timeline to show a citation as an answer.
 *
 * Derived from the timeline entries rather than fetched: an Evidence carries the
 * transcript segment id the timeline keys its entries by, so the sentence the AI quoted
 * is already in memory by the time the report renders.
 */
export type ReviewEvidenceContext = {
  answersBySegmentId: Record<string, ReviewAnswerQuote>;
  /** The scored question immediately before each applicant answer. */
  stageBySegmentId: Record<string, InterviewStage>;
  /** Submission excerpts the interview drew on, grouped by the criterion they served. */
  sourcesByCriterionId: Record<string, ReviewQuestionSource[]>;
};

export type ReviewTimeline = {
  entries: ReviewTimelineEntry[];
  playback: {
    status: "ready" | "partial" | "processing" | "unavailable";
    url?: string;
  };
};

export type ReviewRecruitingState = {
  invitationId: string;
  positionId: string;
  recruitingStageId: string;
  pipelineRowVersion: number;
  stages: ReadonlyArray<{
    recruitingStageId: string;
    name: string;
    sortOrder: number;
  }>;
};

export type ReviewApi = {
  overrideAssessment(
    reportItemId: string,
    assessmentState: string,
    reason: string,
  ): Promise<void>;
  overrideRequirement(
    requirementAssessmentId: string,
    requirementStatus: RequirementAssessmentStatus,
    reason: string,
  ): Promise<void>;
  addNote(targetId: string, value: string): Promise<void>;
  /** Phase 4 supplies the transactional pipeline move behind this UI boundary. */
  saveFinalDecisionStage?(stageId: string): Promise<void>;
};
