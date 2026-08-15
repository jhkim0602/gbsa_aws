import { useState } from "react";

import { Avatar } from "./Avatar";
import type { ConnectionState, InterviewState } from "./sessionStore";
import "./interview.css";

export function InterviewRoom({
  question,
  state,
  connectionState,
  textOnly,
  onStartAnswer,
  onCompleteAnswer,
  onReconnect,
  onAddExplanation,
}: {
  question: string;
  state: InterviewState;
  connectionState: ConnectionState;
  textOnly: boolean;
  onStartAnswer(): void;
  onCompleteAnswer(): void;
  onReconnect(): void;
  onAddExplanation?(): void;
}) {
  const [recording, setRecording] = useState(false);

  function startAnswer() {
    setRecording(true);
    onStartAnswer();
  }

  function completeAnswer() {
    setRecording(false);
    onCompleteAnswer();
  }

  return (
    <main className="interview-shell">
      <header className="interview-header room-header">
        <div>
          <p className="interview-brand">GBSA Interview Evidence</p>
          <h1>AI 구조화 면접</h1>
        </div>
        <span className="connection-indicator" data-state={connectionState}>
          {connectionState === "connected" ? "연결됨" : "연결 확인 중"}
        </span>
      </header>

      <p className="ai-disclosure">
        AI가 질문을 진행하며 최종 판단은 사람이 합니다.
      </p>

      {connectionState === "reconnecting" && (
        <section className="reconnect-banner" role="status">
          <p>연결을 복구하고 있습니다. 녹화 조각은 이 기기에 보관됩니다.</p>
          <button type="button" onClick={onReconnect}>
            다시 연결
          </button>
        </section>
      )}

      <section className="question-stage" aria-labelledby="current-question">
        <Avatar
          textOnly={textOnly}
          speaking={state === "in_progress" && !textOnly}
          speechMarkIndex={0}
        />
        <div>
          <p className="question-label">현재 질문</p>
          <h2 id="current-question">{question}</h2>
        </div>
      </section>

      {state === "preparing_question" && (
        <p className="room-state-message" role="status">
          답변을 바탕으로 다음 질문을 준비하고 있습니다.
        </p>
      )}
      {state === "paused" && (
        <p className="room-state-message" role="status">
          기술적인 이유로 면접이 일시 중지되었습니다. 이 상태는 평가에 반영되지
          않습니다.
        </p>
      )}
      {state === "completed" && (
        <p className="room-state-message" role="status">
          면접이 완료되었습니다. 제출된 답변은 기업 검토자가 확인합니다.
        </p>
      )}

      <section className="answer-controls">
        <div>
          <strong>
            {recording ? "답변을 녹음하고 있습니다" : "답변 준비"}
          </strong>
          <p>답변 완료를 누를 때만 최종 답변으로 확정됩니다.</p>
        </div>
        <div className="interview-actions">
          <button
            type="button"
            className="button-secondary"
            disabled={recording || state === "paused"}
            onClick={startAnswer}
          >
            답변 시작
          </button>
          <button
            type="button"
            className="button-primary"
            disabled={!recording || state === "paused"}
            onClick={completeAnswer}
          >
            답변 완료
          </button>
          {onAddExplanation && (
            <button
              type="button"
              className="button-secondary"
              disabled={recording || state === "paused"}
              onClick={onAddExplanation}
            >
              정정 또는 추가 설명
            </button>
          )}
        </div>
      </section>
    </main>
  );
}
