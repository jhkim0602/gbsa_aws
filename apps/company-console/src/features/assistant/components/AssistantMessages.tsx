import {
  BarChart3,
  Check,
  ChevronRight,
  FileSearch,
  LockKeyhole,
  Search,
} from "lucide-react";

import type { ChatMessage, Citation, PositionRow, RagAnswer } from "../types";
import { WhyYouAssistantAvatar } from "./WhyYouAssistantAvatar";

const THINKING_LABEL = "생각 중...";
const THINKING_CHARACTERS = Array.from(THINKING_LABEL);

export function MessageList({
  messages,
  scopeLabel,
  pending,
  error,
  onSelectCitation,
}: {
  messages: readonly ChatMessage[];
  scopeLabel: string;
  pending: boolean;
  error?: string;
  onSelectCitation(sourceId: string): void;
}) {
  const lastMessage = messages.at(-1);
  const waitingForFirstChunk = pending && lastMessage?.role === "user";
  return (
    <div className="mx-auto w-full max-w-[760px] py-8">
      <div className="mb-7 flex items-center justify-center">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1.5 text-[8px] font-medium text-brand">
          <LockKeyhole size={10} aria-hidden="true" />
          분석 범위 · {scopeLabel}
        </span>
      </div>
      <div
        className="mx-auto mb-7 flex max-w-[620px] items-center justify-center gap-2 rounded-xl border border-[color-mix(in_srgb,var(--color-brand)_18%,var(--color-border))] bg-transparent px-3 py-2 text-center text-[9px] leading-[1.55] text-muted"
        role="status"
      >
        <LockKeyhole size={11} className="shrink-0" aria-hidden="true" />
        <span>
          현재 대화의 데이터 검색 범위는 {scopeLabel}로 고정되었습니다. 다른
          범위를 검색하려면 새 채팅을 시작하세요.
        </span>
      </div>
      <div className="grid gap-9">
        {messages.map((message) =>
          message.role === "user" ? (
            <div className="flex justify-end" key={message.id}>
              <p className="max-w-[78%] rounded-[10px] border-0 bg-brand-soft px-4 py-2.5 text-[12px] leading-[1.65] text-ink">
                {message.content}
              </p>
            </div>
          ) : (
            <AssistantMessage
              key={message.id}
              answer={message.answer}
              onSelectCitation={onSelectCitation}
            />
          ),
        )}
        {waitingForFirstChunk ? <AssistantPending /> : null}
        {error ? (
          <p
            className="ml-11 rounded-xl border border-danger/20 bg-danger/5 px-4 py-3 text-[10px] text-danger"
            role="alert"
          >
            {error}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function AssistantPending() {
  return (
    <div
      className="grid grid-cols-[32px_minmax(0,1fr)] gap-3"
      role="status"
      aria-label="답변 생성 중"
    >
      <WhyYouAssistantAvatar state="searching" />
      <div className="pt-3">
        <ThinkingText />
      </div>
    </div>
  );
}

function AssistantMessage({
  answer,
  onSelectCitation,
}: {
  answer: RagAnswer;
  onSelectCitation(sourceId: string): void;
}) {
  return (
    <article
      className="grid grid-cols-[32px_minmax(0,1fr)] gap-3"
      aria-live={answer.streaming ? "polite" : undefined}
    >
      <WhyYouAssistantAvatar
        state={
          answer.streaming
            ? answer.paragraphs.length
              ? "thinking"
              : "searching"
            : "complete"
        }
      />
      <div className="min-w-0 pt-0.5">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="text-[9px] font-semibold text-ink-secondary">
            AI 채용 어시스턴트
          </span>
          {answer.streaming ? (
            <ThinkingText compact />
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-2 py-1 text-[8px] font-semibold text-success">
              <Check size={9} aria-hidden="true" />
              {sourceStatus(answer)}
            </span>
          )}
          {showDegradedBadge(answer.degradedMode) ? (
            <span className="rounded-full bg-warning-soft px-2 py-1 text-[8px] font-semibold text-warning">
              제한된 답변
            </span>
          ) : null}
        </div>

        <div className="grid gap-3">
          {answer.paragraphs.map((paragraph, index) => (
            <p
              className="whitespace-pre-line text-[12px] leading-[1.85] text-ink-secondary"
              key={`${index}-${paragraph}`}
            >
              {paragraph}
              {answer.streaming && index === answer.paragraphs.length - 1 ? (
                <span
                  className="ml-0.5 inline-block h-[1.1em] w-[2px] animate-pulse translate-y-[2px] bg-brand"
                  aria-hidden="true"
                />
              ) : null}
            </p>
          ))}
          {answer.streaming && !answer.paragraphs.length ? (
            <p className="text-[11px] text-muted" role="status">
              관련 리포트와 면접 근거를 조회하고 있습니다.
            </p>
          ) : null}
        </div>

        {!answer.streaming && answer.findings.length ? (
          <div className="mt-5 border-y border-border-muted py-1">
            <div className="flex items-center gap-2 px-1 py-3">
              <Search
                size={13}
                className="text-ink-secondary"
                aria-hidden="true"
              />
              <strong className="text-[10px] text-ink">
                검색 결과에서 확인된 핵심
              </strong>
            </div>
            <ul className="grid gap-2.5 px-1 pb-3.5">
              {answer.findings.map((finding) => (
                <li
                  className="grid grid-cols-[6px_minmax(0,1fr)] gap-2.5 text-[10px] leading-[1.65] text-ink-secondary"
                  key={finding}
                >
                  <span className="mt-[6px] size-1.5 rounded-full bg-brand" />
                  {finding}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {!answer.streaming && answer.positionRows.length > 1 ? (
          <details className="group mt-5 border-y border-border-muted">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between px-1 text-[10px] font-semibold text-ink-secondary hover:bg-brand-soft">
              <span className="flex items-center gap-2">
                <BarChart3
                  size={14}
                  className="text-ink-secondary"
                  aria-hidden="true"
                />
                포지션 비교 데이터
              </span>
              <ChevronRight
                className="text-muted transition-transform group-open:rotate-90"
                size={14}
                aria-hidden="true"
              />
            </summary>
            <PositionComparison rows={answer.positionRows} />
          </details>
        ) : null}

        {!answer.streaming && answer.citations.length ? (
          <div className="mt-5">
            <p className="mb-2 flex items-center gap-1.5 text-[8px] font-bold tracking-[0.06em] text-muted uppercase">
              <FileSearch size={11} aria-hidden="true" />
              답변에 사용된 근거
            </p>
            <div className="flex flex-wrap gap-2">
              {answer.citations.map((citation) => (
                <CitationButton
                  citation={citation}
                  key={citation.sourceId}
                  onSelect={onSelectCitation}
                />
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </article>
  );
}

function sourceStatus(answer: RagAnswer) {
  if (
    answer.degradedMode === "no_sources" ||
    answer.degradedMode === "search_unavailable"
  ) {
    return "확인 가능한 근거 없음";
  }
  if (answer.degradedMode === "generation_unavailable") {
    return `${answer.citations.length}개 관련 근거 확인`;
  }
  return `${answer.citations.length}개 소스 검색 완료`;
}

function showDegradedBadge(degradedMode: string | undefined) {
  return Boolean(
    degradedMode &&
    !["no_sources", "search_unavailable", "generation_unavailable"].includes(
      degradedMode,
    ),
  );
}

function ThinkingText({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center font-semibold text-brand ${compact ? "text-[8px]" : "text-[10px]"}`}
      aria-label={THINKING_LABEL}
    >
      <span className="inline-flex" aria-hidden="true">
        {THINKING_CHARACTERS.map((character, index) => (
          <span
            className="why-you-thinking-letter inline-block"
            key={`${character}-${index}`}
            style={{ animationDelay: `${index * 75}ms` }}
          >
            {character === " " ? "\u00a0" : character}
          </span>
        ))}
      </span>
    </span>
  );
}

function PositionComparison({ rows }: { rows: readonly PositionRow[] }) {
  return (
    <div className="overflow-x-auto border-t border-border-muted px-1 pb-3">
      <div className="grid min-w-[420px] grid-cols-[minmax(160px,1fr)_60px_60px_54px] py-2.5 text-[8px] font-medium text-muted">
        <span>포지션</span>
        <span className="text-right">지원자</span>
        <span className="text-right">리포트</span>
        <span className="text-right">평균</span>
      </div>
      {rows.map((row) => (
        <div
          className="grid min-h-10 min-w-[420px] grid-cols-[minmax(160px,1fr)_60px_60px_54px] items-center border-t border-border-muted text-[9px]"
          key={row.positionId}
        >
          <strong className="truncate font-medium text-ink-secondary">
            {row.title}
          </strong>
          <span className="text-right text-muted">{row.applicantCount}</span>
          <span className="text-right text-muted">{row.reportCount}</span>
          <span className="text-right font-mono font-semibold text-ink">
            {row.averageScore == null ? "–" : row.averageScore}
          </span>
        </div>
      ))}
    </div>
  );
}

function CitationButton({
  citation,
  onSelect,
}: {
  citation: Citation;
  onSelect(sourceId: string): void;
}) {
  return (
    <button
      className="group inline-flex min-h-8 max-w-full items-center gap-2 rounded-lg border border-border bg-surface px-2.5 text-left text-[9px] text-ink-secondary hover:border-brand hover:bg-brand-soft hover:text-brand"
      type="button"
      aria-label={`근거 ${citation.id}: ${citation.title}`}
      onClick={() => onSelect(citation.sourceId)}
    >
      <span className="grid size-5 shrink-0 place-items-center rounded-md bg-brand-soft font-mono text-[8px] font-semibold text-brand">
        {citation.id}
      </span>
      <span className="truncate">{citation.title}</span>
      <ChevronRight size={11} className="shrink-0" aria-hidden="true" />
    </button>
  );
}
