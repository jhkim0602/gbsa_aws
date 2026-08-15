import { useEffect, useState } from "react";
import {
  Navigate,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";

import {
  beginCompanyLogin,
  completeCompanyLogin,
  getCompanyAccessToken,
  type CompanyAuthConfig,
} from "../features/company/cognitoAuth";
import { HiringWorkspace, type HiringWorkspaceApi } from "../features/hiring";
import {
  HumanReview,
  ReportView,
  TimelineView,
  type ReviewApi,
} from "../features/review";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const AUTH_CONFIG = companyAuthConfig();

function idempotencyKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}

async function companyRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = AUTH_CONFIG
    ? getCompanyAccessToken(localStorage)
    : (localStorage.getItem("iep_company_token") ??
      import.meta.env.VITE_COMPANY_TOKEN ??
      "");
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`company request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

const hiringApi: HiringWorkspaceApi = {
  async createPosition(input) {
    const result = await companyRequest<{ position_id: string }>(
      "/v1/positions",
      {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("position") },
        body: JSON.stringify(input),
      },
    );
    return { positionId: result.position_id };
  },
  async publishCriteria(positionId, name) {
    const draft = await companyRequest<{
      competency_model_version_id: string;
      row_version: number;
    }>(`/v1/positions/${positionId}/competency-model-versions`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("criteria") },
      body: JSON.stringify({
        criteria: [
          {
            code: "PROBLEM_SOLVING",
            name,
            description: "대안과 트레이드오프를 실제 경험으로 설명한다.",
            weight: 1,
            good_evidence: { signal: "tradeoff" },
            weak_evidence: { signal: "unsupported" },
            abstain_guidance: "실제 답변 근거가 없으면 판단을 유보한다.",
            common_questions: ["대안을 비교한 과정을 설명해 주세요."],
            required: true,
          },
        ],
        prohibited_topics: ["가족", "외모"],
        interview_duration_minutes: 30,
        persona_definition: { name: "GBSA AI", tone: "차분함" },
      }),
    });
    const published = await companyRequest<{
      competency_model_version_id: string;
    }>(
      `/v1/competency-model-versions/${draft.competency_model_version_id}/publish`,
      {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey("criteria-publish"),
          "If-Match-Version": String(draft.row_version),
        },
      },
    );
    return { versionId: published.competency_model_version_id };
  },
  async createCampaign(positionId, versionId, name) {
    const draft = await companyRequest<{
      campaign_id: string;
      row_version: number;
    }>("/v1/campaigns", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("campaign") },
      body: JSON.stringify({
        position_id: positionId,
        competency_model_version_id: versionId,
        name,
        candidate_instructions:
          "조용한 환경에서 카메라와 마이크를 준비해 주세요.",
      }),
    });
    await companyRequest(`/v1/campaigns/${draft.campaign_id}/publish`, {
      method: "POST",
      headers: {
        "Idempotency-Key": idempotencyKey("campaign-publish"),
        "If-Match-Version": String(draft.row_version),
      },
    });
    return { campaignId: draft.campaign_id };
  },
  async issueInvitation(campaignId, email) {
    await companyRequest(`/v1/campaigns/${campaignId}/invitations`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("invitation") },
      body: JSON.stringify({
        applicants: [{ email, display_name: email.split("@")[0] }],
        expires_at: new Date(Date.now() + 7 * 86_400_000).toISOString(),
      }),
    });
  },
};

type ReportResponse = {
  report_id: string;
  summary: string;
  status: string;
  items: Array<{
    report_item_id: string;
    criterion_id: string;
    assessment_state:
      | "confirmed"
      | "partially_confirmed"
      | "insufficient_evidence"
      | "needs_follow_up";
    observation: string;
    evidence: Array<{
      evidence_id: string;
      video_start_ms: number;
      video_end_ms: number;
    }>;
  }>;
};

type TimelineResponse = {
  entries: Array<{
    entry_id: string;
    entry_type: "question" | "answer" | "event" | "evidence";
    start_ms: number;
    end_ms: number;
    text: string | null;
  }>;
  playback: {
    status: "ready" | "partial" | "processing" | "unavailable";
    url: string | null;
  };
};

export function CompanyHomeRoute() {
  return <Navigate replace to="/hiring" />;
}

export function HiringRoute() {
  if (AUTH_CONFIG && !getCompanyAccessToken(localStorage)) {
    return <Navigate replace to="/auth/login" />;
  }
  return <HiringWorkspace api={hiringApi} />;
}

export function ReviewRoute() {
  const { sessionId = "" } = useParams();
  const [search] = useSearchParams();
  const invitationId = search.get("invitationId") ?? "";
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [error, setError] = useState(false);
  const authenticated =
    !AUTH_CONFIG || Boolean(getCompanyAccessToken(localStorage));

  useEffect(() => {
    if (!authenticated) return;
    let active = true;
    Promise.all([
      companyRequest<ReportResponse>(
        `/v1/interview-sessions/${sessionId}/report`,
      ),
      companyRequest<TimelineResponse>(
        `/v1/interview-sessions/${sessionId}/timeline`,
      ),
    ])
      .then(([nextReport, nextTimeline]) => {
        if (active) {
          setReport(nextReport);
          setTimeline(nextTimeline);
        }
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [authenticated, sessionId]);

  if (!authenticated) {
    return <Navigate replace to="/auth/login" />;
  }

  const reviewApi: ReviewApi = {
    async overrideAssessment(reportItemId, assessmentState, reason) {
      if (!report) return;
      await companyRequest(
        `/v1/reports/${report.report_id}/items/${reportItemId}/reviews`,
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey("override") },
          body: JSON.stringify({
            assessment_state: assessmentState,
            reason,
          }),
        },
      );
    },
    async addBookmark(targetId, value) {
      await companyRequest(
        `/v1/interview-sessions/${sessionId}/review-artifacts`,
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey("bookmark") },
          body: JSON.stringify({
            review_type: "bookmark",
            target_id: targetId,
            value,
          }),
        },
      );
    },
    async recordFinalDecision(targetInvitationId, decision, reason) {
      await companyRequest(
        `/v1/invitations/${targetInvitationId}/final-decisions`,
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey("decision") },
          body: JSON.stringify({ decision, reason }),
        },
      );
    },
    async requestDeletion(scopeId, reason) {
      await companyRequest("/v1/privacy/deletion-requests", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("deletion") },
        body: JSON.stringify({
          scope_type: "invitation",
          scope_id: scopeId,
          reason,
        }),
      });
    },
  };

  return (
    <main>
      <h1>지원자 검토</h1>
      {!report || !timeline ? (
        <p role="status">
          {error
            ? "리포트를 불러올 수 없습니다."
            : "리포트를 불러오는 중입니다."}
        </p>
      ) : (
        <>
          <ReportView
            report={{
              summary: report.summary,
              status: report.status,
              items: report.items.map((item) => ({
                reportItemId: item.report_item_id,
                criterionName: item.criterion_id,
                assessmentState: item.assessment_state,
                observation: item.observation,
                evidence: item.evidence.map((evidence) => ({
                  evidenceId: evidence.evidence_id,
                  startMs: evidence.video_start_ms,
                  endMs: evidence.video_end_ms,
                })),
              })),
            }}
            onOverride={(reportItemId, assessmentState) =>
              reviewApi.overrideAssessment(
                reportItemId,
                assessmentState,
                "기업 검토자가 평가 상태를 수정함",
              )
            }
            onSelectEvidence={() => undefined}
          />
          <TimelineView
            entries={timeline.entries.map((entry) => ({
              entryId: entry.entry_id,
              type: entry.entry_type,
              startMs: entry.start_ms,
              endMs: entry.end_ms,
              text: entry.text,
            }))}
            playbackStatus={timeline.playback.status}
            playbackUrl={timeline.playback.url ?? undefined}
            onSeek={() => undefined}
          />
          <HumanReview
            api={reviewApi}
            invitationId={invitationId}
            deletion={{
              status: "not_requested",
              verifiedTargets: 0,
              expectedTargets: 0,
            }}
          />
        </>
      )}
    </main>
  );
}

export function CompanyLoginRoute() {
  const [error, setError] = useState(false);

  async function login() {
    if (!AUTH_CONFIG) return;
    try {
      await beginCompanyLogin(AUTH_CONFIG, {
        sessionStorage,
        navigate: (location) => window.location.assign(location),
      });
    } catch {
      setError(true);
    }
  }

  return (
    <main>
      <h1>기업 로그인</h1>
      <p>기업 계정으로 로그인해 채용 캠페인과 지원자 검토를 시작합니다.</p>
      {AUTH_CONFIG ? (
        <button type="button" onClick={() => void login()}>
          Cognito로 로그인
        </button>
      ) : (
        <p role="status">로컬 개발 인증을 사용하고 있습니다.</p>
      )}
      {error && <p role="alert">로그인을 시작할 수 없습니다.</p>}
    </main>
  );
}

export function CompanyAuthCallbackRoute() {
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!AUTH_CONFIG) {
      navigate("/hiring", { replace: true });
      return;
    }
    void completeCompanyLogin(AUTH_CONFIG, search, {
      sessionStorage,
      localStorage,
      fetcher: fetch,
    })
      .then(() => navigate("/hiring", { replace: true }))
      .catch(() => setError(true));
  }, [navigate, search]);

  return (
    <main>
      <h1>기업 로그인 확인</h1>
      <p role={error ? "alert" : "status"}>
        {error
          ? "로그인 응답을 확인할 수 없습니다."
          : "기업 계정 로그인을 확인하고 있습니다."}
      </p>
    </main>
  );
}

function companyAuthConfig(): CompanyAuthConfig | null {
  const domain = import.meta.env.VITE_COGNITO_DOMAIN;
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
  const redirectUri = import.meta.env.VITE_COGNITO_REDIRECT_URI;
  if (!domain || !clientId || !redirectUri) return null;
  return { domain, clientId, redirectUri };
}
