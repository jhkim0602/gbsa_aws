import type { components } from "@iep/contracts/generated/typescript/openapi";
import { useEffect, useRef, useState } from "react";
import {
  Navigate,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";

import {
  ApplicantAccess,
  type ApplicantAccessApi,
  type ApplicantInvitationPreview,
} from "../features/access";
import {
  INTERVIEWER_LEVELS,
  type InterviewerLevel,
} from "../features/interview/Avatar";
import {
  EquipmentCheck,
  createBrowserEquipmentCheckApi,
  type EquipmentCheckResult,
} from "../features/interview/EquipmentCheck";
import { InterviewRoom } from "../features/interview/InterviewRoom";
import {
  InterviewSession,
  type RecordingUploadApi,
} from "../features/interview/InterviewSession";
import type { AutomatedInterviewMode } from "../features/interview/automation";
import type { StoredMediaChunk } from "../features/interview/media";
import {
  SubmissionWorkspace,
  type AnalysisReadiness,
  type SubmissionMaterialId,
  type SubmissionWorkspaceData,
  type SubmissionWorkspaceApi,
} from "../features/submissions";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const COMPANY_CONSOLE_URL =
  import.meta.env.VITE_COMPANY_CONSOLE_URL ?? "http://127.0.0.1:5173";

const AUTOMATED_EQUIPMENT_RESULT: EquipmentCheckResult = {
  camera: { status: "ready" },
  microphone: { status: "ready" },
  network: { status: "ready" },
  overallStatus: "ready",
};

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
      const idempotency = `recording-${sessionId}-${chunk.sequence}`;
      const body = JSON.stringify({
        chunk_sequence: chunk.sequence,
        byte_size: chunk.byteSize,
        sha256: chunk.sha256,
        session_start_ms: chunk.sessionStartMs,
        session_end_ms: chunk.sessionEndMs,
      });
      const intent = await applicantRequest<
        components["schemas"]["UploadIntent"]
      >(`/v1/applicant/interview-sessions/${sessionId}/media-upload-intents`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotency },
        body,
      });
      const response = await fetch(intent.url, {
        method: intent.method,
        headers: intent.required_headers,
        body: chunk.blob,
      });
      if (!response.ok) {
        throw new Error(`recording upload failed: ${response.status}`);
      }
      // The upload only lands in the bucket; the server records the chunk here. Without
      // this confirmation the session has no verified recording, so the review timeline
      // stays empty and the report never leaves the queue. The same idempotency key
      // confirms exactly the upload that was just authorized.
      await applicantRequest(
        `/v1/applicant/interview-sessions/${sessionId}/media-uploads`,
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotency },
          body,
        },
      );
    },
  };
}

const accessApi: ApplicantAccessApi = {
  async getInvitationPreview(token) {
    const preview = await applicantRequest<{
      company_name: string;
      position_title: string;
      position_description: string;
      role_type: string | null;
      interview_at: string | null;
      interview_duration_minutes: number;
      interview_level: ApplicantInvitationPreview["interviewLevel"];
      interviewer_name: string | null;
      submission_requirements: Array<{
        material_type: string;
        required: boolean;
        enabled: boolean;
        instructions: string | null;
      }>;
    }>("/v1/applicant/access/preview", {
      method: "POST",
      body: JSON.stringify({ invitation_token: token }),
    });
    return {
      companyName: preview.company_name,
      positionTitle: preview.position_title,
      positionDescription: preview.position_description,
      roleType: preview.role_type,
      interviewAt: preview.interview_at,
      interviewDurationMinutes: preview.interview_duration_minutes,
      interviewLevel: preview.interview_level,
      interviewerName: preview.interviewer_name,
      submissionRequirements: preview.submission_requirements.map(
        (requirement) => ({
          materialType: requirement.material_type,
          required: requirement.required,
          enabled: requirement.enabled,
          instructions: requirement.instructions,
        }),
      ),
    };
  },
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
    const policy = await applicantRequest<
      components["schemas"]["ConsentPolicyView"]
    >("/v1/applicant/consents");
    return {
      policyVersion: policy.policy_version,
      aiRole: policy.ai_role,
      recordingNotice: policy.recording_notice,
      processingPurposes: policy.processing_purposes,
      retentionDays: policy.retention_days,
      deletionMethod: policy.deletion_method,
      requiredPurposes: [...policy.required_purposes],
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
  async uploadDocument(file, materialId) {
    const digest = await sha256(file);
    const intent = await applicantRequest<
      components["schemas"]["UploadIntent"]
    >("/v1/applicant/submissions/upload-intents", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("upload-intent") },
      body: JSON.stringify({
        source_type: documentSourceType(materialId),
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
      body: JSON.stringify({
        material_type: toApiMaterialType(materialId),
        source_type: documentSourceType(materialId),
        upload_id: intent.upload_id,
      }),
    });
  },
  async registerRepository(url, materialId) {
    await applicantRequest("/v1/applicant/submissions", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("repository") },
      body: JSON.stringify({
        material_type: toApiMaterialType(materialId),
        source_type: "public_git",
        public_url: url,
        candidate_identity_inputs: {},
      }),
    });
  },
  async getReadiness() {
    const readiness = await applicantRequest<{
      overall_status: AnalysisReadiness["overallStatus"];
      interview_ready: boolean;
      impact_summary?: string | null;
      strategy_id?: string | null;
      strategy_version?: number | null;
      submissions: Array<{
        material_type: string;
        status: string;
        created_at: string;
      }>;
    }>("/v1/applicant/analysis-status");
    const materialStatuses: Partial<
      Record<SubmissionMaterialId, { status: string; createdAt: string }>
    > = {};
    for (const submission of readiness.submissions) {
      const materialId = fromApiMaterialType(submission.material_type);
      const current = materialStatuses[materialId];
      if (!current || submission.created_at > current.createdAt) {
        materialStatuses[materialId] = {
          status: submission.status,
          createdAt: submission.created_at,
        };
      }
    }
    return {
      overallStatus: readiness.overall_status,
      interviewReady: readiness.interview_ready,
      impactSummary: readiness.impact_summary ?? undefined,
      strategyId: readiness.strategy_id ?? undefined,
      strategyVersion: readiness.strategy_version ?? undefined,
      materialStatuses: Object.fromEntries(
        Object.entries(materialStatuses).map(([materialId, value]) => [
          materialId,
          value?.status,
        ]),
      ),
    };
  },
  async getWorkspace() {
    const workspace = await applicantRequest<{
      position_title: string;
      requirements: Array<{
        material_type: string;
        required: boolean;
        enabled: boolean;
        instructions: string | null;
      }>;
      submissions: Array<{ material_type: string; status: string }>;
    }>("/v1/applicant/submission-workspace");
    return {
      positionTitle: workspace.position_title,
      requirements: workspace.requirements.map((requirement) => ({
        id: fromApiMaterialType(requirement.material_type),
        required: requirement.required,
        enabled: requirement.enabled,
        instructions: requirement.instructions ?? undefined,
      })),
      submissions: workspace.submissions.map((submission) => ({
        materialId: fromApiMaterialType(submission.material_type),
        status: submission.status,
      })),
    };
  },
  async getAnalysisDebug() {
    return applicantRequest<unknown>("/v1/applicant/analysis-debug");
  },
};

function toApiMaterialType(materialId: SubmissionMaterialId) {
  return materialId.replaceAll("-", "_");
}

function fromApiMaterialType(materialType: string): SubmissionMaterialId {
  return materialType.replaceAll("_", "-") as SubmissionMaterialId;
}

function documentSourceType(materialId: SubmissionMaterialId) {
  if (materialId === "resume") return "resume";
  if (materialId === "cover-letter") return "cover_letter";
  return "pdf";
}

function parseInterviewerLevel(value: string | null): InterviewerLevel {
  if (value && value in INTERVIEWER_LEVELS) {
    return value as InterviewerLevel;
  }
  return "entry";
}

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
  const [workspace, setWorkspace] = useState<SubmissionWorkspaceData | null>(
    null,
  );
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let active = true;
    submissionApi
      .getWorkspace()
      .then((result) => {
        if (active) setWorkspace(result);
      })
      .catch(() => {
        if (active) setLoadFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  if (loadFailed) {
    return <p role="alert">포지션의 제출 자료 설정을 불러오지 못했습니다.</p>;
  }
  if (!workspace) {
    return <p role="status">제출 자료를 불러오는 중입니다.</p>;
  }

  return (
    <SubmissionWorkspace
      api={submissionApi}
      positionTitle={workspace.positionTitle}
      requirements={workspace.requirements}
      submittedMaterials={workspace.submissions}
      onContinue={(strategyId) => navigate(interviewRoutePath(strategyId))}
    />
  );
}

export function interviewRoutePath(strategyId: string) {
  const search = new URLSearchParams({ strategyId });
  return `/interview?${search.toString()}`;
}

export function serializeInterviewSessionRequest(
  equipmentCheckId: string,
  strategyId: string,
) {
  if (!strategyId) throw new Error("interview strategy is required");
  return {
    equipment_check_id: equipmentCheckId,
    strategy_id: strategyId,
    acknowledged_partial_analysis: true,
  };
}

export function InterviewRoute() {
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const strategyIdFromSearch = search.get("strategyId") ?? "";
  const interviewerLevel = parseInterviewerLevel(search.get("level"));
  const roomPreview = import.meta.env.DEV && search.get("preview") === "room";
  const automationMode = import.meta.env.DEV
    ? parseAutomationMode(search.get("auto"))
    : undefined;
  const [resolvedStrategyId, setResolvedStrategyId] =
    useState(strategyIdFromSearch);
  const [strategyLoading, setStrategyLoading] = useState(
    !strategyIdFromSearch && !roomPreview,
  );
  const [session, setSession] = useState<{
    sessionId: string;
    equipmentCheckId: string;
    websocketPath: string;
  } | null>(null);
  const [error, setError] = useState(false);
  const [sessionStarting, setSessionStarting] = useState(false);
  const autoStartRequestedRef = useRef(false);
  const sessionStartPendingRef = useRef(false);
  const strategyId = strategyIdFromSearch || resolvedStrategyId;

  useEffect(() => {
    if (roomPreview) return;
    if (strategyIdFromSearch) {
      setResolvedStrategyId(strategyIdFromSearch);
      setStrategyLoading(false);
      return;
    }
    let active = true;
    setStrategyLoading(true);
    submissionApi
      .getReadiness()
      .then((readiness) => {
        if (!active) return;
        if (readiness.interviewReady && readiness.strategyId) {
          setResolvedStrategyId(readiness.strategyId);
          return;
        }
        setError(true);
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setStrategyLoading(false);
      });
    return () => {
      active = false;
    };
  }, [roomPreview, strategyIdFromSearch]);

  useEffect(() => {
    if (
      !automationMode ||
      !strategyId ||
      strategyLoading ||
      session ||
      autoStartRequestedRef.current
    ) {
      return;
    }
    autoStartRequestedRef.current = true;
    void start(AUTOMATED_EQUIPMENT_RESULT, automationMode);
  }, [automationMode, session, strategyId, strategyLoading]);

  if (roomPreview) {
    return (
      <InterviewRoom
        question="안녕하세요. 서비스 백엔드와 관련해 가장 대표적인 프로젝트 한 가지를 설명해 주시겠어요?"
        state="awaiting_answer"
        connectionState="connected"
        textOnly={false}
        interviewerLevel={interviewerLevel}
        initialElapsedSeconds={9 * 60 + 55}
        onStartAnswer={() => undefined}
        onCompleteAnswer={() => undefined}
        onReconnect={() => undefined}
        onAddExplanation={() => undefined}
      />
    );
  }

  async function start(
    result: EquipmentCheckResult,
    requestedAutomationMode = automationMode,
  ) {
    if (sessionStartPendingRef.current) return;
    if (!strategyId) {
      setError(true);
      return;
    }
    sessionStartPendingRef.current = true;
    setSessionStarting(true);
    setError(false);
    try {
      const check = await applicantRequest<
        components["schemas"]["EquipmentCheck"]
      >("/v1/applicant/equipment-checks", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("equipment") },
        body: JSON.stringify({
          camera: serializeEquipmentComponent(result.camera),
          microphone: serializeEquipmentComponent(result.microphone),
          network: serializeEquipmentComponent(result.network),
        }),
      });
      const session = await applicantRequest<
        components["schemas"]["InterviewSessionView"]
      >("/v1/applicant/interview-sessions", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("interview") },
        body: JSON.stringify(
          serializeInterviewSessionRequest(
            check.equipment_check_id,
            strategyId,
          ),
        ),
      });
      setSession({
        sessionId: session.interview_session_id,
        equipmentCheckId: check.equipment_check_id,
        websocketPath: session.websocket_path,
      });
      const nextSearch = new URLSearchParams({ level: interviewerLevel });
      if (strategyId) nextSearch.set("strategyId", strategyId);
      if (requestedAutomationMode) {
        nextSearch.set("auto", requestedAutomationMode);
      }
      navigate(
        {
          pathname: "/interview/session",
          search: nextSearch.toString(),
        },
        { replace: true },
      );
    } catch {
      setError(true);
      autoStartRequestedRef.current = false;
      sessionStartPendingRef.current = false;
      setSessionStarting(false);
    }
  }

  if (strategyLoading) {
    return <p role="status">면접 전략을 불러오는 중입니다.</p>;
  }

  if (!strategyId) {
    return (
      <main>
        <p role="alert">분석이 완료된 면접 전략을 불러올 수 없습니다.</p>
        <button type="button" onClick={() => navigate("/submissions")}>
          지원 자료로 돌아가기
        </button>
      </main>
    );
  }

  if (!session) {
    return (
      <>
        {import.meta.env.DEV ? (
          <section className="mx-auto mt-8 w-[min(calc(100%-48px),920px)] rounded-panel border border-[#cfe0bd] bg-[#f4faee] p-4 text-ink mw-680:w-[min(calc(100%-32px),920px)]">
            <p className="text-[13px] font-semibold">로컬 자동 면접</p>
            <p className="mt-1 text-[12px] leading-[1.6] text-muted">
              환경 점검부터 답변, 결과 화면 이동까지 자동으로 진행합니다.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                className="min-h-10 rounded-panel border border-brand bg-brand px-4 text-[12px] font-semibold text-white"
                type="button"
                disabled={sessionStarting}
                onClick={() => void start(AUTOMATED_EQUIPMENT_RESULT, "fast")}
              >
                빠른 자동 면접 실행
              </button>
              <button
                className="min-h-10 rounded-panel border border-border bg-white px-4 text-[12px] font-semibold text-ink"
                type="button"
                disabled={sessionStarting}
                onClick={() => void start(AUTOMATED_EQUIPMENT_RESULT, "speech")}
              >
                음성 포함 자동 면접 실행
              </button>
            </div>
            {sessionStarting ? (
              <p className="mt-2 text-[12px] text-muted" role="status">
                자동 면접 세션을 준비하고 있습니다.
              </p>
            ) : null}
          </section>
        ) : null}
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
      interviewerLevel={interviewerLevel}
      automationMode={automationMode}
      onComplete={() => {
        if (automationMode) {
          const reviewUrl = new URL(
            `/review/${session.sessionId}?auto=1`,
            COMPANY_CONSOLE_URL,
          );
          window.location.assign(reviewUrl.toString());
          return;
        }
        navigate("/interview/complete", { replace: true });
      }}
    />
  );
}

function parseAutomationMode(
  value: string | null,
): AutomatedInterviewMode | undefined {
  return value === "fast" || value === "speech" ? value : undefined;
}
