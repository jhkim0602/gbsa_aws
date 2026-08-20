import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HiringWorkspace, type HiringWorkspaceApi } from "../index";

function createApi(): HiringWorkspaceApi {
  return {
    createPosition: vi.fn().mockResolvedValue({ positionId: "position-1" }),
    publishCriteria: vi.fn().mockResolvedValue({ versionId: "version-1" }),
  };
}

async function advanceToEvaluation(api: HiringWorkspaceApi) {
  render(<HiringWorkspace api={api} />);
  fireEvent.change(screen.getByLabelText("포지션명"), {
    target: { value: "백엔드 플랫폼 엔지니어" },
  });
  fireEvent.change(screen.getByLabelText("모집 시작일"), {
    target: { value: "2026-09-01" },
  });
  fireEvent.change(screen.getByLabelText("모집 종료일"), {
    target: { value: "2026-09-30" },
  });
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
  it("can insert the long-form position description example", () => {
    const api = createApi();
    render(<HiringWorkspace api={api} />);

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
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    await screen.findByText("면접은 어떻게 진행할까요?");
    expect(screen.queryByText("내부 면접 정책")).toBeNull();
    expect(screen.queryByLabelText("금지 주제")).toBeNull();
    expect(screen.queryByLabelText("면접 시간(분)")).toBeNull();
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

    fireEvent.click(screen.getByRole("button", { name: "자격요건 추가" }));
    fireEvent.change(screen.getByLabelText("자격요건 2"), {
      target: { value: "대규모 API 설계 경험" },
    });
    expect(screen.queryByLabelText("연결 평가기준 2")).toBeNull();
    expect(screen.queryByLabelText("평가 축 2")).toBeNull();
    expect(
      screen
        .getAllByRole("button", { name: "우대 사항" })[1]
        .getAttribute("aria-pressed"),
    ).toBe("true");
    expect(screen.getByText("가중치 합계").parentElement?.textContent).toBe(
      "가중치 합계100",
    );
    expect((screen.getByLabelText("가중치 1") as HTMLInputElement).value).toBe(
      "80",
    );
    expect((screen.getByLabelText("가중치 2") as HTMLInputElement).value).toBe(
      "20",
    );
  });

  it("keeps only the qualification and weight editable", async () => {
    const api = createApi();
    await advanceToEvaluation(api);

    const addEvaluationItem = screen.getByRole("button", {
      name: "자격요건 추가",
    });
    expect(addEvaluationItem.textContent).toContain("자격요건 추가");
    fireEvent.click(addEvaluationItem);
    expect(screen.queryByLabelText("평가 축 1")).toBeNull();
    const qualification = screen.getByLabelText("자격요건 1");
    fireEvent.change(qualification, {
      target: { value: "끝까지 파고드는 태도" },
    });
    qualification.focus();
    fireEvent.keyDown(qualification, { key: "Enter", code: "Enter" });
    expect(document.activeElement).not.toBe(qualification);
    expect(screen.getByText("어떤 기준으로 평가할까요?")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("가중치 1 직접 입력"), {
      target: { value: "35" },
    });

    expect(screen.getByText("가중치 합계").parentElement?.textContent).toBe(
      "가중치 합계100",
    );
    expect((screen.getByLabelText("가중치 1") as HTMLInputElement).value).toBe(
      "35",
    );
    expect((screen.getByLabelText("가중치 2") as HTMLInputElement).value).toBe(
      "65",
    );
  });
});
