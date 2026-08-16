import { invitationRecruiterPhase } from "../hiring";
import type { CompanyInvitation } from "./types";

export type PositionTab =
  "overview" | "applicants" | "statistics" | "stages" | "information";

export const recruiterStages = [
  {
    phase: 1,
    title: "초대·확인",
    description: "초대 발송부터 본인 확인과 필수 동의까지",
  },
  {
    phase: 2,
    title: "자료 제출·분석",
    description: "지원자 자료 제출과 면접 검증 목표 준비",
  },
  {
    phase: 3,
    title: "면접",
    description: "장비 점검부터 구조화 면접 완료까지",
  },
  {
    phase: 4,
    title: "결과 검토",
    description: "영상·응답·분석 확인과 사람의 최종 검토",
  },
] as const;

const attentionStatuses = new Set(["interrupted", "expired", "revoked"]);

export function countRecruiterPhases(
  invitations: readonly CompanyInvitation[],
) {
  return recruiterStages.map(
    ({ phase }) =>
      invitations.filter(
        (invitation) => invitationRecruiterPhase(invitation.status) === phase,
      ).length,
  );
}

export function countAttentionInvitations(
  invitations: readonly CompanyInvitation[],
) {
  return invitations.filter((invitation) =>
    attentionStatuses.has(invitation.status),
  ).length;
}

export function countAwaitingInvitations(
  invitations: readonly CompanyInvitation[],
) {
  return invitations.filter(
    (invitation) => invitationRecruiterPhase(invitation.status) === 1,
  ).length;
}
