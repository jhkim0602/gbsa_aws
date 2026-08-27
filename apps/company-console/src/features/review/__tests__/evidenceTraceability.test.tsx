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
  addNote: vi.fn().mockResolvedValue(undefined),
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
    scoringBreakdown: null,
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
            weight: null,
          },
          {
            axis: "ownership",
            label: "본인 기여",
            score: 70,
            rationale: "본인이 직접 롤백을 결정했다고 설명했습니다.",
            quotedEvidenceIds: ["ev-1", "ev-2"],
            weight: null,
          },
        ],
        evidence: [DIRECT_EVIDENCE, SUPPORTING_EVIDENCE],
        criterionWeight: 1,
        axisBreakdown: null,
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
      interviewStage: "technical",
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
      interviewStage: "project_deep_dive",
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
  const onOverride = vi.fn();
  render(
    <ReportView
      report={value}
      evidenceContext={buildEvidenceContext(entries)}
      onSelectEvidence={onSelectEvidence}
      onOverride={onOverride}
    />,
  );
  fireEvent.click(screen.getByRole("tab", { name: "면접 답변 근거" }));
  return { onSelectEvidence, onOverride };
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
    expect(screen.getAllByText("기술").length).toBeGreaterThan(0);
    expect(screen.getAllByText("프로젝트").length).toBeGreaterThan(0);
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

  it("marks the answer a reviewer follows so the citation is not matched by eye", () => {
    const { onSelectEvidence } = renderReport(report());

    const card = screen
      .getByText(SUPPORTING_EVIDENCE.observation)
      .closest("article");
    expect(card?.getAttribute("aria-current")).toBeNull();

    fireEvent.click(
      screen.getAllByRole("button", { name: "Evidence 재생" })[1]!,
    );

    expect(onSelectEvidence).toHaveBeenCalledWith(SUPPORTING_EVIDENCE.startMs);
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
        recruitingState={null}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "면접 답변 근거" }));

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
        recruitingState={null}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "면접 답변 근거" }));
    fireEvent.click(
      screen.getAllByRole("button", { name: "Evidence 재생" })[1]!,
    );

    fireEvent.click(screen.getByRole("tab", { name: "면접 타임라인" }));
    expect(document.querySelector("video")?.currentTime).toBe(121);
    expect(play).toHaveBeenCalled();
  });
  it("records the reviewer's own reason when they overrule the AI, not a fixed string", () => {
    // The API always accepted a real reason; the console used to send
    // "기업 검토자가 평가 상태를 수정함" for every override, which records the fact and loses the
    // only part a later reader needs. Disagreement with a score is exactly where "why" matters.
    const { onOverride } = renderReport(report());

    fireEvent.change(screen.getByLabelText("사람 평가 1"), {
      target: { value: "needs_follow_up" },
    });
    fireEvent.change(screen.getByLabelText("수정 사유 1"), {
      target: { value: "인용된 답변이 복구 판단까지는 설명하지 않습니다." },
    });
    fireEvent.click(screen.getByRole("button", { name: "사람 평가 저장" }));

    expect(onOverride).toHaveBeenCalledWith(
      "item-1",
      "needs_follow_up",
      "인용된 답변이 복구 판단까지는 설명하지 않습니다.",
    );
  });

  it("will not submit an override without a reason", () => {
    const { onOverride } = renderReport(report());

    fireEvent.change(screen.getByLabelText("사람 평가 1"), {
      target: { value: "insufficient_evidence" },
    });

    const save = screen.getByRole("button", { name: "사람 평가 저장" });
    expect(save.hasAttribute("disabled")).toBe(true);
    fireEvent.click(save);
    expect(onOverride).not.toHaveBeenCalled();
  });
});
