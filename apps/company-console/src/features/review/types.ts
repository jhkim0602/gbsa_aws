export type AssessmentState =
  | "confirmed"
  | "partially_confirmed"
  | "insufficient_evidence"
  | "needs_follow_up";

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
};

export type ReviewReport = {
  summary: string;
  status: string;
  /** Mean across the criteria that could be scored. Never a hiring verdict. */
  overallScore: number | null;
  /** Read beside `overallScore` so the number is not mistaken for the whole interview. */
  unscoredCriteriaCount: number;
  items: ReviewReportItem[];
};

export type ReviewTimelineEntry = {
  entryId: string;
  type: "question" | "answer" | "event" | "evidence";
  startMs: number;
  endMs: number;
  text: string | null;
  questionRationale?: {
    criterionId: string;
    verificationTargetType:
      | "not_mentioned"
      | "claim_found"
      | "detail_missing"
      | "source_conflict"
      | "ownership_uncertain";
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

export type ReviewDeletion = {
  status: string;
  verifiedTargets: number;
  expectedTargets: number;
};

export type ReviewHistoryEntry = {
  id: string;
  type: string;
  createdBy: string;
  createdAt: string;
};

export type ReviewApi = {
  overrideAssessment(
    reportItemId: string,
    assessmentState: string,
    reason: string,
  ): Promise<void>;
  addBookmark(targetId: string, value: string): Promise<void>;
  recordFinalDecision(
    invitationId: string,
    decision: "advance" | "reject" | "hold" | "withdrawn",
    reason: string,
  ): Promise<void>;
  requestDeletion(scopeId: string, reason: string): Promise<void>;
};
