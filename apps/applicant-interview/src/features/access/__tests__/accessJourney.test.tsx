import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApplicantAccess, type ApplicantAccessApi } from "../index";

describe("ApplicantAccess", () => {
  it("exchanges the token, verifies identity, and records all required consents", async () => {
    const api: ApplicantAccessApi = {
      exchangeToken: vi.fn().mockResolvedValue(undefined),
      verifyIdentity: vi.fn().mockResolvedValue(undefined),
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
    for (const label of ["문서 분석", "면접 녹화", "AI 평가 보조"]) {
      fireEvent.click(screen.getByLabelText(label));
    }
    fireEvent.click(screen.getByRole("button", { name: "동의하고 계속" }));

    expect(
      await screen.findByText("면접 준비를 시작할 수 있습니다."),
    ).toBeTruthy();
    expect(api.exchangeToken).toHaveBeenCalledWith("t".repeat(48));
    expect(api.verifyIdentity).toHaveBeenCalledWith("홍길동", "1234");
    expect(api.recordConsent).toHaveBeenCalledWith([
      "document_analysis",
      "recording",
      "ai_assessment",
    ]);
  });

  it("does not continue until every required purpose is accepted", async () => {
    const api: ApplicantAccessApi = {
      exchangeToken: vi.fn().mockResolvedValue(undefined),
      verifyIdentity: vi.fn().mockResolvedValue(undefined),
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
