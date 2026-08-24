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
    expect(screen.getByText("GitHub 공개 저장소 · 1개")).toBeTruthy();
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
    fireEvent.change(screen.getByLabelText("지원자 GitHub 아이디"), {
      target: { value: "candidate-dev" },
    });
    fireEvent.change(screen.getByLabelText("GitHub 저장소 URL"), {
      target: { value: "https://github.com/example/project-one" },
    });

    fireEvent.click(screen.getByRole("button", { name: "프로젝트 제출" }));
    expect(
      await screen.findByText("GitHub 프로젝트가 제출되었습니다."),
    ).toBeTruthy();
    expect(api.registerRepository).toHaveBeenCalledOnce();
    expect(api.registerRepository).toHaveBeenCalledWith(
      "https://github.com/example/project-one",
      "projects",
      "candidate-dev",
    );
    expect(
      screen.getByText("https://github.com/example/project-one"),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "프로젝트 제출" })).toBeNull();

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

  it("keeps polling an optional GitHub analysis after required materials are ready", async () => {
    vi.useFakeTimers();
    const getReadiness = vi
      .fn()
      .mockResolvedValueOnce({
        overallStatus: "analyzing",
        interviewReady: true,
        strategyId: "strategy-ready",
        materialStatuses: {
          resume: "ready",
          projects: "analyzing",
        },
      })
      .mockResolvedValue({
        overallStatus: "waiting",
        interviewReady: true,
        strategyId: "strategy-ready",
        materialStatuses: {
          resume: "ready",
          projects: "failed",
        },
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
        requirements={[
          { id: "resume", required: true, enabled: true },
          { id: "projects", required: false, enabled: true },
        ]}
        submittedMaterials={[
          { materialId: "resume", status: "ready" },
          {
            materialId: "projects",
            status: "analyzing",
            sourceUrl: "https://github.com/example/repo",
          },
        ]}
      />,
    );
    await act(async () => {
      await Promise.resolve();
    });

    expect(
      within(
        screen.getByRole("button", { name: "대표 프로젝트 선택" }),
      ).getByText("분석 중"),
    ).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "환경 점검으로 이동" }),
    ).toBeNull();
    expect(screen.getByText("자료 분석 중")).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(READINESS_POLL_INTERVAL_MS_FOR_TEST);
    });

    expect(getReadiness).toHaveBeenCalledTimes(2);
    expect(
      within(
        screen.getByRole("button", { name: "대표 프로젝트 선택" }),
      ).getByText("분석 보류"),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "환경 점검으로 이동" }),
    ).toBeTruthy();
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

  it("shows when completed materials are waiting for the interview strategy", async () => {
    const api: SubmissionWorkspaceApi = {
      uploadDocument: vi.fn(),
      registerRepository: vi.fn(),
      getReadiness: vi.fn().mockResolvedValue({
        overallStatus: "ready",
        interviewReady: false,
        materialStatuses: { resume: "ready" },
      }),
      getWorkspace: vi.fn(),
    };

    render(
      <SubmissionWorkspace
        api={api}
        requirements={[{ id: "resume", required: true, enabled: true }]}
        submittedMaterials={[{ materialId: "resume", status: "ready" }]}
      />,
    );

    expect(
      await screen.findByText(
        "자료 분석은 완료됐습니다. 면접 질문과 꼬리질문 전략을 생성하고 있습니다.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("면접 전략 생성 중")).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "환경 점검으로 이동" }),
    ).toBeNull();
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

  it("shows a submitted repository without another submission action", async () => {
    const api: SubmissionWorkspaceApi = {
      uploadDocument: vi.fn(),
      registerRepository: vi.fn(),
      getReadiness: vi
        .fn()
        .mockResolvedValue({ overallStatus: "ready", interviewReady: true }),
      getWorkspace: vi.fn(),
    };

    render(
      <SubmissionWorkspace
        api={api}
        requirements={[{ id: "projects", required: true, enabled: true }]}
        submittedMaterials={[
          {
            materialId: "projects",
            status: "ready",
            sourceUrl: "https://github.com/example/repo",
          },
        ]}
      />,
    );
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getAllByText("제출 완료").length).toBeGreaterThan(0);
    expect(screen.getByText("등록된 공개 저장소")).toBeTruthy();
    expect(screen.getByText("https://github.com/example/repo")).toBeTruthy();
    expect(screen.queryByLabelText("GitHub 저장소 URL")).toBeNull();
    expect(screen.queryByRole("button", { name: "프로젝트 제출" })).toBeNull();
  });

  it("clears a previous failure when the applicant edits the input", async () => {
    const api: SubmissionWorkspaceApi = {
      uploadDocument: vi.fn(),
      registerRepository: vi.fn(),
      getReadiness: vi
        .fn()
        .mockResolvedValue({ overallStatus: "waiting", interviewReady: false }),
      getWorkspace: vi.fn(),
    };

    render(
      <SubmissionWorkspace
        api={api}
        requirements={[{ id: "projects", required: true, enabled: true }]}
        submittedMaterials={[{ materialId: "projects", status: "failed" }]}
      />,
    );
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getAllByText("확인 필요").length).toBeGreaterThan(0);
    expect(screen.getAllByText("분석 보류").length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText("GitHub 저장소 URL"), {
      target: { value: "https://github.com/example/repo" },
    });

    expect(screen.queryByText("확인 필요")).toBeNull();
  });
});

const READINESS_POLL_INTERVAL_MS_FOR_TEST = 2_000;
