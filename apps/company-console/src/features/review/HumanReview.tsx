import {
  Bookmark,
  CheckCircle2,
  Clock3,
  History,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useState } from "react";

import type { ReviewApi, ReviewDeletion, ReviewHistoryEntry } from "./types";

export function HumanReview({
  api,
  invitationId,
  deletion,
  history = [],
}: {
  api: ReviewApi;
  invitationId: string;
  deletion: ReviewDeletion;
  history?: ReviewHistoryEntry[];
}) {
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const deletionProgress =
    deletion.expectedTargets === 0
      ? 0
      : Math.round((deletion.verifiedTargets / deletion.expectedTargets) * 100);

  async function decide(decision: "advance" | "reject" | "hold") {
    await api.recordFinalDecision(invitationId, decision, reason);
    setMessage("사람 결정이 기록되었습니다.");
  }

  return (
    <section
      className="review-panel human-review-panel"
      aria-labelledby="human-review-title"
    >
      <header className="review-panel__header">
        <div className="review-panel__title">
          <span className="review-panel__icon" aria-hidden="true">
            <ShieldCheck size={18} />
          </span>
          <span>
            <p>Human in the loop</p>
            <h2 id="human-review-title">사람 검토</h2>
          </span>
        </div>
        <span className="human-only-badge">사람만 최종 결정</span>
      </header>

      <div className="human-review__body">
        <label className="review-field">
          <span>최종 결정 사유</span>
          <textarea
            required
            rows={4}
            value={reason}
            placeholder="Evidence와 인터뷰 내용을 근거로 판단 사유를 기록하세요."
            onChange={(event) => setReason(event.target.value)}
          />
        </label>

        <div className="decision-actions" aria-label="최종 결정">
          <button
            className="is-advance"
            type="button"
            disabled={!reason}
            onClick={() => decide("advance")}
          >
            <CheckCircle2 size={16} aria-hidden="true" />
            진행 결정
          </button>
          <button
            className="is-hold"
            type="button"
            disabled={!reason}
            onClick={() => decide("hold")}
          >
            <Clock3 size={16} aria-hidden="true" />
            보류 결정
          </button>
          <button
            className="is-reject"
            type="button"
            disabled={!reason}
            onClick={() => decide("reject")}
          >
            <XCircle size={16} aria-hidden="true" />
            불합격 결정
          </button>
        </div>

        <div className="bookmark-control">
          <label className="review-field">
            <span>검토 메모</span>
            <input
              value={note}
              placeholder="팀과 공유할 메모"
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
          <button
            type="button"
            disabled={!note}
            onClick={() => api.addBookmark(invitationId, note)}
          >
            <Bookmark size={16} aria-hidden="true" />
            북마크 저장
          </button>
        </div>

        {message && (
          <p className="review-success" role="status">
            <CheckCircle2 size={15} aria-hidden="true" />
            {message}
          </p>
        )}

        <section className="history-section">
          <h3>
            <History size={16} aria-hidden="true" />
            검토 이력
          </h3>
          {history.length === 0 ? (
            <p>아직 기록된 검토 이력이 없습니다.</p>
          ) : (
            <ol>
              {history.map((entry) => (
                <li key={entry.id}>
                  <strong>{entry.type}</strong>
                  <span>
                    {entry.createdBy} · {entry.createdAt}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="deletion-status" aria-label="개인정보 삭제 확인">
          <header>
            <span>
              <ShieldCheck size={16} aria-hidden="true" />
              삭제 검증
            </span>
            <strong>
              삭제 확인 {deletion.verifiedTargets}/{deletion.expectedTargets}
            </strong>
          </header>
          <div
            className="deletion-progress"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={deletion.expectedTargets}
            aria-valuenow={deletion.verifiedTargets}
          >
            <span style={{ width: `${deletionProgress}%` }} />
          </div>
          <p>{deletionStatusLabel(deletion.status)}</p>
        </section>
      </div>
    </section>
  );
}

function deletionStatusLabel(status: string) {
  return (
    {
      not_requested: "삭제 요청 없음",
      pending: "삭제 대기",
      retrying: "일부 저장소 재확인 중",
      completed: "모든 대상 삭제 확인",
    }[status] ?? status
  );
}
