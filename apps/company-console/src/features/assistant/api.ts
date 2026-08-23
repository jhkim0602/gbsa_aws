import type { components } from "@iep/contracts/generated/typescript/openapi";

import { companyFetch, companyRequest } from "../../app/api/companyClient";

export type AssistantScope = "company" | "position";

export type AssistantAnswerRequest = Readonly<{
  scope: AssistantScope;
  positionId?: string;
  query: string;
  limit?: number;
}>;

export type AssistantSearchSource = Readonly<{
  sourceId: string;
  positionId: string;
  applicantId: string;
  invitationId: string;
  reportId: string;
  reportItemId: string | null;
  criterionId: string | null;
  documentType: string;
  excerpt: string;
  score: number;
  scoreComponents: Readonly<Record<string, number>>;
  metadata: Readonly<Record<string, unknown>>;
}>;

export type AssistantAnswerResponse = Readonly<{
  scope: AssistantScope;
  positionId: string | null;
  answer: string;
  sources: readonly AssistantSearchSource[];
  degradedMode: string | null;
}>;

export type RecruitingAssistantApi = Readonly<{
  answerQuestion(
    request: AssistantAnswerRequest,
  ): Promise<AssistantAnswerResponse>;
  streamAnswer(
    request: AssistantAnswerRequest,
    handlers: AssistantStreamHandlers,
    signal?: AbortSignal,
  ): Promise<AssistantAnswerResponse>;
}>;

export type AssistantStreamHandlers = Readonly<{
  onStart?(event: Readonly<{ archivedScope: boolean }>): void;
  onDelta?(delta: string, accumulated: string): void;
  onSources?(sources: readonly AssistantSearchSource[]): void;
}>;

type AssistantAnswerWireResponse =
  components["schemas"]["AssistantAnswerResponse"];
type AssistantSourceWire = components["schemas"]["AssistantSearchSource"];

export const recruitingAssistantApi: RecruitingAssistantApi = {
  async answerQuestion(request) {
    const response = await companyRequest<AssistantAnswerWireResponse>(
      "/v1/assistant/answers",
      {
        method: "POST",
        body: JSON.stringify({
          scope: request.scope,
          position_id: request.positionId,
          query: request.query,
          limit: request.limit ?? 8,
        }),
      },
    );
    return {
      scope: response.scope,
      positionId: response.position_id,
      answer: response.answer,
      degradedMode: response.degraded_mode,
      sources: response.sources.map(toAssistantSource),
    };
  },
  async streamAnswer(request, handlers, signal) {
    const response = await companyFetch("/v1/assistant/answers/stream", {
      method: "POST",
      signal,
      headers: { Accept: "text/event-stream" },
      body: JSON.stringify({
        scope: request.scope,
        position_id: request.positionId,
        query: request.query,
        limit: request.limit ?? 8,
      }),
    });
    if (!response.body) {
      throw new Error("assistant stream response has no body");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let answer = "";
    let sources: readonly AssistantSearchSource[] = [];
    let degradedMode: string | null = null;

    function dispatch(block: string) {
      const lines = block.split("\n");
      const event = lines
        .find((line) => line.startsWith("event:"))
        ?.slice("event:".length)
        .trim();
      const dataText = lines
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice("data:".length).trimStart())
        .join("\n");
      const data = dataText
        ? (JSON.parse(dataText) as Record<string, unknown>)
        : {};
      if (event === "start") {
        handlers.onStart?.({
          archivedScope: data.archived_scope === true,
        });
      } else if (event === "delta" && typeof data.delta === "string") {
        answer += data.delta;
        handlers.onDelta?.(data.delta, answer);
      } else if (event === "sources") {
        const wireSources = Array.isArray(data.sources)
          ? (data.sources as AssistantSourceWire[])
          : [];
        sources = wireSources.map(toAssistantSource);
        degradedMode =
          typeof data.degraded_mode === "string"
            ? data.degraded_mode
            : null;
        handlers.onSources?.(sources);
      }
    }

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary).trim();
        buffer = buffer.slice(boundary + 2);
        if (block) dispatch(block);
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    if (buffer.trim()) dispatch(buffer.trim());
    return {
      scope: request.scope,
      positionId: request.positionId ?? null,
      answer,
      sources,
      degradedMode,
    };
  },
};

function toAssistantSource(source: AssistantSourceWire): AssistantSearchSource {
  return {
    sourceId: source.source_id,
    positionId: source.position_id,
    applicantId: source.applicant_id,
    invitationId: source.invitation_id,
    reportId: source.report_id,
    reportItemId: source.report_item_id,
    criterionId: source.criterion_id,
    documentType: source.document_type,
    excerpt: source.excerpt,
    score: source.score,
    scoreComponents: source.score_components,
    metadata: source.metadata,
  };
}
