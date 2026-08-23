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
    addBookmark: vi.fn().mockResolvedValue(undefined),
    recordFinalDecision: vi.fn().mockResolvedValue(undefined),
    requestDeletion: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

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
  fireEvent.click(screen.getByRole("tab", { name: "기준별 평가" }));
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
  }

  it("reports a rejected decision instead of staying silent", async () => {
    const reviewApi = api({
      recordFinalDecision: vi
        .fn()
        .mockRejectedValue(
          new StubRequestError(500, "decision store unavailable"),
        ),
    });
    renderReview(reviewApi);

    fireEvent.click(screen.getByRole("button", { name: "진행 결정" }));

    // Previously this produced no change at all -- no confirmation, no error.
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText("사람 결정이 기록되었습니다.")).toBeNull();
  });

  it("records the decision once when the reviewer clicks several times", async () => {
    let settle: (() => void) | undefined;
    const recordFinalDecision = vi.fn().mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          settle = resolve;
        }),
    );
    renderReview(api({ recordFinalDecision }));

    const advance = screen.getByRole("button", { name: "진행 결정" });
    fireEvent.click(advance);
    fireEvent.click(advance);
    fireEvent.click(screen.getByRole("button", { name: "불합격 결정" }));

    expect(recordFinalDecision).toHaveBeenCalledTimes(1);
    settle?.();
    await waitFor(() =>
      expect(screen.getByText("사람 결정이 기록되었습니다.")).toBeTruthy(),
    );
  });

  it("keeps the note when saving a bookmark fails", async () => {
    const reviewApi = api({
      addBookmark: vi
        .fn()
        .mockRejectedValue(new StubRequestError(500, "unavailable")),
    });
    renderReview(reviewApi);
    const note = screen.getByPlaceholderText("팀과 공유할 메모");
    fireEvent.change(note, { target: { value: "면접관 두 명과 재확인 필요" } });

    fireEvent.click(screen.getByRole("button", { name: "북마크 저장" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    // The bookmark write reported nothing at all before, success or failure.
    expect((note as HTMLInputElement).value).toBe("면접관 두 명과 재확인 필요");
  });
});

describe("review history", () => {
  it("lists the reviews already recorded instead of claiming there are none", () => {
    render(
      <HumanReview
        api={api()}
        invitationId="invitation-1"
        deletion={{
          status: "not_requested",
          verifiedTargets: 0,
          expectedTargets: 0,
        }}
        history={[
          {
            id: "review-1",
            type: "최종 결정",
            detail: "불합격",
            reason: "이미 채용 내정자가 존재하므로 채용 불가.",
            createdBy: "검토자 00000000",
            createdAt: "2026. 8. 23. 오후 11:20",
          },
          {
            id: "review-2",
            type: "검토 메모",
            detail: "면접관 두 명과 재확인 필요",
            createdBy: "검토자 00000000",
            createdAt: "2026. 8. 23. 오후 11:21",
          },
        ]}
      />,
    );

    expect(screen.queryByText("아직 기록된 검토 이력이 없습니다.")).toBeNull();
    // Scoped to the list: "검토 메모" is also the label of the note input above it.
    const entries = screen.getByRole("list");
    expect(entries.textContent).toContain("최종 결정");
    expect(entries.textContent).toContain("검토 메모");
    expect(entries.textContent).toContain("2026. 8. 23. 오후 11:20");
    // The point of the panel: which decision, and why. Listing only the type made it useless.
    expect(entries.textContent).toContain("불합격");
    expect(entries.textContent).toContain(
      "이미 채용 내정자가 존재하므로 채용 불가.",
    );
    expect(entries.textContent).toContain("면접관 두 명과 재확인 필요");
  });

  it("says so when nothing has been recorded yet", () => {
    render(
      <HumanReview
        api={api()}
        invitationId="invitation-1"
        deletion={{
          status: "not_requested",
          verifiedTargets: 0,
          expectedTargets: 0,
        }}
      />,
    );

    expect(screen.getByText("아직 기록된 검토 이력이 없습니다.")).toBeTruthy();
  });
});
