export type AssessmentState =
  | "confirmed"
  | "partially_confirmed"
  | "insufficient_evidence"
  | "needs_follow_up";

export type EvidenceRange = {
  evidenceId: string;
  startMs: number;
  endMs: number;
};

export type ReviewReportItem = {
  reportItemId: string;
  criterionName: string;
  assessmentState: AssessmentState;
  observation: string;
  evidence: EvidenceRange[];
};

export type ReviewReport = {
  summary: string;
  status: string;
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
    sourceReferences: Array<{
      sourceId: string;
      sourceType: string;
      locator: Record<string, unknown>;
      excerpt: string;
    }>;
  } | null;
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
