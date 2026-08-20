import type { components } from "@iep/contracts/generated/typescript/openapi";

import {
  getCompanyAccessToken,
  type CompanyAuthConfig,
} from "../../features/company/cognitoAuth";
import type { CompanyWorkspaceApi } from "../../features/company";

export const companyAuthConfig = readCompanyAuthConfig();

export function idempotencyKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}

export class CompanyRequestError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(`company request failed: ${status}`);
    this.name = "CompanyRequestError";
  }
}

export async function companyRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = companyAuthConfig
    ? getCompanyAccessToken(localStorage)
    : (localStorage.getItem("iep_company_token") ?? "");
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
    const body = await response.text();
    let detail = body;
    try {
      detail = (JSON.parse(body) as { detail?: string }).detail ?? body;
    } catch {
      // Non-JSON error bodies are surfaced verbatim.
    }
    throw new CompanyRequestError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const companyWorkspaceApi: CompanyWorkspaceApi = {
  async getCurrentUser() {
    const result =
      await companyRequest<components["schemas"]["CompanyUserView"]>("/v1/me");
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

type PositionResponse = components["schemas"]["Position"] & {
  submission_requirements: Array<{
    material_type:
      | "resume"
      | "cover_letter"
      | "career_description"
      | "projects"
      | "portfolio";
    required: boolean;
    enabled: boolean;
    instructions?: string | null;
  }>;
};

function toCompanyPosition(position: PositionResponse) {
  return {
    positionId: position.position_id,
    title: position.title,
    description: position.description,
    roleType: position.role_type,
    headcount: position.headcount,
    interviewCapacity: position.interview_capacity,
    interviewAt: position.interview_at,
    recruitmentStartAt: position.recruitment_start_at,
    recruitmentEndAt: position.recruitment_end_at,
    submissionRequirements: position.submission_requirements.map(
      (requirement) => ({
        materialType: requirement.material_type,
        required: requirement.required,
        enabled: requirement.enabled,
        instructions: requirement.instructions,
      }),
    ),
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
