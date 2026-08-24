import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CompanyOperationsApi } from "../../company/types";
import type { RecruitingAssistantApi } from "../api";
import { AiRecruitingAssistant } from "../AiRecruitingAssistant";

const api: CompanyOperationsApi = {
  getCurrentUser: vi.fn().mockResolvedValue({
    companyUserId: "user-1",
    companyId: "company-1",
    email: "recruiter@example.com",
    status: "active",
  }),
  listPositions: vi.fn().mockResolvedValue([
    {
      positionId: "position-1",
      title: "백엔드 플랫폼 엔지니어",
      description: "플랫폼을 개발합니다.",
      submissionRequirements: [],
      status: "active",
      rowVersion: 1,
      createdAt: "2026-08-21T00:00:00Z",
    },
  ]),
  getPosition: vi.fn(),
  listInvitations: vi.fn().mockResolvedValue([
    {
      invitationId: "invitation-1",
      positionId: "position-1",
      competencyModelVersionId: "version-1",
      applicantEmail: "minjun@example.com",
      applicantDisplayName: "김민준",
      status: "completed",
      expiresAt: "2026-08-30T00:00:00Z",
      rowVersion: 1,
      interviewSessionId: "session-1",
    },
  ]),
  updatePosition: vi.fn(),
  listCriterionVersions: vi.fn().mockResolvedValue([]),
  publishCriteria: vi.fn(),
  listSubmissions: vi.fn().mockResolvedValue([]),
  listApplicantInsights: vi.fn().mockResolvedValue([
    {
      invitationId: "invitation-1",
      interviewSessionId: "session-1",
      competencyModelVersionId: "version-1",
      overallScore: 87,
      unscoredCriteriaCount: 0,
      evidenceCoverage: 100,
      summary: "구체적인 시스템 설계 근거가 확인됩니다.",
      criteria: [
        {
          criterionId: "system-design",
          criterionName: "시스템 설계",
          score: 87,
          assessmentState: "confirmed",
          evidenceCount: 2,
        },
      ],
    },
  ]),
};

const assistantResponse = {
  scope: "company",
  positionId: null,
  answer:
    "김민준 지원자의 시스템 설계 근거가 확인됩니다.\n\n최종 판단 전 기준별 원문 근거를 함께 검토해 주세요.",
  degradedMode: null,
  sources: [
    {
      sourceId: "source-1",
      positionId: "position-1",
      applicantId: "applicant-1",
      invitationId: "invitation-1",
      reportId: "report-1",
      reportItemId: null,
      criterionId: null,
      documentType: "report_summary",
      excerpt:
        "지원자 종합 평가 리포트\n지원자명: 김민준\n지원 포지션: 백엔드 플랫폼 엔지니어\n리포트 상태: ready\n종합 점수: 87\n종합 요약: 구체적인 시스템 설계 근거가 확인됩니다.",
      score: 0.96,
      scoreComponents: { vector: 0.97, lexical: 0.94 },
      metadata: { overall_score: 87 },
    },
    {
      sourceId: "source-2",
      positionId: "position-1",
      applicantId: "applicant-1",
      invitationId: "invitation-1",
      reportId: "report-1",
      reportItemId: "item-1",
      criterionId: "system-design",
      documentType: "report_criterion",
      excerpt: "트래픽 증가 상황의 확장 전략을 설명했습니다.",
      score: 0.91,
      scoreComponents: { vector: 0.92, lexical: 0.89 },
      metadata: { criterion_name: "시스템 설계", score: 87 },
    },
    {
      sourceId: "source-3",
      positionId: "position-1",
      applicantId: "applicant-1",
      invitationId: "invitation-1",
      reportId: "report-1",
      reportItemId: "item-2",
      criterionId: "evidence",
      documentType: "report_criterion",
      excerpt: "답변에 연결된 면접 근거가 확인되었습니다.",
      score: 0.88,
      scoreComponents: { vector: 0.9, lexical: 0.83 },
      metadata: { criterion_name: "근거 구체성", score: 84 },
    },
  ],
} as const;

const assistantApi: RecruitingAssistantApi = {
  answerQuestion: vi.fn().mockResolvedValue(assistantResponse),
  streamAnswer: vi.fn().mockImplementation(async (_request, handlers) => {
    handlers.onStart?.({ archivedScope: false });
    const first = "김민준 지원자의 시스템 설계 근거가 확인됩니다. ";
    const second = "최종 판단 전 기준별 원문 근거를 함께 검토해 주세요.";
    handlers.onDelta?.(first, first);
    handlers.onDelta?.(second, `${first}${second}`);
    handlers.onSources?.(assistantResponse.sources);
    return assistantResponse;
  }),
};

describe("AI recruiting assistant", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderAssistant() {
    render(
      <MemoryRouter>
        <AiRecruitingAssistant api={api} assistantApi={assistantApi} />
      </MemoryRouter>,
    );
  }

  it("keeps the selected position scope fixed after a conversation starts", async () => {
    renderAssistant();

    await screen.findByRole("heading", {
      name: "채용 데이터에 대해 무엇이든 물어보세요",
    });
    expect(
      screen.getByRole("heading", { name: "AI 채용 어시스턴트" }),
    ).toBeTruthy();
    expect(await screen.findByText("1개 포지션")).toBeTruthy();
    expect(screen.getByText("1명 지원자")).toBeTruthy();
    expect(await screen.findByText("1건 리포트")).toBeTruthy();
    expect(
      screen.getByText(
        "선택한 범위의 최종 리포트를 근거로 검색·생성한 답변이며, AI의 요약과 평가는 부정확할 수 있습니다.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText(/최종 판단은 담당자/)).toBeNull();

    const scope = screen.getByRole("combobox", { name: "분석 범위" });
    fireEvent.change(scope, { target: { value: "position-1" } });
    fireEvent.click(
      screen.getByRole("button", {
        name: "현재 범위에서 근거가 구체적인 지원자를 정리해줘.",
      }),
    );

    expect((scope as HTMLSelectElement).disabled).toBe(true);
    expect(
      await screen.findByText("분석 범위 · 백엔드 플랫폼 엔지니어"),
    ).toBeTruthy();
    expect(
      screen.getByText(
        /현재 대화의 데이터 검색 범위는 백엔드 플랫폼 엔지니어로 고정되었습니다/,
      ),
    ).toBeTruthy();
    expect(screen.getByText("범위 고정됨 · 변경하려면 새 채팅")).toBeTruthy();
    expect(screen.getByText("3개 소스 검색 완료")).toBeTruthy();
    expect(assistantApi.streamAnswer).toHaveBeenCalledWith(
      {
        scope: "position",
        positionId: "position-1",
        query: "현재 범위에서 근거가 구체적인 지원자를 정리해줘.",
        limit: 8,
      },
      expect.any(Object),
    );
  });

  it("plainly reports when no relevant evidence is found", async () => {
    const noSourcesResponse = {
      scope: "position" as const,
      positionId: "position-1",
      answer:
        "선택한 범위의 최종 리포트를 검색해봤지만, 지금 질문과 직접 연결되는 근거는 확인할 수 없었어요. 다른 표현으로 묻거나 새 채팅에서 검색 범위를 넓혀보세요.",
      degradedMode: "no_sources",
      sources: [],
    };
    const noSourcesApi: RecruitingAssistantApi = {
      answerQuestion: vi.fn().mockResolvedValue(noSourcesResponse),
      streamAnswer: vi.fn().mockResolvedValue(noSourcesResponse),
    };
    render(
      <MemoryRouter>
        <AiRecruitingAssistant api={api} assistantApi={noSourcesApi} />
      </MemoryRouter>,
    );

    const scope = await screen.findByRole("combobox", { name: "분석 범위" });
    fireEvent.change(scope, { target: { value: "position-1" } });
    fireEvent.click(
      screen.getByRole("button", {
        name: "현재 범위에서 근거가 구체적인 지원자를 정리해줘.",
      }),
    );

    expect(await screen.findByText("확인 가능한 근거 없음")).toBeTruthy();
    expect(
      screen.getByText(
        "선택한 범위의 최종 리포트를 검색해봤지만, 지금 질문과 직접 연결되는 근거는 확인할 수 없었어요. 다른 표현으로 묻거나 새 채팅에서 검색 범위를 넓혀보세요.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("제한된 답변")).toBeNull();
  });

  it("shows professional RAG evidence and an inline applicant report", async () => {
    renderAssistant();

    await screen.findByRole("heading", {
      name: "채용 데이터에 대해 무엇이든 물어보세요",
    });
    fireEvent.click(
      screen.getByRole("button", {
        name: "현재 범위에서 근거가 구체적인 지원자를 정리해줘.",
      }),
    );
    fireEvent.click(
      await screen.findByRole("button", {
        name: "근거 1: 김민준 · AI 최종 리포트",
      }),
    );

    expect(
      screen.getByRole("complementary", { name: "RAG 답변 근거" }),
    ).toBeTruthy();
    expect(screen.getByText("일치도 96%")).toBeTruthy();
    const drawer = screen.getByRole("complementary", {
      name: "RAG 답변 근거",
    });
    expect(
      within(drawer).getByRole("table", { name: "근거 요약 정보" }),
    ).toBeTruthy();
    expect(
      within(drawer).getByRole("table", { name: "검색 문맥 기본 정보" }),
    ).toBeTruthy();
    expect(within(drawer).getByText("생성 완료")).toBeTruthy();
    expect(within(drawer).getByText("종합 요약")).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "간단 리포트 보기" }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("heading", { name: "지원자 평가 요약서" }),
    ).toBeTruthy();
    expect(
      within(dialog).getByRole("heading", { name: "한눈에 보기" }),
    ).toBeTruthy();
    expect(within(dialog).getByText("1 / 6")).toBeTruthy();

    fireEvent.click(
      within(dialog).getByRole("button", { name: "2 기준별 평가" }),
    );
    expect(
      within(dialog).getByRole("heading", { name: "기준별 평가" }),
    ).toBeTruthy();
    expect(within(dialog).getByText("시스템 설계")).toBeTruthy();
    expect(within(dialog).getByText("근거 충분 · 근거 2건")).toBeTruthy();

    fireEvent.click(
      within(dialog).getByRole("button", { name: "6 최종 검토" }),
    );
    expect(
      within(dialog).getByText(
        "현재 화면은 조회 전용입니다. 채용 단계 변경은 지원자 관리의 칸반보드에서 할 수 있습니다.",
      ),
    ).toBeTruthy();
    expect(within(dialog).queryByText(/문서 구분:/)).toBeNull();
    expect(within(dialog).queryByText(/보안 등급:/)).toBeNull();
    expect(within(dialog).queryByText("검토자")).toBeNull();
    expect(within(dialog).queryByText("검토일")).toBeNull();
  });

  it("creates separate in-memory chat rooms with message history", async () => {
    renderAssistant();

    await screen.findByRole("heading", {
      name: "채용 데이터에 대해 무엇이든 물어보세요",
    });
    fireEvent.click(
      screen.getByRole("button", {
        name: "AWS 운영 경험이 확인된 지원자를 근거와 함께 알려줘.",
      }),
    );

    expect(
      await screen.findByText(
        "AWS 운영 경험이 확인된 지원자를 근거와 함께 알려줘.",
      ),
    ).toBeTruthy();
    fireEvent.click(
      screen.getAllByRole("button", { name: "새 채팅 만들기" })[1],
    );

    expect(
      await screen.findByRole("heading", {
        name: "채용 데이터에 대해 무엇이든 물어보세요",
      }),
    ).toBeTruthy();
    expect(
      within(
        screen.getByRole("complementary", { name: "AI 대화 목록" }),
      ).getByRole("button", {
        name: /AWS 운영 경험.*전체 진행 중 포지션$/,
      }),
    ).toBeTruthy();
  });

  it("renames a conversation and preserves the custom title", async () => {
    renderAssistant();

    await screen.findByRole("heading", {
      name: "채용 데이터에 대해 무엇이든 물어보세요",
    });
    fireEvent.click(
      screen.getByRole("button", { name: "새 채용 분석 제목 수정" }),
    );
    const titleInput = screen.getByRole("textbox", { name: "대화 제목" });
    fireEvent.change(titleInput, { target: { value: "AWS 운영 후보 검토" } });
    fireEvent.click(screen.getByRole("button", { name: "대화 제목 저장" }));

    expect(screen.getAllByText("AWS 운영 후보 검토").length).toBeGreaterThan(0);
    fireEvent.click(
      screen.getByRole("button", {
        name: "AWS 운영 경험이 확인된 지원자를 근거와 함께 알려줘.",
      }),
    );
    expect(await screen.findByText("3개 소스 검색 완료")).toBeTruthy();
    expect(screen.getAllByText("AWS 운영 후보 검토").length).toBeGreaterThan(0);
  });

  it("explains which data the RAG search does and does not use", async () => {
    renderAssistant();

    expect(await screen.findByText("RAG 검색 데이터")).toBeTruthy();
    expect(
      screen.getByText("최종 리포트와 평가 기준별 근거를 검색합니다."),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "어떻게 검색되나요?" }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("heading", {
        name: "RAG 검색은 이렇게 동작합니다",
      }),
    ).toBeTruthy();
    expect(within(dialog).getByText("직접 검색하는 자료")).toBeTruthy();
    expect(within(dialog).getByText("검색 범위와 방식")).toBeTruthy();
    expect(within(dialog).getByText("직접 검색하지 않는 자료")).toBeTruthy();
    expect(
      within(dialog).getByText(/이력서, 포트폴리오, 면접 영상·음성/),
    ).toBeTruthy();
  });

  it("separates archived positions and opens them as read-only analysis", async () => {
    const archivedApi: CompanyOperationsApi = {
      ...api,
      listPositions: vi.fn().mockResolvedValue([
        {
          positionId: "position-1",
          title: "백엔드 플랫폼 엔지니어",
          description: "플랫폼을 개발합니다.",
          submissionRequirements: [],
          status: "active",
          rowVersion: 1,
          createdAt: "2026-08-21T00:00:00Z",
        },
        {
          positionId: "position-closed",
          title: "지난 데이터 엔지니어 채용",
          description: "종료된 채용입니다.",
          recruitmentEndAt: "2026-08-20",
          submissionRequirements: [],
          status: "active",
          rowVersion: 1,
          createdAt: "2026-08-01T00:00:00Z",
        },
      ]),
    };
    render(
      <MemoryRouter>
        <AiRecruitingAssistant api={archivedApi} assistantApi={assistantApi} />
      </MemoryRouter>,
    );

    const scope = await screen.findByRole("combobox", {
      name: "분석 범위",
    });
    expect(
      within(scope).getByRole("option", {
        name: "지난 데이터 엔지니어 채용 (종료)",
      }),
    ).toBeTruthy();
    fireEvent.change(scope, { target: { value: "position-closed" } });
    expect(await screen.findByText("읽기 전용 과거 채용 분석")).toBeTruthy();
    expect(
      screen.getByText(
        "지난 데이터 엔지니어 채용 · 모집 종료에서 시작하는 대화",
      ),
    ).toBeTruthy();
  });

  it("renders answer deltas before the validated sources arrive", async () => {
    let finishSearch: (() => void) | undefined;
    let finishStream: (() => void) | undefined;
    const streamingApi: RecruitingAssistantApi = {
      answerQuestion: assistantApi.answerQuestion,
      streamAnswer: vi.fn().mockImplementation(async (_request, handlers) => {
        await new Promise<void>((resolve) => {
          finishSearch = resolve;
        });
        const first = "첫 번째 근거 문장이 스트리밍됩니다. ";
        handlers.onDelta?.(first, first);
        await new Promise<void>((resolve) => {
          finishStream = resolve;
        });
        const second = "검증된 근거를 확인했습니다.";
        handlers.onDelta?.(second, `${first}${second}`);
        handlers.onSources?.(assistantResponse.sources);
        return {
          ...assistantResponse,
          answer: `${first}${second}`,
        };
      }),
    };
    render(
      <MemoryRouter>
        <AiRecruitingAssistant api={api} assistantApi={streamingApi} />
      </MemoryRouter>,
    );

    fireEvent.click(
      await screen.findByRole("button", {
        name: "현재 범위에서 근거가 구체적인 지원자를 정리해줘.",
      }),
    );
    expect(await screen.findByLabelText("생각 중...")).toBeTruthy();
    expect(
      screen.getByText("관련 리포트와 면접 근거를 조회하고 있습니다."),
    ).toBeTruthy();
    expect(
      document.querySelector('[data-assistant-avatar-state="searching"]'),
    ).toBeTruthy();

    await act(async () => {
      finishSearch?.();
    });
    expect(await screen.findByLabelText("생각 중...")).toBeTruthy();
    expect(
      await screen.findByText("첫 번째 근거 문장이 스트리밍됩니다."),
    ).toBeTruthy();
    expect(
      document.querySelector('[data-assistant-avatar-state="thinking"]'),
    ).toBeTruthy();

    await act(async () => {
      finishStream?.();
    });
    expect(await screen.findByText("3개 소스 검색 완료")).toBeTruthy();
    expect(
      document.querySelector('[data-assistant-avatar-state="complete"]'),
    ).toBeTruthy();
  });

  it("turns a streaming failure into a friendly searchable fallback", async () => {
    const failingApi: RecruitingAssistantApi = {
      answerQuestion: assistantApi.answerQuestion,
      streamAnswer: vi.fn().mockRejectedValue(new Error("stream unavailable")),
    };
    render(
      <MemoryRouter>
        <AiRecruitingAssistant api={api} assistantApi={failingApi} />
      </MemoryRouter>,
    );

    fireEvent.click(
      await screen.findByRole("button", {
        name: "AWS 운영 경험이 확인된 지원자를 근거와 함께 알려줘.",
      }),
    );

    expect(
      await screen.findByText(
        "선택한 범위의 채용 리포트를 검색해봤지만, 지금 질문과 직접 연결되는 내용을 확인할 수 없었어요. 채용 데이터와 관련된 다른 표현으로 다시 질문해 주세요.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("확인 가능한 근거 없음")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText("제한된 답변")).toBeNull();
  });
});
