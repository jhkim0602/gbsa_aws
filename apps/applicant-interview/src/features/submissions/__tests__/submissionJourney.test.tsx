import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SubmissionWorkspace, type SubmissionWorkspaceApi } from "../index";

describe("SubmissionWorkspace", () => {
  it("manages each material from the two-column workspace", async () => {
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

    expect(
      screen.getByRole("heading", { name: "지원 자료 제출" }),
    ).toBeTruthy();
    expect(screen.getByText("자기소개서")).toBeTruthy();
    expect(screen.getByText("포트폴리오")).toBeTruthy();
    expect(screen.getByText("공개 Git 저장소 · 최대 3개")).toBeTruthy();
    expect(screen.queryByText("이미 제출했어요")).toBeNull();
    expect(screen.queryByText("분석 진행 중")).toBeNull();
    const file = new File(["resume"], "resume.pdf", {
      type: "application/pdf",
    });
    fireEvent.change(screen.getByLabelText("이력서 PDF"), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "제출하기" }));
    expect(await screen.findByText("이력서가 제출되었습니다.")).toBeTruthy();
    expect(api.uploadDocument).toHaveBeenCalledWith(file, "resume");

    fireEvent.click(screen.getByRole("button", { name: "대표 프로젝트 선택" }));
    fireEvent.change(screen.getByLabelText("저장소 URL 1"), {
      target: { value: "https://github.com/example/project-one" },
    });
    fireEvent.click(screen.getByRole("button", { name: "저장소 추가" }));
    fireEvent.change(screen.getByLabelText("저장소 URL 2"), {
      target: { value: "https://github.com/example/project-two" },
    });
    fireEvent.click(screen.getByRole("button", { name: "저장소 추가" }));
    fireEvent.change(screen.getByLabelText("저장소 URL 3"), {
      target: { value: "https://github.com/example/project-three" },
    });
    expect(screen.queryByRole("button", { name: "저장소 추가" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "프로젝트 제출" }));
    expect(
      await screen.findByText("프로젝트 3개가 제출되었습니다."),
    ).toBeTruthy();
    expect(api.registerRepository).toHaveBeenCalledTimes(3);
    expect(api.registerRepository).toHaveBeenNthCalledWith(
      1,
      "https://github.com/example/project-one",
      "projects",
    );
    expect(api.registerRepository).toHaveBeenNthCalledWith(
      3,
      "https://github.com/example/project-three",
      "projects",
    );

    expect(await screen.findByText("일부 완료")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "분석 상태 확인" })).toBeNull();
  });
});
