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
    ["/access/token-value", "지원자 면접"],
    ["/submissions", "면접 자료 제출"],
    ["/interview", "면접 환경 점검"],
  ])("renders %s through the integration route registry", (path, heading) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <ApplicantRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
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
      .mockResolvedValueOnce(new Response(null, { status: 200 }));
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
  });
});
