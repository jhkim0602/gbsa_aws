import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SubmissionWorkspace, type SubmissionWorkspaceApi } from "../index";

describe("SubmissionWorkspace", () => {
  it("uploads a document, registers a public repository, and shows partial readiness", async () => {
    const api: SubmissionWorkspaceApi = {
      uploadDocument: vi.fn().mockResolvedValue(undefined),
      registerRepository: vi.fn().mockResolvedValue(undefined),
      getReadiness: vi.fn().mockResolvedValue({
        overallStatus: "partial",
        interviewReady: true,
        impactSummary:
          "Git 분석 일부가 실패했지만 문서 기반 면접은 가능합니다.",
      }),
    };
    render(<SubmissionWorkspace api={api} />);

    const file = new File(["resume"], "resume.pdf", {
      type: "application/pdf",
    });
    fireEvent.change(screen.getByLabelText("PDF 자료"), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "자료 업로드" }));
    expect(await screen.findByText("문서가 등록되었습니다.")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("공개 Git 저장소"), {
      target: { value: "https://github.com/example/project" },
    });
    fireEvent.click(screen.getByRole("button", { name: "저장소 등록" }));
    expect(await screen.findByText("저장소가 등록되었습니다.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "분석 상태 확인" }));
    expect(await screen.findByText("부분 완료")).toBeTruthy();
    expect(
      screen.getByText(
        "Git 분석 일부가 실패했지만 문서 기반 면접은 가능합니다.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("면접 진행 가능")).toBeTruthy();
  });
});
