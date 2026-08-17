import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicantRoutes } from "../App";
import {
  createRecordingUploadApi,
  resolveWebSocketUrl,
  serializeEquipmentComponent,
} from "../routeAdapters";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("applicant feature routes", () => {
  it.each([
    ["/access/token-value", "지원자 면접", "초대 확인"],
    ["/submissions", "지원 자료 제출", "자료 제출"],
    ["/interview", "면접 환경 점검", "환경 점검"],
  ])(
    "renders %s through the applicant portal shell",
    (path, heading, currentStep) => {
      render(
        <MemoryRouter initialEntries={[path]}>
          <ApplicantRoutes />
        </MemoryRouter>,
      );

      expect(
        screen.getByRole("banner", { name: "제품 탐색" }).textContent,
      ).toContain("InterviewEP");
      expect(
        screen.getByRole("navigation", { name: "면접 진행 단계" }),
      ).toBeTruthy();
      expect(
        screen.getByLabelText(currentStep).getAttribute("aria-current"),
      ).toBe("step");
      expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
    },
  );

  it("links only to applicant steps backed by a real route", () => {
    render(
      <MemoryRouter initialEntries={["/access/token-value"]}>
        <ApplicantRoutes />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("link", { name: "자료 제출" }).getAttribute("href"),
    ).toBe("/submissions");
    expect(screen.queryByRole("link", { name: "면접 완료" })).toBeNull();
  });

  it.each([
    ["/interview/session", "AI 면접"],
    ["/interview/complete", "면접 완료"],
  ])("maps %s to the correct journey stage", (path, currentStep) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <ApplicantRoutes />
      </MemoryRouter>,
    );

    expect(
      screen.getByLabelText(currentStep).getAttribute("aria-current"),
    ).toBe("step");
  });

  it("serializes browser equipment results to the frozen HTTP contract", async () => {
    const serialized = serializeEquipmentComponent({
      status: "failed",
      sanitizedCode: "CAMERA_UNAVAILABLE",
    });

    expect(serialized).toEqual({
      status: "failed",
      sanitized_code: "CAMERA_UNAVAILABLE",
    });
    expect(serialized).not.toHaveProperty("sanitizedCode");
  });

  it("resolves the server websocket path and uploads recording chunks directly", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            upload_id: "00000000-0000-7000-8000-000000000601",
            method: "PUT",
            url: "https://uploads.local/chunk",
            required_headers: { "x-amz-checksum-sha256": "checksum" },
            expires_at: "2026-08-15T12:00:00Z",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            recording_chunk_id: "00000000-0000-7000-8000-000000000602",
            chunk_sequence: 3,
            upload_status: "verified",
            session_start_ms: 2000,
            session_end_ms: 4000,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    expect(
      resolveWebSocketUrl("/v1/applicant/interview-sessions/session-id/stream"),
    ).toMatch(/^ws:\/\/localhost/);
    await createRecordingUploadApi("session-id").upload({
      sessionId: "session-id",
      sequence: 3,
      blob: new Blob(["recording"]),
      byteSize: 9,
      sha256: "c".repeat(64),
      sessionStartMs: 2000,
      sessionEndMs: 4000,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining(
        "/v1/applicant/interview-sessions/session-id/media-upload-intents",
      ),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://uploads.local/chunk",
      expect.objectContaining({
        method: "PUT",
        headers: { "x-amz-checksum-sha256": "checksum" },
      }),
    );
    // The chunk is only recorded once the upload is confirmed, and the intent's own
    // idempotency key has to be reused so the confirmation names that same upload.
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      expect.stringContaining(
        "/v1/applicant/interview-sessions/session-id/media-uploads",
      ),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: expect.objectContaining({
          "Idempotency-Key": "recording-session-id-3",
        }),
      }),
    );
  });
});
