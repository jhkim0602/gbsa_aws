import { describe, expect, it, vi } from "vitest";

import {
  beginCompanyLogin,
  completeCompanyLogin,
  type CompanyAuthConfig,
} from "../cognitoAuth";

const config: CompanyAuthConfig = {
  domain: "https://iep-company.auth.ap-northeast-2.amazoncognito.com",
  clientId: "company-client",
  redirectUri: "https://company.example.com/auth/callback",
};

describe("Cognito company authentication", () => {
  it("creates a PKCE authorization URL without persisting a raw credential", async () => {
    const session = memoryStorage();
    const location = await beginCompanyLogin(config, {
      sessionStorage: session,
      navigate: vi.fn(),
    });
    const url = new URL(location);

    expect(url.pathname).toBe("/oauth2/authorize");
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("code_challenge")).toBeTruthy();
    expect(session.getItem("iep_company_pkce_verifier")).toBeTruthy();
    expect(location).not.toContain(
      session.getItem("iep_company_pkce_verifier") ?? "missing",
    );
  });

  it("validates state and exchanges the code before storing the access token", async () => {
    const session = memoryStorage();
    const local = memoryStorage();
    const authorization = await beginCompanyLogin(config, {
      sessionStorage: session,
      navigate: vi.fn(),
    });
    const state = new URL(authorization).searchParams.get("state") ?? "";
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "cognito-access-token",
          expires_in: 900,
          token_type: "Bearer",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await completeCompanyLogin(
      config,
      new URLSearchParams({ code: "authorization-code", state }),
      {
        sessionStorage: session,
        localStorage: local,
        fetcher,
      },
    );

    expect(fetcher).toHaveBeenCalledWith(
      `${config.domain}/oauth2/token`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(local.getItem("iep_company_token")).toBe("cognito-access-token");
    expect(session.getItem("iep_company_pkce_verifier")).toBeNull();
    expect(session.getItem("iep_company_oauth_state")).toBeNull();
  });
});

function memoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  };
}
