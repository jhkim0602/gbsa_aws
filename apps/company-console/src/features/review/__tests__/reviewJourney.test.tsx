import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  HumanReview,
  ReportView,
  ReviewWorkspace,
  summarizeInterviewStages,
  TimelineView,
  type ReviewApi,
} from "../index";

const api: ReviewApi = {
  overrideAssessment: vi.fn().mockResolvedValue(undefined),
  addBookmark: vi.fn().mockResolvedValue(undefined),
  recordFinalDecision: vi.fn().mockResolvedValue(undefined),
  requestDeletion: vi.fn().mockResolvedValue(undefined),
};

describe("Lane D review journey", () => {
  it("shows immutable AI results and seeks Evidence on the timeline", () => {
    const seek = vi.fn();
    render(
      <>
        <ReportView
          report={{
            summary: "지원자는 장애 대응 대안을 비교했습니다.",
            status: "ready",
            overallScore: 74,
            unscoredCriteriaCount: 0,
            items: [
              {
                reportItemId: "item-1",
                criterionId: "criterion-1",
                criterionName: "문제 해결",
                assessmentState: "confirmed",
                observation: "대안을 비교함",
                followUpQuestion: null,
                averageScore: 74,
                axisAssessments: [
                  {
                    axis: "correctness",
                    label: "정확성",
                    score: 74,
                    rationale: "재시도 폭주를 원인으로 정확히 짚었습니다.",
                    quotedEvidenceIds: ["ev-1"],
                  },
                ],
                evidence: [
                  {
                    evidenceId: "ev-1",
                    answerTurnId: "turn-1",
                    transcriptSegmentId: "segment-1",
                    startMs: 1200,
                    endMs: 3200,
                    observation: "두 선택지의 트레이드오프를 짚었습니다.",
                    rationale: "선택지를 버린 이유까지 설명했습니다.",
                    sufficiency: "direct",
                  },
                ],
              },
            ],
          }}
          onSelectEvidence={seek}
        />
        <TimelineView
          entries={[
            {
              entryId: "segment-question",
              type: "question",
              startMs: 200,
              endMs: 1000,
              text: "ECS 장애의 원인을 어떻게 좁혔나요?",
              questionRationale: {
                criterionId: "criterion-1",
                interviewStage: "project_deep_dive",
                verificationTargetType: "detail_missing",
                objective: "자료에서 확인되지 않은 원인 분석과 복구 역할 확인",
                questionType: "follow_up",
                policyResult: "accepted",
                sourceReferences: [
                  {
                    sourceId: "source-1",
                    sourceType: "submission_chunk",
                    locator: { page_number: 2 },
                    excerpt:
                      "ECS 배포 경험은 있으나 장애 대응 설명은 없습니다.",
                  },
                ],
              },
            },
            {
              entryId: "segment-1",
              type: "answer",
              startMs: 1200,
              endMs: 3200,
              text: "캐시와 큐를 비교했습니다.",
            },
          ]}
          playbackStatus="ready"
          onSeek={seek}
        />
      </>,
    );

    expect(screen.getByText("AI 원본 · 변경 불가")).toBeTruthy();
    expect(screen.getByLabelText("AI 리포트")).toBeTruthy();
    // 종합평가 opens first: it counts the states and lists them per criterion, so the
    // badge appears once in each. Evidence playback lives one tab over.
    expect(screen.getAllByText("확인됨").length).toBe(2);
    fireEvent.click(screen.getByRole("tab", { name: "기준별 평가" }));
    fireEvent.click(screen.getByRole("button", { name: "Evidence 재생" }));
    expect(seek).toHaveBeenCalledWith(1200);
    expect(screen.getByText("캐시와 큐를 비교했습니다.")).toBeTruthy();
    expect(screen.getByPlaceholderText("자막 내용 검색")).toBeTruthy();
    fireEvent.click(screen.getByText("질문 근거"));
    expect(
      screen.getByText("자료에서 확인되지 않은 원인 분석과 복구 역할 확인"),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "지원자 답변 Evidence가 아닌 질문 생성 참고 자료입니다.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText("ECS 배포 경험은 있으나 장애 대응 설명은 없습니다."),
    ).toBeTruthy();
    expect(screen.getAllByText("프로젝트 심층").length).toBeGreaterThan(0);
  });

  it("summarizes question counts in the fixed interview stage order", () => {
    const stages = summarizeInterviewStages([
      {
        entryId: "question-1",
        type: "question",
        startMs: 0,
        endMs: 1000,
        text: "기술 질문",
        questionRationale: {
          criterionId: "criterion-1",
          interviewStage: "technical",
          verificationTargetType: "detail_missing",
          objective: "기술 판단 확인",
          questionType: "adaptive",
          policyResult: "accepted",
          sourceReferences: [],
        },
      },
      {
        entryId: "question-2",
        type: "question",
        startMs: 2000,
        endMs: 3000,
        text: "협업 질문",
        questionRationale: {
          criterionId: "criterion-1",
          interviewStage: "behavioral",
          verificationTargetType: "detail_missing",
          objective: "협업 방식 확인",
          questionType: "stage_opening",
          policyResult: "accepted",
          sourceReferences: [],
        },
      },
    ]);

    expect(stages.map((stage) => [stage.label, stage.questionCount])).toEqual([
      ["기술 면접", 1],
      ["프로젝트 심층", 0],
      ["협업·인성", 1],
    ]);
  });

  it("records a human decision and exposes deletion residue", async () => {
    render(
      <HumanReview
        api={api}
        invitationId="invitation-1"
        deletion={{
          status: "retrying",
          verifiedTargets: 3,
          expectedTargets: 4,
        }}
      />,
    );
    fireEvent.change(screen.getByLabelText("최종 결정 사유"), {
      target: { value: "사람 검토 결과 다음 단계 진행" },
    });
    fireEvent.click(screen.getByRole("button", { name: "진행 결정" }));
    expect(await screen.findByText("사람 결정이 기록되었습니다.")).toBeTruthy();
    expect(api.recordFinalDecision).toHaveBeenCalled();
    expect(screen.getByText("삭제 확인 3/4")).toBeTruthy();
    expect(screen.getByRole("progressbar")).toBeTruthy();
  });

  it("keeps Evidence selection synchronized with the media timeline", () => {
    const play = vi
      .spyOn(HTMLMediaElement.prototype, "play")
      .mockResolvedValue(undefined);

    render(
      <ReviewWorkspace
        api={api}
        invitationId="invitation-1"
        sessionId="session-12345678"
        report={{
          summary: "지원자는 장애 대응 선택지를 비교했습니다.",
          status: "ready",
          overallScore: 71,
          unscoredCriteriaCount: 0,
          items: [
            {
              reportItemId: "item-1",
              criterionId: "criterion-1",
              criterionName: "문제 해결",
              assessmentState: "confirmed",
              observation: "선택지를 비교한 근거가 확인됩니다.",
              followUpQuestion: null,
              averageScore: 71,
              axisAssessments: [
                {
                  axis: "depth",
                  label: "깊이",
                  score: 71,
                  rationale: "대안을 버린 이유까지 설명했습니다.",
                  quotedEvidenceIds: ["ev-1"],
                },
              ],
              evidence: [
                {
                  evidenceId: "ev-1",
                  answerTurnId: "turn-1",
                  transcriptSegmentId: "segment-1",
                  startMs: 62_000,
                  endMs: 68_000,
                  observation: "두 선택지의 트레이드오프를 짚었습니다.",
                  rationale: "선택 기준을 스스로 설명했습니다.",
                  sufficiency: "direct",
                },
              ],
            },
          ],
        }}
        timeline={{
          entries: [
            {
              entryId: "segment-1",
              type: "answer",
              startMs: 62_000,
              endMs: 68_000,
              text: "캐시와 큐의 장단점을 비교했습니다.",
            },
          ],
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
    fireEvent.click(screen.getByRole("button", { name: "Evidence 재생" }));

    const video = document.querySelector("video");
    expect(video?.currentTime).toBe(62);
    expect(play).toHaveBeenCalled();
    expect(screen.getByText("세션 12345678")).toBeTruthy();

    const timelinePanel = screen
      .getByRole("heading", { name: "면접 타임라인" })
      .closest("section");
    const humanReviewPanel = screen
      .getByRole("heading", { name: "사람 검토" })
      .closest("section");
    expect(timelinePanel?.parentElement?.className).not.toContain("sticky");
    expect(humanReviewPanel?.parentElement?.className).toContain("sticky");

    const reportTabList = screen.getByRole("tablist", {
      name: "리포트 항목",
    });
    expect(
      within(reportTabList)
        .getAllByRole("tab")
        .map((tab) => tab.textContent),
    ).toEqual(["종합평가", "기준별 평가", "면접 타임라인", "추가 확인"]);
    expect(reportTabList.className).not.toContain("overflow-x-auto");

    fireEvent.click(screen.getByRole("tab", { name: "면접 타임라인" }));
    const expandedTimeline = screen.getByRole("tabpanel", {
      name: "면접 타임라인",
    });
    expect(within(expandedTimeline).queryByRole("video")).toBeNull();
    expect(
      within(expandedTimeline).getByText(
        "구간을 선택하면 왼쪽 면접 영상이 해당 시점으로 이동합니다.",
      ),
    ).toBeTruthy();
    const expandedAnswer = within(expandedTimeline)
      .getByText("캐시와 큐의 장단점을 비교했습니다.")
      .closest("button");
    expect(expandedAnswer).toBeTruthy();
    fireEvent.click(expandedAnswer!);
    expect(video?.currentTime).toBe(62);
    expect(
      within(expandedTimeline).getByPlaceholderText("자막 내용 검색"),
    ).toBeTruthy();
  });
});
