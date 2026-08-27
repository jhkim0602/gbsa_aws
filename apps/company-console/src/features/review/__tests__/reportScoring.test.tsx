import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportView, RequirementRadarProfile } from "../ReportView";
import type {
  RequirementAssessment,
  RequirementAssessmentStatus,
  ReviewReport,
} from "../types";

function requirement(
  index: number,
  status: RequirementAssessmentStatus,
  requirementType: "required" | "preferred" = "required",
): RequirementAssessment {
  return {
    requirementAssessmentId: `assessment-${index}`,
    jobRequirementId: `requirement-${index}`,
    requirementType,
    statement: `${requirementType === "required" ? "필수" : "우대"} 자격요건 ${index}`,
    status,
    rationale: "제출 자료와 면접 답변을 함께 확인했습니다.",
    confidence: 0.9,
    evidence: [],
    humanOverride: null,
  };
}

function report(requirementAssessments: RequirementAssessment[]): ReviewReport {
  return {
    summary: "기업이 등록한 자격요건을 기준으로 검토했습니다.",
    status: "ready",
    overallScore: 12,
    communicationScore: null,
    communicationScoredCriteriaCount: 0,
    unscoredCriteriaCount: 0,
    scoringBreakdown: null,
    items: [],
    requirementAssessments,
  };
}

function renderReport(requirements: RequirementAssessment[]) {
  render(
    <ReportView
      report={report(requirements)}
      stageSummary={[]}
      onSelectEvidence={vi.fn()}
    />,
  );
}

describe("requirement-only report scoring", () => {
  it("uses only scorable qualification statuses for the overview score", () => {
    renderReport([
      requirement(1, "met"),
      requirement(2, "partially_met"),
      requirement(3, "unknown", "preferred"),
    ]);

    // (100 + 50) / 2 = 75. The legacy overallScore (12) and unknown item are ignored.
    expect(screen.getByText("75")).toBeTruthy();
    expect(screen.queryByText("12")).toBeNull();
    expect(screen.getByText("전체 3개 자격요건")).toBeTruthy();
    expect(
      screen.getByRole("img", {
        name: "기업이 설정한 자격요건 3개의 충족 점수 레이더 그래프",
      }),
    ).toBeTruthy();
  });

  it("shows the transparent 100, 50, 0 and unknown mapping", () => {
    renderReport([
      requirement(1, "met"),
      requirement(2, "partially_met"),
      requirement(3, "not_met", "preferred"),
      requirement(4, "unknown", "preferred"),
    ]);

    fireEvent.click(screen.getByRole("tab", { name: "자격요건 평가" }));

    expect(
      screen.getByText(/충족 100점·부분 충족 50점·미충족 0점/),
    ).toBeTruthy();
    expect(screen.getAllByText("100점").length).toBeGreaterThan(0);
    expect(screen.getAllByText("50점").length).toBeGreaterThan(0);
    expect(screen.getAllByText("0점").length).toBeGreaterThan(0);
    expect(screen.getAllByText("판단 근거 없음").length).toBeGreaterThan(0);
  });

  it("draws a dynamic polygon from every configured qualification", () => {
    render(
      <RequirementRadarProfile
        assessments={[
          requirement(1, "met"),
          requirement(2, "partially_met"),
          requirement(3, "not_met"),
          requirement(4, "met", "preferred"),
          requirement(5, "partially_met", "preferred"),
          requirement(6, "unknown", "preferred"),
        ]}
      />,
    );

    expect(
      screen.getByRole("img", {
        name: "기업이 설정한 자격요건 6개의 충족 점수 레이더 그래프",
      }),
    ).toBeTruthy();
    expect(screen.getAllByText("필수 1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("우대 3").length).toBeGreaterThan(0);
  });

  it("moves from the overview to answer evidence with the arrow key", () => {
    renderReport([requirement(1, "met")]);

    const overview = screen.getByRole("tab", { name: "종합평가" });
    overview.focus();
    fireEvent.keyDown(overview, { key: "ArrowRight" });

    expect(
      screen.getByRole("tab", { name: "면접 답변 근거", selected: true }),
    ).toBeTruthy();
  });

  it("does not turn a qualification score into a hiring verdict", () => {
    renderReport([requirement(1, "met")]);

    const sheet = screen.getByRole("tabpanel");
    expect(sheet.textContent).toContain(
      "이 점수는 합격 여부가 아니며 최종 결정은 담당자가 기록합니다",
    );
    expect(sheet.textContent).not.toContain("합격입니다");
    expect(sheet.textContent).not.toContain("불합격입니다");
  });
});
