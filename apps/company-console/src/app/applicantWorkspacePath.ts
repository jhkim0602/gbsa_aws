type ApplicantWorkspaceTarget = Readonly<{
  invitationId: string;
  positionId: string;
  status: string;
  interviewStatus?: string | null;
  reportStatus?: string | null;
  interviewSessionId?: string | null;
}>;

export function interviewReviewPath(
  interviewSessionId: string,
  invitationId: string,
): string {
  const search = new URLSearchParams({ invitationId });
  return `/review/${interviewSessionId}?${search.toString()}`;
}

export function applicantWorkspacePath(
  invitation: ApplicantWorkspaceTarget,
): string {
  const interviewCompleted =
    invitation.interviewStatus === "completed" ||
    invitation.status === "completed" ||
    invitation.status === "reviewed" ||
    invitation.reportStatus === "ready";
  if (invitation.interviewSessionId && interviewCompleted) {
    return interviewReviewPath(
      invitation.interviewSessionId,
      invitation.invitationId,
    );
  }
  return `/positions/${invitation.positionId}/applicants/${invitation.invitationId}`;
}
