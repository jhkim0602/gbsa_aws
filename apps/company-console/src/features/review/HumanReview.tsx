import { useState } from "react";

import type { ReviewApi } from "./types";

export function HumanReview({
  api,
  invitationId,
  deletion,
  history = [],
}: {
  api: ReviewApi;
  invitationId: string;
  deletion: {
    status: string;
    verifiedTargets: number;
    expectedTargets: number;
  };
  history?: Array<{
    id: string;
    type: string;
    createdBy: string;
    createdAt: string;
  }>;
}) {
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");

  async function decide(decision: "advance" | "reject" | "hold") {
    await api.recordFinalDecision(invitationId, decision, reason);
    setMessage("사람 결정이 기록되었습니다.");
  }

  return (
    <section aria-labelledby="human-review-title">
      <h2 id="human-review-title">사람 검토</h2>
      <label>
        최종 결정 사유
        <textarea
          required
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </label>
      <div>
        <button
          type="button"
          disabled={!reason}
          onClick={() => decide("advance")}
        >
          진행 결정
        </button>
        <button
          type="button"
          disabled={!reason}
          onClick={() => decide("reject")}
        >
          불합격 결정
        </button>
        <button type="button" disabled={!reason} onClick={() => decide("hold")}>
          보류 결정
        </button>
      </div>
      <label>
        검토 메모
        <input value={note} onChange={(event) => setNote(event.target.value)} />
      </label>
      <button
        type="button"
        disabled={!note}
        onClick={() => api.addBookmark(invitationId, note)}
      >
        북마크 저장
      </button>
      {message && <p role="status">{message}</p>}
      <h3>검토 이력</h3>
      <ol>
        {history.map((entry) => (
          <li key={entry.id}>
            {entry.type} · {entry.createdBy} · {entry.createdAt}
          </li>
        ))}
      </ol>
      <p>
        삭제 확인 {deletion.verifiedTargets}/{deletion.expectedTargets}
      </p>
      <p>{deletion.status}</p>
    </section>
  );
}
