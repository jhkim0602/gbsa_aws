import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HiringWorkspace, type HiringWorkspaceApi } from "../index";

describe("HiringWorkspace", () => {
  it("creates a position, publishes criteria, and issues invitations in order", async () => {
    const api: HiringWorkspaceApi = {
      createPosition: vi.fn().mockResolvedValue({ positionId: "position-1" }),
      publishCriteria: vi.fn().mockResolvedValue({ versionId: "version-1" }),
      createCampaign: vi.fn().mockResolvedValue({ campaignId: "campaign-1" }),
      issueInvitation: vi.fn().mockResolvedValue(undefined),
    };
    render(<HiringWorkspace api={api} />);

    fireEvent.change(screen.getByLabelText("포지션명"), {
      target: { value: "백엔드 개발자" },
    });
    fireEvent.change(screen.getByLabelText("포지션 설명"), {
      target: { value: "Python과 AWS 기반 서비스를 개발합니다." },
    });
    fireEvent.click(screen.getByRole("button", { name: "포지션 만들기" }));

    expect(await screen.findByText("평가기준 작성")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("평가기준 이름"), {
      target: { value: "문제 해결" },
    });
    fireEvent.click(screen.getByRole("button", { name: "평가기준 게시" }));

    expect(await screen.findByText("캠페인 설정")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("캠페인 이름"), {
      target: { value: "2026 백엔드 채용" },
    });
    fireEvent.click(screen.getByRole("button", { name: "캠페인 만들기" }));

    expect(await screen.findByText("지원자 초대")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("지원자 이메일"), {
      target: { value: "applicant@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "초대 보내기" }));

    expect(await screen.findByText("초대를 보냈습니다.")).toBeTruthy();
    expect(api.createPosition).toHaveBeenCalledOnce();
    expect(api.publishCriteria).toHaveBeenCalledWith("position-1", "문제 해결");
    expect(api.createCampaign).toHaveBeenCalledWith(
      "position-1",
      "version-1",
      "2026 백엔드 채용",
    );
    expect(api.issueInvitation).toHaveBeenCalledWith(
      "campaign-1",
      "applicant@example.com",
    );
  });
});
