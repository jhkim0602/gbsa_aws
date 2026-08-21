import { describe, expect, it } from "vitest";

import {
  applicantWorkspacePath,
  interviewReviewPath,
} from "../applicantWorkspacePath";

const invitation = {
  invitationId: "invitation-1",
  positionId: "position-1",
  status: "materials_submitted",
};

describe("applicantWorkspacePath", () => {
  it("opens the detailed review when the interview projection is completed", () => {
    expect(
      applicantWorkspacePath({
        ...invitation,
        interviewStatus: "completed",
        reportStatus: "ready",
        interviewSessionId: "session-1",
      }),
    ).toBe("/review/session-1?invitationId=invitation-1");
  });

  it("keeps an active interview in the applicant detail", () => {
    expect(
      applicantWorkspacePath({
        ...invitation,
        interviewStatus: "interviewing",
        interviewSessionId: "session-1",
      }),
    ).toBe("/positions/position-1/applicants/invitation-1");
  });

  it("builds a detailed review path for report insights", () => {
    expect(interviewReviewPath("session-1", "invitation-1")).toBe(
      "/review/session-1?invitationId=invitation-1",
    );
  });
});
