import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApplicantAccess, type ApplicantAccessApi } from "../index";

describe("ApplicantAccess", () => {
  it("exchanges the token, verifies identity, and records all required consents", async () => {
    const api: ApplicantAccessApi = {
      exchangeToken: vi.fn().mockResolvedValue(undefined),
      verifyIdentity: vi.fn().mockResolvedValue(undefined),
      getConsentPolicy: vi.fn().mockResolvedValue(consentPolicy),
      recordConsent: vi.fn().mockResolvedValue(undefined),
    };
    render(<ApplicantAccess api={api} initialToken={"t".repeat(48)} />);

    fireEvent.click(screen.getByRole("button", { name: "초대 확인" }));
    expect(await screen.findByText("본인 확인")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("이름"), {
      target: { value: "홍길동" },
    });
    fireEvent.change(screen.getByLabelText("확인 값"), {
      target: { value: "1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: "본인 확인 완료" }));

    expect(await screen.findByText("개인정보 및 면접 처리 동의")).toBeTruthy();
    expect(screen.getByText(consentPolicy.aiRole)).toBeTruthy();
    expect(screen.getByText(consentPolicy.recordingNotice)).toBeTruthy();
    expect(screen.getByText("보관기간: 180일")).toBeTruthy();
    expect(screen.getByText(consentPolicy.deletionMethod)).toBeTruthy();
    for (const label of ["문서 분석", "면접 녹화", "AI 평가 보조"]) {
      fireEvent.click(screen.getByLabelText(label));
    }
    fireEvent.click(screen.getByRole("button", { name: "동의하고 계속" }));

    expect(
      await screen.findByText("면접 준비를 시작할 수 있습니다."),
    ).toBeTruthy();
    expect(api.exchangeToken).toHaveBeenCalledWith("t".repeat(48));
    expect(api.verifyIdentity).toHaveBeenCalledWith("홍길동", "1234");
    expect(api.recordConsent).toHaveBeenCalledWith(consentPolicy, [
      "document_analysis",
      "recording",
      "ai_assessment",
    ]);
  });

  it("does not continue until every required purpose is accepted", async () => {
    const api: ApplicantAccessApi = {
      exchangeToken: vi.fn().mockResolvedValue(undefined),
      verifyIdentity: vi.fn().mockResolvedValue(undefined),
      getConsentPolicy: vi.fn().mockResolvedValue(consentPolicy),
      recordConsent: vi.fn().mockResolvedValue(undefined),
    };
    render(<ApplicantAccess api={api} initialToken={"t".repeat(48)} />);

    fireEvent.click(screen.getByRole("button", { name: "초대 확인" }));
    fireEvent.change(await screen.findByLabelText("이름"), {
      target: { value: "홍길동" },
    });
    fireEvent.change(screen.getByLabelText("확인 값"), {
      target: { value: "1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: "본인 확인 완료" }));
    fireEvent.click(await screen.findByLabelText("문서 분석"));

    expect(
      screen.getByRole("button", { name: "동의하고 계속" }),
    ).toHaveProperty("disabled", true);
  });
});

const consentPolicy = {
  policyVersion: "2026-08-v1",
  aiRole:
    "AI는 질문과 평가 초안을 만들지만 최종 채용 결정은 기업의 사람이 수행합니다.",
  recordingNotice: "면접 중 음성과 영상이 녹화됩니다.",
  processingPurposes: [
    {
      purpose: "document_analysis" as const,
      title: "문서 분석",
      description: "제출 자료를 질문 준비에 사용합니다.",
    },
    {
      purpose: "recording" as const,
      title: "면접 녹화",
      description: "영상과 음성을 사람 검토에 사용합니다.",
    },
    {
      purpose: "ai_assessment" as const,
      title: "AI 평가 보조",
      description: "최종 답변 근거로 평가 초안을 만듭니다.",
    },
  ],
  retentionDays: 180,
  deletionMethod: "보관기간 만료 또는 요청 시 원본과 파생 데이터를 삭제합니다.",
  requiredPurposes: [
    "document_analysis" as const,
    "recording" as const,
    "ai_assessment" as const,
  ],
  contentDigest: "d".repeat(64),
};
