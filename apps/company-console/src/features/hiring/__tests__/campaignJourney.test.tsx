import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HiringWorkspace, type HiringWorkspaceApi } from "../index";

describe("HiringWorkspace", () => {
  it("creates a position, publishes criteria, and issues invitations in order", async () => {
    const api: HiringWorkspaceApi = {
      createPosition: vi.fn().mockResolvedValue({ positionId: "position-1" }),
      publishCriteria: vi.fn().mockResolvedValue({ versionId: "version-1" }),
      previewVoice: vi.fn(),
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
    fireEvent.change(screen.getByLabelText("좋은 Evidence"), {
      target: { value: "대안과 트레이드오프를 실제 사례로 설명함" },
    });
    fireEvent.change(screen.getByLabelText("약한 Evidence"), {
      target: { value: "근거 없이 결과만 주장함" },
    });
    fireEvent.change(screen.getByLabelText("판단 유보 기준"), {
      target: { value: "최종 답변 근거가 없으면 판단을 유보한다." },
    });
    fireEvent.change(screen.getByLabelText("공통 질문"), {
      target: { value: "대안을 비교한 과정을 설명해 주세요." },
    });
    fireEvent.change(screen.getByLabelText("금지 주제"), {
      target: { value: "가족, 외모" },
    });
    fireEvent.change(screen.getByLabelText("면접 시간(분)"), {
      target: { value: "45" },
    });
    fireEvent.change(screen.getByLabelText("면접관 이름"), {
      target: { value: "GBSA 기술 면접관" },
    });
    fireEvent.change(screen.getByLabelText("면접관 말투"), {
      target: { value: "차분하고 간결함" },
    });
    fireEvent.change(screen.getByLabelText("음성"), {
      target: { value: "Seoyeon" },
    });
    fireEvent.click(screen.getByRole("button", { name: "음성 미리듣기" }));
    expect(api.previewVoice).toHaveBeenCalledWith({
      name: "GBSA 기술 면접관",
      tone: "차분하고 간결함",
      voiceId: "Seoyeon",
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
    expect(api.publishCriteria).toHaveBeenCalledWith("position-1", {
      criteria: [
        expect.objectContaining({
          name: "문제 해결",
          goodEvidence: "대안과 트레이드오프를 실제 사례로 설명함",
          weakEvidence: "근거 없이 결과만 주장함",
          abstainGuidance: "최종 답변 근거가 없으면 판단을 유보한다.",
          commonQuestions: ["대안을 비교한 과정을 설명해 주세요."],
        }),
      ],
      prohibitedTopics: ["가족", "외모"],
      interviewDurationMinutes: 45,
      persona: {
        name: "GBSA 기술 면접관",
        tone: "차분하고 간결함",
        voiceId: "Seoyeon",
      },
    });
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
