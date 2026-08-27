import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HiringWorkspace, type HiringWorkspaceApi } from "../index";
import type {
  InvitationEmailTemplateApi,
  InvitationEmailTemplateState,
} from "../invitationEmailTemplate";

const invitationTemplate: InvitationEmailTemplateState = {
  subject: "[{{회사명}}] {{포지션명}} 온라인 면접 안내",
  headline: "서류 전형 합격을 축하드립니다",
  intro: "{{지원자명}}님, 온라인 면접에 초대드립니다.",
  guides: [],
  ctaLabel: "면접 시작하기",
  outro: "좋은 결과로 만나뵙기를 기대합니다.",
  footer: "본 메일은 발신 전용입니다",
  brandColor: "#5966ce",
  useApplicantName: true,
  emphasizeDeadline: true,
  showSecurityNotice: true,
  logoUrl: null,
  isPositionOverride: false,
};

function createApi(): HiringWorkspaceApi {
  return {
    createPosition: vi
      .fn()
      .mockResolvedValue({ positionId: "position-1", rowVersion: 1 }),
    publishCriteria: vi.fn().mockResolvedValue({ versionId: "version-1" }),
    activatePosition: vi.fn().mockResolvedValue(undefined),
  };
}

function createInvitationTemplateApi(): InvitationEmailTemplateApi {
  return {
    getCompanyTemplate: vi.fn().mockResolvedValue(invitationTemplate),
    saveCompanyTemplate: vi.fn().mockResolvedValue(invitationTemplate),
    resetCompanyTemplate: vi.fn().mockResolvedValue(invitationTemplate),
    getPositionTemplate: vi.fn().mockResolvedValue(invitationTemplate),
    savePositionTemplate: vi.fn().mockResolvedValue({
      ...invitationTemplate,
      isPositionOverride: true,
    }),
    resetPositionTemplate: vi.fn().mockResolvedValue(invitationTemplate),
    previewTemplate: vi.fn().mockResolvedValue({ subject: "", htmlBody: "" }),
    uploadLogo: vi.fn(),
    deleteLogo: vi.fn(),
  };
}

function completePositionBasics() {
  fireEvent.change(screen.getByLabelText("포지션명"), {
    target: { value: "백엔드 플랫폼 엔지니어" },
  });
  fireEvent.change(screen.getByLabelText("모집 시작일"), {
    target: { value: "2026-09-01" },
  });
  fireEvent.change(screen.getByLabelText("모집 종료일"), {
    target: { value: "2026-09-30" },
  });
}

async function advanceToPositionDescription() {
  fireEvent.click(screen.getByLabelText("포지션명"));
  fireEvent.click(
    screen.getByRole("button", { name: /서비스 백엔드 사용자 기능/ }),
  );
  fireEvent.click(screen.getByRole("button", { name: "적용하기" }));
  completePositionBasics();
  fireEvent.click(screen.getByRole("button", { name: "다음" }));
  await screen.findByRole("heading", { name: "포지션 상세와 초대 메일" });
}

async function advanceToEvaluation(
  api: HiringWorkspaceApi,
  invitationTemplateApi?: InvitationEmailTemplateApi,
) {
  render(
    <HiringWorkspace api={api} invitationTemplateApi={invitationTemplateApi} />,
  );
  await advanceToPositionDescription();
  fireEvent.change(await screen.findByLabelText("포지션 설명"), {
    target: { value: "ECS 기반 서비스의 안정성과 운영 품질을 개선합니다." },
  });
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await screen.findByText("포지션 상세와 초대 메일을 저장했습니다.");
  fireEvent.click(screen.getByRole("button", { name: "다음" }));
  await screen.findByText("지원자에게 무엇을 요청할까요?");
  fireEvent.click(screen.getByRole("button", { name: "다음" }));
  await screen.findByText("어떤 기준으로 평가할까요?");
}

describe("HiringWorkspace", () => {
  it("shows one position question at a time and keeps the active step number visible", async () => {
    const api = createApi();
    render(<HiringWorkspace api={api} />);

    expect(screen.getByText("포지션명과 모집 기간")).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByText("주요 기술 스택을 선택해 주세요")).toBeNull();
    expect(screen.queryByText("포지션 상세")).toBeNull();

    const progress = screen.getByRole("navigation", {
      name: "채용 설정 진행 단계",
    });
    const currentStep = within(progress).getByText("1");
    expect(currentStep.className).toContain("text-[11px]");
    expect(currentStep.className).toContain("!text-white");

    fireEvent.click(screen.getByLabelText("포지션명"));
    const roleDialog = await screen.findByRole("dialog");
    expect(within(roleDialog).getByText("찾아보세요!")).toBeTruthy();
    const editableTitle = within(roleDialog).getByLabelText("포지션명 수정");
    expect(editableTitle).toBe(document.activeElement);
    fireEvent.change(editableTitle, {
      target: { value: "직접 수정한 포지션명" },
    });
    expect((screen.getByLabelText("포지션명") as HTMLInputElement).value).toBe(
      "",
    );
    fireEvent.click(
      within(roleDialog).getByRole("button", { name: "적용하기" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect((screen.getByLabelText("포지션명") as HTMLInputElement).value).toBe(
      "직접 수정한 포지션명",
    );

    fireEvent.click(screen.getByLabelText("포지션명"));
    fireEvent.click(
      screen.getByRole("button", { name: /서비스 백엔드 사용자 기능/ }),
    );
    expect((screen.getByLabelText("포지션명") as HTMLInputElement).value).toBe(
      "직접 수정한 포지션명",
    );
    expect(screen.getByRole("dialog")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "적용하기" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect((screen.getByLabelText("포지션명") as HTMLInputElement).value).toBe(
      "서비스 백엔드",
    );

    completePositionBasics();
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    expect(
      await screen.findByRole("heading", {
        name: "포지션 상세와 초대 메일",
      }),
    ).toBeTruthy();
    expect(screen.getByText("이 내용은 어디에 쓰이나요?")).toBeTruthy();
    expect(
      screen.getByText(/면접 질문이나 점수에는 직접 반영되지 않으며/),
    ).toBeTruthy();
    expect(screen.queryByText("주요 기술 스택을 선택해 주세요")).toBeNull();
    expect(screen.queryByLabelText("기술 스택 검색")).toBeNull();
    expect(screen.queryByText("포지션명과 모집 기간")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "이전" }));
    expect(await screen.findByText("포지션명과 모집 기간")).toBeTruthy();
  });

  it("can insert a short plain-text position description example", async () => {
    const api = createApi();
    render(<HiringWorkspace api={api} />);
    await advanceToPositionDescription();

    expect(await screen.findByText("초대 메일")).toBeTruthy();
    expect(
      await screen.findByText(/미리보기 안의 내용을 클릭하면 바로 수정/),
    ).toBeTruthy();
    expect(
      (screen.getByLabelText("초대 메일 헤드라인") as HTMLInputElement).value,
    ).toBe("지원해주셔서 감사합니다");
    expect(screen.getByText("면접 일정에 맞춰 자동 설정")).toBeTruthy();
    expect(screen.queryByText("2026년 9월 30일 23:59")).toBeNull();
    expect(screen.queryByText("안내 메시지")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "예시 적용" }));

    const description = screen.getByLabelText(
      "포지션 설명",
    ) as HTMLTextAreaElement;
    expect(description.maxLength).toBe(400);
    expect(description.value).toContain("AI 기반 업무 자동화 서비스");
    expect(description.value).toContain("서버 API, 비즈니스 로직");
    expect(description.value.split("\n")).toHaveLength(4);
    expect(description.value).not.toContain("##");
    expect(description.value).not.toContain("[");
    expect(description.value).not.toContain("•");

    expect(screen.getByText(`${description.value.length} / 400`)).toBeTruthy();

    const saveButton = screen.getByRole("button", { name: "저장" });
    fireEvent.click(saveButton);
    expect(
      await screen.findByText("포지션 상세와 초대 메일을 저장했습니다."),
    ).toBeTruthy();
    expect(saveButton).toHaveProperty("disabled", true);

    fireEvent.change(description, { target: { value: "수정된 내용" } });
    expect(saveButton).toHaveProperty("disabled", false);

    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    expect(
      screen.getByText("수정한 포지션 상세와 초대 메일을 먼저 저장해 주세요."),
    ).toBeTruthy();
    expect(scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "center",
    });
    expect(saveButton).toBe(document.activeElement);
  });

  it("publishes evaluation items with internal verification guides", async () => {
    const api = createApi();
    const invitationTemplateApi = createInvitationTemplateApi();
    await advanceToEvaluation(api, invitationTemplateApi);

    expect(screen.queryByText("AI 면접관")).toBeNull();
    expect(screen.queryByLabelText("음성")).toBeNull();
    expect(screen.queryByLabelText("중요도 1")).toBeNull();
    expect(screen.queryByLabelText("연결 평가기준 1")).toBeNull();
    expect(screen.queryByLabelText("확인할 요소 1")).toBeNull();
    expect(screen.queryByLabelText("공통 질문 1")).toBeNull();
    expect(screen.queryByLabelText("평가 축 1")).toBeNull();

    fireEvent.change(screen.getByLabelText("자격요건 1"), {
      target: { value: "ECS 운영 장애 대응 경험" },
    });
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    await screen.findByText("면접은 어떻게 진행할까요?");
    expect(screen.queryByText("내부 면접 정책")).toBeNull();
    expect(screen.queryByLabelText("금지 주제")).toBeNull();
    expect(screen.queryByLabelText("면접 시간(분)")).toBeNull();
    expect(screen.getByText("반드시 물어볼 질문")).toBeTruthy();
    expect(
      screen.getByText(/필수·우대 자격요건은 질문을 직접 만들지 않고/),
    ).toBeTruthy();
    expect(
      screen.getByText(/아래 질문만 기업이 직접 지정한 질문으로 별도 표시/),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "필수 질문 추가" }));
    fireEvent.change(screen.getByLabelText("필수 질문 1"), {
      target: { value: "최근 가장 어려웠던 기술적 판단은 무엇이었나요?" },
    });
    expect(screen.getByAltText("신입 AI 면접관").getAttribute("src")).toBe(
      "/interviewers/entry_eyes_open_mouth_closed.webp",
    );
    expect(screen.getByAltText("주니어 AI 면접관").getAttribute("src")).toBe(
      "/interviewers/junior_eyes_open_mouth_closed.webp",
    );
    expect(screen.getByAltText("시니어 AI 면접관").getAttribute("src")).toBe(
      "/interviewers/senior_eyes_open_mouth_closed.webp",
    );
    expect(screen.getAllByText("한국어 남성 음성")).toHaveLength(3);
    expect(screen.queryByText("Seoyeon")).toBeNull();
    fireEvent.change(screen.getByLabelText("채용 인원"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText("면접 정원"), {
      target: { value: "4" },
    });
    expect(
      screen.getByLabelText("예약 오토스케일링 예상 비용").textContent,
    ).toContain("추가 증설 없음 · 0원");
    fireEvent.change(screen.getByLabelText("면접 정원"), {
      target: { value: "100" },
    });
    expect(
      screen.getByLabelText("예약 오토스케일링 예상 비용").textContent,
    ).toContain("필요 최소 용량 · API 5개 · Worker 5개");
    expect(
      screen.getByLabelText("예약 오토스케일링 예상 비용").textContent,
    ).toContain("예약 증설 약 484원/회");
    fireEvent.change(screen.getByLabelText("면접 정원"), {
      target: { value: "4" },
    });
    fireEvent.change(screen.getByLabelText("면접 시각"), {
      target: { value: "2026-09-15T14:00" },
    });
    fireEvent.change(screen.getByLabelText("면접 정원"), {
      target: { value: "401" },
    });
    expect(
      (screen.getByRole("button", { name: "포지션 게시" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    fireEvent.change(screen.getByLabelText("면접 정원"), {
      target: { value: "4" },
    });
    fireEvent.change(screen.getByLabelText("면접 난이도"), {
      target: { value: "senior" },
    });
    fireEvent.click(screen.getByRole("button", { name: "포지션 게시" }));

    expect(await screen.findByText("채용 기준 게시 완료")).toBeTruthy();
    expect(api.createPosition).toHaveBeenCalledWith(
      expect.objectContaining({
        headcount: 2,
        interviewCapacity: 4,
        interviewAt: "2026-09-15T14:00",
        recruitmentStartAt: "2026-09-01",
        recruitmentEndAt: "2026-09-30",
        submissionRequirements: expect.arrayContaining([
          expect.objectContaining({
            materialType: "resume",
            required: true,
            enabled: true,
          }),
          expect.objectContaining({
            materialType: "portfolio",
            required: false,
            enabled: false,
          }),
        ]),
      }),
    );
    expect(api.publishCriteria).toHaveBeenCalledWith("position-1", {
      jobRequirements: [
        {
          requirementType: "required",
          statement: "ECS 운영 장애 대응 경험",
          priority: 1,
          criterionCode: "TECHNICAL_COMPETENCY",
        },
      ],
      criteria: expect.arrayContaining([
        expect.objectContaining({
          code: "TECHNICAL_COMPETENCY",
          name: "기술 역량",
          weight: 30,
          commonQuestions: ["최근 가장 어려웠던 기술적 판단은 무엇이었나요?"],
          verificationGuide: {
            observableDimensions: [
              "기술 선택 이유",
              "구현 방식",
              "원리 이해",
              "대안과 트레이드오프",
              "검증 결과",
            ],
            strongAnswerSignals: [
              "직접 사용한 기술의 선택 이유와 구현 방식, 검증 결과를 구체적으로 설명함",
            ],
            weakAnswerSignals: [
              "기술 이름만 나열하거나 원리와 직접 수행한 내용이 불명확함",
            ],
            followUpDirections: [
              "기술 선택 이유",
              "구현 세부사항",
              "대안 비교",
              "검증 방법",
            ],
            maxFollowUps: 2,
            timeBudgetSeconds: 540,
          },
        }),
        expect.objectContaining({
          code: "PROJECT_EXECUTION",
          name: "프로젝트 실행 역량",
          weight: 40,
          commonQuestions: [],
        }),
        expect.objectContaining({
          code: "COLLABORATION_BEHAVIOR",
          name: "협업·행동 역량",
          weight: 30,
        }),
      ]),
      prohibitedTopics: ["가족관계", "출신지역", "혼인·임신 여부", "외모"],
      interviewDurationMinutes: 30,
      interviewLevel: "senior",
      personaDefinition: {
        name: "심층형 면접관",
        tone: "concise",
        voiceId: "Seoyeon",
      },
    });
    expect(invitationTemplateApi.savePositionTemplate).toHaveBeenCalledWith(
      "position-1",
      expect.objectContaining({
        subject: invitationTemplate.subject,
        headline: invitationTemplate.headline,
        guides: [],
      }),
    );
    expect(invitationTemplateApi.saveCompanyTemplate).not.toHaveBeenCalled();
    expect(api.activatePosition).toHaveBeenCalledWith(
      "position-1",
      1,
      expect.objectContaining({
        title: "백엔드 플랫폼 엔지니어",
        recruitmentStartAt: "2026-09-01",
        recruitmentEndAt: "2026-09-30",
      }),
    );
    expect(
      vi.mocked(api.createPosition).mock.invocationCallOrder[0],
    ).toBeLessThan(
      vi.mocked(invitationTemplateApi.savePositionTemplate).mock
        .invocationCallOrder[0],
    );
    expect(
      vi.mocked(invitationTemplateApi.savePositionTemplate).mock
        .invocationCallOrder[0],
    ).toBeLessThan(vi.mocked(api.publishCriteria).mock.invocationCallOrder[0]);
    expect(
      vi.mocked(api.publishCriteria).mock.invocationCallOrder[0],
    ).toBeLessThan(vi.mocked(api.activatePosition).mock.invocationCallOrder[0]);
  });

  it("adds qualifications without creating score criteria", async () => {
    const api = createApi();
    await advanceToEvaluation(api);

    fireEvent.click(screen.getByRole("button", { name: "자격요건 행 추가" }));
    fireEvent.change(screen.getByLabelText("자격요건 2"), {
      target: { value: "대규모 API 설계 경험" },
    });
    expect(
      (screen.getByLabelText("자격요건 2") as HTMLInputElement).value,
    ).toBe("대규모 API 설계 경험");
    expect(screen.queryByLabelText("연결 평가기준 2")).toBeNull();
    expect(screen.queryByLabelText("평가 축 2")).toBeNull();
    expect(screen.getByRole("list", { name: "자격요건 목록" })).toBeTruthy();
    expect(screen.getByText("필 2")).toBeTruthy();
    expect(screen.getByText("우 0")).toBeTruthy();
    const secondType = screen.getByRole("group", {
      name: "자격요건 2 구분",
    });
    expect(
      within(secondType)
        .getByRole("button", { name: "필수" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    fireEvent.click(within(secondType).getByRole("button", { name: "우대" }));
    expect(
      within(secondType)
        .getByRole("button", { name: "우대" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    expect(screen.getByText("필 1")).toBeTruthy();
    expect(screen.getByText("우 1")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "우대 사항" })).toBeNull();
    expect(
      screen.queryByRole("group", { name: "자격요건 1 중요도" }),
    ).toBeNull();
    expect(screen.getByText("자격요건을 적으면 이렇게 동작해요")).toBeTruthy();
    expect(screen.getByText("“대규모 API 설계 경험”")).toBeTruthy();
    expect(screen.getByText("우대 사항 예시")).toBeTruthy();
    expect(screen.getByText(/각각 하나의 리포트 판정/)).toBeTruthy();
    expect(
      screen.getByText(/다음 단계의 ‘필수 질문’에 따로 입력/),
    ).toBeTruthy();
  });

  it("fills realistic project qualification examples with a staggered animation", async () => {
    const api = createApi();
    await advanceToEvaluation(api);

    fireEvent.click(screen.getByRole("button", { name: "예시 채우기" }));

    expect(screen.getByText("필 4")).toBeTruthy();
    expect(screen.getByText("우 4")).toBeTruthy();
    const requirements = within(
      screen.getByRole("list", { name: "자격요건 목록" }),
    ).getAllByRole("listitem");
    expect(requirements).toHaveLength(8);
    expect(
      (screen.getByLabelText("자격요건 1") as HTMLInputElement).value,
    ).toContain("Python·FastAPI");
    expect(
      (screen.getByLabelText("자격요건 8") as HTMLInputElement).value,
    ).toContain("B2B SaaS");
    expect(requirements[0]?.className).toContain("requirement-row-in");
    expect(requirements[0]?.style.animationDelay).toBe("0ms");
    expect(requirements[7]?.style.animationDelay).toBe("490ms");
  });

  it("keeps qualification importance out of the form", async () => {
    const api = createApi();
    await advanceToEvaluation(api);

    const addEvaluationItem = screen.getByRole("button", {
      name: "자격요건 행 추가",
    });
    expect(addEvaluationItem.textContent).toContain("자격요건 추가");
    fireEvent.click(addEvaluationItem);
    expect(screen.queryByLabelText("평가 축 1")).toBeNull();
    const qualification = screen.getByLabelText("자격요건 1");
    fireEvent.change(qualification, {
      target: { value: "끝까지 파고드는 태도" },
    });
    expect(screen.getByText("어떤 기준으로 평가할까요?")).toBeTruthy();
    expect(
      screen.queryByRole("group", { name: "자격요건 1 중요도" }),
    ).toBeNull();
    expect(screen.queryByLabelText("자격요건 1 자동 가중치")).toBeNull();
    expect(screen.queryByLabelText("가중치 1 직접 입력")).toBeNull();
  });

  it("continues input inside the same requirement group with Enter", async () => {
    const api = createApi();
    await advanceToEvaluation(api);

    const qualification = screen.getByLabelText("자격요건 1");
    qualification.focus();
    fireEvent.keyDown(qualification, { key: "Enter", code: "Enter" });

    expect(screen.getByLabelText("자격요건 2")).toBe(document.activeElement);
    const typeGroups = screen.getAllByRole("group", {
      name: /자격요건 \d 구분/,
    });
    expect(typeGroups).toHaveLength(2);
    typeGroups.forEach((group) => {
      expect(
        within(group)
          .getByRole("button", { name: "필수" })
          .getAttribute("aria-pressed"),
      ).toBe("true");
    });
  });

  it("uses only the required and preferred qualification list for evaluation", async () => {
    const api = createApi();
    await advanceToEvaluation(api);

    expect(screen.getByRole("list", { name: "자격요건 목록" })).toBeTruthy();
    expect(
      screen.getByText(/필수·우대 항목은 질문이 아니라 각각 하나의 리포트/),
    ).toBeTruthy();
    expect(screen.queryByRole("slider")).toBeNull();
    expect(screen.queryByText(/다섯 방향/)).toBeNull();
    expect(screen.queryByText("정확성")).toBeNull();
  });
});
