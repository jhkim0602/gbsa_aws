import { afterEach, describe, expect, it, vi } from "vitest";

import { CompanyRequestError, companyRequest } from "../api/companyClient";

function respondWith(status: number, body: string, contentType: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(body, {
        status,
        headers: { "Content-Type": contentType },
      }),
    ),
  );
}

describe("companyRequest", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    localStorage.clear();
  });

  it("sends the configured local company token when Cognito is absent", async () => {
    vi.stubEnv("VITE_LOCAL_COMPANY_TOKEN", "local-company-token");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("{}", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await companyRequest("/v1/me");

    expect(fetchMock).toHaveBeenCalledWith(
      "/v1/me",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer local-company-token",
        }),
      }),
    );
  });

  it("keeps the localStorage token fallback when no local env token is set", async () => {
    vi.stubEnv("VITE_LOCAL_COMPANY_TOKEN", "");
    localStorage.setItem("iep_company_token", "stored-company-token");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("{}", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await companyRequest("/v1/me");

    expect(fetchMock).toHaveBeenCalledWith(
      "/v1/me",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer stored-company-token",
        }),
      }),
    );
  });

  it("keeps the server status and detail so callers can tell a conflict apart", async () => {
    respondWith(409, '{"detail":"stale position version"}', "application/json");

    const error = await companyRequest("/v1/positions/position-1", {
      method: "PATCH",
    }).catch((thrown: unknown) => thrown);

    expect(error).toBeInstanceOf(CompanyRequestError);
    expect((error as CompanyRequestError).status).toBe(409);
    expect((error as CompanyRequestError).detail).toBe(
      "stale position version",
    );
  });

  it("surfaces non-JSON error bodies verbatim", async () => {
    respondWith(502, "upstream unavailable", "text/plain");

    const error = await companyRequest("/v1/positions").catch(
      (thrown: unknown) => thrown,
    );

    expect((error as CompanyRequestError).status).toBe(502);
    expect((error as CompanyRequestError).detail).toBe("upstream unavailable");
  });
});
