/**
 * The review route must render criterion names, not raw UUIDs.
 *
 * The ReviewWorkspace component tests hand it an already-readable `criterionName`,
 * so they pass even when the adapter feeds the component a UUID. Only a test that
 * goes through `ReviewRoute` with a real API payload catches that.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReviewRoute } from "../routeAdapters";

const SESSION_ID = "00000000-0000-7000-8000-000000000001";
const INVITATION_ID = "00000000-0000-7000-8000-000000000002";
const REPORT_ID = "00000000-0000-7000-8000-000000000003";
const REPORT_ITEM_ID = "00000000-0000-7000-8000-000000000004";
const CRITERION_ID = "00000000-0000-7000-8000-000000000005";

function reportPayload(criterionName: string) {
  return {
    report_id: REPORT_ID,
    report_version: 1,
    status: "ready",
    summary: "최종 답변 Evidence에 기반한 AI 원본 리포트",
    ai_original_immutable: true,
    items: [
      {
        report_item_id: REPORT_ITEM_ID,
        criterion_id: CRITERION_ID,
        criterion_name: criterionName,
        assessment_state: "confirmed",
        observation: "장애 대응에서 큐 도입 근거를 설명함",
        rationale: "실제 최종 답변만 평가 근거로 사용",
        uncertainty: "AI 원본이며 사람 검토 필요",
        follow_up_question: null,
        evidence: [],
      },
    ],
    human_reviews: [],
  };
}

const TIMELINE_PAYLOAD = {
  entries: [],
  playback: { url: null, expires_at: null, status: "unavailable" },
};

function stubApi(criterionName: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.endsWith("/timeline")
        ? TIMELINE_PAYLOAD
        : reportPayload(criterionName);
      return Promise.resolve(
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }),
  );
}

function renderReview() {
  render(
    <MemoryRouter
      initialEntries={[`/review/${SESSION_ID}?invitationId=${INVITATION_ID}`]}
    >
      <Routes>
        <Route path="/review/:sessionId" element={<ReviewRoute />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ReviewRoute", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the criterion name the report captured", async () => {
    stubApi("장애 대응");
    renderReview();

    // The name is a row header on the 종합평가 sheet's criterion table.
    expect(
      await screen.findByRole("rowheader", { name: "장애 대응" }),
    ).toBeTruthy();
    expect(screen.queryByText(CRITERION_ID)).toBeNull();
  });

  it("falls back to the id for reports generated before names were captured", async () => {
    stubApi("");
    renderReview();

    expect(
      await screen.findByRole("rowheader", { name: CRITERION_ID }),
    ).toBeTruthy();
  });

  it("reads a report generated before scoring existed without inventing zeroes", async () => {
    // This payload has no overall_score, average_score or axis_assessments at all,
    // which is what every report written before the scoring migration looks like.
    stubApi("장애 대응");
    renderReview();

    await screen.findByRole("rowheader", { name: "장애 대응" });
    expect(screen.getByText("점수화된 기준 없음")).toBeTruthy();
    expect(screen.getAllByText("판단 근거 없음").length).toBeGreaterThan(0);
    expect(screen.queryByText("0점")).toBeNull();
  });
});
