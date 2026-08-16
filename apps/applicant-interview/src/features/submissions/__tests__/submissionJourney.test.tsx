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
    const onContinue = vi.fn();
    render(<SubmissionWorkspace api={api} onContinue={onContinue} />);

    expect(
      screen.getByRole("heading", { name: "지원 자료 제출" }),
    ).toBeTruthy();
    expect(screen.getByText("PDF · 최대 10MB")).toBeTruthy();
    expect(
      screen.getByText("공개 Git 저장소 · 최대 3개 · 선택사항"),
    ).toBeTruthy();
    const file = new File(["resume"], "resume.pdf", {
      type: "application/pdf",
    });
    fireEvent.change(screen.getByLabelText("PDF 자료"), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "자료 업로드" }));
    expect(await screen.findByText("문서가 등록되었습니다.")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("대표 프로젝트 URL 1"), {
      target: { value: "https://github.com/example/project-one" },
    });
    fireEvent.click(screen.getByRole("button", { name: "프로젝트 추가" }));
    fireEvent.change(screen.getByLabelText("대표 프로젝트 URL 2"), {
      target: { value: "https://github.com/example/project-two" },
    });
    fireEvent.click(screen.getByRole("button", { name: "프로젝트 추가" }));
    fireEvent.change(screen.getByLabelText("대표 프로젝트 URL 3"), {
      target: { value: "https://github.com/example/project-three" },
    });
    expect(screen.queryByRole("button", { name: "프로젝트 추가" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "프로젝트 등록" }));
    expect(
      await screen.findByText("프로젝트 3개가 등록되었습니다."),
    ).toBeTruthy();
    expect(api.registerRepository).toHaveBeenCalledTimes(3);
    expect(api.registerRepository).toHaveBeenNthCalledWith(
      1,
      "https://github.com/example/project-one",
    );
    expect(api.registerRepository).toHaveBeenNthCalledWith(
      3,
      "https://github.com/example/project-three",
    );

    fireEvent.click(screen.getByRole("button", { name: "분석 상태 확인" }));
    expect(await screen.findByText("부분 완료")).toBeTruthy();
    expect(
      screen.getByText(
        "Git 분석 일부가 실패했지만 문서 기반 면접은 가능합니다.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("면접 진행 가능")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "환경 점검으로 이동" }));
    expect(onContinue).toHaveBeenCalledOnce();
  });
});
