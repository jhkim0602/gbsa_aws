import { displayApplicant } from "../company/recruitingState";
import type {
  CompanyApplicantInsight,
  CompanyInvitation,
  CompanyPosition,
} from "../company/types";
import type {
  AssistantAnswerResponse,
  AssistantSearchSource,
} from "./api";
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
    findings: citations
      .filter((citation) => citation.sourceType === "평가 기준 리포트")
      .slice(0, 3)
      .map((citation) => citation.meta),
    sourceIds: citations.map((citation) => citation.sourceId),
    citations,
    positionRows,
    ...(response.degradedMode
      ? { degradedMode: response.degradedMode }
      : {}),
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
  const criterionName = readString(source.metadata.criterion_name);
  const applicantDisplayName = readString(
    source.metadata.applicant_display_name,
  );
  const positionTitle = readString(source.metadata.position_title);
  const overallScore = readNumber(source.metadata.overall_score);
  const criterionScore = readNumber(source.metadata.score);
  const sourceType =
    source.documentType === "report_summary"
      ? "지원자 종합 리포트"
      : "평가 기준 리포트";
  const title = invitation
    ? `${displayApplicant(invitation)} · ${criterionName ?? "AI 최종 리포트"}`
    : `${applicantDisplayName ?? "지원자"} · ${
        criterionName ?? "AI 최종 리포트"
      }`;
  const scoreText =
    criterionScore != null
      ? `${criterionName ?? "평가 기준"} ${Math.round(criterionScore)}점`
      : overallScore != null
        ? `종합 ${Math.round(overallScore)}점`
        : insight?.overallScore != null
          ? `종합 ${insight.overallScore}점`
          : "점수 미산정";
  return {
    id: String(ordinal),
    sourceId: source.sourceId,
    title,
    sourceType,
    source: position?.title ?? positionTitle ?? "채용 포지션",
    excerpt: source.excerpt,
    meta: `${scoreText} · 검색 일치도 ${Math.round(source.score * 100)}%`,
    scopeLabel,
    confidence: source.score,
    rationale:
      source.documentType === "report_summary"
        ? "질문과 관련된 지원자의 최종 평가 요약이 검색되어 답변 생성에 사용되었습니다."
        : "질문과 관련된 평가 기준의 관찰 내용과 근거가 검색되어 답변 생성에 사용되었습니다.",
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

export function conversationTitle(question: string) {
  return question.length > 28 ? `${question.slice(0, 28)}…` : question;
}
