import {
  Check,
  FileSearch,
  FileText,
  UserRound,
  X,
} from "lucide-react";

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
        className="absolute inset-[0_0_0_auto] w-[min(440px,100%)] overflow-y-auto border-l border-[#dededb] bg-[#f7f7f5] shadow-float"
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
          <div className="rounded-xl border border-[#dededb] bg-surface p-5">
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-md bg-ink px-2 font-mono text-[9px] font-bold text-white">
                {citation.id}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-2.5 py-1 text-[8px] font-semibold text-success">
                <Check size={9} aria-hidden="true" />
                검색 일치도 {Math.round(citation.confidence * 100)}%
              </span>
            </div>
            <h3 className="mt-4 text-[15px] font-semibold leading-[1.45] text-ink">
              {citation.title}
            </h3>
            <p className="mt-1 text-[9px] text-muted">{citation.source}</p>

            <dl className="mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border-muted bg-border-muted">
              <SourceMeta label="문서 유형" value={citation.sourceType} />
              <SourceMeta label="검색 범위" value={citation.scopeLabel} />
              <SourceMeta label="검색 정보" value={citation.meta} />
              <SourceMeta
                label="검색 상태"
                value="인덱싱 완료"
                tone="text-success"
              />
            </dl>
          </div>

          <section className="mt-4 rounded-xl border border-[#dededb] bg-surface p-5">
            <p className="flex items-center gap-2 text-[9px] font-semibold text-ink-secondary">
              <FileSearch size={13} aria-hidden="true" />
              검색된 문맥
            </p>
            <blockquote className="mt-4 whitespace-pre-line border-l-2 border-ink bg-[#f7f7f5] px-4 py-3.5 text-[11px] leading-[1.8] text-ink-secondary">
              {citation.excerpt}
            </blockquote>
            <div className="mt-4">
              <p className="text-[9px] font-semibold text-ink">
                이 근거가 사용된 이유
              </p>
              <p className="mt-1.5 text-[10px] leading-[1.65] text-muted">
                {citation.rationale}
              </p>
            </div>
          </section>

          {citation.applicantInvitationId ? (
            <section className="mt-4 rounded-xl border border-[#dededb] bg-white p-5">
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
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[#f1f1ef] text-ink">
                  <UserRound size={16} aria-hidden="true" />
                </span>
              </div>
              <button
                className="mt-4 inline-flex min-h-9 w-full items-center justify-center gap-2 rounded-lg bg-ink px-3 text-[10px] font-semibold text-white hover:bg-[#303030]"
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
                    ? "bg-[#efefed]"
                    : "hover:bg-surface-muted"
                }`}
                key={item.sourceId}
                type="button"
                onClick={() => onSelect(item.sourceId)}
              >
                <span
                  className={`grid size-[25px] place-items-center rounded-lg font-mono text-[8px] font-bold ${
                    item.sourceId === citation.sourceId
                      ? "bg-ink text-white"
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

function SourceMeta({
  label,
  value,
  tone = "text-ink-secondary",
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="bg-surface px-3 py-3">
      <dt className="text-[7px] font-bold tracking-[0.05em] text-subtle uppercase">
        {label}
      </dt>
      <dd className={`mt-1 truncate text-[9px] font-semibold ${tone}`}>
        {value}
      </dd>
    </div>
  );
}
