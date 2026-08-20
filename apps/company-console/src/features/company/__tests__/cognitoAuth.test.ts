import { describe, expect, it, vi } from "vitest";

import {
  beginCompanyLogin,
  beginCompanySignup,
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
    // The API resolves the caller by calling GetUser with this token, and GetUser rejects a
    // token that was not granted this scope -- so a login without it succeeds and then 401s
    // on every request.
    expect(url.searchParams.get("scope")?.split(" ")).toContain(
      "aws.cognito.signin.user.admin",
    );
    expect(session.getItem("iep_company_pkce_verifier")).toBeTruthy();
    expect(location).not.toContain(
      session.getItem("iep_company_pkce_verifier") ?? "missing",
    );
  });

  it("opens the Cognito self-registration screen with the same PKCE protection", async () => {
    const session = memoryStorage();
    const location = await beginCompanySignup(config, {
      sessionStorage: session,
      navigate: vi.fn(),
    });
    const url = new URL(location);

    expect(url.pathname).toBe("/signup");
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("code_challenge")).toBeTruthy();
    expect(session.getItem("iep_company_oauth_state")).toBeTruthy();
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
  // `fetch` throws `TypeError: Illegal invocation` when its `this` is not the window, so
  // calling the dependency as `dependencies.fetcher(...)` broke every real login while the
  // mock-based test above kept passing. This pins the call shape: a `this`-sensitive fetcher
  // must survive being handed over as a plain property.
  it("calls the fetcher without rebinding its receiver", async () => {
    const session = memoryStorage();
    const local = memoryStorage();
    const authorization = await beginCompanyLogin(config, {
      sessionStorage: session,
      navigate: vi.fn(),
    });
    const state = new URL(authorization).searchParams.get("state") ?? "";
    const host = {
      calls: 0,
      fetcher(this: unknown, _url: string, _init?: RequestInit) {
        if (this !== undefined) throw new TypeError("Illegal invocation");
        host.calls += 1;
        return Promise.resolve(
          new Response(
            JSON.stringify({ access_token: "token", expires_in: 900 }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      },
    };

    await completeCompanyLogin(
      config,
      new URLSearchParams({ code: "authorization-code", state }),
      {
        sessionStorage: session,
        localStorage: local,
        fetcher: host.fetcher as unknown as typeof fetch,
      },
    );

    expect(host.calls).toBe(1);
    expect(local.getItem("iep_company_token")).toBe("token");
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
