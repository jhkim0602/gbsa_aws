import { displayApplicant } from "../company/recruitingState";
import type {
  CompanyApplicantInsight,
  CompanyInvitation,
  CompanyPosition,
} from "../company/types";
import type { AssistantAnswerResponse, AssistantSearchSource } from "./api";
import type {
  ApplicantReportPreview,
  Citation,
  InsightByPosition,
  PositionRow,
  RagAnswer,
} from "./types";

export function buildPositionRows(
  positions: readonly CompanyPosition[],
  invitations: readonly CompanyInvitation[],
  insightsByPosition: InsightByPosition,
): PositionRow[] {
  const invitationCountByPosition = new Map<string, number>();
  for (const invitation of invitations) {
    invitationCountByPosition.set(
      invitation.positionId,
      (invitationCountByPosition.get(invitation.positionId) ?? 0) + 1,
    );
  }
  return positions.map((position) => {
    const positionInsights = insightsByPosition[position.positionId] ?? [];
    const scores = positionInsights.flatMap((insight) =>
      insight.overallScore == null ? [] : [insight.overallScore],
    );
    return {
      positionId: position.positionId,
      title: position.title,
      applicantCount: invitationCountByPosition.get(position.positionId) ?? 0,
      reportCount: positionInsights.length,
      averageScore: scores.length
        ? Math.round(
            scores.reduce((sum, score) => sum + score, 0) / scores.length,
          )
        : null,
    };
  });
}

export function buildApplicantReportPreviews(
  positions: readonly CompanyPosition[],
  invitations: readonly CompanyInvitation[],
  insightsByPosition: InsightByPosition,
) {
  const positionTitleById = new Map(
    positions.map((position) => [position.positionId, position.title]),
  );
  const insightByInvitationId = new Map<string, CompanyApplicantInsight>();
  Object.values(insightsByPosition).forEach((insights) => {
    insights.forEach((insight) => {
      insightByInvitationId.set(insight.invitationId, insight);
    });
  });
  const previews = new Map<string, ApplicantReportPreview>();
  invitations.forEach((invitation) => {
    const insight = insightByInvitationId.get(invitation.invitationId);
    if (!insight) return;
    previews.set(invitation.invitationId, {
      invitation,
      insight,
      positionTitle:
        positionTitleById.get(invitation.positionId) ?? "채용 포지션",
    });
  });
  return previews;
}

export function toRagAnswer({
  response,
  scopeLabel,
  positionRows,
  positions,
  invitations,
  insightsByPosition,
}: {
  response: AssistantAnswerResponse;
  scopeLabel: string;
  positionRows: readonly PositionRow[];
  positions: readonly CompanyPosition[];
  invitations: readonly CompanyInvitation[];
  insightsByPosition: InsightByPosition;
}): RagAnswer {
  const positionById = new Map(
    positions.map((position) => [position.positionId, position]),
  );
  const invitationById = new Map(
    invitations.map((invitation) => [invitation.invitationId, invitation]),
  );
  const insightByInvitationId = new Map<string, CompanyApplicantInsight>();
  Object.values(insightsByPosition).forEach((insights) => {
    insights.forEach((insight) => {
      insightByInvitationId.set(insight.invitationId, insight);
    });
  });
  const citations = response.sources.map((source, index) =>
    toCitation({
      source,
      ordinal: index + 1,
      scopeLabel,
      positionById,
      invitationById,
      insightByInvitationId,
    }),
  );
  return {
    paragraphs: splitParagraphs(response.answer),
    findings: [
      ...new Set(
        citations
          .filter((citation) => citation.sourceType === "자격요건·답변 근거")
          .map((citation) => citation.meta),
      ),
    ].slice(0, 3),
    sourceIds: citations.map((citation) => citation.sourceId),
    citations,
    positionRows,
    ...(response.degradedMode ? { degradedMode: response.degradedMode } : {}),
  };
}

export function toStreamingRagAnswer(
  answer: string,
  positionRows: readonly PositionRow[],
): RagAnswer {
  return {
    paragraphs: answer ? splitParagraphs(answer) : [],
    findings: [],
    sourceIds: [],
    citations: [],
    positionRows,
    streaming: true,
  };
}

function toCitation({
  source,
  ordinal,
  scopeLabel,
  positionById,
  invitationById,
  insightByInvitationId,
}: {
  source: AssistantSearchSource;
  ordinal: number;
  scopeLabel: string;
  positionById: ReadonlyMap<string, CompanyPosition>;
  invitationById: ReadonlyMap<string, CompanyInvitation>;
  insightByInvitationId: ReadonlyMap<string, CompanyApplicantInsight>;
}): Citation {
  const position = positionById.get(source.positionId);
  const invitation = invitationById.get(source.invitationId);
  const insight = insightByInvitationId.get(source.invitationId);
  const requirementStatement = readString(
    source.metadata.requirement_statement,
  );
  const applicantDisplayName = readString(
    source.metadata.applicant_display_name,
  );
  const positionTitle = readString(source.metadata.position_title);
  const requirementType = readString(source.metadata.requirement_type);
  const requirementStatus = readString(source.metadata.requirement_status);
  const assessments = insight?.requirementAssessments ?? [];
  const statusCounts = assessments.reduce(
    (counts, assessment) => {
      const sourceStatus =
        assessment.humanOverride?.status ?? assessment.status;
      const status = sourceStatus === "unknown" ? "not_met" : sourceStatus;
      counts[status] += 1;
      return counts;
    },
    { met: 0, partially_met: 0, not_met: 0 },
  );
  const sourceType =
    source.documentType === "report_summary"
      ? "자격요건 종합 판정"
      : "자격요건·답변 근거";
  const applicantName = invitation
    ? displayApplicant(invitation)
    : (applicantDisplayName ?? "지원자");
  const title = `${applicantName} · ${
    source.documentType === "report_summary"
      ? "자격요건 종합 판정"
      : (requirementStatement ?? "답변 근거")
  }`;
  const metadataTotal = readNumber(source.metadata.requirements_total) ?? 0;
  const requirementSummary = assessments.length
    ? `충족 ${statusCounts.met} / 전체 ${assessments.length} · 부분 충족 ${statusCounts.partially_met} · 미충족 ${statusCounts.not_met}`
    : metadataTotal
      ? `충족 ${readNumber(source.metadata.requirements_met) ?? 0} / 전체 ${metadataTotal} · 부분 충족 ${readNumber(source.metadata.requirements_partially_met) ?? 0} · 미충족 ${(readNumber(source.metadata.requirements_not_met) ?? 0) + (readNumber(source.metadata.requirements_unknown) ?? 0)}`
      : "자격요건 판정 대기";
  const requirementItemMeta =
    requirementType && requirementStatus
      ? `${requirementType === "required" ? "필수" : "우대"} · ${requirementStatusLabel(requirementStatus)}`
      : requirementSummary;
  return {
    id: String(ordinal),
    sourceId: source.sourceId,
    title,
    sourceType,
    source: position?.title ?? positionTitle ?? "채용 포지션",
    excerpt: source.excerpt,
    meta:
      source.documentType === "report_summary"
        ? requirementSummary
        : requirementItemMeta,
    scopeLabel,
    confidence: source.score,
    rationale:
      source.documentType === "report_summary"
        ? "질문과 관련된 지원자의 필수·우대 자격요건 종합 판정과 근거 요약이 검색되어 답변 생성에 사용되었습니다."
        : "질문과 관련된 실제 면접 답변 또는 제출 자료의 근거가 검색되어 답변 생성에 사용되었습니다.",
    applicantInvitationId: source.invitationId,
  };
}

function splitParagraphs(answer: string) {
  const paragraphs = answer
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
  return paragraphs.length ? paragraphs : [answer];
}

function readString(value: unknown) {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function readNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : undefined;
}

function requirementStatusLabel(status: string) {
  return (
    {
      met: "충족",
      partially_met: "부분 충족",
      not_met: "미충족",
      unknown: "미충족",
    }[status] ?? "판정 대기"
  );
}

export function conversationTitle(question: string) {
  return question.length > 28 ? `${question.slice(0, 28)}…` : question;
}
