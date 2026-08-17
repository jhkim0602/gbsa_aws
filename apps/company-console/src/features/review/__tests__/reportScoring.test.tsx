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
    ...overrides,
  };
}

function report(overrides: Partial<ReviewReport> = {}): ReviewReport {
  return {
    summary: "면접 답변을 근거로 기준을 검토했습니다.",
    status: "ready",
    overallScore: 78,
    unscoredCriteriaCount: 0,
    items: [item()],
    ...overrides,
  };
}

function renderReport(value: ReviewReport) {
  render(<ReportView report={value} onSelectEvidence={vi.fn()} />);
}

describe("report scoring", () => {
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
    expect(screen.getByText("80점")).toBeTruthy();
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
});
