/**
 * A reviewer must be able to reach the answer behind any number, from one screen.
 *
 * The backend refuses to store a score whose citations do not resolve, but a console that
 * renders those citations as a bare count throws that guarantee away: a reviewer told
 * "인용한 답변 2건" cannot check either one. These tests pin the chain the report is for --
 * axis score -> which answer -> what was said -> where in the video -- plus the two ways
 * it can be honestly incomplete: an answer missing from the transcript, and a citation the
 * Evidence rows no longer carry.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { buildEvidenceContext } from "../evidenceContext";
import { ReportView } from "../ReportView";
import { ReviewWorkspace } from "../ReviewWorkspace";
import type {
  EvidenceRange,
  ReviewApi,
  ReviewReport,
  ReviewTimelineEntry,
} from "../types";

const api: ReviewApi = {
  overrideAssessment: vi.fn().mockResolvedValue(undefined),
  addBookmark: vi.fn().mockResolvedValue(undefined),
  recordFinalDecision: vi.fn().mockResolvedValue(undefined),
  requestDeletion: vi.fn().mockResolvedValue(undefined),
};

const DIRECT_EVIDENCE: EvidenceRange = {
  evidenceId: "ev-1",
  answerTurnId: "turn-2",
  transcriptSegmentId: "segment-answer-1",
  startMs: 62_000,
  endMs: 68_000,
  observation: "재시도 폭주를 원인으로 지목했습니다.",
  rationale: "원인 추정과 확인 방법을 함께 말해 정확성의 직접 근거가 됩니다.",
  sufficiency: "direct",
};

const SUPPORTING_EVIDENCE: EvidenceRange = {
  evidenceId: "ev-2",
  answerTurnId: "turn-4",
  transcriptSegmentId: "segment-answer-2",
  startMs: 121_000,
  endMs: 129_000,
  observation: "지표를 보고 롤백을 결정했다고 말했습니다.",
  rationale: "판단 근거는 있으나 수치가 없어 보조 근거로만 봤습니다.",
  sufficiency: "supporting",
};

function report(overrides: Partial<ReviewReport> = {}): ReviewReport {
  return {
    summary: "지원자는 장애 원인을 좁힌 과정을 설명했습니다.",
    status: "ready",
    overallScore: 74,
    unscoredCriteriaCount: 0,
    items: [
      {
        reportItemId: "item-1",
        criterionId: "criterion-1",
        criterionName: "운영 문제 해결",
        assessmentState: "confirmed",
        observation: "원인 분석과 복구 판단을 모두 설명했습니다.",
        followUpQuestion: null,
        averageScore: 74,
        axisAssessments: [
          {
            axis: "correctness",
            label: "정확성",
            score: 78,
            rationale: "재시도 폭주를 원인으로 정확히 짚었습니다.",
            quotedEvidenceIds: ["ev-1"],
          },
          {
            axis: "ownership",
            label: "본인 기여",
            score: 70,
            rationale: "본인이 직접 롤백을 결정했다고 설명했습니다.",
            quotedEvidenceIds: ["ev-1", "ev-2"],
          },
        ],
        evidence: [DIRECT_EVIDENCE, SUPPORTING_EVIDENCE],
      },
    ],
    ...overrides,
  };
}

const TIMELINE: ReviewTimelineEntry[] = [
  {
    entryId: "segment-question-1",
    type: "question",
    startMs: 55_000,
    endMs: 60_000,
    text: "ECS 장애의 원인을 어떻게 좁혔나요?",
    questionRationale: {
      criterionId: "criterion-1",
      verificationTargetType: "detail_missing",
      objective: "이력서에 없는 장애 대응 과정을 확인",
      questionType: "planned",
      policyResult: "accepted",
      sourceReferences: [
        {
          sourceId: "source-1",
          sourceType: "submission_chunk",
          locator: { page_number: 2 },
          excerpt: "ECS 배포 경험은 있으나 장애 대응 설명은 없습니다.",
        },
      ],
    },
  },
  {
    entryId: "segment-answer-1",
    type: "answer",
    startMs: 62_000,
    endMs: 68_000,
    text: "재시도가 폭주해 커넥션이 마른 것을 대시보드에서 먼저 확인했습니다.",
  },
  {
    entryId: "segment-question-2",
    type: "question",
    startMs: 115_000,
    endMs: 120_000,
    text: "롤백은 누가 결정했나요?",
    questionRationale: {
      criterionId: "criterion-1",
      verificationTargetType: "ownership_uncertain",
      objective: "복구 결정의 본인 기여를 확인",
      questionType: "follow_up",
      policyResult: "accepted",
      // Repeats source-1: a follow-up on the same criterion re-reads the same chunk.
      sourceReferences: [
        {
          sourceId: "source-1",
          sourceType: "submission_chunk",
          locator: { page_number: 2 },
          excerpt: "ECS 배포 경험은 있으나 장애 대응 설명은 없습니다.",
        },
        {
          sourceId: "source-2",
          sourceType: "candidate_code_unit",
          locator: { path: "deploy/rollback.sh", symbol: "rollback" },
          excerpt: "롤백 스크립트를 직접 작성한 커밋입니다.",
        },
      ],
    },
  },
  {
    entryId: "segment-answer-2",
    type: "answer",
    startMs: 121_000,
    endMs: 129_000,
    text: "제가 지표를 보고 롤백을 결정했고 팀에 공유했습니다.",
  },
];

function renderReport(value: ReviewReport, entries = TIMELINE) {
  const onSelectEvidence = vi.fn();
  render(
    <ReportView
      report={value}
      evidenceContext={buildEvidenceContext(entries)}
      onSelectEvidence={onSelectEvidence}
    />,
  );
  fireEvent.click(screen.getByRole("tab", { name: "기준별 평가" }));
  return { onSelectEvidence };
}

describe("evidence traceability", () => {
  it("shows what the AI read into each quoted answer, not just its timestamps", () => {
    renderReport(report());

    expect(
      screen.getByText("재시도 폭주를 원인으로 지목했습니다."),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "원인 추정과 확인 방법을 함께 말해 정확성의 직접 근거가 됩니다.",
      ),
    ).toBeTruthy();
    // How far the citation carries the criterion, in the reviewer's words.
    expect(screen.getByText("직접 근거")).toBeTruthy();
    expect(screen.getByText("보조 근거")).toBeTruthy();
  });

  it("resolves a citation to the applicant's own words from the transcript", () => {
    renderReport(report());

    expect(
      screen.getByText(
        "재시도가 폭주해 커넥션이 마른 것을 대시보드에서 먼저 확인했습니다.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText("제가 지표를 보고 롤백을 결정했고 팀에 공유했습니다."),
    ).toBeTruthy();
  });

  it("makes an axis score reach its own evidence instead of stating a count", () => {
    const { onSelectEvidence } = renderReport(report());

    // 본인 기여 rests on two answers, so it offers two ways in -- not "2건".
    fireEvent.click(
      screen.getByRole("button", { name: "본인 기여 근거 2 답변 보기" }),
    );

    expect(onSelectEvidence).toHaveBeenCalledWith(SUPPORTING_EVIDENCE.startMs);
  });

  it("marks the answer a reviewer followed so the citation is not matched by eye", () => {
    renderReport(report());

    const card = screen
      .getByText(SUPPORTING_EVIDENCE.observation)
      .closest("article");
    expect(card?.getAttribute("aria-current")).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: "본인 기여 근거 2 답변 보기" }),
    );

    expect(
      screen
        .getByText(SUPPORTING_EVIDENCE.observation)
        .closest("article")
        ?.getAttribute("aria-current"),
    ).toBe("true");
    // The answer the reviewer did not follow stays unmarked.
    expect(
      screen
        .getByText(DIRECT_EVIDENCE.observation)
        .closest("article")
        ?.getAttribute("aria-current"),
    ).toBeNull();
  });

  it("says so when a citation cannot be resolved rather than showing one fewer", () => {
    renderReport(
      report({
        items: [
          {
            ...report().items[0]!,
            axisAssessments: [
              {
                axis: "correctness",
                label: "정확성",
                score: 78,
                rationale: "재시도 폭주를 원인으로 정확히 짚었습니다.",
                quotedEvidenceIds: ["ev-1", "ev-missing"],
              },
            ],
          },
        ],
      }),
    );

    expect(screen.getByText("인용한 답변 2건")).toBeTruthy();
    expect(screen.getByText("근거 2 · 확인 불가")).toBeTruthy();
  });

  it("says so when the quoted answer is missing from the transcript", () => {
    renderReport(report(), [
      TIMELINE[0]!,
      TIMELINE[2]!,
      // Both answer segments withheld, as a partially processed transcript would.
    ]);

    expect(
      screen.getAllByText(/이 구간의 답변 전문이 타임라인에 없습니다/).length,
    ).toBe(2);
  });

  it("shows the submitted material a criterion's questions came from, once each", () => {
    renderReport(report());

    const sources = screen.getByText("질문 근거 자료").closest("details")!;
    expect(within(sources).getByText("2개")).toBeTruthy();
    expect(
      within(sources).getByText(
        "지원자 답변이 아니라 AI가 질문을 만들 때 참고한 제출 자료입니다.",
      ),
    ).toBeTruthy();
    // source-1 was cited by both questions; it is one piece of submitted material.
    expect(
      within(sources).getAllByText(
        "ECS 배포 경험은 있으나 장애 대응 설명은 없습니다.",
      ).length,
    ).toBe(1);
    expect(within(sources).getByText("Git 코드")).toBeTruthy();
    expect(
      within(sources).getByText("deploy/rollback.sh · rollback"),
    ).toBeTruthy();
  });

  it("resolves citations against the timeline the workspace already loaded", () => {
    const play = vi
      .spyOn(HTMLMediaElement.prototype, "play")
      .mockResolvedValue(undefined);

    render(
      <ReviewWorkspace
        api={api}
        invitationId="invitation-1"
        sessionId="session-12345678"
        report={report()}
        timeline={{
          entries: TIMELINE,
          playback: {
            status: "ready",
            url: "https://media.example.test/interview.m3u8",
          },
        }}
        deletion={{
          status: "not_requested",
          verifiedTargets: 0,
          expectedTargets: 0,
        }}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "기준별 평가" }));

    // Scoped to the report: the timeline renders the same sentence one panel over, so an
    // unscoped query would pass even with the report reading no transcript at all.
    const reportPanel = screen.getByLabelText("AI 리포트");
    expect(
      within(reportPanel).getByText(
        "재시도가 폭주해 커넥션이 마른 것을 대시보드에서 먼저 확인했습니다.",
      ),
    ).toBeTruthy();
    expect(within(reportPanel).getByText("질문 근거 자료")).toBeTruthy();
    expect(play).not.toHaveBeenCalled();
  });

  it("seeks the interview video when a reviewer follows a citation", () => {
    const play = vi
      .spyOn(HTMLMediaElement.prototype, "play")
      .mockResolvedValue(undefined);

    render(
      <ReviewWorkspace
        api={api}
        invitationId="invitation-1"
        sessionId="session-12345678"
        report={report()}
        timeline={{
          entries: TIMELINE,
          playback: {
            status: "ready",
            url: "https://media.example.test/interview.m3u8",
          },
        }}
        deletion={{
          status: "not_requested",
          verifiedTargets: 0,
          expectedTargets: 0,
        }}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "기준별 평가" }));
    fireEvent.click(
      screen.getByRole("button", { name: "본인 기여 근거 2 답변 보기" }),
    );

    expect(document.querySelector("video")?.currentTime).toBe(121);
    expect(play).toHaveBeenCalled();
  });
});
