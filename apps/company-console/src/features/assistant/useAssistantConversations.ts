import { useCallback, useRef, useState } from "react";

import type { CompanyInvitation, CompanyPosition } from "../company/types";
import type { RecruitingAssistantApi } from "./api";
import { conversationTitle, toRagAnswer, toStreamingRagAnswer } from "./data";
import { isPositionArchived, isPositionRecruiting } from "./positionLifecycle";
import type { ChatConversation, InsightByPosition, PositionRow } from "./types";
import { INITIAL_CONVERSATION } from "./types";

const SEARCH_UNCONFIRMED_MESSAGE =
  "선택한 범위의 채용 리포트를 검색해봤지만, 지금 질문과 직접 연결되는 내용을 확인할 수 없었어요. 채용 데이터와 관련된 다른 표현으로 다시 질문해 주세요.";

export function useAssistantConversations({
  assistantApi,
  positions,
  invitations,
  insightsByPosition,
  positionRows,
}: {
  assistantApi: RecruitingAssistantApi;
  positions: readonly CompanyPosition[];
  invitations: readonly CompanyInvitation[];
  insightsByPosition: InsightByPosition;
  positionRows: readonly PositionRow[];
}) {
  const [conversations, setConversations] = useState<
    readonly ChatConversation[]
  >([INITIAL_CONVERSATION]);
  const [activeConversationId, setActiveConversationId] = useState(
    INITIAL_CONVERSATION.id,
  );
  const sequence = useRef(2);
  const activeConversation =
    conversations.find(
      (conversation) => conversation.id === activeConversationId,
    ) ?? conversations[0];

  const createConversation = useCallback((scopeId = "all") => {
    const id = `conversation-${sequence.current}`;
    sequence.current += 1;
    const next: ChatConversation = {
      id,
      title: "새 채용 분석",
      scopeId,
      messages: [],
      pending: false,
    };
    setConversations((current) => [next, ...current]);
    setActiveConversationId(id);
    return id;
  }, []);

  const deleteConversation = useCallback(
    (conversationId: string) => {
      setConversations((current) => {
        const remaining = current.filter(
          (conversation) => conversation.id !== conversationId,
        );
        if (remaining.length) {
          if (conversationId === activeConversationId) {
            setActiveConversationId(remaining[0].id);
          }
          return remaining;
        }
        const replacement: ChatConversation = {
          ...INITIAL_CONVERSATION,
          id: `conversation-${sequence.current}`,
        };
        sequence.current += 1;
        setActiveConversationId(replacement.id);
        return [replacement];
      });
    },
    [activeConversationId],
  );

  const renameConversation = useCallback(
    (conversationId: string, nextTitle: string) => {
      const title = nextTitle.trim().slice(0, 60);
      if (!title) return false;
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id === conversationId
            ? { ...conversation, title, titleCustomized: true }
            : conversation,
        ),
      );
      return true;
    },
    [],
  );

  const updateConversationScope = useCallback(
    (scopeId: string) => {
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id === activeConversationId &&
          conversation.messages.length === 0 &&
          !conversation.pending
            ? { ...conversation, scopeId }
            : conversation,
        ),
      );
    },
    [activeConversationId],
  );

  const ask = useCallback(
    async (nextQuestion: string) => {
      const normalized = nextQuestion.trim();
      if (!normalized || !activeConversation || activeConversation.pending) {
        return false;
      }
      const conversationId = activeConversation.id;
      const scopeId = activeConversation.scopeId;
      const activeScopeLabel =
        scopeId === "all"
          ? "전체 진행 중 포지션"
          : (() => {
              const position = positions.find(
                (item) => item.positionId === scopeId,
              );
              if (!position) return "선택한 포지션";
              return isPositionArchived(position)
                ? `${position.title} · 모집 종료`
                : position.title;
            })();
      const scopePositions =
        scopeId === "all"
          ? positions.filter((position) => isPositionRecruiting(position))
          : positions.filter((position) => position.positionId === scopeId);
      const scopePositionIds = new Set(
        scopePositions.map((position) => position.positionId),
      );
      const scopeInvitations = invitations.filter((invitation) =>
        scopePositionIds.has(invitation.positionId),
      );
      const scopePositionRows = positionRows.filter((row) =>
        scopePositionIds.has(row.positionId),
      );
      const messageSequence = sequence.current;
      const assistantMessageId = `message-${messageSequence}-assistant`;
      sequence.current += 1;
      setConversations((current) =>
        current.map((conversation) => {
          if (conversation.id !== conversationId) return conversation;
          return {
            ...conversation,
            title:
              conversation.messages.length === 0 &&
              !conversation.titleCustomized
                ? conversationTitle(normalized)
                : conversation.title,
            pending: true,
            error: undefined,
            messages: [
              ...conversation.messages,
              {
                id: `message-${messageSequence}-user`,
                role: "user" as const,
                content: normalized,
              },
              {
                id: assistantMessageId,
                role: "assistant" as const,
                answer: toStreamingRagAnswer("", scopePositionRows),
              },
            ],
          };
        }),
      );
      try {
        const response = await assistantApi.streamAnswer(
          {
            scope: scopeId === "all" ? "company" : "position",
            ...(scopeId === "all" ? {} : { positionId: scopeId }),
            query: normalized,
            limit: 8,
          },
          {
            onDelta(_delta, accumulated) {
              setConversations((current) =>
                updateAssistantMessage(
                  current,
                  conversationId,
                  assistantMessageId,
                  toStreamingRagAnswer(accumulated, scopePositionRows),
                ),
              );
            },
          },
        );
        const answer = toRagAnswer({
          response,
          scopeLabel: activeScopeLabel,
          positionRows: scopePositionRows,
          positions: scopePositions,
          invitations: scopeInvitations,
          insightsByPosition,
        });
        setConversations((current) =>
          current.map((conversation) =>
            conversation.id === conversationId
              ? {
                  ...conversation,
                  pending: false,
                  messages: conversation.messages.map((message) =>
                    message.id === assistantMessageId &&
                    message.role === "assistant"
                      ? { ...message, answer }
                      : message,
                  ),
                }
              : conversation,
          ),
        );
        return true;
      } catch {
        setConversations((current) =>
          current.map((conversation) =>
            conversation.id === conversationId
              ? {
                  ...conversation,
                  pending: false,
                  error: undefined,
                  messages: conversation.messages.map((message) =>
                    message.id === assistantMessageId &&
                    message.role === "assistant"
                      ? {
                          ...message,
                          answer: {
                            ...message.answer,
                            paragraphs: [SEARCH_UNCONFIRMED_MESSAGE],
                            findings: [],
                            sourceIds: [],
                            citations: [],
                            streaming: false,
                            degradedMode: "search_unavailable",
                          },
                        }
                      : message,
                  ),
                }
              : conversation,
          ),
        );
        return true;
      }
    },
    [
      activeConversation,
      assistantApi,
      insightsByPosition,
      invitations,
      positionRows,
      positions,
    ],
  );

  return {
    conversations,
    activeConversation,
    activeConversationId,
    setActiveConversationId,
    createConversation,
    deleteConversation,
    renameConversation,
    updateConversationScope,
    ask,
  };
}

function updateAssistantMessage(
  conversations: readonly ChatConversation[],
  conversationId: string,
  messageId: string,
  answer: import("./types").RagAnswer,
) {
  return conversations.map((conversation) =>
    conversation.id === conversationId
      ? {
          ...conversation,
          messages: conversation.messages.map((message) =>
            message.id === messageId && message.role === "assistant"
              ? { ...message, answer }
              : message,
          ),
        }
      : conversation,
  );
}
