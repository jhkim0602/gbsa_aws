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
