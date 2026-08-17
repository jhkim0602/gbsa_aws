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
} from "../features/company/cognitoAuth";
import {
  ApplicantDetail,
  ApplicantManagement,
  CompanyOverview,
  CompanyPositions,
  PositionOperations,
  type CompanyOperationsApi,
} from "../features/company";
import {
  type InvitationStatus,
  HiringWorkspace,
  InvitationEmailSettings,
  type InvitationEmailTemplate,
  type InvitationEmailTemplateApi,
  type InvitationEmailTemplateState,
  type PositionInvitationApi,
  type HiringWorkspaceApi,
} from "../features/hiring";
import { ReviewWorkspace, type ReviewApi } from "../features/review";
import type { components } from "@iep/contracts/generated/typescript/openapi";

import {
  companyAuthConfig as AUTH_CONFIG,
  companyRequest,
  companyWorkspaceApi,
  idempotencyKey,
} from "./api/companyClient";

const hiringApi: HiringWorkspaceApi = {
  async createPosition(input) {
    const result = await companyRequest<components["schemas"]["Position"]>(
      "/v1/positions",
      {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("position") },
        body: JSON.stringify({
          title: input.title,
          description: input.description,
          role_type: input.roleType,
          headcount: input.headcount,
          recruitment_start_at: input.recruitmentStartAt,
          recruitment_end_at: input.recruitmentEndAt,
        }),
      },
    );
    return { positionId: result.position_id };
  },
  async publishCriteria(positionId, input) {
    const draft = await companyRequest<
      components["schemas"]["CompetencyModelVersion"]
    >(`/v1/positions/${positionId}/competency-model-versions`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("criteria") },
      body: JSON.stringify({
        job_requirements: input.jobRequirements.map((requirement) => ({
          requirement_type: requirement.requirementType,
          statement: requirement.statement,
          priority: requirement.priority,
          criterion_code: requirement.criterionCode,
        })),
        criteria: input.criteria.map((criterion) => ({
          code: criterion.code,
          name: criterion.name,
          description: criterion.description,
          weight: criterion.weight,
          verification_guide: {
            observable_dimensions:
              criterion.verificationGuide.observableDimensions,
            strong_answer_signals:
              criterion.verificationGuide.strongAnswerSignals,
            weak_answer_signals: criterion.verificationGuide.weakAnswerSignals,
            follow_up_directions:
              criterion.verificationGuide.followUpDirections,
            max_follow_ups: criterion.verificationGuide.maxFollowUps,
            time_budget_seconds: criterion.verificationGuide.timeBudgetSeconds,
          },
          abstain_guidance: criterion.abstainGuidance,
          common_questions: criterion.commonQuestions,
          required: criterion.required,
        })),
        prohibited_topics: input.prohibitedTopics,
        interview_duration_minutes: input.interviewDurationMinutes,
        interview_level: input.interviewLevel,
      }),
    });
    const published = await companyRequest<
      components["schemas"]["CompetencyModelVersion"]
    >(
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
};

const positionInvitationApi: PositionInvitationApi = {
  async listInvitations(positionId) {
    const result = await companyRequest<
      components["schemas"]["InvitationPage"]
    >(`/v1/positions/${positionId}/invitations?limit=100`);
    return result.items.map((invitation) => ({
      invitationId: invitation.invitation_id,
      positionId: invitation.position_id,
      competencyModelVersionId: invitation.competency_model_version_id,
      applicantEmail: invitation.applicant_email,
      applicantDisplayName: invitation.applicant_display_name,
      status: invitation.status as InvitationStatus,
      expiresAt: invitation.expires_at,
      rowVersion: invitation.row_version,
      analysisStatus: invitation.analysis_status,
      interviewStatus: invitation.interview_status,
      reportStatus: invitation.report_status,
      interviewSessionId: invitation.interview_session_id,
    }));
  },
  async createInvitations(positionId, applicants, expiresInDays) {
    const result = await companyRequest<
      components["schemas"]["InvitationBatchResult"]
    >(`/v1/positions/${positionId}/invitations`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("invitation-batch") },
      body: JSON.stringify({
        applicants: applicants.map((applicant) => ({
          email: applicant.email,
          display_name: applicant.displayName,
        })),
        expires_at: new Date(
          Date.now() + expiresInDays * 86_400_000,
        ).toISOString(),
      }),
    });
    return {
      acceptedCount: result.accepted_count,
      rejectedCount: result.rejected_count,
      invitations: result.invitations.map((invitation) => ({
        invitationId: invitation.invitation_id,
        positionId: invitation.position_id,
        competencyModelVersionId: invitation.competency_model_version_id,
        applicantEmail: invitation.applicant_email,
        applicantDisplayName: invitation.applicant_display_name,
        status: invitation.status as InvitationStatus,
        expiresAt: invitation.expires_at,
        rowVersion: invitation.row_version,
      })),
    };
  },
};

type TemplateResponse = components["schemas"]["InvitationEmailTemplateView"];

function toTemplateState(
  response: TemplateResponse,
): InvitationEmailTemplateState {
  return {
    subject: response.subject,
    headline: response.headline,
    intro: response.intro,
    guides: response.guides,
    ctaLabel: response.cta_label,
    outro: response.outro,
    footer: response.footer,
    brandColor: response.brand_color,
    useApplicantName: response.use_applicant_name,
    emphasizeDeadline: response.emphasize_deadline,
    showSecurityNotice: response.show_security_notice,
    logoUrl: response.logo_url ?? null,
    isPositionOverride: response.is_position_override,
  };
}

function toTemplateBody(template: InvitationEmailTemplate) {
  // logo_url is deliberately not sent: the server derives it from the uploaded logo.
  return JSON.stringify({
    subject: template.subject,
    headline: template.headline,
    intro: template.intro,
    guides: template.guides,
    cta_label: template.ctaLabel,
    outro: template.outro,
    footer: template.footer,
    brand_color: template.brandColor,
    use_applicant_name: template.useApplicantName,
    emphasize_deadline: template.emphasizeDeadline,
    show_security_notice: template.showSecurityNotice,
  });
}

const invitationEmailTemplateApi: InvitationEmailTemplateApi = {
  async getCompanyTemplate() {
    return toTemplateState(
      await companyRequest<TemplateResponse>("/v1/invitation-email-template"),
    );
  },
  async saveCompanyTemplate(template) {
    return toTemplateState(
      await companyRequest<TemplateResponse>("/v1/invitation-email-template", {
        method: "PUT",
        body: toTemplateBody(template),
      }),
    );
  },
  async resetCompanyTemplate() {
    return toTemplateState(
      await companyRequest<TemplateResponse>("/v1/invitation-email-template", {
        method: "DELETE",
      }),
    );
  },
  async getPositionTemplate(positionId) {
    return toTemplateState(
      await companyRequest<TemplateResponse>(
        `/v1/positions/${positionId}/invitation-email-template`,
      ),
    );
  },
  async savePositionTemplate(positionId, template) {
    return toTemplateState(
      await companyRequest<TemplateResponse>(
        `/v1/positions/${positionId}/invitation-email-template`,
        { method: "PUT", body: toTemplateBody(template) },
      ),
    );
  },
  async resetPositionTemplate(positionId) {
    return toTemplateState(
      await companyRequest<TemplateResponse>(
        `/v1/positions/${positionId}/invitation-email-template`,
        { method: "DELETE" },
      ),
    );
  },
  async previewTemplate(template) {
    const result = await companyRequest<
      components["schemas"]["InvitationEmailPreview"]
    >("/v1/invitation-email-template/preview", {
      method: "POST",
      body: toTemplateBody(template),
    });
    return { subject: result.subject, htmlBody: result.html_body };
  },
  async uploadLogo(file) {
    const result = await companyRequest<
      components["schemas"]["CompanyLogoView"]
    >("/v1/invitation-email-template/logo", {
      method: "PUT",
      headers: { "Content-Type": file.type },
      body: file,
    });
    return {
      logoUrl: result.logo_url,
      contentType: result.content_type,
      byteSize: result.byte_size,
    };
  },
  async deleteLogo() {
    await companyRequest("/v1/invitation-email-template/logo", {
      method: "DELETE",
    });
  },
};

const companyOperationsApi: CompanyOperationsApi = {
  ...companyWorkspaceApi,
  listInvitations: positionInvitationApi.listInvitations,
  async updatePosition(input) {
    const result = await companyRequest<components["schemas"]["Position"]>(
      `/v1/positions/${input.positionId}`,
      {
        method: "PATCH",
        headers: { "If-Match-Version": String(input.rowVersion) },
        body: JSON.stringify({
          title: input.title,
          description: input.description,
          role_type: input.roleType ?? null,
          headcount: input.headcount ?? null,
          recruitment_start_at: input.recruitmentStartAt ?? null,
          recruitment_end_at: input.recruitmentEndAt ?? null,
          status: input.status,
        }),
      },
    );
    return {
      positionId: result.position_id,
      title: result.title,
      description: result.description,
      roleType: result.role_type,
      headcount: result.headcount,
      recruitmentStartAt: result.recruitment_start_at,
      recruitmentEndAt: result.recruitment_end_at,
      status: result.status,
      rowVersion: result.row_version,
      createdAt: result.created_at,
    };
  },
  async listCriterionVersions(positionId) {
    const result = await companyRequest<
      components["schemas"]["CompetencyModelVersionPage"]
    >(`/v1/positions/${positionId}/competency-model-versions?limit=100`);
    return result.items.map((version) => ({
      versionId: version.competency_model_version_id,
      positionId: version.position_id,
      versionNumber: version.version_number,
      status: version.status,
      rowVersion: version.row_version,
      publishedAt: version.published_at,
      jobRequirements: version.job_requirements.map((requirement) => ({
        requirementType: requirement.requirement_type,
        statement: requirement.statement,
        priority: requirement.priority,
        criterionCode: requirement.criterion_code,
      })),
      criteria: version.criteria.map((criterion) => ({
        code: criterion.code,
        name: criterion.name,
        description: criterion.description,
        weight: criterion.weight,
        required: criterion.required,
        verificationGuide: {
          observableDimensions:
            criterion.verification_guide.observable_dimensions,
          strongAnswerSignals:
            criterion.verification_guide.strong_answer_signals,
          weakAnswerSignals: criterion.verification_guide.weak_answer_signals,
          followUpDirections: criterion.verification_guide.follow_up_directions,
          maxFollowUps: criterion.verification_guide.max_follow_ups,
          timeBudgetSeconds: criterion.verification_guide.time_budget_seconds,
        },
        abstainGuidance: criterion.abstain_guidance,
        commonQuestions: criterion.common_questions ?? [],
      })),
      prohibitedTopics: version.prohibited_topics,
      interviewDurationMinutes: version.interview_duration_minutes,
      // Versions published before the difficulty toggle existed omit the field.
      interviewLevel: version.interview_level ?? "junior",
    }));
  },
  publishCriteria: hiringApi.publishCriteria,
};

type ReportResponse = components["schemas"]["ReportView"];

type TimelineResponse = components["schemas"]["TimelineView"];

export function CompanyHomeRoute() {
  if (AUTH_CONFIG && !getCompanyAccessToken(localStorage)) {
    return <Navigate replace to="/auth/login" />;
  }
  return <CompanyOverview api={companyOperationsApi} />;
}

export function CompanyPositionsRoute() {
  if (AUTH_CONFIG && !getCompanyAccessToken(localStorage)) {
    return <Navigate replace to="/auth/login" />;
  }
  return <CompanyPositions api={companyOperationsApi} />;
}

export function PositionOperationsRoute() {
  const { positionId = "" } = useParams();
  if (AUTH_CONFIG && !getCompanyAccessToken(localStorage)) {
    return <Navigate replace to="/auth/login" />;
  }
  if (!positionId) {
    return <Navigate replace to="/positions" />;
  }
  return (
    <PositionOperations
      positionId={positionId}
      api={companyOperationsApi}
      invitationApi={positionInvitationApi}
      templateApi={invitationEmailTemplateApi}
    />
  );
}

export function InvitationEmailSettingsRoute() {
  if (AUTH_CONFIG && !getCompanyAccessToken(localStorage)) {
    return <Navigate replace to="/auth/login" />;
  }
  return <InvitationEmailSettings api={invitationEmailTemplateApi} />;
}

export function ApplicantManagementRoute() {
  if (AUTH_CONFIG && !getCompanyAccessToken(localStorage)) {
    return <Navigate replace to="/auth/login" />;
  }
  return <ApplicantManagement api={companyOperationsApi} />;
}

export function ApplicantDetailRoute() {
  const { positionId = "", invitationId = "" } = useParams();
  if (AUTH_CONFIG && !getCompanyAccessToken(localStorage)) {
    return <Navigate replace to="/auth/login" />;
  }
  if (!positionId || !invitationId) {
    return <Navigate replace to="/applicants" />;
  }
  return (
    <ApplicantDetail
      positionId={positionId}
      invitationId={invitationId}
      api={companyOperationsApi}
    />
  );
}

export function HiringRoute() {
  const navigate = useNavigate();
  if (AUTH_CONFIG && !getCompanyAccessToken(localStorage)) {
    return <Navigate replace to="/auth/login" />;
  }
  return (
    <HiringWorkspace
      api={hiringApi}
      onOpenPosition={(positionId) => navigate(`/positions/${positionId}`)}
    />
  );
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
    <>
      {!report || !timeline ? (
        <section className="review-workspace">
          <header className="page-header">
            <div>
              <p className="page-eyebrow">Interview evidence</p>
              <h1>지원자 검토</h1>
              <p>AI 분석과 실제 답변 구간을 불러오고 있습니다.</p>
            </div>
          </header>
          <div className="async-state" role={error ? "alert" : "status"}>
            <p>
              {error
                ? "리포트를 불러올 수 없습니다. 잠시 후 다시 시도해 주세요."
                : "리포트와 영상 타임라인을 불러오는 중입니다."}
            </p>
          </div>
        </section>
      ) : (
        <ReviewWorkspace
          sessionId={sessionId}
          invitationId={invitationId}
          api={reviewApi}
          report={{
            summary: report.summary,
            status: report.status,
            overallScore: report.overall_score ?? null,
            unscoredCriteriaCount: report.unscored_criteria_count ?? 0,
            items: report.items.map((item) => ({
              reportItemId: item.report_item_id,
              criterionId: item.criterion_id,
              // Reports generated before the name was captured carry an empty string.
              criterionName: item.criterion_name || item.criterion_id,
              assessmentState: item.assessment_state,
              observation: item.observation,
              followUpQuestion: item.follow_up_question ?? null,
              averageScore: item.average_score ?? null,
              // Absent on reports generated before scoring existed.
              axisAssessments: (item.axis_assessments ?? []).map((axis) => ({
                axis: axis.axis,
                label: axis.label,
                score: axis.score,
                rationale: axis.rationale,
                quotedEvidenceIds: [...axis.quoted_evidence_ids],
              })),
              evidence: item.evidence.map((evidence) => ({
                evidenceId: evidence.evidence_id,
                answerTurnId: evidence.answer_turn_id,
                // Matches a timeline entry id, which is how the report resolves the
                // quoted answer text without asking the API for it again.
                transcriptSegmentId: evidence.transcript_segment_id,
                startMs: evidence.video_start_ms,
                endMs: evidence.video_end_ms,
                observation: evidence.observation,
                rationale: evidence.rationale,
                sufficiency: evidence.sufficiency,
              })),
            })),
          }}
          timeline={{
            entries: timeline.entries.map((entry) => ({
              entryId: entry.entry_id,
              type: entry.entry_type,
              startMs: entry.start_ms,
              endMs: entry.end_ms,
              text: entry.text ?? null,
              questionRationale: entry.question_rationale
                ? {
                    criterionId: entry.question_rationale.criterion_id,
                    verificationTargetType:
                      entry.question_rationale.verification_target_type,
                    objective: entry.question_rationale.objective,
                    questionType: entry.question_rationale.question_type,
                    policyResult: entry.question_rationale.policy_result,
                    sourceReferences:
                      entry.question_rationale.source_references.map(
                        (source) => ({
                          sourceId: source.source_id,
                          sourceType: source.source_type,
                          locator: source.locator,
                          excerpt: source.excerpt,
                        }),
                      ),
                  }
                : null,
            })),
            playback: {
              status: timeline.playback.status,
              url: timeline.playback.url ?? undefined,
            },
          }}
          deletion={{
            status: "not_requested",
            verifiedTargets: 0,
            expectedTargets: 0,
          }}
        />
      )}
    </>
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
    <main className="auth-page">
      <section className="auth-panel">
        <span className="company-brand__mark" aria-hidden="true">
          G
        </span>
        <h1>기업 로그인</h1>
        <p>기업 계정으로 로그인해 채용 포지션과 지원자 검토를 시작합니다.</p>
        {AUTH_CONFIG ? (
          <button type="button" onClick={() => void login()}>
            Cognito로 로그인
          </button>
        ) : (
          <p role="status">로컬 개발 인증을 사용하고 있습니다.</p>
        )}
        {error && <p role="alert">로그인을 시작할 수 없습니다.</p>}
      </section>
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
    <main className="auth-page">
      <section className="auth-panel">
        <span className="company-brand__mark" aria-hidden="true">
          G
        </span>
        <h1>기업 로그인 확인</h1>
        <p role={error ? "alert" : "status"}>
          {error
            ? "로그인 응답을 확인할 수 없습니다."
            : "기업 계정 로그인을 확인하고 있습니다."}
        </p>
      </section>
    </main>
  );
}
