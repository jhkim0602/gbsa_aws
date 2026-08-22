import { Check, FileSearch, FileText, UserRound, X } from "lucide-react";

import type { Citation } from "../types";

export function EvidenceDrawer({
  citation,
  citations,
  onClose,
  onOpenReport,
  onSelect,
}: {
  citation: Citation;
  citations: readonly Citation[];
  onClose(): void;
  onOpenReport(invitationId: string): void;
  onSelect(sourceId: string): void;
}) {
  return (
    <div className="fixed inset-[58px_0_0_224px] z-50 mw-760:left-0">
      <button
        className="absolute inset-0 bg-[rgb(26_31_54_/_24%)] backdrop-blur-[1px]"
        type="button"
        aria-label="근거 패널 닫기"
        onClick={onClose}
      />
      <aside
        className="absolute inset-[0_0_0_auto] w-[min(440px,100%)] overflow-y-auto border-l border-border bg-canvas shadow-float"
        aria-label="RAG 답변 근거"
      >
        <header className="sticky top-0 z-10 flex h-15 items-center justify-between border-b border-border-muted bg-[rgb(255_255_255_/_96%)] px-5 backdrop-blur">
          <div>
            <p className="text-[8px] font-medium text-muted">검색 근거</p>
            <h2 className="mt-0.5 text-[13px] font-semibold">
              근거 자세히 보기
            </h2>
          </div>
          <button
            className="grid size-8 place-items-center rounded-lg text-muted hover:bg-surface-muted hover:text-ink"
            type="button"
            aria-label="근거 패널 닫기"
            onClick={onClose}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </header>

        <div className="p-5">
          <EvidenceSummaryTable citation={citation} />
          <EvidenceContext
            excerpt={citation.excerpt}
            rationale={citation.rationale}
          />

          {citation.applicantInvitationId ? (
            <section className="mt-4 rounded-xl border border-border bg-surface p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[8px] font-medium text-muted">
                    지원자 평가 문서
                  </p>
                  <h3 className="mt-1 text-[12px] font-semibold text-ink">
                    지원자 리포트 요약
                  </h3>
                  <p className="mt-1 text-[9px] leading-[1.55] text-muted">
                    페이지를 이동하지 않고 평가 요약과 기준별 근거를 확인합니다.
                  </p>
                </div>
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-soft text-brand">
                  <UserRound size={16} aria-hidden="true" />
                </span>
              </div>
              <button
                className="mt-4 inline-flex min-h-9 w-full items-center justify-center gap-2 rounded-lg bg-brand px-3 text-[10px] font-semibold text-white hover:bg-brand-strong"
                type="button"
                onClick={() =>
                  onOpenReport(citation.applicantInvitationId as string)
                }
              >
                <FileText size={13} aria-hidden="true" />
                간단 리포트 보기
              </button>
            </section>
          ) : null}
        </div>

        <div className="border-t border-border-muted bg-surface px-3 py-4">
          <p className="px-2 pb-2 text-[8px] font-bold tracking-[0.06em] text-muted uppercase">
            이 답변에 사용된 전체 소스
          </p>
          <div className="grid gap-1">
            {citations.map((item) => (
              <button
                className={`grid grid-cols-[25px_minmax(0,1fr)_14px] items-center gap-2 rounded-xl px-2.5 py-2.5 text-left ${
                  item.sourceId === citation.sourceId
                    ? "bg-brand-soft"
                    : "hover:bg-surface-muted"
                }`}
                key={item.sourceId}
                type="button"
                onClick={() => onSelect(item.sourceId)}
              >
                <span
                  className={`grid size-[25px] place-items-center rounded-lg font-mono text-[8px] font-bold ${
                    item.sourceId === citation.sourceId
                      ? "bg-brand text-white"
                      : "bg-surface-strong text-muted"
                  }`}
                >
                  {item.id}
                </span>
                <span className="min-w-0">
                  <strong className="block truncate text-[9px] font-semibold text-ink-secondary">
                    {item.title}
                  </strong>
                  <small className="mt-0.5 block truncate text-[8px] text-muted">
                    {item.sourceType} · 일치도{" "}
                    {Math.round(item.confidence * 100)}%
                  </small>
                </span>
                {item.sourceId === citation.sourceId ? (
                  <Check size={12} className="text-ink" aria-hidden="true" />
                ) : null}
              </button>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

function EvidenceSummaryTable({ citation }: { citation: Citation }) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="flex items-center justify-between gap-3 border-b border-border-muted px-4 py-3.5">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-md bg-brand font-mono text-[9px] font-bold text-white">
            {citation.id}
          </span>
          <div className="min-w-0">
            <p className="text-[8px] font-medium text-muted">검색 근거 요약</p>
            <h3 className="truncate text-[11px] font-semibold text-ink">
              {citation.title}
            </h3>
          </div>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-success-soft px-2.5 py-1 text-[8px] font-semibold text-success">
          <Check size={9} aria-hidden="true" />
          일치도 {Math.round(citation.confidence * 100)}%
        </span>
      </div>
      <table
        className="w-full table-fixed text-left"
        aria-label="근거 요약 정보"
      >
        <tbody>
          <EvidenceSummaryRow label="지원 포지션" value={citation.source} />
          <EvidenceSummaryRow label="문서 유형" value={citation.sourceType} />
          <EvidenceSummaryRow label="검색 범위" value={citation.scopeLabel} />
          <EvidenceSummaryRow label="검색 정보" value={citation.meta} />
          <EvidenceSummaryRow
            label="검색 상태"
            value="인덱싱 완료"
            valueClassName="text-success"
          />
        </tbody>
      </table>
    </section>
  );
}

function EvidenceSummaryRow({
  label,
  value,
  valueClassName = "text-ink-secondary",
}: {
  label: string;
  value: string;
  valueClassName?: string;
}) {
  return (
    <tr className="border-t border-border-muted first:border-t-0">
      <th className="w-[104px] bg-surface-muted px-4 py-3 text-[8px] font-semibold text-muted">
        {label}
      </th>
      <td
        className={`break-words px-4 py-3 text-[9px] font-medium leading-[1.55] ${valueClassName}`}
      >
        {value}
      </td>
    </tr>
  );
}

const NARRATIVE_CONTEXT_LABELS = new Set([
  "종합 요약",
  "관찰 내용",
  "평가 근거",
  "불확실성",
  "정확성",
  "깊이",
  "CS 기본기",
  "본인 기여",
  "설명력",
]);

function EvidenceContext({
  excerpt,
  rationale,
}: {
  excerpt: string;
  rationale: string;
}) {
  const context = parseEvidenceContext(excerpt);
  const metadata = context.fields.filter(
    (field) => !NARRATIVE_CONTEXT_LABELS.has(field.label),
  );
  const narratives = context.fields.filter((field) =>
    NARRATIVE_CONTEXT_LABELS.has(field.label),
  );
  return (
    <section className="mt-4 overflow-hidden rounded-xl border border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border-muted px-4 py-3.5 text-[9px] font-semibold text-ink-secondary">
        <FileSearch size={13} aria-hidden="true" />
        검색된 문맥
      </div>
      <div className="p-4">
        {context.title ? (
          <p className="mb-3 text-[11px] font-semibold text-ink">
            {context.title}
          </p>
        ) : null}
        {metadata.length ? (
          <table
            className="w-full table-fixed overflow-hidden rounded-lg border border-border-muted text-left"
            aria-label="검색 문맥 기본 정보"
          >
            <tbody>
              {metadata.map((field) => (
                <ContextMetaRow field={field} key={field.label} />
              ))}
            </tbody>
          </table>
        ) : null}
        {narratives.length ? (
          <div className="mt-3 grid gap-2.5">
            {narratives.map((field) => (
              <article
                className="rounded-lg border border-border-muted bg-surface-muted px-3.5 py-3"
                key={field.label}
              >
                <p className="text-[8px] font-semibold text-muted">
                  {field.label}
                </p>
                <p className="mt-1.5 whitespace-pre-line text-[10px] leading-[1.75] text-ink-secondary">
                  {field.value}
                </p>
              </article>
            ))}
          </div>
        ) : null}
        {context.looseText.length ? (
          <div className="mt-3 rounded-lg bg-brand-soft px-3.5 py-3 text-[10px] leading-[1.75] text-ink-secondary">
            {context.looseText.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
        ) : null}
        <div className="mt-4 border-t border-border-muted pt-3.5">
          <p className="text-[8px] font-semibold text-ink">
            답변에 활용된 이유
          </p>
          <p className="mt-1.5 text-[9px] leading-[1.65] text-muted">
            {rationale}
          </p>
        </div>
      </div>
    </section>
  );
}

type ContextField = Readonly<{ label: string; value: string }>;

function ContextMetaRow({ field }: { field: ContextField }) {
  return (
    <tr className="border-t border-border-muted first:border-t-0">
      <th className="w-[96px] bg-surface-muted px-3 py-2.5 text-[8px] font-semibold text-muted">
        {field.label}
      </th>
      <td className="break-words px-3 py-2.5 text-[9px] font-medium leading-[1.55] text-ink-secondary">
        {displayContextValue(field)}
      </td>
    </tr>
  );
}

function parseEvidenceContext(excerpt: string) {
  const fields: ContextField[] = [];
  const looseText: string[] = [];
  let title = "";
  for (const line of excerpt.split("\n").map((item) => item.trim())) {
    if (!line) continue;
    const separator = line.indexOf(":");
    if (separator < 1) {
      if (!title) title = line;
      else looseText.push(line);
      continue;
    }
    const label = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();
    if (value) fields.push({ label, value });
  }
  return { title, fields, looseText };
}

function displayContextValue(field: ContextField) {
  if (field.label === "리포트 상태" && field.value === "ready") {
    return "생성 완료";
  }
  if (field.label === "평가 상태") {
    if (field.value === "confirmed") return "근거 확인";
    if (field.value === "partially_confirmed") return "일부 확인";
    if (field.value === "insufficient_evidence") return "근거 부족";
  }
  return field.value;
}
