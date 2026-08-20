import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SubmissionWorkspace, type SubmissionWorkspaceApi } from "../index";

afterEach(() => {
  vi.useRealTimers();
});

describe("SubmissionWorkspace", () => {
  it("shows only configured materials and blocks interview until all required ones are ready", async () => {
    const onContinue = vi.fn();
    const api: SubmissionWorkspaceApi = {
      uploadDocument: vi.fn(),
      registerRepository: vi.fn(),
      getReadiness: vi.fn().mockResolvedValue({
        overallStatus: "ready",
        interviewReady: true,
      }),
      getWorkspace: vi.fn(),
    };
    render(
      <SubmissionWorkspace
        api={api}
        requirements={[
          { id: "resume", required: true, enabled: true },
          { id: "cover-letter", required: false, enabled: false },
        ]}
        submittedMaterials={[]}
        onContinue={onContinue}
      />,
    );

    expect(screen.getAllByText("이력서").length).toBeGreaterThan(0);
    expect(screen.queryByText("자기소개서")).toBeNull();
    expect(
      await screen.findByText("필수 자료 1개를 더 제출해 주세요."),
    ).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "환경 점검으로 이동" }),
    ).toBeNull();
  });

  it("manages each material from the two-column workspace", async () => {
    const api: SubmissionWorkspaceApi = {
      uploadDocument: vi.fn().mockResolvedValue(undefined),
      registerRepository: vi.fn().mockResolvedValue(undefined),
      getReadiness: vi.fn().mockResolvedValue({
        overallStatus: "partial",
        interviewReady: true,
        materialStatuses: {
          resume: "partial",
          projects: "partial",
        },
        impactSummary:
          "Git 분석 일부가 실패했지만 문서 기반 면접은 가능합니다.",
      }),
      getWorkspace: vi.fn(),
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

    expect((await screen.findAllByText("일부 완료")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "분석 상태 확인" })).toBeNull();
  });

  it("polls analysis readiness and enables the interview journey when ready", async () => {
    vi.useFakeTimers();
    const onContinue = vi.fn();
    const getReadiness = vi
      .fn()
      .mockResolvedValueOnce({
        overallStatus: "waiting",
        interviewReady: false,
      })
      .mockResolvedValue({
        overallStatus: "ready",
        interviewReady: true,
        strategyId: "strategy-ready",
      });
    const api: SubmissionWorkspaceApi = {
      uploadDocument: vi.fn(),
      registerRepository: vi.fn(),
      getReadiness,
      getWorkspace: vi.fn(),
    };

    render(
      <SubmissionWorkspace
        api={api}
        requirements={[{ id: "resume", required: true, enabled: true }]}
        submittedMaterials={[{ materialId: "resume", status: "requested" }]}
        onContinue={onContinue}
      />,
    );

    await act(async () => {
      await Promise.resolve();
    });
    expect(getReadiness).toHaveBeenCalledTimes(1);
    expect(
      screen.queryByRole("button", { name: "환경 점검으로 이동" }),
    ).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(READINESS_POLL_INTERVAL_MS_FOR_TEST);
    });

    const continueButton = screen.getByRole("button", {
      name: "환경 점검으로 이동",
    });
    expect(
      screen.getAllByRole("button", { name: "환경 점검으로 이동" }),
    ).toHaveLength(1);
    fireEvent.click(continueButton);
    expect(getReadiness).toHaveBeenCalledTimes(2);
    expect(onContinue).toHaveBeenCalledWith("strategy-ready");
  });

  it("shows analysis status independently for each submitted material", async () => {
    const api: SubmissionWorkspaceApi = {
      uploadDocument: vi.fn(),
      registerRepository: vi.fn(),
      getReadiness: vi.fn().mockResolvedValue({
        overallStatus: "analyzing",
        interviewReady: false,
        materialStatuses: {
          resume: "analyzing",
          "cover-letter": "ready",
        },
      }),
      getWorkspace: vi.fn(),
    };

    render(
      <SubmissionWorkspace
        api={api}
        requirements={[
          { id: "resume", required: true, enabled: true },
          { id: "cover-letter", required: true, enabled: true },
        ]}
        submittedMaterials={[
          { materialId: "resume", status: "analyzing" },
          { materialId: "cover-letter", status: "ready" },
        ]}
      />,
    );

    expect(
      await within(
        screen.getByRole("button", { name: "이력서 선택" }),
      ).findByText("분석 중"),
    ).toBeTruthy();
    expect(
      within(screen.getByRole("button", { name: "자기소개서 선택" })).getByText(
        "분석 완료",
      ),
    ).toBeTruthy();
  });

  it("shows local analysis output in the developer panel", async () => {
    const getAnalysisDebug = vi.fn().mockResolvedValue({
      analyses: [
        {
          extractor_version: "hybrid-pypdf-gcp-document-ai-v1",
          status: "ready",
        },
      ],
      extracted_documents: [
        {
          source_id: "source-1",
          material_type: "resume",
          locator: { page_number: 1, section: "경력" },
          text: "백엔드 서비스 개발 및 운영 경험",
        },
      ],
      strategy: {
        strategy_version: 3,
        status: "ready",
        common_topics: ["문제 해결"],
        verification_points: [
          {
            criterion_id: "criterion-1",
            prompt: "가장 어려웠던 기술적 문제를 설명해주세요.",
            source_ids: ["source-1"],
          },
        ],
        follow_up_directions: {
          "criterion-1": ["다른 해결 방법도 검토했나요?"],
        },
        time_budget: { total_seconds: 1800 },
        required_evidence_plan: { "criterion-1": 3 },
        source_reference_candidates: [{ source_id: "source-1" }],
        model_config_version: "strategy-v1",
      },
    });
    const api: SubmissionWorkspaceApi = {
      uploadDocument: vi.fn(),
      registerRepository: vi.fn(),
      getReadiness: vi.fn().mockResolvedValue({
        overallStatus: "ready",
        interviewReady: true,
      }),
      getWorkspace: vi.fn(),
      getAnalysisDebug,
    };

    render(
      <SubmissionWorkspace
        api={api}
        requirements={[{ id: "resume", required: true, enabled: true }]}
        submittedMaterials={[{ materialId: "resume", status: "ready" }]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "분석 결과 불러오기" }));

    expect(
      (await screen.findAllByText(/hybrid-pypdf-gcp-document-ai-v1/)).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("최종 면접 전략")).toBeTruthy();
    expect(screen.getByText("문제 해결")).toBeTruthy();
    expect(
      screen.getByText("가장 어려웠던 기술적 문제를 설명해주세요."),
    ).toBeTruthy();
    expect(screen.getByText("다른 해결 방법도 검토했나요?")).toBeTruthy();
    expect(
      screen.getAllByText("백엔드 서비스 개발 및 운영 경험").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("원본 JSON 보기")).toBeTruthy();
    expect(getAnalysisDebug).toHaveBeenCalledOnce();
  });
});

const READINESS_POLL_INTERVAL_MS_FOR_TEST = 2_000;
