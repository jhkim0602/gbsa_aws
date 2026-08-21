import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../../features/interview/InterviewSession", () => ({
  InterviewSession: ({ onComplete }: { onComplete(): void }) => (
    <button type="button" onClick={onComplete}>
      자동 면접 완료
    </button>
  ),
}));

import { ApplicantRoutes } from "../App";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("automated interview completion", () => {
  it("returns the applicant to the interview completion screen", async () => {
    const strategyId = "00000000-0000-7000-8000-000000000701";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            equipment_check_id: "00000000-0000-7000-8000-000000000702",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            interview_session_id: "00000000-0000-7000-8000-000000000703",
            websocket_path:
              "/v1/applicant/interview-sessions/00000000-0000-7000-8000-000000000703/stream",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            overall_status: "ready",
            interview_ready: true,
            strategy_id: strategyId,
            submissions: [],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter
        initialEntries={[`/interview?strategyId=${strategyId}&auto=fast`]}
      >
        <ApplicantRoutes />
      </MemoryRouter>,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    fireEvent.click(
      await screen.findByRole("button", { name: "자동 면접 완료" }),
    );

    await waitFor(() =>
      expect(
        screen.getByLabelText("면접 완료").getAttribute("aria-current"),
      ).toBe("step"),
    );
  });
});
