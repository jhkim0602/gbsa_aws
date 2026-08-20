import { useEffect, useState } from "react";
import {
  Link,
  Navigate,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";

import {
  beginCompanyLogin,
  beginCompanySignup,
  completeCompanyLogin,
  getCompanyAccessToken,
} from "../features/company/cognitoAuth";
import {
  ApplicantDetail,
  ApplicantManagement,
  CompanyOverview,
  CompanyPositions,
  PositionOperations,
  type CompanyApplicantInsight,
  type CompanyApplicantReport,
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
import {
  ReviewWorkspace,
  type ReviewApi,
  type ReviewReport,
  type ReviewTimeline,
} from "../features/review";
import {
  mockCompanyOperationsApi,
  mockInvitationEmailTemplateApi,
  mockPositionInvitationApi,
} from "../mocks/recruitingApi";
import type { components } from "@iep/contracts/generated/typescript/openapi";

import {
  companyAuthConfig as AUTH_CONFIG,
  companyRequest,
  companyWorkspaceApi,
  idempotencyKey,
} from "./api/companyClient";
import {
  ASYNC_STATE,
  PAGE_EYEBROW_IN_HEADER,
  PAGE_HEADER,
  PAGE_HEADER_TEXT,
  PAGE_HEADER_TITLE,
} from "./styles/primitives";

const AUTH_PAGE = "grid min-h-screen place-items-center bg-surface-muted p-6";
const AUTH_PANEL =
  "grid w-[min(100%,400px)] gap-4 rounded-lg border border-border bg-white p-7 shadow-float";
// `.auth-panel p` — every paragraph in the panel, including the status and error lines.
const AUTH_TEXT = "text-[13px] leading-[1.6] text-muted";
const AUTH_PRIMARY_ACTION =
  "min-h-[38px] rounded-lg border border-brand bg-brand font-[650] text-white" +
  " hover:bg-brand-strong";
const BRAND_MARK =
  "grid size-9 flex-[0_0_36px] place-items-center rounded-panel bg-brand text-[12px]" +
  " font-extrabold text-white";

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
          interview_capacity: input.interviewCapacity,
          interview_at: input.interviewAt
            ? new Date(input.interviewAt).toISOString()
            : undefined,
          recruitment_start_at: input.recruitmentStartAt,
          recruitment_end_at: input.recruitmentEndAt,
          submission_requirements: input.submissionRequirements.map(
            (requirement) => ({
              material_type: requirement.materialType,
              required: requirement.required,
              enabled: requirement.enabled,
              instructions: null,
            }),
          ),
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
        persona_definition: {
          name: input.personaDefinition.name,
          tone: input.personaDefinition.tone,
          voice_id: input.personaDefinition.voiceId,
        },
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
  async requestApplicantDeletion(invitationId) {
    await companyRequest<components["schemas"]["DeletionStatus"]>(
      "/v1/privacy/deletion-requests",
      {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("applicant-deletion") },
        body: JSON.stringify({
          scope_type: "invitation",
          scope_id: invitationId,
          reason: "company_user_requested_applicant_deletion",
        }),
      },
    );
  },
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
          interview_capacity: input.interviewCapacity ?? null,
          interview_at: input.interviewAt
            ? new Date(input.interviewAt).toISOString()
            : null,
          recruitment_start_at: input.recruitmentStartAt ?? null,
          recruitment_end_at: input.recruitmentEndAt ?? null,
          submission_requirements: input.submissionRequirements.map(
            (requirement) => ({
              material_type: requirement.materialType,
              required: requirement.required,
              enabled: requirement.enabled,
              instructions: requirement.instructions ?? null,
            }),
          ),
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
      interviewCapacity: result.interview_capacity,
      interviewAt: result.interview_at,
      recruitmentStartAt: result.recruitment_start_at,
      recruitmentEndAt: result.recruitment_end_at,
      submissionRequirements: (
        result as typeof result & {
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
        }
      ).submission_requirements.map((requirement) => ({
        materialType: requirement.material_type,
        required: requirement.required,
        enabled: requirement.enabled,
        instructions: requirement.instructions,
      })),
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
      personaDefinition: toCompanyPersona(version.persona_definition),
    }));
  },
  async listSubmissions(invitationId) {
    const result = await companyRequest<
      Array<{
        submission_id: string;
        material_type:
          | "resume"
          | "cover_letter"
          | "career_description"
          | "projects"
          | "portfolio";
        source_type: string;
        original_filename: string | null;
        source_url: string | null;
        status: string;
        failure_code: string | null;
        impact_summary: string | null;
        created_at: string;
      }>
    >(`/v1/company/invitations/${invitationId}/submissions`);
    return result.map((submission) => ({
      submissionId: submission.submission_id,
      materialType: submission.material_type,
      sourceType: submission.source_type,
      originalFilename: submission.original_filename,
      sourceUrl: submission.source_url,
      status: submission.status,
      failureCode: submission.failure_code,
      impactSummary: submission.impact_summary,
      createdAt: submission.created_at,
    }));
  },
  async listApplicantInsights(positionId) {
    const invitations = await positionInvitationApi.listInvitations(positionId);
    const completed = invitations.filter(
      (invitation) => invitation.interviewSessionId,
    );
    const reports = await Promise.allSettled(
      completed.map(async (invitation) => {
        const sessionId = invitation.interviewSessionId;
        if (!sessionId) return null;
        const report = await companyRequest<ReportResponse>(
          `/v1/interview-sessions/${sessionId}/report`,
        );
        return toApplicantInsight(
          invitation.invitationId,
          sessionId,
          invitation.competencyModelVersionId,
          toReviewReport(report),
        );
      }),
    );
    return reports.flatMap((result) =>
      result.status === "fulfilled" && result.value ? [result.value] : [],
    );
  },
  async getApplicantReport(
    interviewSessionId,
    invitationId,
    competencyModelVersionId,
  ) {
    const [report, timeline] = await Promise.all([
      companyRequest<ReportResponse>(
        `/v1/interview-sessions/${interviewSessionId}/report`,
      ),
      companyRequest<TimelineResponse>(
        `/v1/interview-sessions/${interviewSessionId}/timeline`,
      ),
    ]);
    const mappedReport = toReviewReport(report);
    return {
      insight: toApplicantInsight(
        invitationId,
        interviewSessionId,
        competencyModelVersionId,
        mappedReport,
      ),
      report: mappedReport,
      timeline: toReviewTimeline(timeline),
    } satisfies CompanyApplicantReport;
  },
  publishCriteria: hiringApi.publishCriteria,
};

function toCompanyPersona(value: unknown) {
  if (!value || typeof value !== "object") return undefined;
  const persona = value as Record<string, unknown>;
  const tone = persona.tone;
  if (
    typeof persona.name !== "string" ||
    typeof persona.voice_id !== "string" ||
    !["calm", "friendly", "analytical", "concise"].includes(String(tone))
  ) {
    return undefined;
  }
  return {
    name: persona.name,
    tone: tone as "calm" | "friendly" | "analytical" | "concise",
    voiceId: persona.voice_id,
  };
}

function toReviewReport(report: ReportResponse): ReviewReport {
  return {
    summary: report.summary,
    status: report.status,
    overallScore: report.overall_score ?? null,
    unscoredCriteriaCount: report.unscored_criteria_count ?? 0,
    items: report.items.map((item) => ({
      reportItemId: item.report_item_id,
      criterionId: item.criterion_id,
      criterionName: item.criterion_name || item.criterion_id,
      assessmentState: item.assessment_state,
      observation: item.observation,
      followUpQuestion: item.follow_up_question ?? null,
      averageScore: item.average_score ?? null,
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
        transcriptSegmentId: evidence.transcript_segment_id,
        startMs: evidence.video_start_ms,
        endMs: evidence.video_end_ms,
        observation: evidence.observation,
        rationale: evidence.rationale,
        sufficiency: evidence.sufficiency,
      })),
    })),
  };
}

function toReviewTimeline(timeline: TimelineResponse): ReviewTimeline {
  return {
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
            sourceReferences: entry.question_rationale.source_references.map(
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
  };
}

function toApplicantInsight(
  invitationId: string,
  interviewSessionId: string,
  competencyModelVersionId: string,
  report: ReviewReport,
): CompanyApplicantInsight {
  const criteria = report.items.map((item) => ({
    criterionId: item.criterionId,
    criterionName: item.criterionName,
    score: item.averageScore,
    assessmentState: item.assessmentState,
    evidenceCount: item.evidence.length,
  }));
  return {
    invitationId,
    interviewSessionId,
    competencyModelVersionId,
    overallScore: report.overallScore,
    unscoredCriteriaCount: report.unscoredCriteriaCount,
    evidenceCoverage: criteria.length
      ? Math.round(
          (criteria.filter((criterion) => criterion.evidenceCount > 0).length /
            criteria.length) *
            100,
        )
      : 0,
    summary: report.summary,
    criteria,
  };
}

const useMockRecruitingData =
  import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_DATA === "true";
const recruitingOperationsApi = useMockRecruitingData
  ? mockCompanyOperationsApi
  : companyOperationsApi;
const recruitingInvitationApi = useMockRecruitingData
  ? mockPositionInvitationApi
  : positionInvitationApi;
const recruitingTemplateApi = useMockRecruitingData
  ? mockInvitationEmailTemplateApi
  : invitationEmailTemplateApi;

type ReportResponse = components["schemas"]["ReportView"];

type TimelineResponse = components["schemas"]["TimelineView"];

export function CompanyHomeRoute() {
  if (AUTH_CONFIG && !getCompanyAccessToken(localStorage)) {
    return <Navigate replace to="/auth/login" />;
  }
  return <CompanyOverview api={recruitingOperationsApi} />;
}

export function CompanyPositionsRoute() {
  if (AUTH_CONFIG && !getCompanyAccessToken(localStorage)) {
    return <Navigate replace to="/auth/login" />;
  }
  return <CompanyPositions api={recruitingOperationsApi} />;
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
      api={recruitingOperationsApi}
      invitationApi={recruitingInvitationApi}
      templateApi={recruitingTemplateApi}
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
  return <ApplicantManagement api={recruitingOperationsApi} />;
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
      api={recruitingOperationsApi}
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
        <section className="min-w-0">
          {/* `.review-workspace .page-header { display: none }` under `@media print`. */}
          <header className={`${PAGE_HEADER} print:hidden`}>
            <div>
              <p className={PAGE_EYEBROW_IN_HEADER}>Interview evidence</p>
              <h1 className={PAGE_HEADER_TITLE}>지원자 검토</h1>
              <p className={PAGE_HEADER_TEXT}>
                AI 분석과 실제 답변 구간을 불러오고 있습니다.
              </p>
            </div>
          </header>
          <div className={ASYNC_STATE} role={error ? "alert" : "status"}>
            <p className="text-[12px]">
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
          report={toReviewReport(report)}
          timeline={toReviewTimeline(timeline)}
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
    <main className={AUTH_PAGE}>
      <section className={AUTH_PANEL}>
        <span className={BRAND_MARK} aria-hidden="true">
          G
        </span>
        <h1>기업 로그인</h1>
        <p className={AUTH_TEXT}>
          기업 계정으로 로그인해 채용 포지션과 지원자 검토를 시작합니다.
        </p>
        {AUTH_CONFIG ? (
          <button
            className={AUTH_PRIMARY_ACTION}
            type="button"
            onClick={() => void login()}
          >
            로그인
          </button>
        ) : (
          <p className={AUTH_TEXT} role="status">
            로컬 개발 인증을 사용하고 있습니다.
          </p>
        )}
        <p className={`${AUTH_TEXT} text-center`}>
          처음 이용하시나요?{" "}
          <Link className="font-[650] text-brand" to="/auth/signup">
            회원가입
          </Link>
        </p>
        {error && (
          <p className={AUTH_TEXT} role="alert">
            로그인을 시작할 수 없습니다.
          </p>
        )}
      </section>
    </main>
  );
}

export function CompanySignupRoute() {
  const [error, setError] = useState(false);

  async function signup() {
    if (!AUTH_CONFIG) return;
    try {
      await beginCompanySignup(AUTH_CONFIG, {
        sessionStorage,
        navigate: (location) => window.location.assign(location),
      });
    } catch {
      setError(true);
    }
  }

  return (
    <main className={AUTH_PAGE}>
      <section className={AUTH_PANEL}>
        <span className={BRAND_MARK} aria-hidden="true">
          G
        </span>
        <h1>기업 회원가입</h1>
        <p className={AUTH_TEXT}>
          기업 계정을 만들고 바로 채용 운영을 시작하세요.
        </p>
        {AUTH_CONFIG ? (
          <button
            className={AUTH_PRIMARY_ACTION}
            type="button"
            onClick={() => void signup()}
          >
            기업 계정 만들기
          </button>
        ) : (
          <p className={AUTH_TEXT} role="status">
            배포된 데모 환경에서 회원가입할 수 있습니다.
          </p>
        )}
        <p className={`${AUTH_TEXT} text-center`}>
          이미 계정이 있나요?{" "}
          <Link className="font-[650] text-brand" to="/auth/login">
            로그인
          </Link>
        </p>
        {error && (
          <p className={AUTH_TEXT} role="alert">
            회원가입을 시작할 수 없습니다.
          </p>
        )}
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
      // Bound, because `completeCompanyLogin` calls this as `dependencies.fetcher(...)`,
      // which would set `this` to the dependencies object -- and `fetch` throws
      // `TypeError: Illegal invocation` unless `this` is the window. Passing it bare made
      // every hosted login fail at the token exchange with "로그인 응답을 확인할 수 없습니다",
      // indistinguishable from a rejected credential. The unit suite injects a mock, which
      // ignores `this`, so only a browser can catch it.
      fetcher: (...args) => fetch(...args),
    })
      .then(() => navigate("/hiring", { replace: true }))
      .catch(() => setError(true));
  }, [navigate, search]);

  return (
    <main className={AUTH_PAGE}>
      <section className={AUTH_PANEL}>
        <span className={BRAND_MARK} aria-hidden="true">
          G
        </span>
        <h1>기업 로그인 확인</h1>
        <p className={AUTH_TEXT} role={error ? "alert" : "status"}>
          {error
            ? "로그인 응답을 확인할 수 없습니다."
            : "기업 계정 로그인을 확인하고 있습니다."}
        </p>
      </section>
    </main>
  );
}
