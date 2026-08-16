import { useState } from "react";
import {
  Navigate,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";

import {
  ApplicantAccess,
  type ApplicantAccessApi,
  type ConsentPolicy,
} from "../features/access";
import {
  EquipmentCheck,
  createBrowserEquipmentCheckApi,
  type EquipmentCheckResult,
} from "../features/interview/EquipmentCheck";
import {
  InterviewSession,
  type RecordingUploadApi,
} from "../features/interview/InterviewSession";
import type { StoredMediaChunk } from "../features/interview/media";
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

export function resolveWebSocketUrl(path: string): string {
  const base = API_BASE || window.location.origin;
  const url = new URL(path, base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

export function createRecordingUploadApi(
  sessionId: string,
): RecordingUploadApi {
  return {
    async upload(chunk: StoredMediaChunk) {
      const intent = await applicantRequest<{
        method: string;
        url: string;
        required_headers: Record<string, string>;
      }>(`/v1/applicant/interview-sessions/${sessionId}/media-upload-intents`, {
        method: "POST",
        headers: {
          "Idempotency-Key": `recording-${sessionId}-${chunk.sequence}`,
        },
        body: JSON.stringify({
          chunk_sequence: chunk.sequence,
          byte_size: chunk.byteSize,
          sha256: chunk.sha256,
          session_start_ms: chunk.sessionStartMs,
          session_end_ms: chunk.sessionEndMs,
        }),
      });
      const response = await fetch(intent.url, {
        method: intent.method,
        headers: intent.required_headers,
        body: chunk.blob,
      });
      if (!response.ok) {
        throw new Error(`recording upload failed: ${response.status}`);
      }
    },
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
  async getConsentPolicy() {
    const policy = await applicantRequest<{
      policy_version: string;
      ai_role: string;
      recording_notice: string;
      processing_purposes: Array<{
        purpose: ConsentPolicy["requiredPurposes"][number];
        title: string;
        description: string;
      }>;
      retention_days: number;
      deletion_method: string;
      required_purposes: ConsentPolicy["requiredPurposes"];
      content_digest: string;
    }>("/v1/applicant/consents");
    return {
      policyVersion: policy.policy_version,
      aiRole: policy.ai_role,
      recordingNotice: policy.recording_notice,
      processingPurposes: policy.processing_purposes,
      retentionDays: policy.retention_days,
      deletionMethod: policy.deletion_method,
      requiredPurposes: policy.required_purposes,
      contentDigest: policy.content_digest,
    };
  },
  async recordConsent(policy, purposes) {
    await applicantRequest("/v1/applicant/consents", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("consent") },
      body: JSON.stringify({
        policy_version: policy.policyVersion,
        accepted_purposes: purposes,
        consent_content_digest: policy.contentDigest,
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
  const navigate = useNavigate();
  return (
    <ApplicantAccess
      api={accessApi}
      initialToken={token}
      onContinue={() => navigate("/submissions")}
    />
  );
}

export function SubmissionsRoute() {
  const navigate = useNavigate();
  return (
    <SubmissionWorkspace
      api={submissionApi}
      onContinue={() => navigate("/interview")}
    />
  );
}

export function InterviewRoute() {
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const strategyId = search.get("strategyId") ?? "";
  const [session, setSession] = useState<{
    sessionId: string;
    equipmentCheckId: string;
    websocketPath: string;
  } | null>(null);
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
        websocket_path: string;
      }>("/v1/applicant/interview-sessions", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("interview") },
        body: JSON.stringify({
          equipment_check_id: check.equipment_check_id,
          strategy_id: strategyId,
          acknowledged_partial_analysis: true,
        }),
      });
      setSession({
        sessionId: session.interview_session_id,
        equipmentCheckId: check.equipment_check_id,
        websocketPath: session.websocket_path,
      });
      navigate(
        {
          pathname: "/interview/session",
          search: strategyId
            ? `?strategyId=${encodeURIComponent(strategyId)}`
            : "",
        },
        { replace: true },
      );
    } catch {
      setError(true);
    }
  }

  if (!session) {
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
    <InterviewSession
      sessionId={session.sessionId}
      equipmentCheckId={session.equipmentCheckId}
      websocketUrl={resolveWebSocketUrl(session.websocketPath)}
      recordingApi={createRecordingUploadApi(session.sessionId)}
      onComplete={() => navigate("/interview/complete", { replace: true })}
    />
  );
}
