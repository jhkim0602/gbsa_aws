import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../../features/interview/InterviewSession", () => ({
  InterviewSession: ({
    onComplete,
    equipmentCheckId,
  }: {
    onComplete(): void;
    equipmentCheckId?: string;
  }) => (
    <>
      <span data-testid="equipment-check-id">{equipmentCheckId ?? ""}</span>
      <button type="button" onClick={onComplete}>
        자동 면접 완료
      </button>
    </>
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

    // Two calls, not three: the equipment check and the session. `start` writes the session id
    // into the query string, but a session started here must not be re-fetched through recovery.
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    fireEvent.click(
      await screen.findByRole("button", { name: "자동 면접 완료" }),
    );

    await waitFor(() =>
      expect(
        screen.getByLabelText("면접 완료").getAttribute("aria-current"),
      ).toBe("step"),
    );
  });

  it("keeps the equipment check id after start writes the session id into the query", async () => {
    // Without this the socket never sends `session.start`, because the client only sends it when
    // it holds an equipment check id, and the session sits in `preparing` with no first question.
    const strategyId = "00000000-0000-7000-8000-000000000711";
    const equipmentCheckId = "00000000-0000-7000-8000-000000000712";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ equipment_check_id: equipmentCheckId }), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            interview_session_id: "00000000-0000-7000-8000-000000000713",
            websocket_path:
              "/v1/applicant/interview-sessions/00000000-0000-7000-8000-000000000713/stream",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValue(
        new Response(JSON.stringify({ state: "preparing" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter
        initialEntries={[`/interview?strategyId=${strategyId}&auto=fast`]}
      >
        <ApplicantRoutes />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("equipment-check-id").textContent).toBe(
        equipmentCheckId,
      ),
    );
    expect(
      fetchMock.mock.calls.filter((call) =>
        String(call[0]).endsWith("/resume"),
      ),
    ).toHaveLength(0);
  });

  it("still recovers a session named only by the query string", async () => {
    // The reload path that `fix: recover automated interview sessions` added: nothing started the
    // session in this mount, so recovery must run and the equipment check id is genuinely unknown.
    const sessionId = "00000000-0000-7000-8000-000000000721";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ state: "awaiting_answer" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter
        initialEntries={[
          `/interview?strategyId=00000000-0000-7000-8000-000000000722&sessionId=${sessionId}`,
        ]}
      >
        <ApplicantRoutes />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "자동 면접 완료" }),
      ).toBeTruthy(),
    );
    expect(
      fetchMock.mock.calls.filter((call) =>
        String(call[0]).endsWith(`/${sessionId}/resume`),
      ),
    ).toHaveLength(1);
    expect(screen.getByTestId("equipment-check-id").textContent).toBe("");
  });
});
