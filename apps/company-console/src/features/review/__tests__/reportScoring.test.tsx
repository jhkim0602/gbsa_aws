/**
 * What a reviewer is allowed to read as a score.
 *
 * The backend refuses to invent a score it cannot trace to an answer; these tests pin
 * the other half of that promise, which is that the console does not undo it on the way
 * to the screen. A null axis rendered as "0점", or folded into an average, would tell a
 * reviewer the candidate failed a question the interview never asked.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportView } from "../ReportView";
import type {
  AxisAssessment,
  EvidenceRange,
  InterviewStageSummary,
  ReviewReport,
  ReviewReportItem,
} from "../types";

function axis(overrides: Partial<AxisAssessment> = {}): AxisAssessment {
  return {
    axis: "correctness",
    label: "정확성",
    score: 78,
    rationale: "재시도 폭주를 원인으로 정확히 짚었습니다.",
    quotedEvidenceIds: ["ev-1"],
    weight: null,
    ...overrides,
  };
}

function evidence(overrides: Partial<EvidenceRange> = {}): EvidenceRange {
  return {
    evidenceId: "ev-1",
    answerTurnId: "turn-1",
    transcriptSegmentId: "segment-1",
    startMs: 1000,
    endMs: 4000,
    observation: "재시도 폭주를 원인으로 지목했습니다.",
    rationale: "원인과 조치를 함께 설명해 정확성의 근거가 됩니다.",
    sufficiency: "direct",
    ...overrides,
  };
}

function item(overrides: Partial<ReviewReportItem> = {}): ReviewReportItem {
  return {
    reportItemId: "item-1",
    criterionId: "criterion-1",
    criterionName: "장애 대응 판단",
    assessmentState: "confirmed",
    observation: "큐 도입 근거를 설명했습니다.",
    followUpQuestion: null,
    averageScore: 78,
    axisAssessments: [axis()],
    evidence: [evidence()],
    // Equal weight, which is what a report generated before weights existed carries. The axis
    // averages then reduce to the plain mean these tests were written against.
    criterionWeight: 1,
    axisBreakdown: null,
    ...overrides,
  };
}

function report(overrides: Partial<ReviewReport> = {}): ReviewReport {
  return {
    summary: "면접 답변을 근거로 기준을 검토했습니다.",
    status: "ready",
    overallScore: 78,
    communicationScore: null,
    communicationScoredCriteriaCount: 0,
    unscoredCriteriaCount: 0,
    scoringBreakdown: null,
    items: [item()],
    requirementAssessments: [],
    ...overrides,
  };
}

function renderReport(
  value: ReviewReport,
  stageSummary: InterviewStageSummary[] = [],
) {
  render(
    <ReportView
      report={value}
      stageSummary={stageSummary}
      onSelectEvidence={vi.fn()}
    />,
  );
}

describe("report scoring", () => {
  it("shows qualification fulfillment separately from interview scores", () => {
    renderReport(
      report({
        requirementAssessments: [
          {
            requirementAssessmentId: "requirement-assessment-1",
            jobRequirementId: "requirement-1",
            requirementType: "required",
            statement: "Java 기반 서비스 개발 경험",
            status: "unknown",
            rationale: "관련 근거를 찾지 못했습니다.",
            confidence: 0,
            evidence: [],
            humanOverride: null,
          },
        ],
      }),
    );

    fireEvent.click(screen.getByRole("tab", { name: "자격요건 충족도" }));

    expect(screen.getByText("Java 기반 서비스 개발 경험")).toBeTruthy();
    expect(screen.getByText("판단 불가")).toBeTruthy();
    expect(
      screen.getByText(/면접 역량 점수에는 더하거나 빼지 않으며/),
    ).toBeTruthy();
  });

  it("opens on 종합평가 and shows the score beside what it does not cover", () => {
    renderReport(
      report({
        overallScore: 82,
        unscoredCriteriaCount: 3,
        items: [item(), item({ reportItemId: "item-2", averageScore: null })],
      }),
    );

    expect(
      screen.getByRole("tab", { name: "종합평가", selected: true }),
    ).toBeTruthy();
    expect(screen.getByText("82")).toBeTruthy();
    // A reviewer reading 82 has to see that three criteria are not in it.
    expect(
      screen.getByText(/기준 3개는 인용할 답변이 없어/, { exact: false }),
    ).toBeTruthy();
  });

  it("shows communication separately from competency and lists interview stages", () => {
    renderReport(
      report({
        overallScore: 84,
        communicationScore: 63,
        communicationScoredCriteriaCount: 2,
        items: [
          item({
            axisAssessments: [
              axis(),
              axis({
                axis: "communication",
                label: "설명력",
                score: 63,
              }),
            ],
          }),
        ],
      }),
      [
        {
          stage: "technical",
          label: "기술 면접",
          questionCount: 4,
          evidenceCount: 3,
        },
        {
          stage: "project_deep_dive",
          label: "프로젝트 심층",
          questionCount: 5,
          evidenceCount: 4,
        },
        {
          stage: "behavioral",
          label: "협업·인성",
          questionCount: 3,
          evidenceCount: 2,
        },
      ],
    );

    expect(screen.getByText("직무 역량")).toBeTruthy();
    expect(screen.getAllByText("설명력").length).toBeGreaterThan(0);
    expect(screen.getByText("84")).toBeTruthy();
    expect(screen.getByText("63")).toBeTruthy();
    expect(screen.getByText("기준 2개에서 판단")).toBeTruthy();
    expect(screen.getByText("질문 5개 · 평가 근거 4개")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "기준별 평가" }));
    expect(screen.getByText("별도 집계")).toBeTruthy();
  });

  it("says a null score is unjudged rather than showing a zero", () => {
    renderReport(
      report({
        overallScore: null,
        unscoredCriteriaCount: 1,
        items: [
          item({
            averageScore: null,
            axisAssessments: [
              axis({
                score: null,
                rationale: "CS 기본기를 확인할 질문이 없었습니다.",
                quotedEvidenceIds: [],
              }),
            ],
          }),
        ],
      }),
    );

    expect(screen.getByText("점수화된 기준 없음")).toBeTruthy();
    expect(screen.getAllByText("판단 근거 없음").length).toBeGreaterThan(0);
    expect(screen.queryByText("0점")).toBeNull();
  });

  it("averages an axis over the criteria that could be judged, not all of them", () => {
    renderReport(
      report({
        items: [
          item({
            axisAssessments: [axis({ score: 80 })],
          }),
          item({
            reportItemId: "item-2",
            axisAssessments: [axis({ score: null, quotedEvidenceIds: [] })],
          }),
        ],
      }),
    );

    // Counting the unjudged criterion as zero would print 40.
    expect(screen.getAllByText("80점").length).toBeGreaterThan(0);
    expect(screen.getByText("기준 1개에서 판단")).toBeTruthy();
  });

  it("shows each axis rationale so a reviewer can overrule the number", () => {
    renderReport(report());

    fireEvent.click(screen.getByRole("tab", { name: "기준별 평가" }));

    expect(
      screen.getByText("재시도 폭주를 원인으로 정확히 짚었습니다."),
    ).toBeTruthy();
    expect(screen.getByText("인용한 답변 1건")).toBeTruthy();
  });

  it("tells the reviewer when a score was withheld because its citation failed", () => {
    renderReport(
      report({
        overallScore: null,
        unscoredCriteriaCount: 1,
        items: [
          item({
            averageScore: null,
            axisAssessments: [
              axis({
                score: null,
                rationale: "인용한 답변을 확인할 수 없어 점수를 보류했습니다.",
                quotedEvidenceIds: [],
              }),
            ],
          }),
        ],
      }),
    );

    fireEvent.click(screen.getByRole("tab", { name: "기준별 평가" }));

    expect(
      screen.getByText("인용한 답변을 확인할 수 없어 점수를 보류했습니다."),
    ).toBeTruthy();
  });

  it("collects the follow-up questions a human should ask", () => {
    renderReport(
      report({
        items: [
          item({
            followUpQuestion: "큐 지연을 어떻게 측정했는지 확인해 주세요.",
          }),
        ],
      }),
    );

    fireEvent.click(screen.getByRole("tab", { name: "추가 확인" }));

    expect(
      screen.getByText("큐 지연을 어떻게 측정했는지 확인해 주세요."),
    ).toBeTruthy();
  });

  it("reads a report generated before scoring existed", () => {
    renderReport(
      report({
        overallScore: null,
        unscoredCriteriaCount: 1,
        items: [item({ averageScore: null, axisAssessments: [] })],
      }),
    );

    expect(screen.getByText(/이 리포트에는 축별 점수가 없습니다/)).toBeTruthy();
    expect(screen.queryByText("0점")).toBeNull();
  });

  it("never states a hiring verdict on the score", () => {
    renderReport(report({ overallScore: 91 }));

    const sheet = screen.getByRole("tabpanel");
    expect(sheet.textContent).toContain("합격 여부를 판단한 점수가 아닙니다");
    for (const verdict of ["합격", "불합격", "탈락", "채용 추천"]) {
      expect(sheet.textContent).not.toContain(`${verdict}입니다`);
    }
  });

  it("moves between sheets with the arrow keys", () => {
    renderReport(report());

    const overview = screen.getByRole("tab", { name: "종합평가" });
    overview.focus();
    fireEvent.keyDown(overview, { key: "ArrowRight" });

    expect(
      screen.getByRole("tab", { name: "기준별 평가", selected: true }),
    ).toBeTruthy();
  });

  it("renders the divisor, not only the score", () => {
    // The whole reason the breakdown travels. "74" cannot say that a quarter of the interview
    // is missing from it; "55.7 ÷ 0.75" can, and a reviewer can redo the arithmetic by hand.
    renderReport(
      report({
        overallScore: 74,
        unscoredCriteriaCount: 1,
        scoringBreakdown: {
          numerator: 55.7,
          denominator: 0.75,
          contributions: [
            {
              key: "criterion-1",
              score: 85,
              weight: 30,
              normalizedWeight: 0.3,
              contribution: 25.5,
              criterionName: "시스템 설계",
              assessmentState: "confirmed",
              reason: null,
            },
          ],
          exclusions: [],
        },
      }),
    );

    const sheet = screen.getByRole("tabpanel");
    expect(sheet.textContent).toContain("합 55.7 ÷ 0.75");
    expect(sheet.textContent).toContain("가중치 75%만 반영");
    expect(screen.getByText("시스템 설계")).toBeTruthy();
    expect(screen.getByText("30%")).toBeTruthy();
    expect(screen.getByText("25.5")).toBeTruthy();
  });

  it("names every excluded criterion with the reason it was excluded", () => {
    // Without the reason, "기준 D (25%)" tells a reviewer a quarter of the interview is missing
    // from the number but not why, and the divisor appears from nowhere.
    renderReport(
      report({
        overallScore: 80,
        unscoredCriteriaCount: 1,
        scoringBreakdown: {
          numerator: 60,
          denominator: 0.75,
          contributions: [
            {
              key: "criterion-1",
              score: 80,
              weight: 75,
              normalizedWeight: 0.75,
              contribution: 60,
              criterionName: "장애 대응 판단",
              assessmentState: "confirmed",
              reason: null,
            },
          ],
          exclusions: [
            {
              key: "criterion-2",
              weight: 25,
              normalizedWeight: 0.25,
              criterionName: "협업 경험",
              assessmentState: "insufficient_evidence",
              reason: "이 기준을 확인할 답변이 면접에서 나오지 않았음",
            },
          ],
        },
      }),
    );

    const sheet = screen.getByRole("tabpanel");
    expect(sheet.textContent).toContain("점수에서 제외된 기준");
    expect(sheet.textContent).toContain(
      "협업 경험 — 이 기준을 확인할 답변이 면접에서 나오지 않았음",
    );
  });

  it("shows no calculator at all on a report generated before the arithmetic was recorded", () => {
    // An empty calculator reading "0 ÷ 0" would look like a finding. Saying nothing is accurate.
    renderReport(report({ scoringBreakdown: null }));

    expect(screen.queryByText("이 점수가 나온 계산")).toBeNull();
    expect(screen.getByRole("tabpanel").textContent).toContain("기준 1개 평균");
  });

  it("weights the axis averages by criterion so they agree with the report score", () => {
    // An unweighted axis average beside a weighted report score would leave a reviewer with two
    // numbers and no way to tell which one the company's configuration produced.
    renderReport(
      report({
        items: [
          item({
            criterionWeight: 90,
            axisAssessments: [axis({ score: 90 })],
          }),
          item({
            reportItemId: "item-2",
            criterionWeight: 10,
            axisAssessments: [axis({ score: 10 })],
          }),
        ],
      }),
    );

    // 0.9*90 + 0.1*10 = 82. A plain mean would have printed 50.
    expect(screen.getAllByText("82점").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("img", {
        name: /면접 점수 레이더 그래프/,
      }),
    ).toBeTruthy();
  });
});
