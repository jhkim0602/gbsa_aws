import {
  getCompanyAccessToken,
  type CompanyAuthConfig,
} from "../../features/company/cognitoAuth";
import type { CompanyWorkspaceApi } from "../../features/company";

export const companyAuthConfig = readCompanyAuthConfig();

export function idempotencyKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}

export async function companyRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = companyAuthConfig
    ? getCompanyAccessToken(localStorage)
    : (localStorage.getItem("iep_company_token") ??
      import.meta.env.VITE_LOCAL_DEMO_ACCESS ??
      "");
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL ?? ""}${path}`,
    {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    },
  );
  if (!response.ok) {
    throw new Error(`company request failed: ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const companyWorkspaceApi: CompanyWorkspaceApi = {
  async getCurrentUser() {
    const result = await companyRequest<{
      company_user_id: string;
      company_id: string;
      email: string;
      status: string;
    }>("/v1/me");
    return {
      companyUserId: result.company_user_id,
      companyId: result.company_id,
      email: result.email,
      status: result.status,
    };
  },
  async listPositions() {
    const result = await companyRequest<{
      items: PositionResponse[];
    }>("/v1/positions?limit=100");
    return result.items.map(toCompanyPosition);
  },
  async getPosition(positionId) {
    const result = await companyRequest<PositionResponse>(
      `/v1/positions/${positionId}`,
    );
    return toCompanyPosition(result);
  },
};

type PositionResponse = Readonly<{
  position_id: string;
  title: string;
  description: string;
  role_type?: string | null;
  headcount?: number | null;
  recruitment_start_at?: string | null;
  recruitment_end_at?: string | null;
  status: string;
  row_version: number;
  created_at: string;
}>;

function toCompanyPosition(position: PositionResponse) {
  return {
    positionId: position.position_id,
    title: position.title,
    description: position.description,
    roleType: position.role_type,
    headcount: position.headcount,
    recruitmentStartAt: position.recruitment_start_at,
    recruitmentEndAt: position.recruitment_end_at,
    status: position.status,
    rowVersion: position.row_version,
    createdAt: position.created_at,
  };
}

function readCompanyAuthConfig(): CompanyAuthConfig | null {
  const domain = import.meta.env.VITE_COGNITO_DOMAIN;
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
  const redirectUri = import.meta.env.VITE_COGNITO_REDIRECT_URI;
  if (!domain || !clientId || !redirectUri) return null;
  return { domain, clientId, redirectUri };
}
