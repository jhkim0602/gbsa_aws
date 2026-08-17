import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HiringWorkspace, type HiringWorkspaceApi } from "../index";

function createApi(): HiringWorkspaceApi {
  return {
    createPosition: vi.fn().mockResolvedValue({ positionId: "position-1" }),
    publishCriteria: vi.fn().mockResolvedValue({ versionId: "version-1" }),
  };
}

async function advanceToCriteria(api: HiringWorkspaceApi) {
  render(<HiringWorkspace api={api} />);
  fireEvent.change(screen.getByLabelText("포지션명"), {
    target: { value: "백엔드 플랫폼 엔지니어" },
  });
  fireEvent.change(screen.getByLabelText("채용 인원"), {
    target: { value: "2" },
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
  fireEvent.click(screen.getByRole("button", { name: "포지션 만들기" }));
  await screen.findByText("면접 기준 설정");
}

describe("HiringWorkspace", () => {
  it("publishes linked requirements and verification guides without interviewer controls", async () => {
    const api = createApi();
    await advanceToCriteria(api);

    expect(screen.queryByText("AI 면접관")).toBeNull();
    expect(screen.queryByLabelText("음성")).toBeNull();

    fireEvent.change(screen.getByLabelText("요구사항 1"), {
      target: { value: "ECS 운영 장애 대응 경험" },
    });
    fireEvent.change(screen.getByLabelText("평가기준 이름 1"), {
      target: { value: "운영 문제 해결" },
    });
    fireEvent.change(screen.getByLabelText("설명 1"), {
      target: { value: "장애 원인을 분석하고 복구하는 역량" },
    });
    fireEvent.change(screen.getByLabelText("확인할 요소 1"), {
      target: {
        value: "실제 장애 상황\n원인 분석\n직접 수행한 복구\n재발 방지",
      },
    });
    fireEvent.change(screen.getByLabelText("좋은 답변 신호 1"), {
      target: { value: "본인 행동과 판단 근거가 구체적임" },
    });
    fireEvent.change(screen.getByLabelText("추가 확인 신호 1"), {
      target: { value: "팀 활동이나 결과만 언급함" },
    });
    fireEvent.change(screen.getByLabelText("꼬리질문 방향 1"), {
      target: { value: "본인이 직접 수행한 행동\n복구 우선순위" },
    });
    fireEvent.change(screen.getByLabelText("공통 질문 1"), {
      target: { value: "운영 장애를 해결한 경험을 설명해 주세요." },
    });
    fireEvent.change(screen.getByLabelText("면접 난이도"), {
      target: { value: "senior" },
    });
    fireEvent.click(screen.getByRole("button", { name: "평가기준 게시" }));

    expect(await screen.findByText("채용 기준 게시 완료")).toBeTruthy();
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
          name: "운영 문제 해결",
          verificationGuide: {
            observableDimensions: [
              "실제 장애 상황",
              "원인 분석",
              "직접 수행한 복구",
              "재발 방지",
            ],
            strongAnswerSignals: ["본인 행동과 판단 근거가 구체적임"],
            weakAnswerSignals: ["팀 활동이나 결과만 언급함"],
            followUpDirections: ["본인이 직접 수행한 행동", "복구 우선순위"],
            maxFollowUps: 2,
            timeBudgetSeconds: 300,
          },
        }),
      ],
      prohibitedTopics: ["가족관계", "출신지역", "혼인·임신 여부", "외모"],
      interviewDurationMinutes: 30,
      interviewLevel: "senior",
    });
  });

  it("adds multiple criteria and keeps requirement links selectable", async () => {
    const api = createApi();
    await advanceToCriteria(api);

    fireEvent.click(screen.getByRole("button", { name: "평가기준 추가" }));
    expect(screen.getByLabelText("평가기준 이름 2")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "요구사항 추가" }));
    fireEvent.change(screen.getByLabelText("요구사항 2"), {
      target: { value: "대규모 API 설계 경험" },
    });
    fireEvent.change(screen.getByLabelText("연결 평가기준 2"), {
      target: { value: "CRITERION_2" },
    });

    expect(
      (screen.getByLabelText("연결 평가기준 2") as HTMLSelectElement).value,
    ).toBe("CRITERION_2");
    expect(screen.getByText("2개 평가기준")).toBeTruthy();
  });
});
