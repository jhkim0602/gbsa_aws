// Created: 2026-08-23 23:15
/**
 * Review writes must not report success the server did not give.
 *
 * The override call was fired without `await` and the confirmation rendered on the next line;
 * the decision buttons had no catch at all. Both reported success unconditionally, so a reviewer
 * who overruled a score or recorded a hire/no-hire was told it was saved either way and found the
 * judgement gone on re-opening the applicant. These cover the failure path, which had no test.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HumanReview, ReportView, type ReviewApi } from "../index";

class StubRequestError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(`company request failed: ${status}`);
  }
}

function api(overrides: Partial<ReviewApi> = {}): ReviewApi {
  return {
    overrideAssessment: vi.fn().mockResolvedValue(undefined),
    addNote: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

const RECRUITING_STATE = {
  invitationId: "invitation-1",
  positionId: "position-1",
  recruitingStageId: "stage-review",
  pipelineRowVersion: 2,
  stages: [
    { recruitingStageId: "stage-review", name: "검토", sortOrder: 0 },
    { recruitingStageId: "stage-pass", name: "1차 합격", sortOrder: 1 },
  ],
};

const REPORT = {
  summary: "지원자는 장애 대응 대안을 비교했습니다.",
  status: "ready" as const,
  overallScore: 74,
  unscoredCriteriaCount: 0,
  items: [
    {
      reportItemId: "item-1",
      criterionId: "criterion-1",
      criterionName: "문제 해결",
      assessmentState: "confirmed" as const,
      observation: "대안을 비교함",
      followUpQuestion: null,
      averageScore: 74,
      axisAssessments: [],
      evidence: [],
    },
  ],
};

function renderOverride(onOverride: (...args: never[]) => Promise<void>) {
  const rendered = render(
    <ReportView
      report={REPORT}
      onSelectEvidence={vi.fn()}
      onOverride={onOverride as never}
    />,
  );
  // The override control lives on the per-criterion tab, not the summary the report opens on.
  fireEvent.click(screen.getByRole("tab", { name: "면접 답변 근거" }));
  return rendered;
}

async function submitOverride() {
  fireEvent.change(screen.getByLabelText("사람 평가 1"), {
    target: { value: "needs_follow_up" },
  });
  fireEvent.change(screen.getByLabelText("수정 사유 1"), {
    target: { value: "Evidence가 결론을 지지하지 않습니다" },
  });
  fireEvent.click(screen.getByRole("button", { name: "사람 평가 저장" }));
}

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("assessment override", () => {
  it("does not claim the override was recorded when the server rejects it", async () => {
    const rejected = vi
      .fn()
      .mockRejectedValue(
        new StubRequestError(422, "assessment state is not allowed"),
      );
    renderOverride(rejected);

    await submitOverride();

    expect(
      await screen.findByText(/사람 평가를 기록하지 못했습니다/),
    ).toBeTruthy();
    // The confirmation is the part that used to render regardless of the outcome.
    expect(screen.queryByText(/사람 평가를 기록했습니다/)).toBeNull();
  });

  it("surfaces the reason the server gave instead of a generic message", async () => {
    renderOverride(
      vi
        .fn()
        .mockRejectedValue(
          new StubRequestError(422, "assessment state is not allowed"),
        ),
    );

    await submitOverride();

    expect(
      await screen.findByText(/assessment state is not allowed/),
    ).toBeTruthy();
  });

  it("confirms only after the write resolves", async () => {
    let settle: (() => void) | undefined;
    const pending = vi.fn().mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          settle = resolve;
        }),
    );
    renderOverride(pending);

    await submitOverride();

    // Mid-flight: no confirmation yet, and the control says so.
    expect(screen.queryByText(/사람 평가를 기록했습니다/)).toBeNull();
    expect(screen.getByRole("button", { name: "저장 중…" })).toBeTruthy();

    settle?.();
    expect(await screen.findByText(/사람 평가를 기록했습니다/)).toBeTruthy();
  });

  it("submits once even if the button is clicked repeatedly mid-flight", async () => {
    const pending = vi
      .fn()
      .mockImplementation(() => new Promise<void>(() => undefined));
    renderOverride(pending);

    await submitOverride();
    fireEvent.click(screen.getByRole("button", { name: "저장 중…" }));
    fireEvent.click(screen.getByRole("button", { name: "저장 중…" }));

    expect(pending).toHaveBeenCalledTimes(1);
  });
});

describe("final decision", () => {
  function renderReview(reviewApi: ReviewApi) {
    render(
      <HumanReview
        api={reviewApi}
        invitationId="invitation-1"
        recruitingState={RECRUITING_STATE}
      />,
    );
    fireEvent.change(screen.getByLabelText("최종 결정 채용 단계"), {
      target: { value: "stage-pass" },
    });
  }

  it("reports a rejected decision instead of staying silent", async () => {
    const reviewApi = api({
      saveFinalDecisionStage: vi
        .fn()
        .mockRejectedValue(
          new StubRequestError(500, "decision store unavailable"),
        ),
    });
    renderReview(reviewApi);

    fireEvent.click(screen.getByRole("button", { name: "최종 결정 저장" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText("최종 결정을 저장했습니다.")).toBeNull();
  });

  it("records the decision once when the reviewer clicks several times", async () => {
    let settle: (() => void) | undefined;
    const saveFinalDecisionStage = vi.fn().mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          settle = resolve;
        }),
    );
    renderReview(api({ saveFinalDecisionStage }));

    const save = screen.getByRole("button", { name: "최종 결정 저장" });
    fireEvent.click(save);
    fireEvent.click(save);

    expect(saveFinalDecisionStage).toHaveBeenCalledTimes(1);
    settle?.();
    await waitFor(() =>
      expect(screen.getByText("최종 결정을 저장했습니다.")).toBeTruthy(),
    );
  });

  it("keeps the note when saving a note fails", async () => {
    const reviewApi = api({
      addNote: vi
        .fn()
        .mockRejectedValue(new StubRequestError(500, "unavailable")),
    });
    renderReview(reviewApi);
    const note = screen.getByLabelText("검토 메모");
    fireEvent.change(note, { target: { value: "면접관 두 명과 재확인 필요" } });

    fireEvent.click(screen.getByRole("button", { name: "메모 저장" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect((note as HTMLTextAreaElement).value).toBe(
      "면접관 두 명과 재확인 필요",
    );
  });
});

describe("simplified review panel", () => {
  it("does not render bookmarks, history, or deletion controls", () => {
    render(
      <HumanReview
        api={api()}
        invitationId="invitation-1"
        recruitingState={RECRUITING_STATE}
      />,
    );

    expect(screen.queryByText("검토 이력")).toBeNull();
    expect(screen.queryByText("북마크 저장")).toBeNull();
    expect(screen.queryByText(/삭제 확인/)).toBeNull();
  });
});
