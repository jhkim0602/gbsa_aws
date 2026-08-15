import { useState } from "react";
import { Navigate, useParams, useSearchParams } from "react-router-dom";

import { ApplicantAccess, type ApplicantAccessApi } from "../features/access";
import {
  EquipmentCheck,
  createBrowserEquipmentCheckApi,
  type EquipmentCheckResult,
} from "../features/interview/EquipmentCheck";
import { InterviewRoom } from "../features/interview/InterviewRoom";
import {
  SubmissionWorkspace,
  type SubmissionWorkspaceApi,
} from "../features/submissions";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

function idempotencyKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}

async function applicantRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`applicant request failed: ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function serializeEquipmentComponent(
  component: EquipmentCheckResult["camera"],
) {
  return {
    status: component.status,
    sanitized_code: component.sanitizedCode ?? null,
  };
}

const accessApi: ApplicantAccessApi = {
  async exchangeToken(token) {
    await applicantRequest("/v1/applicant/access/exchange", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("token-exchange") },
      body: JSON.stringify({ invitation_token: token }),
    });
  },
  async verifyIdentity(displayName, verificationValue) {
    await applicantRequest("/v1/applicant/identity-verifications", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("identity") },
      body: JSON.stringify({
        display_name: displayName,
        verification_value: verificationValue,
      }),
    });
  },
  async recordConsent(purposes) {
    await applicantRequest("/v1/applicant/consents", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("consent") },
      body: JSON.stringify({
        policy_version: "2026-08-v1",
        accepted_purposes: purposes,
        consent_content_digest: "a".repeat(64),
      }),
    });
  },
};

async function sha256(file: File) {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    await file.arrayBuffer(),
  );
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

const submissionApi: SubmissionWorkspaceApi = {
  async uploadDocument(file) {
    const digest = await sha256(file);
    const intent = await applicantRequest<{
      upload_id: string;
      method: string;
      url: string;
      required_headers: Record<string, string>;
    }>("/v1/applicant/submissions/upload-intents", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("upload-intent") },
      body: JSON.stringify({
        source_type: "pdf",
        filename: file.name,
        media_type: file.type || "application/pdf",
        byte_size: file.size,
        sha256: digest,
      }),
    });
    await fetch(intent.url, {
      method: intent.method,
      headers: intent.required_headers,
      body: file,
    });
    await applicantRequest("/v1/applicant/submissions", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("submission") },
      body: JSON.stringify({ source_type: "pdf", upload_id: intent.upload_id }),
    });
  },
  async registerRepository(url) {
    await applicantRequest("/v1/applicant/submissions", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("repository") },
      body: JSON.stringify({
        source_type: "public_git",
        public_url: url,
        candidate_identity_inputs: {},
      }),
    });
  },
  async getReadiness() {
    const readiness = await applicantRequest<{
      overall_status: "waiting" | "analyzing" | "ready" | "partial" | "failed";
      interview_ready: boolean;
      impact_summary?: string;
    }>("/v1/applicant/analysis-status");
    return {
      overallStatus: readiness.overall_status,
      interviewReady: readiness.interview_ready,
      impactSummary: readiness.impact_summary,
    };
  },
};

export function ApplicantHomeRoute() {
  return <Navigate replace to="/access" />;
}

export function AccessRoute() {
  const { token = "" } = useParams();
  return <ApplicantAccess api={accessApi} initialToken={token} />;
}

export function SubmissionsRoute() {
  return <SubmissionWorkspace api={submissionApi} />;
}

export function InterviewRoute() {
  const [search] = useSearchParams();
  const strategyId = search.get("strategyId") ?? "";
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState(false);

  async function start(result: EquipmentCheckResult) {
    try {
      const check = await applicantRequest<{ equipment_check_id: string }>(
        "/v1/applicant/equipment-checks",
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey("equipment") },
          body: JSON.stringify({
            camera: serializeEquipmentComponent(result.camera),
            microphone: serializeEquipmentComponent(result.microphone),
            network: serializeEquipmentComponent(result.network),
          }),
        },
      );
      const session = await applicantRequest<{
        interview_session_id: string;
      }>("/v1/applicant/interview-sessions", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("interview") },
        body: JSON.stringify({
          equipment_check_id: check.equipment_check_id,
          strategy_id: strategyId,
          acknowledged_partial_analysis: true,
        }),
      });
      setSessionId(session.interview_session_id);
    } catch {
      setError(true);
    }
  }

  if (!sessionId) {
    return (
      <>
        <EquipmentCheck
          api={createBrowserEquipmentCheckApi()}
          onReady={(result) => void start(result)}
        />
        {error && <p role="alert">면접 세션을 시작할 수 없습니다.</p>}
      </>
    );
  }
  return (
    <InterviewRoom
      question="최근 경험에서 대안을 비교한 과정을 설명해 주세요."
      state="awaiting_answer"
      connectionState="connected"
      textOnly={false}
      onStartAnswer={() => undefined}
      onCompleteAnswer={() => undefined}
      onReconnect={() => undefined}
      onAddExplanation={() => undefined}
    />
  );
}
