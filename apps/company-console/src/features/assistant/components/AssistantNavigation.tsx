import * as Dialog from "@radix-ui/react-dialog";
import {
  BriefcaseBusiness,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  Database,
  FileCheck2,
  FileSearch,
  FileText,
  History,
  PanelLeftClose,
  Pencil,
  Plus,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

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
  onRename,
  onSelect,
}: {
  conversations: readonly ChatConversation[];
  activeConversationId: string;
  positionTitleById: ReadonlyMap<string, string>;
  archivedPositionIds: ReadonlySet<string>;
  onClose(): void;
  onCreate(): void;
  onDelete(id: string): void;
  onRename(id: string, title: string): boolean;
  onSelect(id: string): void;
}) {
  const [editingConversationId, setEditingConversationId] = useState<
    string | null
  >(null);
  const [titleDraft, setTitleDraft] = useState("");

  function startEditing(conversation: ChatConversation) {
    setEditingConversationId(conversation.id);
    setTitleDraft(conversation.title);
  }

  function stopEditing() {
    setEditingConversationId(null);
    setTitleDraft("");
  }

  function saveTitle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingConversationId) return;
    if (onRename(editingConversationId, titleDraft)) stopEditing();
  }

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
            const editing = conversation.id === editingConversationId;
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
                className={`group grid grid-cols-[minmax(0,1fr)_56px] items-center rounded-xl border ${
                  active
                    ? "border-[#e5e5e2] bg-white shadow-[0_1px_3px_rgb(0_0_0_/_5%)]"
                    : "border-transparent hover:bg-[#ececea]"
                }`}
                key={conversation.id}
              >
                {editing ? (
                  <form
                    className="col-span-2 grid grid-cols-[minmax(0,1fr)_56px] items-center gap-1 p-1.5"
                    onSubmit={saveTitle}
                  >
                    <label className="min-w-0">
                      <span className="sr-only">대화 제목</span>
                      <input
                        className="h-8 w-full rounded-lg border border-[#d7d7d3] bg-white px-2.5 text-[10px] font-semibold text-ink outline-none focus:border-brand"
                        autoFocus
                        maxLength={60}
                        value={titleDraft}
                        onChange={(event) => setTitleDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Escape") stopEditing();
                        }}
                      />
                    </label>
                    <div className="flex items-center">
                      <button
                        className="grid size-7 place-items-center rounded-lg text-success hover:bg-success-soft disabled:text-subtle"
                        type="submit"
                        aria-label="대화 제목 저장"
                        disabled={!titleDraft.trim()}
                      >
                        <Check size={12} aria-hidden="true" />
                      </button>
                      <button
                        className="grid size-7 place-items-center rounded-lg text-muted hover:bg-white hover:text-ink"
                        type="button"
                        aria-label="대화 제목 수정 취소"
                        onClick={stopEditing}
                      >
                        <X size={12} aria-hidden="true" />
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
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
                    <div className="flex items-center">
                      <button
                        className="grid size-7 place-items-center rounded-lg text-subtle hover:bg-white hover:text-ink"
                        type="button"
                        aria-label={`${conversation.title} 제목 수정`}
                        onClick={() => startEditing(conversation)}
                      >
                        <Pencil size={12} aria-hidden="true" />
                      </button>
                      <button
                        className="grid size-7 place-items-center rounded-lg text-subtle hover:bg-white hover:text-danger"
                        type="button"
                        aria-label={`${conversation.title} 삭제`}
                        onClick={() => onDelete(conversation.id)}
                      >
                        <Trash2 size={12} aria-hidden="true" />
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="border-t border-[#e8e8e5] bg-white p-3">
        <div className="flex items-center gap-2 rounded-xl border border-[#e5e5e2] bg-[#fafaf9] px-3 py-2.5">
          <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-white text-brand shadow-[0_1px_3px_rgb(0_0_0_/_6%)]">
            <CircleHelp size={13} aria-hidden="true" />
          </span>
          <span className="min-w-0">
            <strong className="block text-[9px] font-semibold text-ink-secondary">
              RAG 검색 데이터
            </strong>
            <small className="mt-0.5 block truncate text-[7px] text-muted">
              최종 리포트와 평가 기준별 근거를 검색합니다.
            </small>
          </span>
        </div>
      </div>
    </aside>
  );
}

function SearchHelpSection({
  icon,
  title,
  body,
  last = false,
}: {
  icon: ReactNode;
  title: string;
  body: string;
  last?: boolean;
}) {
  return (
    <section className={last ? "" : "border-b border-[#ececea] pb-4"}>
      <p className="flex items-center gap-2 text-[11px] font-semibold text-ink-secondary">
        <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-[#f4f6ff] text-brand">
          {icon}
        </span>
        {title}
      </p>
      <p className="mt-2 pl-9 text-[10px] leading-[1.7] text-muted">{body}</p>
    </section>
  );
}

function RagSearchHelpDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange(open: boolean): void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-80 bg-[#11182766] backdrop-blur-[1px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-90 max-h-[min(720px,88vh)] w-[min(660px,calc(100vw-24px))] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border border-[#e5e5e2] bg-white shadow-[0_24px_80px_rgb(15_23_42_/_22%)] outline-none">
          <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-[#e8e8e5] bg-white px-6 py-5">
            <div>
              <p className="text-[9px] font-semibold text-brand">
                RAG 검색 안내
              </p>
              <Dialog.Title className="mt-1 text-[18px] font-semibold tracking-[-0.02em] text-ink">
                RAG 검색은 이렇게 동작합니다
              </Dialog.Title>
              <Dialog.Description className="mt-2 max-w-[520px] text-[10px] leading-[1.65] text-muted">
                선택한 채용 범위의 최종 리포트에서 질문과 관련된 근거를 찾고,
                AI가 그 근거를 바탕으로 답변을 구성합니다.
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="grid size-8 shrink-0 place-items-center rounded-lg text-muted hover:bg-[#f2f2f0] hover:text-ink"
              aria-label="검색 안내 닫기"
            >
              <X size={16} aria-hidden="true" />
            </Dialog.Close>
          </header>

          <div className="grid gap-6 px-6 py-6">
            <section>
              <h3 className="text-[12px] font-semibold text-ink">검색 흐름</h3>
              <ol className="mt-3 grid grid-cols-4 gap-2 mw-620:grid-cols-1">
                {[
                  ["1", "범위 고정", "첫 질문의 포지션 범위를 대화에 고정"],
                  ["2", "질문 이해", "의미와 핵심 키워드를 함께 분석"],
                  ["3", "근거 검색", "관련도가 높은 최종 리포트를 검색"],
                  ["4", "답변 구성", "검색 근거를 바탕으로 AI가 답변"],
                ].map(([step, title, description]) => (
                  <li
                    className="rounded-xl border border-[#e8e8e5] bg-[#fafaf9] p-3"
                    key={step}
                  >
                    <span className="grid size-5 place-items-center rounded-full bg-ink text-[8px] font-semibold text-white">
                      {step}
                    </span>
                    <strong className="mt-3 block text-[10px] text-ink-secondary">
                      {title}
                    </strong>
                    <span className="mt-1 block text-[8px] leading-[1.55] text-muted">
                      {description}
                    </span>
                  </li>
                ))}
              </ol>
            </section>

            <section className="grid gap-4 rounded-2xl border border-[#e8e8e5] p-5">
              <SearchHelpSection
                icon={<FileSearch size={13} />}
                title="직접 검색하는 자료"
                body="완료된 지원자 AI 최종 리포트의 종합 요약과 평가 기준별 관찰 내용, 평가 근거, 불확실성, 세부 점수를 검색합니다."
              />
              <SearchHelpSection
                icon={<Database size={13} />}
                title="검색 범위와 방식"
                body="선택한 포지션 또는 전체 진행 중 포지션 안에서 의미 기반 검색과 키워드 검색을 함께 사용합니다. 지원자명과 포지션명은 결과를 이해하기 위한 정보로 표시합니다."
              />
              <SearchHelpSection
                icon={<FileCheck2 size={13} />}
                title="평가 기준 정보"
                body="최종 리포트에 포함된 평가 항목명, 판정 상태와 기준별 근거를 검색합니다. 별도의 정책 문서를 통째로 검색하는 방식은 아닙니다."
              />
              <SearchHelpSection
                icon={<ShieldCheck size={13} />}
                title="직접 검색하지 않는 자료"
                body="이력서, 포트폴리오, 면접 영상·음성, 전체 녹취 원문을 직접 검색하지 않습니다. 해당 자료를 바탕으로 생성된 최종 리포트만 사용합니다."
              />
              <SearchHelpSection
                icon={<Clock3 size={13} />}
                title="데이터 반영 시점"
                body="면접 분석과 최종 리포트 생성이 끝난 뒤 검색 인덱스에 반영됩니다. 리포트가 갱신되면 검색 문서도 새 버전으로 교체됩니다."
                last
              />
            </section>

            <p className="rounded-xl bg-[#f4f6ff] px-4 py-3 text-[9px] leading-[1.65] text-[#4f5f83]">
              검색 결과가 질문과 정확히 일치하지 않으면, 일치하는 지원자가
              없다는 점과 함께 확인된 유사 근거를 안내합니다. AI가 생성한 요약과
              평가는 실제 채용 판단 전에 원문 근거를 다시 확인해 주세요.
            </p>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
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
  const [searchHelpOpen, setSearchHelpOpen] = useState(false);

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
      <button
        className="mt-2 inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[9px] font-semibold text-brand hover:bg-[#f4f6ff]"
        type="button"
        onClick={() => setSearchHelpOpen(true)}
      >
        <CircleHelp size={12} aria-hidden="true" />
        어떻게 검색되나요?
      </button>
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
          value={insightsLoading ? "리포트 집계 중" : `${reportCount}건 리포트`}
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
      <RagSearchHelpDialog
        open={searchHelpOpen}
        onOpenChange={setSearchHelpOpen}
      />
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
