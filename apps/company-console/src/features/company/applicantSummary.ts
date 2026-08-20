import type { CompanyInvitation } from "./types";

const progressStatuses = new Set<CompanyInvitation["status"]>([
  "materials_submitted",
  "analyzing",
  "ready",
  "interviewing",
  "interrupted",
]);

export function summarizeApplicantPipeline(
  invitations: readonly CompanyInvitation[],
) {
  return invitations.reduce(
    (summary, invitation) => {
      summary.total += 1;
      if (progressStatuses.has(invitation.status)) summary.inProgress += 1;
      if (invitation.status === "completed") summary.reviewPending += 1;
      if (invitation.status === "reviewed") summary.completed += 1;
      return summary;
    },
    { total: 0, inProgress: 0, reviewPending: 0, completed: 0 },
  );
}

export function applicantWorkspacePath(invitation: CompanyInvitation): string {
  if (
    invitation.interviewSessionId &&
    (invitation.status === "completed" || invitation.status === "reviewed")
  ) {
    const search = new URLSearchParams({
      invitationId: invitation.invitationId,
    });
    return `/review/${invitation.interviewSessionId}?${search.toString()}`;
  }
  return `/positions/${invitation.positionId}/applicants/${invitation.invitationId}`;
}
