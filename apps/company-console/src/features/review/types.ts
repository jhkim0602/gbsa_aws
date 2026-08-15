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
