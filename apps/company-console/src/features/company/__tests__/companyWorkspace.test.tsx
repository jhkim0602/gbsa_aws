import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import {
  ApplicantDetail,
  ApplicantManagement,
  CompanyOverview,
  CompanyPositions,
  PositionOperations,
  type CompanyInvitation,
  type CompanyOperationsApi,
  type CompanyWorkspaceApi,
} from "../index";
import type { PositionInvitationApi } from "../../hiring";

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
      status: "draft",
      rowVersion: 1,
      createdAt: "2026-08-15T01:00:00Z",
    },
    {
      positionId: "position-2",
      title: "프로덕트 디자이너",
      description: "지원자 경험과 운영 도구를 설계합니다.",
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
      recruitmentStartAt: input.recruitmentStartAt,
      recruitmentEndAt: input.recruitmentEndAt,
      status: input.status,
      rowVersion: input.rowVersion + 1,
      createdAt: "2026-08-14T01:00:00Z",
    }),
  ),
  listCriterionVersions: vi.fn().mockResolvedValue([publishedCriterionVersion]),
  publishCriteria: vi.fn().mockResolvedValue({ versionId: "version-2" }),
};

const invitationApi: PositionInvitationApi = {
  listInvitations: operationsApi.listInvitations,
  createInvitations: vi.fn().mockResolvedValue({
    acceptedCount: 1,
    rejectedCount: 0,
    invitations: [],
  }),
};

describe("company workspace", () => {
  it("renders recruiter KPIs, position status and real timestamped activity", async () => {
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
    expect(screen.getByRole("heading", { name: "최근 활동" })).toBeTruthy();
    expect(screen.getByText("프로덕트 디자이너 포지션 생성")).toBeTruthy();
    expect(screen.getAllByText("검토 대기").length).toBeGreaterThan(0);
    expect(screen.getByText("오늘 확인할 업무")).toBeTruthy();
    expect(screen.getByText("검토할 지원자")).toBeTruthy();
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
    expect(screen.getAllByText("초안")).toHaveLength(2);
    expect(screen.getAllByText("운영 중")).toHaveLength(2);
    expect(screen.getByText("3명")).toBeTruthy();
    expect(screen.getByText("08. 15.")).toBeTruthy();
    expect(screen.getByText("09. 30.")).toBeTruthy();

    expect(
      screen
        .getByRole("link", {
          name: "백엔드 플랫폼 엔지니어 운영 보기",
        })
        .getAttribute("href"),
    ).toBe("/positions/position-1");
    expect(screen.getByText("지원자 0명")).toBeTruthy();
    expect(screen.getByText("지원자 4명")).toBeTruthy();
  });

  it("opens a divided position dashboard and connects every detailed workspace", async () => {
    render(
      <MemoryRouter>
        <PositionOperations
          positionId="position-2"
          api={operationsApi}
          invitationApi={invitationApi}
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
        .getByRole("tab", { name: "대시보드" })
        .getAttribute("aria-selected"),
    ).toBe("true");
    expect(
      screen.getByRole("heading", { name: "지원자 운영 현황" }),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "최근 지원자" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "초대 현황" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "단계 분포" })).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "면접 기준 요약" }),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "검토할 지원자 종합 리포트" })
        .getAttribute("href"),
    ).toBe("/positions/position-2/applicants/invitation-2");

    fireEvent.click(
      screen.getByRole("button", { name: "지원자 목록 상세 보기" }),
    );
    expect(
      screen
        .getByRole("tab", { name: "지원자 목록" })
        .getAttribute("aria-selected"),
    ).toBe("true");
    expect(await screen.findByText("준비된 지원자")).toBeTruthy();
    expect(screen.getByText("ready@example.com")).toBeTruthy();
    expect(screen.getByText("검토할 지원자")).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "지원자 초대 관리" }),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "초대 패널 접기" })).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "검토할 지원자 상세 보기" })
        .getAttribute("href"),
    ).toBe("/positions/position-2/applicants/invitation-2");

    fireEvent.click(screen.getByRole("tab", { name: "대시보드" }));
    fireEvent.click(
      screen.getByRole("button", { name: "지원자 통계 상세 보기" }),
    );
    expect(screen.getByLabelText("전체 지원자 4명")).toBeTruthy();
    expect(screen.getByLabelText("진행 중인 지원자 2명")).toBeTruthy();
    expect(screen.getByLabelText("검토 대기 지원자 1명")).toBeTruthy();
    expect(screen.getByLabelText("완료된 지원자 1명")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "대시보드" }));
    fireEvent.click(
      screen.getByRole("button", { name: "면접 단계 상세 보기" }),
    );
    expect(
      screen.getByRole("heading", { name: "지원자 면접 흐름" }),
    ).toBeTruthy();
    expect(screen.getByText("초대·확인")).toBeTruthy();
    expect(screen.getByText("자료 제출·분석")).toBeTruthy();
    expect(screen.getByText("결과 검토")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "대시보드" }));
    fireEvent.click(
      screen.getByRole("button", { name: "포지션 정보 상세 보기" }),
    );
    expect(
      screen.getByRole("heading", { name: "현재 적용 중인 면접 기준" }),
    ).toBeTruthy();
    expect(screen.getByText("제품 문제를 구조화하는 경험")).toBeTruthy();
    expect(screen.getByText("문제 해결")).toBeTruthy();
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
    expect(screen.getByLabelText("진행 중인 지원자 2명")).toBeTruthy();
    expect(screen.getByLabelText("검토 대기 지원자 1명")).toBeTruthy();
    expect(screen.getByLabelText("완료된 지원자 1명")).toBeTruthy();
    expect(screen.getAllByText("프로덕트 디자이너")).toHaveLength(4);
    expect(screen.getByText("검토할 지원자")).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "검토할 지원자 상세 보기" })
        .getAttribute("href"),
    ).toBe("/positions/position-2/applicants/invitation-2");
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
        .getByRole("tab", { name: "종합 개요" })
        .getAttribute("aria-selected"),
    ).toBe("true");
    expect(
      screen.getByRole("heading", { name: "지원 진행 요약" }),
    ).toBeTruthy();
    expect(screen.getByLabelText("현재 채용 단계 4단계 중 4단계")).toBeTruthy();
    expect(screen.getAllByText("면접 완료").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("tab", { name: "면접 기록" }));
    expect(
      screen.getByRole("heading", { name: "면접 기록과 응답" }),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "분석 리포트" }));
    expect(
      screen.getByRole("heading", { name: "면접 분석 리포트" }),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "전체 분석 리포트 열기" })
        .getAttribute("href"),
    ).toBe("/review/session-1?invitationId=invitation-2");
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
      .getAllByRole("link", { name: /상세 보기$/ })
      .map((link) => link.getAttribute("href"));
    expect(order[0]).toContain("/applicants/bulk-0");
    expect(order[1]).toContain("/applicants/bulk-1");
  });
});
