import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import {
  parseInvitationImport,
  PositionInvitations,
  type PositionInvitationApi,
} from "../PositionInvitations";
import type {
  InvitationEmailTemplateApi,
  InvitationEmailTemplateState,
} from "../invitationEmailTemplate";

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

function buildTemplateApi(
  overrides: Partial<InvitationEmailTemplateApi> = {},
): InvitationEmailTemplateApi {
  return {
    getCompanyTemplate: vi.fn().mockResolvedValue(emailTemplate),
    saveCompanyTemplate: vi.fn().mockResolvedValue(emailTemplate),
    resetCompanyTemplate: vi.fn().mockResolvedValue(emailTemplate),
    getPositionTemplate: vi.fn().mockResolvedValue(emailTemplate),
    savePositionTemplate: vi.fn((_positionId, next) =>
      Promise.resolve({ ...emailTemplate, ...next, isPositionOverride: true }),
    ),
    resetPositionTemplate: vi.fn().mockResolvedValue(emailTemplate),
    previewTemplate: vi
      .fn()
      .mockResolvedValue({ subject: "미리보기", htmlBody: "<p>본문</p>" }),
    uploadLogo: vi.fn(),
    deleteLogo: vi.fn(),
    ...overrides,
  };
}

const invitations = [
  {
    invitationId: "invitation-1",
    positionId: "position-1",
    competencyModelVersionId: "version-1",
    applicantEmail: "hong@example.com",
    applicantDisplayName: "홍길동",
    status: "consented",
    expiresAt: "2026-08-22T09:00:00Z",
    rowVersion: 3,
    analysisStatus: null,
    interviewStatus: null,
    reportStatus: null,
  },
  {
    invitationId: "invitation-2",
    positionId: "position-1",
    competencyModelVersionId: "version-1",
    applicantEmail: "kim@example.com",
    applicantDisplayName: "김개발",
    status: "expired",
    expiresAt: "2026-08-14T09:00:00Z",
    rowVersion: 2,
    analysisStatus: null,
    interviewStatus: null,
    reportStatus: null,
  },
] as const;

describe("PositionInvitations", () => {
  it("shows applicants beside a collapsible invitation panel", async () => {
    const api: PositionInvitationApi = {
      listInvitations: vi.fn().mockResolvedValue(invitations),
      createInvitations: vi.fn().mockResolvedValue({
        acceptedCount: 0,
        rejectedCount: 0,
        invitations: [],
      }),
    };

    render(
      <MemoryRouter>
        <PositionInvitations
          embedded
          view="workspace"
          positionId="position-1"
          positionName="백엔드 개발자"
          api={api}
        />
      </MemoryRouter>,
    );

    expect(await screen.findByText("홍길동")).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "지원자 초대 관리" }),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "초대 패널 접기" }));
    expect(
      screen.queryByRole("heading", { name: "지원자 초대 관리" }),
    ).toBeNull();
    expect(
      screen.getByRole("button", { name: "초대 패널 펼치기" }),
    ).toBeTruthy();
  });

  it("issues only valid rows and excludes duplicates from the editable table", async () => {
    const api: PositionInvitationApi = {
      listInvitations: vi.fn().mockResolvedValue(invitations),
      createInvitations: vi.fn().mockResolvedValue({
        acceptedCount: 1,
        rejectedCount: 0,
        invitations: [],
      }),
    };

    render(
      <MemoryRouter>
        <PositionInvitations
          positionId="position-1"
          positionName="백엔드 개발자"
          api={api}
        />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "지원자 관리" }),
    ).toBeTruthy();
    expect(screen.getByText("홍길동")).toBeTruthy();
    expect(screen.getByText("동의 완료")).toBeTruthy();
    expect(screen.getByText("1 / 4")).toBeTruthy();
    expect(screen.getByText("만료")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("지원자 1 이름"), {
      target: { value: "박지원" },
    });
    fireEvent.change(screen.getByLabelText("지원자 1 이메일"), {
      target: { value: "park@example.com" },
    });

    fireEvent.click(screen.getByRole("button", { name: "지원자 행 추가" }));
    fireEvent.change(screen.getByLabelText("지원자 2 이름"), {
      target: { value: "이확인" },
    });
    fireEvent.change(screen.getByLabelText("지원자 2 이메일"), {
      target: { value: "잘못된 주소" },
    });

    fireEvent.click(screen.getByRole("button", { name: "지원자 행 추가" }));
    fireEvent.change(screen.getByLabelText("지원자 3 이름"), {
      target: { value: "박지원 중복" },
    });
    fireEvent.change(screen.getByLabelText("지원자 3 이메일"), {
      target: { value: "PARK@example.com" },
    });

    expect(screen.getByText("발송 가능 1명")).toBeTruthy();
    expect(screen.getByText("확인 필요 1명")).toBeTruthy();
    expect(screen.getByText("중복 제외 1명")).toBeTruthy();
    expect(screen.getByText("이메일 형식을 확인하세요.")).toBeTruthy();
    expect(screen.getByText("입력 명단 내 중복")).toBeTruthy();

    fireEvent.click(
      screen.getByRole("button", { name: "1명에게 초대 보내기" }),
    );

    await waitFor(() =>
      expect(api.createInvitations).toHaveBeenCalledWith(
        "position-1",
        [{ displayName: "박지원", email: "park@example.com" }],
        7,
      ),
    );
    const successNotice = await screen.findByText(
      "1명에게 초대 메일을 발송했습니다.",
    );
    expect(successNotice.className).toContain("mb-4");

    fireEvent.change(screen.getByLabelText("지원자 검색"), {
      target: { value: "김개발" },
    });
    expect(screen.getByText("김개발")).toBeTruthy();
    expect(screen.queryByText("홍길동")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "김개발 다시 초대" }));
    await waitFor(() =>
      expect(api.createInvitations).toHaveBeenCalledWith(
        "position-1",
        [{ displayName: "김개발", email: "kim@example.com" }],
        7,
      ),
    );
  });

  it("imports CSV and JSON recipients into the validation table", async () => {
    const api: PositionInvitationApi = {
      listInvitations: vi.fn().mockResolvedValue(invitations),
      createInvitations: vi.fn().mockResolvedValue({
        acceptedCount: 2,
        rejectedCount: 0,
        invitations: [],
      }),
    };
    render(
      <MemoryRouter>
        <PositionInvitations
          positionId="position-1"
          positionName="백엔드 개발자"
          api={api}
        />
      </MemoryRouter>,
    );
    await screen.findByText("홍길동");

    const csvFile = new File([], "applicants.csv", { type: "text/csv" });
    Object.defineProperty(csvFile, "text", {
      value: vi
        .fn()
        .mockResolvedValue(
          [
            "이름,이메일",
            "최서버,server@example.com",
            "윤플랫폼,platform@example.com",
            "기존지원자,HONG@example.com",
          ].join("\n"),
        ),
    });
    fireEvent.change(screen.getByLabelText("CSV 또는 JSON 가져오기"), {
      target: { files: [csvFile] },
    });

    expect(await screen.findByDisplayValue("최서버")).toBeTruthy();
    expect(screen.getByDisplayValue("platform@example.com")).toBeTruthy();
    expect(screen.getByText("발송 가능 2명")).toBeTruthy();
    expect(screen.getByText("중복 제외 1명")).toBeTruthy();
    expect(screen.getByText("이미 등록된 지원자")).toBeTruthy();
  });

  it("summarises the outgoing mail and edits it in place", async () => {
    const api: PositionInvitationApi = {
      listInvitations: vi.fn().mockResolvedValue(invitations),
      createInvitations: vi.fn(),
    };
    const templateApi = buildTemplateApi();

    render(
      <MemoryRouter>
        <PositionInvitations
          embedded
          view="workspace"
          positionId="position-1"
          positionName="백엔드 개발자"
          api={api}
          templateApi={templateApi}
        />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("[{{회사명}}] {{포지션명}} 면접 안내"),
    ).toBeTruthy();
    expect(screen.getByText("전사 기본 문구")).toBeTruthy();
    const mailPreview =
      screen.getByText("발송될 메일").parentElement?.parentElement
        ?.parentElement;
    expect(mailPreview?.className).toContain("m-[12px_14px_12px]");

    fireEvent.click(screen.getByRole("button", { name: "수정" }));
    const drawer = screen.getByRole("dialog", { name: "초대 메일 수정" });
    expect(templateApi.getPositionTemplate).toHaveBeenCalledWith("position-1");

    fireEvent.change(
      await screen.findByRole("textbox", { name: /버튼 텍스트/ }),
      { target: { value: "지금 응답하기" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "저장하고 닫기" }));

    await waitFor(() =>
      expect(templateApi.savePositionTemplate).toHaveBeenCalledWith(
        "position-1",
        expect.objectContaining({ ctaLabel: "지금 응답하기" }),
      ),
    );
    // Saving closes the drawer and the card reflects the new scope, so the
    // recruiter can see what will go out without leaving the send screen.
    await waitFor(() => expect(drawer.isConnected).toBe(false));
    expect(await screen.findByText("이 포지션 전용 문구")).toBeTruthy();
  });

  it("switches the invite modal content to the editor without opening a nested dialog", async () => {
    const api: PositionInvitationApi = {
      listInvitations: vi.fn().mockResolvedValue(invitations),
      createInvitations: vi.fn(),
    };
    const templateApi = buildTemplateApi();

    render(
      <MemoryRouter>
        <PositionInvitations
          embedded
          view="invite"
          positionId="position-1"
          positionName="백엔드 개발자"
          api={api}
          templateApi={templateApi}
        />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "초대할 지원자" }),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "수정" }));

    expect(
      await screen.findByRole("heading", { name: "초대 메일 설정" }),
    ).toBeTruthy();
    expect(screen.queryByRole("dialog", { name: "초대 메일 수정" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "명단으로" }));
    expect(
      await screen.findByRole("heading", { name: "초대할 지원자" }),
    ).toBeTruthy();
  });

  it("keeps sending available when the mail summary cannot load", async () => {
    const api: PositionInvitationApi = {
      listInvitations: vi.fn().mockResolvedValue(invitations),
      createInvitations: vi.fn(),
    };
    const templateApi = buildTemplateApi({
      getPositionTemplate: vi.fn().mockRejectedValue(new Error("boom")),
    });

    render(
      <MemoryRouter>
        <PositionInvitations
          embedded
          view="workspace"
          positionId="position-1"
          positionName="백엔드 개발자"
          api={api}
          templateApi={templateApi}
        />
      </MemoryRouter>,
    );

    expect(await screen.findByText("홍길동")).toBeTruthy();
    expect(screen.getByRole("button", { name: "수정" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /초대 보내기/ })).toBeTruthy();
  });

  it("reports the invitations whose mail did not go out", async () => {
    // `rejectedCount` was in the response and rendered nowhere, so a batch where delivery
    // mostly failed reported as a plain success and the draft rows were cleared -- leaving no
    // way to see who had been left out.
    const api: PositionInvitationApi = {
      listInvitations: vi.fn().mockResolvedValue(invitations),
      createInvitations: vi.fn().mockResolvedValue({
        acceptedCount: 1,
        rejectedCount: 2,
        invitations: [],
      }),
    };

    render(
      <MemoryRouter>
        <PositionInvitations
          positionId="position-1"
          positionName="백엔드 개발자"
          api={api}
        />
      </MemoryRouter>,
    );

    await screen.findByRole("heading", { name: "지원자 관리" });
    fireEvent.change(screen.getByLabelText("지원자 1 이름"), {
      target: { value: "박지원" },
    });
    fireEvent.change(screen.getByLabelText("지원자 1 이메일"), {
      target: { value: "park@example.com" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "1명에게 초대 보내기" }),
    );

    expect(
      await screen.findByText(
        /2명은 초대가 만들어졌지만 메일이 발송되지 않았습니다/,
      ),
    ).toBeTruthy();
    expect(screen.getByText("1명에게 초대 메일을 발송했습니다.")).toBeTruthy();
  });

  it("does not call a batch with no delivered mail a success", async () => {
    const api: PositionInvitationApi = {
      listInvitations: vi.fn().mockResolvedValue(invitations),
      createInvitations: vi.fn().mockResolvedValue({
        acceptedCount: 0,
        rejectedCount: 1,
        invitations: [],
      }),
    };

    render(
      <MemoryRouter>
        <PositionInvitations
          positionId="position-1"
          positionName="백엔드 개발자"
          api={api}
        />
      </MemoryRouter>,
    );

    await screen.findByRole("heading", { name: "지원자 관리" });
    fireEvent.change(screen.getByLabelText("지원자 1 이름"), {
      target: { value: "박지원" },
    });
    fireEvent.change(screen.getByLabelText("지원자 1 이메일"), {
      target: { value: "park@example.com" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "1명에게 초대 보내기" }),
    );

    // `0명의 초대를 발송했습니다.` used to render here, as a success banner.
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText(/초대 메일을 발송했습니다/)).toBeNull();
  });
});

describe("parseInvitationImport", () => {
  it("parses quoted CSV headers and JSON applicants", () => {
    expect(
      parseInvitationImport(
        "applicants.csv",
        'name,email\n"김,개발",kim@example.com\n박서버,park@example.com',
      ),
    ).toEqual([
      { displayName: "김,개발", email: "kim@example.com" },
      { displayName: "박서버", email: "park@example.com" },
    ]);

    expect(
      parseInvitationImport(
        "applicants.json",
        JSON.stringify({
          applicants: [
            { name: "이클라우드", email: "cloud@example.com" },
            { displayName: "정데이터", email: "data@example.com" },
          ],
        }),
      ),
    ).toEqual([
      { displayName: "이클라우드", email: "cloud@example.com" },
      { displayName: "정데이터", email: "data@example.com" },
    ]);
  });
  it("shows each score with the share of the criteria it was taken over", async () => {
    // Two applicants ranked side by side whose interviews reached different criteria do not have
    // comparable numbers. A column of bare scores invites exactly that comparison, so the
    // coverage travels with the number and a partial one is marked.
    const scored = [
      {
        ...invitations[0],
        status: "reviewed" as const,
        reportStatus: "ready",
        overallScore: 82,
        scoredCriteriaCount: 4,
        totalCriteriaCount: 4,
      },
      {
        ...invitations[1],
        status: "completed" as const,
        reportStatus: "ready",
        overallScore: 91,
        scoredCriteriaCount: 3,
        totalCriteriaCount: 4,
      },
    ];
    const api: PositionInvitationApi = {
      listInvitations: vi.fn().mockResolvedValue(scored),
      createInvitations: vi.fn(),
    };

    render(
      <MemoryRouter>
        <PositionInvitations
          embedded
          view="workspace"
          positionId="position-1"
          positionName="백엔드 개발자"
          api={api}
          templateApi={buildTemplateApi()}
        />
      </MemoryRouter>,
    );

    expect(await screen.findByText("82점")).toBeTruthy();
    expect(screen.getByText("91점")).toBeTruthy();
    expect(screen.getByText("기준 4 / 4")).toBeTruthy();
    // The partial one is flagged, because its divisor is not the other's.
    expect(screen.getByText("기준 3 / 4 ⚠")).toBeTruthy();
  });

  it("ranks by score on request and puts applicants without one last", async () => {
    // Not sorted by default: the roster keeps invitation order until the recruiter asks to rank.
    // An unscored applicant sorts last rather than as a zero -- the interview has not happened,
    // which is not the same as answering badly.
    const mixed = [
      { ...invitations[0], overallScore: null },
      {
        ...invitations[1],
        reportStatus: "ready",
        overallScore: 64,
        scoredCriteriaCount: 4,
        totalCriteriaCount: 4,
      },
    ];
    const api: PositionInvitationApi = {
      listInvitations: vi.fn().mockResolvedValue(mixed),
      createInvitations: vi.fn(),
    };

    render(
      <MemoryRouter>
        <PositionInvitations
          embedded
          view="workspace"
          positionId="position-1"
          positionName="백엔드 개발자"
          api={api}
          templateApi={buildTemplateApi()}
        />
      </MemoryRouter>,
    );

    await screen.findByText("64점");
    const names = () =>
      screen
        .getAllByRole("row")
        .slice(1)
        .map((row) => row.textContent ?? "");
    expect(names()[0]).toContain("홍길동");

    fireEvent.click(screen.getByRole("button", { name: /점수 높은 순 정렬/ }));

    expect(names()[0]).toContain("김개발");
    expect(names()[1]).toContain("홍길동");
    // And the unscored applicant says why there is no number, rather than showing 0.
    expect(screen.getByText("면접 전")).toBeTruthy();
  });
});
