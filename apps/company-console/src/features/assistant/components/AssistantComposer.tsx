import {
  ArrowUp,
  BriefcaseBusiness,
  Check,
  Database,
  FileText,
  Plus,
  ShieldCheck,
  X,
} from "lucide-react";
import type { FormEvent, KeyboardEvent, ReactNode } from "react";

const COMPOSER_WRAP =
  "relative z-10 bg-gradient-to-t from-canvas via-canvas to-transparent" +
  " px-5 pt-4 pb-5 mw-620:px-3 mw-620:pb-3";

export function AssistantComposer({
  query,
  scopeLabel,
  reportCount,
  scopeLocked,
  pending,
  toolsOpen,
  onQueryChange,
  onSubmit,
  onToggleTools,
  onCloseTools,
}: {
  query: string;
  scopeLabel: string;
  reportCount: number;
  scopeLocked: boolean;
  pending: boolean;
  toolsOpen: boolean;
  onQueryChange(value: string): void;
  onSubmit(): void;
  onToggleTools(): void;
  onCloseTools(): void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    onSubmit();
  }

  return (
    <form className={COMPOSER_WRAP} onSubmit={submit}>
      <div className="mx-auto w-full max-w-[780px]">
        <div className="relative rounded-[26px] border border-border bg-surface p-2 shadow-soft transition focus-within:border-brand focus-within:shadow-[0_6px_24px_rgb(89_102_206_/_14%)]">
          {toolsOpen ? (
            <RagContextMenu
              scopeLabel={scopeLabel}
              reportCount={reportCount}
              onClose={onCloseTools}
            />
          ) : null}
          <textarea
            className="block max-h-36 min-h-12 w-full resize-none border-0 bg-transparent px-3 py-2 text-[13px] leading-[1.55] outline-none placeholder:text-subtle"
            aria-label="AI 채용 어시스턴트에게 질문"
            placeholder={`${scopeLabel}의 채용 데이터에 대해 질문하세요`}
            rows={1}
            value={query}
            disabled={pending}
            onChange={(event) => onQueryChange(event.target.value)}
            onKeyDown={handleKeyDown}
          />
          <div className="flex items-center justify-between px-1 pb-0.5">
            <div className="flex items-center gap-1">
              <button
                className={`grid size-8 place-items-center rounded-full border transition ${
                  toolsOpen
                    ? "border-brand bg-brand-soft text-brand"
                    : "border-transparent bg-surface-strong text-muted hover:bg-brand-soft hover:text-brand"
                }`}
                type="button"
                aria-label="참조 데이터 보기"
                aria-expanded={toolsOpen}
                onClick={onToggleTools}
              >
                <Plus size={16} aria-hidden="true" />
              </button>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-2.5 py-1.5 text-[8px] font-medium text-brand">
                <Database size={10} aria-hidden="true" />
                {scopeLabel} · RAG
              </span>
              {scopeLocked ? (
                <span className="text-[8px] text-muted mw-620:hidden">
                  범위 고정됨 · 변경하려면 새 채팅
                </span>
              ) : null}
            </div>
            <button
              className="grid size-8 place-items-center rounded-full bg-brand text-white shadow-soft transition hover:bg-brand-strong disabled:bg-surface-strong disabled:text-subtle disabled:shadow-none"
              type="submit"
              aria-label="질문 보내기"
              disabled={!query.trim() || pending}
            >
              <ArrowUp size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
        <p className="mt-2 text-center text-[8px] text-subtle">
          선택한 범위의 최종 리포트를 근거로 검색·생성한 답변이며, AI의 요약과
          평가는 부정확할 수 있습니다.
        </p>
      </div>
    </form>
  );
}

function RagContextMenu({
  scopeLabel,
  reportCount,
  onClose,
}: {
  scopeLabel: string;
  reportCount: number;
  onClose(): void;
}) {
  return (
    <div className="absolute bottom-[calc(100%+10px)] left-0 z-30 w-[300px] rounded-2xl border border-border bg-surface p-2.5 shadow-float mw-620:w-[min(300px,calc(100vw-32px))]">
      <div className="flex items-center justify-between px-2 py-1.5">
        <div>
          <strong className="block text-[10px] text-ink">참조 데이터</strong>
          <span className="text-[8px] text-muted">
            질문마다 아래 문서를 검색합니다
          </span>
        </div>
        <button
          className="grid size-7 place-items-center rounded-lg text-muted hover:bg-surface-muted"
          type="button"
          aria-label="참조 데이터 닫기"
          onClick={onClose}
        >
          <X size={13} aria-hidden="true" />
        </button>
      </div>
      <div className="mt-1 grid gap-1">
        <ContextSource
          icon={<FileText size={13} />}
          title="지원자 AI 최종 리포트"
          detail={`${reportCount}건의 자격요건 판정·답변 근거`}
        />
        <ContextSource
          icon={<BriefcaseBusiness size={13} />}
          title="고정된 검색 범위"
          detail={`${scopeLabel}에서만 검색`}
        />
        <ContextSource
          icon={<ShieldCheck size={13} />}
          title="근거 검증"
          detail="실제 검색된 source_id만 인용"
        />
      </div>
    </div>
  );
}

function ContextSource({
  icon,
  title,
  detail,
}: {
  icon: ReactNode;
  title: string;
  detail: string;
}) {
  return (
    <div className="grid grid-cols-[30px_minmax(0,1fr)_16px] items-center gap-2 rounded-xl px-2 py-2 hover:bg-surface-muted">
      <span className="grid size-7 place-items-center rounded-lg bg-brand-soft text-brand">
        {icon}
      </span>
      <span className="min-w-0">
        <strong className="block truncate text-[9px] font-semibold text-ink-secondary">
          {title}
        </strong>
        <small className="mt-0.5 block truncate text-[8px] text-muted">
          {detail}
        </small>
      </span>
      <Check size={12} className="text-success" aria-label="검색에 포함됨" />
    </div>
  );
}
