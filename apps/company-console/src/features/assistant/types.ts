import type {
  CompanyApplicantInsight,
  CompanyInvitation,
} from "../company/types";

export type InsightByPosition = Readonly<
  Record<string, readonly CompanyApplicantInsight[]>
>;

export type PositionRow = Readonly<{
  positionId: string;
  title: string;
  applicantCount: number;
  reportCount: number;
  averageScore: number | null;
}>;

export type Citation = Readonly<{
  id: string;
  sourceId: string;
  title: string;
  sourceType: string;
  source: string;
  excerpt: string;
  meta: string;
  scopeLabel: string;
  confidence: number;
  rationale: string;
  applicantInvitationId?: string;
}>;

export type RagAnswer = Readonly<{
  paragraphs: readonly string[];
  findings: readonly string[];
  sourceIds: readonly string[];
  citations: readonly Citation[];
  positionRows: readonly PositionRow[];
  degradedMode?: string;
  streaming?: boolean;
}>;

export type ChatMessage =
  | Readonly<{
      id: string;
      role: "user";
      content: string;
    }>
  | Readonly<{
      id: string;
      role: "assistant";
      answer: RagAnswer;
    }>;

export type ChatConversation = Readonly<{
  id: string;
  title: string;
  titleCustomized?: boolean;
  scopeId: string;
  messages: readonly ChatMessage[];
  pending: boolean;
  error?: string;
}>;

export type ApplicantReportPreview = Readonly<{
  invitation: CompanyInvitation;
  insight?: CompanyApplicantInsight;
  positionTitle: string;
  recruitingStageName?: string;
}>;

export const INITIAL_CONVERSATION: ChatConversation = {
  id: "conversation-1",
  title: "새 채용 분석",
  scopeId: "all",
  messages: [],
  pending: false,
};

export const suggestedQuestions = [
  "현재 범위에서 근거가 구체적인 지원자를 정리해줘.",
  "근거가 부족해 추가 검토가 필요한 지원자를 찾아줘.",
  "AWS 운영 경험이 확인된 지원자를 근거와 함께 알려줘.",
  "필수·우대 자격요건의 충족 근거가 뚜렷한 지원자를 정리해줘.",
] as const;
