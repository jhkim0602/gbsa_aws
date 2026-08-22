import {
  BriefcaseBusiness,
  ChevronRight,
  LockKeyhole,
  Menu,
  PanelLeftClose,
  Plus,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { ASYNC_STATE } from "../../app/styles/primitives";
import type { CompanyOperationsApi } from "../company/types";
import { useRecruitingOperations } from "../company/useRecruitingOperations";
import { recruitingAssistantApi, type RecruitingAssistantApi } from "./api";
import { buildApplicantReportPreviews, buildPositionRows } from "./data";
import { ApplicantReportModal } from "./components/ApplicantReportModal";
import { AssistantComposer } from "./components/AssistantComposer";
import { MessageList } from "./components/AssistantMessages";
import {
  ConversationHistory,
  EmptyConversation,
} from "./components/AssistantNavigation";
import { EvidenceDrawer } from "./components/EvidenceDrawer";
import { isPositionArchived, isPositionRecruiting } from "./positionLifecycle";
import type { Citation, InsightByPosition } from "./types";
import { useAssistantConversations } from "./useAssistantConversations";

const ROOT =
  "relative grid h-[calc(100vh-58px)] min-h-[640px] overflow-hidden bg-canvas" +
  " mw-760:h-auto mw-760:min-h-[calc(100vh-58px)]";
const HEADER =
  "relative z-20 flex h-15 items-center gap-3 border-b border-border" +
  " bg-[color-mix(in_srgb,var(--color-surface)_96%,transparent)] px-5 backdrop-blur mw-620:px-3";
const CONVERSATION =
  "min-h-0 overflow-y-auto scroll-smooth bg-canvas px-5 pb-10 mw-620:px-3";

export function AiRecruitingAssistant({
  api,
  assistantApi = recruitingAssistantApi,
}: {
  api: CompanyOperationsApi;
  assistantApi?: RecruitingAssistantApi;
}) {
  const { positions, invitations, loading, error } =
    useRecruitingOperations(api);
  const [insightsByPosition, setInsightsByPosition] =
    useState<InsightByPosition>({});
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [historyOpen, setHistoryOpen] = useState(true);
  const [composerToolsOpen, setComposerToolsOpen] = useState(false);
  const [selectedCitationSourceId, setSelectedCitationSourceId] = useState<
    string | null
  >(null);
  const [selectedReportInvitationId, setSelectedReportInvitationId] = useState<
    string | null
  >(null);

  useEffect(() => {
    if (!positions.length || !api.listApplicantInsights) {
      setInsightsByPosition({});
      setInsightsLoading(false);
      return;
    }
    let active = true;
    setInsightsLoading(true);
    void Promise.all(
      positions.map(async (position) => {
        try {
          const insights = await api.listApplicantInsights?.(
            position.positionId,
          );
          return [position.positionId, insights ?? []] as const;
        } catch {
          return [position.positionId, []] as const;
        }
      }),
    ).then((entries) => {
      if (!active) return;
      setInsightsByPosition(Object.fromEntries(entries));
      setInsightsLoading(false);
    });
    return () => {
      active = false;
    };
  }, [api, positions]);

  const positionTitleById = useMemo(
    () =>
      new Map(
        positions.map((position) => [position.positionId, position.title]),
      ),
    [positions],
  );
  const positionRows = useMemo(
    () => buildPositionRows(positions, invitations, insightsByPosition),
    [insightsByPosition, invitations, positions],
  );
  const recruitingPositions = useMemo(
    () => positions.filter((position) => isPositionRecruiting(position)),
    [positions],
  );
  const archivedPositions = useMemo(
    () => positions.filter((position) => isPositionArchived(position)),
    [positions],
  );
  const archivedPositionIds = useMemo(
    () => new Set(archivedPositions.map((position) => position.positionId)),
    [archivedPositions],
  );
  const conversationState = useAssistantConversations({
    assistantApi,
    positions,
    invitations,
    insightsByPosition,
    positionRows,
  });
  const { activeConversation } = conversationState;
  const selectedScope = activeConversation?.scopeId ?? "all";
  const scopeLocked = Boolean(
    activeConversation?.messages.length || activeConversation?.pending,
  );
  const archivedScope =
    selectedScope !== "all" && archivedPositionIds.has(selectedScope);
  const scopeLabel =
    selectedScope === "all"
      ? "전체 진행 중 포지션"
      : `${positionTitleById.get(selectedScope) ?? "선택한 포지션"}${
          archivedScope ? " · 모집 종료" : ""
        }`;
  const scopedPositions = useMemo(
    () =>
      selectedScope === "all"
        ? recruitingPositions
        : positions.filter((position) => position.positionId === selectedScope),
    [positions, recruitingPositions, selectedScope],
  );
  const scopedPositionIds = useMemo(
    () => new Set(scopedPositions.map((position) => position.positionId)),
    [scopedPositions],
  );
  const scopedInvitations = useMemo(
    () =>
      invitations.filter((invitation) =>
        scopedPositionIds.has(invitation.positionId),
      ),
    [invitations, scopedPositionIds],
  );
  const scopedReportCount = useMemo(
    () =>
      scopedPositions.reduce(
        (count, position) =>
          count + (insightsByPosition[position.positionId]?.length ?? 0),
        0,
      ),
    [insightsByPosition, scopedPositions],
  );
  const activeCitations = useMemo(
    () =>
      (activeConversation?.messages ?? []).flatMap((message) =>
        message.role === "assistant" ? message.answer.citations : [],
      ),
    [activeConversation?.messages],
  );
  const selectedCitation = selectedCitationSourceId
    ? activeCitations.find(
        (citation) => citation.sourceId === selectedCitationSourceId,
      )
    : undefined;
  const selectedCitationGroup = selectedCitation
    ? citationsForAnswer(activeConversation?.messages ?? [], selectedCitation)
    : [];
  const applicantReports = useMemo(
    () =>
      buildApplicantReportPreviews(positions, invitations, insightsByPosition),
    [insightsByPosition, invitations, positions],
  );
  const selectedReport = selectedReportInvitationId
    ? applicantReports.get(selectedReportInvitationId)
    : undefined;

  function selectConversation(conversationId: string) {
    conversationState.setActiveConversationId(conversationId);
    setSelectedCitationSourceId(null);
    setQuery("");
  }

  function createConversation(scopeId = "all") {
    conversationState.createConversation(scopeId);
    setSelectedCitationSourceId(null);
    setQuery("");
    setComposerToolsOpen(false);
  }

  function ask(question: string) {
    const normalized = question.trim();
    if (!normalized || activeConversation?.pending) return;
    setQuery("");
    setComposerToolsOpen(false);
    void conversationState.ask(normalized);
  }

  return (
    <div
      className={`${ROOT} ${
        historyOpen
          ? "grid-cols-[236px_minmax(0,1fr)] mw-900:grid-cols-[minmax(0,1fr)]"
          : "grid-cols-[minmax(0,1fr)]"
      }`}
    >
      {historyOpen ? (
        <>
          <ConversationHistory
            conversations={conversationState.conversations}
            activeConversationId={conversationState.activeConversationId}
            positionTitleById={positionTitleById}
            archivedPositionIds={archivedPositionIds}
            onClose={() => setHistoryOpen(false)}
            onCreate={() => createConversation()}
            onDelete={(conversationId) => {
              conversationState.deleteConversation(conversationId);
              setSelectedCitationSourceId(null);
            }}
            onRename={conversationState.renameConversation}
            onSelect={selectConversation}
          />
          <button
            className="fixed inset-[58px_0_0_0] z-25 hidden bg-[rgb(26_31_54_/_22%)] mw-900:block"
            type="button"
            aria-label="대화 목록 닫기"
            onClick={() => setHistoryOpen(false)}
          />
        </>
      ) : null}

      <section className="grid min-h-0 min-w-0 grid-rows-[60px_minmax(0,1fr)]">
        <header className={HEADER}>
          <button
            className="grid size-8 shrink-0 place-items-center rounded-lg text-muted hover:bg-brand-soft hover:text-brand"
            type="button"
            aria-label="대화 목록 열기"
            aria-expanded={historyOpen}
            onClick={() => setHistoryOpen((current) => !current)}
          >
            {historyOpen ? (
              <PanelLeftClose size={17} aria-hidden="true" />
            ) : (
              <Menu size={17} aria-hidden="true" />
            )}
          </button>

          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 items-center gap-2">
              <span className="grid size-7 shrink-0 place-items-center rounded-full bg-brand text-white shadow-soft">
                <Sparkles size={14} aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <h1 className="sr-only">AI 채용 어시스턴트</h1>
                <p className="truncate text-[13px] font-semibold text-ink">
                  {activeConversation?.title ?? "AI 채용 어시스턴트"}
                </p>
                <p className="truncate text-[8px] text-muted">
                  최종 리포트 근거 검색 대화
                </p>
              </div>
            </div>
          </div>

          <label className="relative flex min-w-0 items-center">
            <span className="sr-only">분석 범위</span>
            <BriefcaseBusiness
              className="pointer-events-none absolute left-2.5 z-10 text-muted"
              size={13}
              aria-hidden="true"
            />
            <select
              className="h-9 max-w-[270px] appearance-none rounded-lg border border-border bg-surface py-0 pr-8 pl-8 text-[10px] font-medium text-ink-secondary outline-none hover:border-brand hover:bg-brand-soft focus:border-brand disabled:cursor-not-allowed disabled:opacity-100 mw-620:max-w-[146px]"
              value={selectedScope}
              disabled={scopeLocked}
              onChange={(event) =>
                conversationState.updateConversationScope(event.target.value)
              }
            >
              <option value="all">전체 진행 중 포지션</option>
              {recruitingPositions.length ? (
                <optgroup label="모집 중">
                  {recruitingPositions.map((position) => (
                    <option
                      key={position.positionId}
                      value={position.positionId}
                    >
                      {position.title}
                    </option>
                  ))}
                </optgroup>
              ) : null}
              {archivedPositions.length ? (
                <optgroup label="모집 종료 · 과거 분석">
                  {archivedPositions.map((position) => (
                    <option
                      key={position.positionId}
                      value={position.positionId}
                    >
                      {position.title} (종료)
                    </option>
                  ))}
                </optgroup>
              ) : null}
            </select>
            {scopeLocked ? (
              <LockKeyhole
                className="pointer-events-none absolute right-2.5 text-muted"
                size={12}
                aria-label="대화에 고정된 분석 범위"
              />
            ) : (
              <ChevronRight
                className="pointer-events-none absolute right-2.5 rotate-90 text-muted"
                size={12}
                aria-hidden="true"
              />
            )}
          </label>

          <button
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-[10px] font-semibold text-ink-secondary hover:border-brand hover:bg-brand-soft hover:text-brand mw-620:size-9 mw-620:justify-center mw-620:px-0"
            type="button"
            aria-label="새 채팅 만들기"
            onClick={() => createConversation(selectedScope)}
          >
            <Plus size={15} aria-hidden="true" />
            <span className="mw-620:hidden">새 채팅</span>
          </button>
        </header>

        <main className="grid min-h-0 grid-rows-[minmax(0,1fr)_auto]">
          {loading ? (
            <div className={ASYNC_STATE} role="status">
              채용 데이터를 불러오는 중입니다.
            </div>
          ) : error ? (
            <div className={ASYNC_STATE} role="alert">
              채용 데이터를 불러오지 못했습니다.
            </div>
          ) : (
            <div className={CONVERSATION}>
              {activeConversation?.messages.length ? (
                <MessageList
                  messages={activeConversation.messages}
                  scopeLabel={scopeLabel}
                  pending={activeConversation.pending}
                  error={activeConversation.error}
                  onSelectCitation={setSelectedCitationSourceId}
                />
              ) : (
                <EmptyConversation
                  scopeLabel={scopeLabel}
                  positionCount={scopedPositions.length}
                  applicantCount={scopedInvitations.length}
                  reportCount={scopedReportCount}
                  insightsLoading={insightsLoading}
                  archivedScope={archivedScope}
                  onAsk={ask}
                />
              )}
            </div>
          )}

          <AssistantComposer
            query={query}
            scopeLabel={scopeLabel}
            reportCount={scopedReportCount}
            scopeLocked={scopeLocked}
            pending={activeConversation?.pending ?? false}
            toolsOpen={composerToolsOpen}
            onQueryChange={setQuery}
            onSubmit={() => ask(query)}
            onToggleTools={() => setComposerToolsOpen((current) => !current)}
            onCloseTools={() => setComposerToolsOpen(false)}
          />
        </main>
      </section>

      {selectedCitation ? (
        <EvidenceDrawer
          citation={selectedCitation}
          citations={selectedCitationGroup}
          onClose={() => setSelectedCitationSourceId(null)}
          onOpenReport={(invitationId) => {
            setSelectedCitationSourceId(null);
            setSelectedReportInvitationId(invitationId);
          }}
          onSelect={setSelectedCitationSourceId}
        />
      ) : null}

      <ApplicantReportModal
        preview={selectedReport}
        open={Boolean(selectedReport)}
        onOpenChange={(open) => {
          if (!open) setSelectedReportInvitationId(null);
        }}
      />
    </div>
  );
}

function citationsForAnswer(
  messages: readonly import("./types").ChatMessage[],
  selected: Citation,
) {
  for (const message of messages) {
    if (
      message.role === "assistant" &&
      message.answer.citations.some(
        (citation) => citation.sourceId === selected.sourceId,
      )
    ) {
      return message.answer.citations;
    }
  }
  return [selected];
}
