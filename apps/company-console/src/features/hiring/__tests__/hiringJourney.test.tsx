import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HiringWorkspace, type HiringWorkspaceApi } from "../index";

function createApi(): HiringWorkspaceApi {
  return {
    createPosition: vi.fn().mockResolvedValue({ positionId: "position-1" }),
    publishCriteria: vi.fn().mockResolvedValue({ versionId: "version-1" }),
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
  completePositionBasics();
  fireEvent.click(screen.getByRole("button", { name: "다음" }));
  await screen.findByRole("heading", {
    name: "주요 기술 스택을 선택해 주세요",
  });
  fireEvent.click(screen.getByRole("button", { name: "백엔드" }));
  fireEvent.click(await screen.findByRole("option", { name: "Spring Boot" }));
  fireEvent.click(screen.getByRole("button", { name: "다음" }));
  await screen.findByRole("heading", { name: "포지션 상세" });
}

async function advanceToEvaluation(api: HiringWorkspaceApi) {
  render(<HiringWorkspace api={api} />);
  await advanceToPositionDescription();
  fireEvent.change(screen.getByLabelText("포지션 설명"), {
    target: { value: "ECS 기반 서비스의 안정성과 운영 품질을 개선합니다." },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "포지션 상세 작성 완료" }),
  );
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
    expect(
      screen
        .getByText("채용할 직무를 선택해 주세요")
        .closest("#position-role-picker")
        ?.getAttribute("aria-hidden"),
    ).toBe("true");
    expect(screen.queryByText("주요 기술 스택을 선택해 주세요")).toBeNull();
    expect(screen.queryByText("포지션 상세")).toBeNull();

    const progress = screen.getByRole("navigation", {
      name: "채용 설정 진행 단계",
    });
    const currentStep = within(progress).getByText("1");
    expect(currentStep.className).toContain("text-[11px]");
    expect(currentStep.className).toContain("!text-white");

    fireEvent.click(screen.getByLabelText("포지션명"));
    expect(await screen.findByText("채용할 직무를 선택해 주세요")).toBeTruthy();
    const customRoleInput = screen.getByLabelText("세부 직무 직접 입력");
    expect(customRoleInput).toBe(document.activeElement);
    fireEvent.keyDown(customRoleInput, { key: "Escape" });
    expect(
      screen
        .getByText("채용할 직무를 선택해 주세요")
        .closest("#position-role-picker")
        ?.getAttribute("aria-hidden"),
    ).toBe("true");

    fireEvent.click(screen.getByLabelText("포지션명"));
    fireEvent.click(
      screen.getByRole("button", { name: /서비스 백엔드 사용자 기능/ }),
    );
    expect((screen.getByLabelText("포지션명") as HTMLInputElement).value).toBe(
      "서비스 백엔드",
    );
    expect(
      screen
        .getByText("채용할 직무를 선택해 주세요")
        .closest("#position-role-picker")
        ?.getAttribute("aria-hidden"),
    ).toBe("true");

    completePositionBasics();
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    expect(
      await screen.findByText("주요 기술 스택을 선택해 주세요"),
    ).toBeTruthy();
    expect(screen.getByLabelText("기술 스택 검색")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "기술 추가" })).toBeNull();
    expect(screen.queryByText("포지션명과 모집 기간")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "이전" }));
    expect(await screen.findByText("포지션명과 모집 기간")).toBeTruthy();
  });

  it("can insert the long-form position description example", async () => {
    const api = createApi();
    render(<HiringWorkspace api={api} />);
    await advanceToPositionDescription();

    fireEvent.click(
      screen.getByRole("button", { name: "포지션 상세 예시 적용" }),
    );

    const description = screen.getByLabelText(
      "포지션 설명",
    ) as HTMLTextAreaElement;
    expect(description.maxLength).toBe(2000);
    expect(description.value).toContain("## Build the Next Version");
    expect(description.value).toContain("주요업무");
    expect(description.value).toContain("Junior Product Engineer");

    const completeButton = screen.getByRole("button", {
      name: "포지션 상세 작성 완료",
    });
    const characterCount = screen.getByText(
      `${description.value.length} / 2000`,
    );
    expect(
      characterCount.compareDocumentPosition(completeButton) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    fireEvent.click(completeButton);
    expect(completeButton.getAttribute("aria-pressed")).toBe("true");

    fireEvent.change(description, { target: { value: "수정된 내용" } });
    expect(completeButton.getAttribute("aria-pressed")).toBe("false");
  });

  it("publishes evaluation items with internal verification guides", async () => {
    const api = createApi();
    await advanceToEvaluation(api);

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
    fireEvent.change(screen.getByRole("slider", { name: "깊이 관점 강도" }), {
      target: { value: "100" },
    });
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    await screen.findByText("면접은 어떻게 진행할까요?");
    expect(screen.queryByText("내부 면접 정책")).toBeNull();
    expect(screen.queryByLabelText("금지 주제")).toBeNull();
    expect(screen.queryByLabelText("면접 시간(분)")).toBeNull();
    expect(screen.getByText("30분 고정 면접")).toBeTruthy();
    expect(screen.getByText("1. 기술 면접 · 9분")).toBeTruthy();
    expect(screen.getByText("2. 프로젝트 심층 · 12분")).toBeTruthy();
    expect(screen.getByText("3. 협업·인성 · 9분")).toBeTruthy();
    expect(screen.getByAltText("신입 AI 면접관").getAttribute("src")).toBe(
      "/interviewers/entry_eyes_open_mouth_closed.webp",
    );
    expect(screen.getByAltText("주니어 AI 면접관").getAttribute("src")).toBe(
      "/interviewers/junior_eyes_open_mouth_closed.webp",
    );
    expect(screen.getByAltText("시니어 AI 면접관").getAttribute("src")).toBe(
      "/interviewers/senior_eyes_open_mouth_closed.webp",
    );
    fireEvent.change(screen.getByLabelText("채용 인원"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText("면접 정원"), {
      target: { value: "4" },
    });
    fireEvent.change(screen.getByLabelText("면접 시각"), {
      target: { value: "2026-09-15T14:00" },
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
          criterionCode: "CRITERION_1",
        },
      ],
      criteria: [
        expect.objectContaining({
          code: "CRITERION_1",
          name: "ECS 운영 장애 대응 경험",
          description: "ECS 운영 장애 대응 경험",
          verificationGuide: {
            observableDimensions: [
              "상황",
              "본인이 직접 수행한 행동",
              "판단 근거",
              "결과",
            ],
            strongAnswerSignals: [
              "구체적인 상황, 본인 역할, 행동과 결과가 포함됨",
            ],
            weakAnswerSignals: [
              "팀 활동이나 기술 이름만 있고 본인 행동이 불명확함",
            ],
            followUpDirections: [
              "본인이 직접 수행한 행동",
              "판단 근거",
              "측정 가능한 결과",
            ],
            maxFollowUps: 2,
            timeBudgetSeconds: 300,
          },
        }),
      ],
      prohibitedTopics: ["가족관계", "출신지역", "혼인·임신 여부", "외모"],
      interviewDurationMinutes: 30,
      interviewLevel: "senior",
      // All five, always, and totalling 100. The API accepts an empty mapping as equal weight
      // but refuses a partial one, so sending fewer than five would be a 422 rather than a
      // default.
      axisWeights: {
        correctness: 17,
        depth: 33,
        fundamentals: 17,
        ownership: 17,
        communication: 16,
      },
      personaDefinition: {
        name: "심층형 면접관",
        tone: "concise",
        voiceId: "Seoyeon",
      },
    });
    expect(
      vi.mocked(api.createPosition).mock.invocationCallOrder[0],
    ).toBeLessThan(vi.mocked(api.publishCriteria).mock.invocationCallOrder[0]);
  });

  it("adds a qualification and its internal criterion together", async () => {
    const api = createApi();
    await advanceToEvaluation(api);

    fireEvent.click(screen.getByRole("button", { name: "자격요건 행 추가" }));
    fireEvent.change(screen.getByLabelText("자격요건 2"), {
      target: { value: "대규모 API 설계 경험" },
    });
    expect(screen.getByText("대규모 API 설계 경험")).toBeTruthy();
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
      screen.getByRole("img", {
        name: "자격요건별 자동 가중치 원그래프",
      }),
    ).toBeTruthy();
    const firstImportance = screen.getByRole("group", {
      name: "자격요건 1 중요도",
    });
    expect(
      within(firstImportance)
        .getByRole("button", { name: "보통" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    fireEvent.click(
      within(firstImportance).getByRole("button", { name: "높음" }),
    );
    expect(screen.getByLabelText("자격요건 1 자동 가중치").textContent).toBe(
      "67%",
    );
    expect(screen.getByLabelText("자격요건 2 자동 가중치").textContent).toBe(
      "33%",
    );
  });

  it("keeps only the qualification and weight editable", async () => {
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
    fireEvent.click(
      within(
        screen.getByRole("group", { name: "자격요건 1 중요도" }),
      ).getByRole("button", { name: "낮음" }),
    );

    expect(screen.getByLabelText("자격요건 1 자동 가중치").textContent).toBe(
      "33%",
    );
    expect(screen.getByLabelText("자격요건 2 자동 가중치").textContent).toBe(
      "67%",
    );
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

  it("keeps the five scoring axes at a total of 100 and sends all of them", async () => {
    // The axes are fixed and the domain requires the five weights to total 100, so dragging one
    // has to redistribute the rest. Sending a partial mapping would be a 422, not a default.
    const api = createApi();
    await advanceToEvaluation(api);

    const control = screen.getByRole("group", {
      name: "답변 평가 관점 오각형",
    });
    const accuracy = screen.getByRole("slider", {
      name: "정확성 관점 강도",
    }) as HTMLInputElement;
    const depth = screen.getByRole("slider", {
      name: "깊이 관점 강도",
    }) as HTMLInputElement;

    expect(accuracy.value).toBe("50");
    expect(depth.value).toBe("50");
    fireEvent.change(depth, { target: { value: "100" } });
    expect(depth.value).toBe("100");
    expect(accuracy.value).toBe("50");
    expect(within(control).queryByText(/합계/)).toBeNull();

    const fundamentals = screen.getByRole("slider", {
      name: "CS 기본기 관점 강도",
    }) as HTMLInputElement;
    fireEvent.change(fundamentals, { target: { value: "0" } });
    expect(fundamentals.value).toBe("0");
    expect(accuracy.value).toBe("50");
  });

  it("axes cannot be added or removed by the recruiter", async () => {
    // A company expresses what it values by which 평가기준 it asks about. The axes describe how
    // an answer is read, and each carries the guidance the scoring prompt is built from, so
    // there is deliberately no control here to add one.
    const api = createApi();
    await advanceToEvaluation(api);

    expect(screen.getByText(/WhyYou는 답변의 근거를/)).toBeTruthy();
    expect(
      screen.getByRole("group", { name: "답변 평가 관점 오각형" }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /채점축 추가/ })).toBeNull();
    for (const label of [
      "정확성",
      "깊이",
      "CS 기본기",
      "본인 기여",
      "설명력",
    ]) {
      expect(screen.getByLabelText(`${label} 관점 강도`)).toBeTruthy();
    }
  });
});
