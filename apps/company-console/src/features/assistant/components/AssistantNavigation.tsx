import {
  BriefcaseBusiness,
  Check,
  ChevronRight,
  Database,
  FileText,
  History,
  PanelLeftClose,
  Plus,
  Sparkles,
  Trash2,
  UserRound,
} from "lucide-react";
import type { ReactNode } from "react";

import type { ChatConversation } from "../types";
import { suggestedQuestions } from "../types";

const HISTORY_PANEL =
  "relative z-30 flex min-h-0 flex-col border-r border-[#e8e8e5] bg-[#f7f7f5]" +
  " mw-900:fixed mw-900:inset-[58px_auto_0_0] mw-900:w-[min(292px,88vw)]" +
  " mw-900:shadow-float";

export function ConversationHistory({
  conversations,
  activeConversationId,
  positionTitleById,
  archivedPositionIds,
  onClose,
  onCreate,
  onDelete,
  onSelect,
}: {
  conversations: readonly ChatConversation[];
  activeConversationId: string;
  positionTitleById: ReadonlyMap<string, string>;
  archivedPositionIds: ReadonlySet<string>;
  onClose(): void;
  onCreate(): void;
  onDelete(id: string): void;
  onSelect(id: string): void;
}) {
  return (
    <aside className={HISTORY_PANEL} aria-label="AI 대화 목록">
      <header className="flex h-15 items-center justify-between px-3.5">
        <div className="flex items-center gap-2">
          <span className="grid size-7 place-items-center rounded-lg bg-white text-ink shadow-[0_1px_3px_rgb(0_0_0_/_8%)]">
            <History size={14} aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-[12px] font-semibold text-ink">대화</h2>
            <p className="text-[8px] text-muted">현재 세션</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            className="grid size-8 place-items-center rounded-lg text-ink hover:bg-[#ececea]"
            type="button"
            aria-label="새 채팅 만들기"
            onClick={onCreate}
          >
            <Plus size={16} aria-hidden="true" />
          </button>
          <button
            className="grid size-8 place-items-center rounded-lg text-muted hover:bg-surface-muted hover:text-ink"
            type="button"
            aria-label="대화 목록 닫기"
            onClick={onClose}
          >
            <PanelLeftClose size={16} aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-2.5">
        <p className="px-2 py-2 text-[8px] font-medium text-muted">최근 대화</p>
        <div className="grid gap-1">
          {conversations.map((conversation) => {
            const active = conversation.id === activeConversationId;
            const label =
              conversation.scopeId === "all"
                ? "전체 진행 중 포지션"
                : `${
                    positionTitleById.get(conversation.scopeId) ??
                    "선택한 포지션"
                  }${
                    archivedPositionIds.has(conversation.scopeId)
                      ? " · 모집 종료"
                      : ""
                  }`;
            return (
              <div
                className={`group grid grid-cols-[minmax(0,1fr)_28px] items-center rounded-xl border ${
                  active
                    ? "border-[#e5e5e2] bg-white shadow-[0_1px_3px_rgb(0_0_0_/_5%)]"
                    : "border-transparent hover:bg-[#ececea]"
                }`}
                key={conversation.id}
              >
                <button
                  className="min-w-0 px-3 py-2.5 text-left"
                  type="button"
                  onClick={() => onSelect(conversation.id)}
                >
                  <span
                    className={`block truncate text-[10px] font-semibold ${
                      active ? "text-ink" : "text-ink-secondary"
                    }`}
                  >
                    {conversation.title}
                  </span>
                  <span className="mt-1 flex items-center gap-1 truncate text-[8px] text-muted">
                    <BriefcaseBusiness size={9} aria-hidden="true" />
                    {label}
                  </span>
                </button>
                <button
                  className="grid size-7 place-items-center rounded-lg text-subtle opacity-0 hover:bg-white hover:text-danger group-hover:opacity-100 focus-visible:opacity-100"
                  type="button"
                  aria-label={`${conversation.title} 삭제`}
                  onClick={() => onDelete(conversation.id)}
                >
                  <Trash2 size={12} aria-hidden="true" />
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <div className="border-t border-[#e8e8e5] p-3">
        <div className="px-2 py-1">
          <p className="flex items-center gap-1.5 text-[9px] font-semibold text-ink-secondary">
            <Database size={11} className="text-muted" aria-hidden="true" />
            연결된 데이터
          </p>
          <div className="mt-2 grid gap-1.5 text-[8px] text-muted">
            <ConnectedSource label="지원자 리포트" />
            <ConnectedSource label="포지션 운영 데이터" />
            <ConnectedSource label="평가 정책" />
          </div>
        </div>
      </div>
    </aside>
  );
}

function ConnectedSource({ label }: { label: string }) {
  return (
    <span className="flex items-center justify-between">
      {label} <Check size={10} className="text-success" />
    </span>
  );
}

export function EmptyConversation({
  scopeLabel,
  positionCount,
  applicantCount,
  reportCount,
  insightsLoading,
  archivedScope,
  onAsk,
}: {
  scopeLabel: string;
  positionCount: number;
  applicantCount: number;
  reportCount: number;
  insightsLoading: boolean;
  archivedScope: boolean;
  onAsk(question: string): void;
}) {
  return (
    <section className="mx-auto grid min-h-full w-full max-w-[760px] content-center justify-items-center py-14 text-center">
      <span className="grid size-11 place-items-center rounded-full border border-[#e5e5e2] bg-white text-ink shadow-[0_2px_8px_rgb(0_0_0_/_6%)]">
        <Sparkles size={19} aria-hidden="true" />
      </span>
      <p className="mt-5 text-[9px] font-medium text-muted">
        {scopeLabel}에서 시작하는 대화
      </p>
      {archivedScope ? (
        <span className="mt-3 rounded-full border border-[#dededb] bg-[#f7f7f5] px-3 py-1.5 text-[8px] font-semibold text-muted">
          읽기 전용 과거 채용 분석
        </span>
      ) : null}
      <h2 className="mt-4 text-[23px] font-semibold tracking-[-0.025em] text-ink">
        채용 데이터에 대해 무엇이든 물어보세요
      </h2>
      <p className="mt-2 max-w-xl text-[11px] leading-[1.65] text-muted">
        이 대화는 첫 질문 이후{" "}
        <b className="text-ink-secondary">{scopeLabel}</b>에 고정되며, 해당
        범위의 최종 리포트를 검색해 답변합니다.
        {archivedScope
          ? " 종료된 포지션의 데이터는 새 지원자를 받지 않고 분석 용도로만 사용합니다."
          : ""}
      </p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        <DataCount
          icon={<BriefcaseBusiness size={11} />}
          value={`${positionCount}개 포지션`}
        />
        <DataCount
          icon={<UserRound size={11} />}
          value={`${applicantCount}명 지원자`}
        />
        <DataCount
          icon={<FileText size={11} />}
          value={
            insightsLoading ? "리포트 집계 중" : `${reportCount}건 리포트`
          }
        />
      </div>
      <div className="mt-8 grid w-full grid-cols-2 gap-2 mw-620:grid-cols-1">
        {suggestedQuestions.map((question) => (
          <button
            className="group min-h-14 rounded-xl border border-[#e8e8e5] bg-[#fafafa] px-4 py-3 text-left text-[11px] leading-[1.5] text-ink-secondary transition hover:bg-[#f2f2f0]"
            key={question}
            type="button"
            onClick={() => onAsk(question)}
          >
            <span className="flex items-start justify-between gap-3">
              {question}
              <ChevronRight
                className="mt-0.5 shrink-0 text-subtle transition group-hover:translate-x-0.5 group-hover:text-ink"
                size={13}
                aria-hidden="true"
              />
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}

function DataCount({ icon, value }: { icon: ReactNode; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-1.5 py-1 text-[8px] text-muted">
      <span className="text-ink-secondary">{icon}</span>
      {value}
    </span>
  );
}
