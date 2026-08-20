import { describe, expect, it } from "vitest";

import { applicantWorkspacePath } from "../applicantSummary";
import type { CompanyInvitation } from "../types";

const invitation = {
  invitationId: "invitation-1",
  positionId: "position-1",
  competencyModelVersionId: "version-1",
  applicantEmail: "applicant@example.com",
  status: "completed",
  expiresAt: "2026-08-30T00:00:00Z",
  rowVersion: 1,
} satisfies CompanyInvitation;

describe("applicantWorkspacePath", () => {
  it("opens the detailed review when the interview session exists", () => {
    expect(
      applicantWorkspacePath({
        ...invitation,
        interviewSessionId: "session-1",
      }),
    ).toBe("/review/session-1?invitationId=invitation-1");
  });

  it("opens the applicant detail before an interview session exists", () => {
    expect(applicantWorkspacePath(invitation)).toBe(
      "/positions/position-1/applicants/invitation-1",
    );
  });

  it("keeps an active interview in the applicant detail", () => {
    expect(
      applicantWorkspacePath({
        ...invitation,
        status: "interviewing",
        interviewSessionId: "session-1",
      }),
    ).toBe("/positions/position-1/applicants/invitation-1");
  });
});
