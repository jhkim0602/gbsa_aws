import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  HumanReview,
  ReportView,
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
    fireEvent.click(screen.getByRole("button", { name: "Evidence 재생" }));
    expect(seek).toHaveBeenCalledWith(1200);
    expect(screen.getByText("캐시와 큐를 비교했습니다.")).toBeTruthy();
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
  });
});
