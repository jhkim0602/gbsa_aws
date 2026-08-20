import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import {
  ApplicantDetail,
  ApplicantManagement,
  CompanyOverview,
  CompanyPositions,
  PositionOperations,
  type CompanyApplicantReport,
  type CompanyDeletionStatus,
  type CompanyInvitation,
  type CompanyOperationsApi,
  type CompanyWorkspaceApi,
} from "../index";
import type {
  InvitationEmailTemplateApi,
  InvitationEmailTemplateState,
  PositionInvitationApi,
} from "../../hiring";

const api: CompanyWorkspaceApi = {
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
      description: "Python과 AWS 기반 플랫폼을 개발합니다.",
      roleType: "개발",
      headcount: 3,
      recruitmentStartAt: "2026-08-15",
      recruitmentEndAt: "2026-09-30",
      submissionRequirements: [
        { materialType: "resume", required: true, enabled: true },
      ],
      status: "draft",
      rowVersion: 1,
      createdAt: "2026-08-15T01:00:00Z",
    },
    {
      positionId: "position-2",
      title: "프로덕트 디자이너",
      description: "지원자 경험과 운영 도구를 설계합니다.",
      submissionRequirements: [
        { materialType: "resume", required: true, enabled: true },
      ],
      status: "active",
      rowVersion: 3,
      createdAt: "2026-08-14T01:00:00Z",
    },
  ]),
  getPosition: vi.fn().mockImplementation((positionId: string) =>
    api.listPositions().then((positions) => {
      const position = positions.find((item) => item.positionId === positionId);
      if (!position) throw new Error("position not found");
      return position;
    }),
  ),
};

const positionTwoInvitations = [
  {
    invitationId: "invitation-1",
    positionId: "position-2",
    competencyModelVersionId: "version-1",
    applicantEmail: "ready@example.com",
    applicantDisplayName: "준비된 지원자",
    status: "ready",
    expiresAt: "2026-08-22T02:00:00Z",
    rowVersion: 3,
    analysisStatus: "ready",
    interviewStatus: "ready",
    reportStatus: null,
  },
  {
    invitationId: "invitation-2",
    positionId: "position-2",
    competencyModelVersionId: "version-1",
    applicantEmail: "review@example.com",
    applicantDisplayName: "검토할 지원자",
    status: "completed",
    expiresAt: "2026-08-22T02:00:00Z",
    rowVersion: 8,
    analysisStatus: "ready",
    interviewStatus: "completed",
    reportStatus: "ready",
  },
  {
    invitationId: "invitation-3",
    positionId: "position-2",
    competencyModelVersionId: "version-1",
    applicantEmail: "interview@example.com",
    applicantDisplayName: "면접 중 지원자",
    status: "interviewing",
    expiresAt: "2026-08-22T02:00:00Z",
    rowVersion: 7,
    analysisStatus: "ready",
    interviewStatus: "interviewing",
    reportStatus: null,
  },
  {
    invitationId: "invitation-4",
    positionId: "position-2",
    competencyModelVersionId: "version-1",
    applicantEmail: "reviewed@example.com",
    applicantDisplayName: "검토 완료 지원자",
    status: "reviewed",
    expiresAt: "2026-08-22T02:00:00Z",
    rowVersion: 10,
    analysisStatus: "ready",
    interviewStatus: "completed",
    reportStatus: "ready",
  },
] satisfies readonly CompanyInvitation[];

const publishedCriterionVersion = {
  versionId: "version-1",
  positionId: "position-2",
  versionNumber: 1,
  status: "published",
  rowVersion: 2,
  publishedAt: "2026-08-15T04:00:00Z",
  jobRequirements: [
    {
      requirementType: "required",
      statement: "제품 문제를 구조화하는 경험",
      priority: 1,
      criterionCode: "PROBLEM_SOLVING",
    },
  ],
  criteria: [
    {
      code: "PROBLEM_SOLVING",
      name: "문제 해결",
      description: "문제를 구조화하고 해결하는 역량",
      weight: 100,
      required: true,
      verificationGuide: {
        observableDimensions: ["상황", "직접 수행한 행동", "결과"],
        strongAnswerSignals: ["판단 근거와 결과가 구체적임"],
        weakAnswerSignals: ["본인의 행동이 불명확함"],
        followUpDirections: ["판단 근거", "측정 가능한 결과"],
        maxFollowUps: 2,
        timeBudgetSeconds: 300,
      },
      abstainGuidance: "답변 근거가 부족하면 판단을 유보합니다.",
      commonQuestions: ["문제를 해결한 경험을 설명해 주세요."],
    },
  ],
  prohibitedTopics: ["가족관계"],
  interviewDurationMinutes: 30,
  interviewLevel: "senior",
} as const;

const operationsApi: CompanyOperationsApi = {
  ...api,
  listInvitations: vi
    .fn()
    .mockImplementation((positionId: string) =>
      Promise.resolve(
        positionId === "position-2" ? positionTwoInvitations : [],
      ),
    ),
  updatePosition: vi.fn().mockImplementation((input) =>
    Promise.resolve({
      positionId: input.positionId,
      title: input.title,
      description: input.description,
      roleType: input.roleType,
      headcount: input.headcount,
      interviewCapacity: input.interviewCapacity,
      interviewAt: input.interviewAt,
      recruitmentStartAt: input.recruitmentStartAt,
      recruitmentEndAt: input.recruitmentEndAt,
      submissionRequirements: input.submissionRequirements,
      status: input.status,
      rowVersion: input.rowVersion + 1,
      createdAt: "2026-08-14T01:00:00Z",
    }),
  ),
  listCriterionVersions: vi.fn().mockResolvedValue([publishedCriterionVersion]),
  publishCriteria: vi.fn().mockResolvedValue({ versionId: "version-2" }),
  listSubmissions: vi.fn().mockResolvedValue([]),
};

const applicantReport: CompanyApplicantReport = {
  insight: {
    invitationId: "invitation-2",
    interviewSessionId: "session-1",
    competencyModelVersionId: "version-1",
    overallScore: 88,
    unscoredCriteriaCount: 0,
    evidenceCoverage: 100,
    summary: "제품 문제를 구조화한 근거가 구체적입니다.",
    criteria: [
      {
        criterionId: "PROBLEM_SOLVING",
        criterionName: "문제 해결",
        score: 88,
        assessmentState: "confirmed",
        evidenceCount: 1,
      },
    ],
  },
  report: {
    summary: "문제의 원인과 해결 결과를 구체적인 수치로 설명했습니다.",
    status: "ready",
    overallScore: 88,
    unscoredCriteriaCount: 0,
    items: [
      {
        reportItemId: "report-item-1",
        criterionId: "PROBLEM_SOLVING",
        criterionName: "문제 해결",
        assessmentState: "confirmed",
        observation: "사용자 조사와 지표를 함께 사용해 문제를 좁혔습니다.",
        followUpQuestion: null,
        averageScore: 88,
        axisAssessments: [],
        evidence: [
          {
            evidenceId: "evidence-1",
            answerTurnId: "answer-1",
            transcriptSegmentId: "answer-1",
            startMs: 4_000,
            endMs: 12_000,
            observation: "문제 정의와 개선 결과를 설명함",
            rationale: "평가 기준을 직접 뒷받침합니다.",
            sufficiency: "direct",
          },
        ],
      },
    ],
  },
  timeline: {
    entries: [
      {
        entryId: "question-1",
        type: "question",
        startMs: 0,
        endMs: 3_500,
        text: "가장 복잡한 제품 문제를 어떻게 정의했나요?",
      },
      {
        entryId: "answer-1",
        type: "answer",
        startMs: 4_000,
        endMs: 12_000,
        text: "사용자 조사와 오류 지표를 교차 검증해 문제를 좁혔습니다.",
      },
    ],
    playback: { status: "ready", url: "https://example.com/interview.mp4" },
  },
};

const invitationApi: PositionInvitationApi = {
  listInvitations: operationsApi.listInvitations,
  createInvitations: vi.fn().mockResolvedValue({
    acceptedCount: 1,
    rejectedCount: 0,
    invitations: [],
  }),
};

const emailTemplate: InvitationEmailTemplateState = {
  subject: "[{{회사명}}] {{포지션명}} 면접 안내",
  headline: "서류 전형 합격을 축하드립니다",
  intro: "{{지원자명}}님, 지원해주셔서 감사합니다.",
  guides: ["소요 시간 | 약 25분"],
  ctaLabel: "면접 시작하기",
  outro: "곧 만나뵙기를 기대합니다.",
  footer: "문의: hiring@example.com",
  brandColor: "#5966ce",
  useApplicantName: true,
  emphasizeDeadline: true,
  showSecurityNotice: true,
  logoUrl: null,
  isPositionOverride: false,
};

const templateApi: InvitationEmailTemplateApi = {
  getCompanyTemplate: vi.fn().mockResolvedValue(emailTemplate),
  saveCompanyTemplate: vi.fn().mockResolvedValue(emailTemplate),
  resetCompanyTemplate: vi.fn().mockResolvedValue(emailTemplate),
  getPositionTemplate: vi.fn().mockResolvedValue(emailTemplate),
  savePositionTemplate: vi.fn().mockResolvedValue(emailTemplate),
  resetPositionTemplate: vi.fn().mockResolvedValue(emailTemplate),
  previewTemplate: vi
    .fn()
    .mockResolvedValue({ subject: "미리보기", htmlBody: "<p>본문</p>" }),
  uploadLogo: vi.fn(),
  deleteLogo: vi.fn(),
};

describe("company workspace", () => {
  it("renders recruiter KPIs, the recruiting calendar and live applicant activity", async () => {
    render(
      <MemoryRouter>
        <CompanyOverview api={operationsApi} />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "채용 운영 대시보드" }),
    ).toBeTruthy();
    expect(await screen.findByLabelText("활성 포지션 1개")).toBeTruthy();
    expect(screen.getByLabelText("진행 중인 면접 1건")).toBeTruthy();
    expect(screen.getByLabelText("검토 대기 1건")).toBeTruthy();
    expect(screen.getByLabelText("완료된 면접 1건")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "포지션 현황" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "채용 캘린더" })).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "지원자 실시간 로그" }),
    ).toBeTruthy();
    expect(screen.getByText("AI 면접을 시작했습니다.")).toBeTruthy();
    expect(screen.getByText("AI 면접을 종료했습니다.")).toBeTruthy();
    expect(screen.getAllByText("검토 대기").length).toBeGreaterThan(0);
    expect(screen.getByText("검토할 지원자")).toBeTruthy();
    expect(screen.queryByText("오늘 확인할 업무")).toBeNull();
    expect(screen.queryByText("지원자 단계")).toBeNull();
    expect(screen.queryByText("최근 활동")).toBeNull();
    expect(screen.queryByText("recruiter@example.com")).toBeNull();
    expect(screen.getByRole("link", { name: "새 채용 관리" })).toBeTruthy();
  });

  it("opens each position in a dedicated recruiting operations screen", async () => {
    render(
      <MemoryRouter>
        <CompanyPositions api={operationsApi} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "채용 포지션" })).toBeTruthy();
    expect(await screen.findByText("백엔드 플랫폼 엔지니어")).toBeTruthy();
    expect(screen.getAllByText("초안").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("운영 중").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("3명").length).toBeGreaterThan(0);
    expect(screen.getByText(/08\. 15\..*09\. 30\./)).toBeTruthy();

    expect(
      screen
        .getByRole("link", {
          name: "백엔드 플랫폼 엔지니어 포지션 열기",
        })
        .getAttribute("href"),
    ).toBe("/positions/position-1");
    expect(
      screen.getByRole("progressbar", {
        name: "백엔드 플랫폼 엔지니어 지원 현황 0%",
      }),
    ).toBeTruthy();
    expect(
      screen.getByRole("progressbar", {
        name: "프로덕트 디자이너 지원 현황 0%",
      }),
    ).toBeTruthy();
    expect(
      screen.getByRole("link", {
        name: "프로덕트 디자이너 포지션 열기",
      }).textContent,
    ).toContain("지원자 4명");
  });

  it("opens a divided position dashboard and connects every detailed workspace", async () => {
    render(
      <MemoryRouter>
        <PositionOperations
          positionId="position-2"
          api={operationsApi}
          invitationApi={invitationApi}
          templateApi={templateApi}
        />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "프로덕트 디자이너" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("tablist", { name: "포지션 운영 메뉴" }),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("tab", { name: "인사이트" })
        .getAttribute("aria-selected"),
    ).toBe("true");
    expect(
      screen.getByRole("heading", { name: "포지션 판단 요약" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "평가 기준별 평균" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "지원자 역량 비교" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "현재 면접 설정" }),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "지원자" }));
    expect(
      screen.getByRole("tab", { name: "지원자" }).getAttribute("aria-selected"),
    ).toBe("true");
    expect(screen.getByRole("heading", { name: "지원자 비교" })).toBeTruthy();
    expect(await screen.findByText("준비된 지원자")).toBeTruthy();
    expect(screen.getByText("ready@example.com")).toBeTruthy();
    expect(screen.getByText("검토할 지원자")).toBeTruthy();
    expect(screen.getByRole("button", { name: "지원자 초대" })).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "검토할 지원자 리포트 열기" })
        .getAttribute("href"),
    ).toBe("/positions/position-2/applicants/invitation-2");

    fireEvent.click(screen.getByRole("tab", { name: "역량 분포" }));
    expect(screen.getByRole("heading", { name: "총점 분포" })).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "지원자 역량 비교" }),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "면접 운영" }));
    expect(
      screen.getByRole("heading", { name: "지원자 면접 흐름" }),
    ).toBeTruthy();
    expect(screen.getByText("초대·확인")).toBeTruthy();
    expect(screen.getByText("자료 제출·분석")).toBeTruthy();
    expect(screen.getByText("결과 검토")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "설정값" }));
    expect(
      screen.getByRole("heading", { name: "현재 적용 중인 면접 기준" }),
    ).toBeTruthy();
    expect(screen.getByText("면접 난이도")).toBeTruthy();
    expect(screen.getByText("시니어")).toBeTruthy();
    expect(screen.getByText("제품 문제를 구조화하는 경험")).toBeTruthy();
    expect(screen.getByText("문제 해결")).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "지원자 제출 자료" }),
    ).toBeTruthy();
    expect(screen.getByText("이력서")).toBeTruthy();
    expect(screen.queryByText(/버전/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "간편 수정" }));
    expect(
      screen.getByRole("dialog", { name: "포지션 간편 수정" }),
    ).toBeTruthy();
    expect(
      ((await screen.findByLabelText("포지션명")) as HTMLInputElement).value,
    ).toBe("프로덕트 디자이너");
    fireEvent.change(screen.getByLabelText("포지션명"), {
      target: { value: "시니어 프로덕트 디자이너" },
    });
    fireEvent.click(screen.getByRole("button", { name: "변경 저장" }));
    await waitFor(() =>
      expect(operationsApi.updatePosition).toHaveBeenCalledWith(
        expect.objectContaining({
          positionId: "position-2",
          title: "시니어 프로덕트 디자이너",
          status: "active",
          rowVersion: 3,
        }),
      ),
    );
    expect(
      await screen.findByRole("heading", {
        name: "시니어 프로덕트 디자이너",
      }),
    ).toBeTruthy();
  });

  it("loads only the selected position invitations in a position workspace", async () => {
    const scopedListInvitations = vi
      .fn()
      .mockImplementation((positionId: string) =>
        Promise.resolve(
          positionId === "position-2" ? positionTwoInvitations : [],
        ),
      );
    const scopedOperationsApi: CompanyOperationsApi = {
      ...operationsApi,
      listInvitations: scopedListInvitations,
    };
    const scopedInvitationApi: PositionInvitationApi = {
      listInvitations: vi.fn().mockResolvedValue(positionTwoInvitations),
      createInvitations: vi.fn().mockResolvedValue({
        acceptedCount: 0,
        rejectedCount: 0,
        invitations: [],
      }),
    };

    render(
      <MemoryRouter>
        <PositionOperations
          positionId="position-2"
          api={scopedOperationsApi}
          invitationApi={scopedInvitationApi}
          templateApi={templateApi}
        />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "프로덕트 디자이너" }),
    ).toBeTruthy();
    expect(scopedListInvitations).toHaveBeenCalledWith("position-2");
    expect(scopedListInvitations).not.toHaveBeenCalledWith("position-1");
  });

  it("confirms a draft position from the quick edit modal", async () => {
    render(
      <MemoryRouter>
        <PositionOperations
          positionId="position-1"
          api={operationsApi}
          invitationApi={invitationApi}
          templateApi={templateApi}
        />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "백엔드 플랫폼 엔지니어" }),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "간편 수정" }));
    const confirmButton = await screen.findByRole("button", {
      name: "채용 확정",
    });
    expect((confirmButton as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(confirmButton);
    await waitFor(() =>
      expect(operationsApi.updatePosition).toHaveBeenCalledWith(
        expect.objectContaining({
          positionId: "position-1",
          status: "active",
        }),
      ),
    );
    expect(
      await screen.findByText("채용을 확정하고 운영을 시작했습니다."),
    ).toBeTruthy();
  });

  it("provides one cross-position applicant management table", async () => {
    render(
      <MemoryRouter>
        <ApplicantManagement api={operationsApi} />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "지원자 관리" }),
    ).toBeTruthy();
    expect(screen.getByLabelText("전체 지원자 4명")).toBeTruthy();
    expect(screen.getByLabelText("지원 포지션 1개")).toBeTruthy();
    expect(screen.getByLabelText("진행 중 2명")).toBeTruthy();
    expect(screen.getByLabelText("검토 대기 1명")).toBeTruthy();
    expect(
      screen.getAllByText("프로덕트 디자이너").length,
    ).toBeGreaterThanOrEqual(4);
    expect(screen.getByText("검토할 지원자")).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "검토할 지원자 리포트 열기" })
        .getAttribute("href"),
    ).toBe("/positions/position-2/applicants/invitation-2");
  });

  it("keeps an applicant visible until asynchronous deletion completes", async () => {
    let resolveDeletion: ((status: CompanyDeletionStatus) => void) | undefined;
    const requestApplicantDeletion = vi.fn().mockResolvedValue({
      deletionRequestId: "deletion-1",
      status: "deleting",
      expectedTargets: 4,
      verifiedTargets: 0,
    } satisfies CompanyDeletionStatus);
    const getApplicantDeletion = vi.fn().mockImplementation(
      () =>
        new Promise<CompanyDeletionStatus>((resolve) => {
          resolveDeletion = resolve;
        }),
    );
    render(
      <MemoryRouter>
        <ApplicantManagement
          api={{
            ...operationsApi,
            requestApplicantDeletion,
            getApplicantDeletion,
          }}
        />
      </MemoryRouter>,
    );

    expect(await screen.findByText("검토할 지원자")).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", { name: "검토할 지원자 지원자 삭제" }),
    );
    expect(
      screen.getByRole("heading", { name: "지원자를 삭제할까요?" }),
    ).toBeTruthy();
    expect(screen.getByText(/되돌릴 수 없습니다/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "삭제" }));

    await waitFor(() =>
      expect(requestApplicantDeletion).toHaveBeenCalledWith("invitation-2"),
    );
    expect(
      screen.getByRole("link", { name: "검토할 지원자 리포트 열기" }),
    ).toBeTruthy();
    expect(screen.getByText("삭제 중 0/4")).toBeTruthy();
    expect(screen.getByLabelText("전체 지원자 4명")).toBeTruthy();
    expect(
      screen.getByText(/실제 삭제가 끝날 때까지 목록에 표시됩니다/),
    ).toBeTruthy();
    await waitFor(() =>
      expect(getApplicantDeletion).toHaveBeenCalledWith("deletion-1"),
    );

    await act(async () => {
      resolveDeletion?.({
        deletionRequestId: "deletion-1",
        status: "completed",
        expectedTargets: 4,
        verifiedTargets: 4,
      });
    });

    await waitFor(() =>
      expect(
        screen.queryByRole("link", {
          name: "검토할 지원자 리포트 열기",
        }),
      ).toBeNull(),
    );
    expect(screen.getByLabelText("전체 지원자 3명")).toBeTruthy();
    expect(
      screen.getByText("검토할 지원자 지원자의 데이터 삭제를 완료했습니다."),
    ).toBeTruthy();
  });

  it("shows applicant progress and opens interview evidence when a session exists", async () => {
    const apiWithSession: CompanyOperationsApi = {
      ...operationsApi,
      listInvitations: vi.fn().mockResolvedValue([
        {
          ...positionTwoInvitations[1],
          interviewSessionId: "session-1",
        },
      ]),
      listSubmissions: vi.fn().mockResolvedValue([
        {
          submissionId: "submission-1",
          materialType: "resume",
          sourceType: "file",
          originalFilename: "resume.pdf",
          sourceUrl: "https://example.com/resume.pdf",
          status: "analyzed",
          createdAt: "2026-08-18T01:00:00Z",
        },
      ]),
      getApplicantReport: vi.fn().mockResolvedValue(applicantReport),
    };
    render(
      <MemoryRouter>
        <ApplicantDetail
          positionId="position-2"
          invitationId="invitation-2"
          api={apiWithSession}
        />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "검토할 지원자" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("tablist", { name: "지원자 리포트 메뉴" }),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("tab", { name: "분석 리포트" })
        .getAttribute("aria-selected"),
    ).toBe("true");
    expect(
      await screen.findByRole("heading", { name: "종합 분석" }),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "기준별 역량" })).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "평가 기준과 답변 근거" }),
    ).toBeTruthy();
    expect(screen.getByText("총점")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "면접 기록" }));
    expect(
      screen.getByRole("heading", { name: "시간별 대화 기록" }),
    ).toBeTruthy();
    expect(
      screen.getByText("가장 복잡한 제품 문제를 어떻게 정의했나요?"),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "제출 자료" }));
    expect(
      screen.getByRole("heading", { name: "제출 자료 원본" }),
    ).toBeTruthy();
    expect(screen.getByText("resume.pdf")).toBeTruthy();
  });

  it("bounds invitation fan-out and keeps invitations in position order", async () => {
    const positions = Array.from({ length: 20 }, (_, index) => ({
      positionId: `bulk-${index}`,
      title: `대량 포지션 ${index}`,
      description: "동시 요청 상한을 확인합니다.",
      status: "active",
      rowVersion: 1,
      createdAt: "2026-08-14T01:00:00Z",
    }));
    let inFlight = 0;
    let peakInFlight = 0;
    const bulkApi: CompanyOperationsApi = {
      ...operationsApi,
      listPositions: vi.fn().mockResolvedValue(positions),
      listInvitations: vi
        .fn()
        .mockImplementation(async (positionId: string) => {
          inFlight += 1;
          peakInFlight = Math.max(peakInFlight, inFlight);
          // Later positions resolve first, so ordering cannot rely on completion order.
          const index = Number(positionId.replace("bulk-", ""));
          await new Promise((resolve) =>
            setTimeout(resolve, (positions.length - index) * 2),
          );
          inFlight -= 1;
          return [{ ...positionTwoInvitations[0], invitationId: positionId }];
        }),
    };

    render(
      <MemoryRouter>
        <ApplicantManagement api={bulkApi} />
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText("전체 지원자 20명")).toBeTruthy();
    expect(peakInFlight).toBeLessThanOrEqual(6);
    const order = screen
      .getAllByRole("link", { name: /리포트 열기$/ })
      .map((link) => link.getAttribute("href"));
    expect(order[0]).toContain("/applicants/bulk-0");
    expect(order[1]).toContain("/applicants/bulk-1");
  });
});
