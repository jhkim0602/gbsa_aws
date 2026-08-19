export type CompanyAuthConfig = Readonly<{
  domain: string;
  clientId: string;
  redirectUri: string;
}>;

const VERIFIER_KEY = "iep_company_pkce_verifier";
const STATE_KEY = "iep_company_oauth_state";
const TOKEN_KEY = "iep_company_token";
const EXPIRES_AT_KEY = "iep_company_token_expires_at";

export async function beginCompanyLogin(
  config: CompanyAuthConfig,
  dependencies: {
    sessionStorage: Storage;
    navigate(location: string): void;
  },
): Promise<string> {
  const verifier = randomBase64Url(48);
  const state = randomBase64Url(32);
  const challenge = await sha256Base64Url(verifier);
  dependencies.sessionStorage.setItem(VERIFIER_KEY, verifier);
  dependencies.sessionStorage.setItem(STATE_KEY, state);

  const authorize = new URL(
    "/oauth2/authorize",
    normalizedDomain(config.domain),
  );
  authorize.search = new URLSearchParams({
    response_type: "code",
    client_id: config.clientId,
    redirect_uri: config.redirectUri,
    // `aws.cognito.signin.user.admin` is required for the token to be usable at all: the API
    // resolves the caller by calling GetUser with it, and GetUser rejects a token without
    // this scope -- so omitting it produced a successful login whose every request 401'd.
    // It must stay in step with `allowed_oauth_scopes` on the pool client; a scope requested
    // but not allowed fails the authorize call with `invalid_scope` instead.
    scope: "openid email profile aws.cognito.signin.user.admin",
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
  }).toString();
  const location = authorize.toString();
  dependencies.navigate(location);
  return location;
}

export async function completeCompanyLogin(
  config: CompanyAuthConfig,
  query: URLSearchParams,
  dependencies: {
    sessionStorage: Storage;
    localStorage: Storage;
    fetcher: typeof fetch;
  },
): Promise<void> {
  const code = query.get("code");
  const state = query.get("state");
  const expectedState = dependencies.sessionStorage.getItem(STATE_KEY);
  const verifier = dependencies.sessionStorage.getItem(VERIFIER_KEY);
  if (
    !code ||
    !state ||
    !expectedState ||
    state !== expectedState ||
    !verifier
  ) {
    clearTransientAuth(dependencies.sessionStorage);
    throw new Error("Cognito callback validation failed");
  }

  // Read off the object first: calling it as `dependencies.fetcher(...)` would pass the
  // dependencies object as `this`, and the real `fetch` throws `Illegal invocation` for any
  // `this` that is not the window. A local binding leaves `this` undefined, which `fetch`
  // accepts, so a caller may hand this the bare global.
  const { fetcher } = dependencies;
  const response = await fetcher(
    `${normalizedDomain(config.domain)}/oauth2/token`,
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        client_id: config.clientId,
        code,
        redirect_uri: config.redirectUri,
        code_verifier: verifier,
      }),
    },
  );
  if (!response.ok) {
    clearTransientAuth(dependencies.sessionStorage);
    throw new Error(`Cognito token exchange failed: ${response.status}`);
  }
  const payload = (await response.json()) as {
    access_token?: unknown;
    expires_in?: unknown;
  };
  if (
    typeof payload.access_token !== "string" ||
    typeof payload.expires_in !== "number"
  ) {
    clearTransientAuth(dependencies.sessionStorage);
    throw new Error("Cognito token response is invalid");
  }
  dependencies.localStorage.setItem(TOKEN_KEY, payload.access_token);
  dependencies.localStorage.setItem(
    EXPIRES_AT_KEY,
    String(Date.now() + payload.expires_in * 1000),
  );
  clearTransientAuth(dependencies.sessionStorage);
}

export function getCompanyAccessToken(storage: Storage): string | null {
  const token = storage.getItem(TOKEN_KEY);
  const expiresAt = Number(storage.getItem(EXPIRES_AT_KEY));
  if (!token || !Number.isFinite(expiresAt) || Date.now() >= expiresAt) {
    clearCompanyLogin(storage);
    return null;
  }
  return token;
}

export function clearCompanyLogin(storage: Storage): void {
  storage.removeItem(TOKEN_KEY);
  storage.removeItem(EXPIRES_AT_KEY);
}

function clearTransientAuth(storage: Storage): void {
  storage.removeItem(VERIFIER_KEY);
  storage.removeItem(STATE_KEY);
}

function normalizedDomain(domain: string): string {
  return domain.replace(/\/+$/, "");
}

function randomBase64Url(byteLength: number): string {
  const values = crypto.getRandomValues(new Uint8Array(byteLength));
  return base64Url(values);
}

async function sha256Base64Url(value: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return base64Url(new Uint8Array(digest));
}

function base64Url(values: Uint8Array): string {
  let binary = "";
  for (const value of values) binary += String.fromCharCode(value);
  return btoa(binary)
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}
