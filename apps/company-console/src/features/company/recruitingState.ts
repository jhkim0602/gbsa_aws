import type { CompanyInvitation } from "./types";

export type RecruitingStage =
  "waiting" | "materials" | "interview" | "review" | "reviewed" | "attention";

const projections: Record<
  string,
  { label: string; stage: RecruitingStage; tone: string }
> = {
  invited: { label: "초대 발송", stage: "waiting", tone: "neutral" },
  identity_verified: {
    label: "본인 확인",
    stage: "waiting",
    tone: "progress",
  },
  consented: { label: "동의 완료", stage: "waiting", tone: "progress" },
  materials_submitted: {
    label: "자료 제출",
    stage: "materials",
    tone: "progress",
  },
  analyzing: { label: "자료 분석", stage: "materials", tone: "progress" },
  ready: { label: "면접 준비", stage: "interview", tone: "ready" },
  interviewing: {
    label: "면접 진행",
    stage: "interview",
    tone: "progress",
  },
  interrupted: {
    label: "재접속 필요",
    stage: "attention",
    tone: "attention",
  },
  completed: { label: "검토 대기", stage: "review", tone: "completed" },
  reviewed: { label: "검토 완료", stage: "reviewed", tone: "completed" },
  expired: { label: "초대 만료", stage: "attention", tone: "attention" },
  revoked: { label: "초대 취소", stage: "attention", tone: "attention" },
  deleted: { label: "삭제 완료", stage: "reviewed", tone: "muted" },
};

export function invitationProjection(status: string) {
  return (
    projections[status] ?? {
      label: status,
      stage: "attention" as const,
      tone: "attention",
    }
  );
}

export function summarizeInvitations(
  invitations: readonly CompanyInvitation[],
) {
  const summary = {
    total: invitations.length,
    waiting: 0,
    materials: 0,
    interview: 0,
    review: 0,
    reviewed: 0,
    attention: 0,
  };
  for (const invitation of invitations) {
    summary[invitationProjection(invitation.status).stage] += 1;
  }
  return summary;
}

export function displayApplicant(invitation: CompanyInvitation) {
  return (
    invitation.applicantDisplayName ||
    invitation.applicantEmail.split("@")[0] ||
    "지원자"
  );
}
