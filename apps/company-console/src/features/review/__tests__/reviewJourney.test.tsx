import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  HumanReview,
  ReportView,
  ReviewWorkspace,
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
            items: [
              {
                reportItemId: "item-1",
                criterionName: "문제 해결",
                assessmentState: "confirmed",
                observation: "대안을 비교함",
                evidence: [{ evidenceId: "ev-1", startMs: 1200, endMs: 3200 }],
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
    expect(screen.getByText("확인됨")).toBeTruthy();
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
          items: [
            {
              reportItemId: "item-1",
              criterionName: "문제 해결",
              assessmentState: "confirmed",
              observation: "캐시와 큐의 장단점을 비교했습니다.",
              evidence: [
                { evidenceId: "ev-1", startMs: 62_000, endMs: 68_000 },
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

    fireEvent.click(screen.getByRole("button", { name: "Evidence 재생" }));

    const video = document.querySelector("video");
    expect(video?.currentTime).toBe(62);
    expect(play).toHaveBeenCalled();
    expect(screen.getByText("세션 12345678")).toBeTruthy();
  });
});
