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

// `.review-panel` + `.review-panel__*`, shared with ReportView/TimelineView.
const PANEL = "overflow-hidden rounded-md border border-border bg-surface";

const PANEL_HEADER =
  "flex min-h-[58px] items-center justify-between gap-3 border-b border-border-muted" +
  " px-[14px] py-3 max-[520px]:items-start";

const PANEL_ICON =
  "grid size-[30px] flex-[0_0_30px] place-items-center rounded-md border" +
  " border-border-muted bg-surface-muted text-brand-strong";

const HUMAN_ONLY_BADGE =
  "inline-flex min-h-[22px] items-center gap-[5px] rounded-full bg-brand-soft" +
  " px-[7px] text-[8px] font-[650] whitespace-nowrap text-brand" +
  " max-[520px]:max-w-[108px] max-[520px]:whitespace-normal";

// `.review-field input/textarea`. Preflight already gives the textarea `resize: vertical`,
// so the source's `resize` declaration needs no utility.
const FIELD_CONTROL =
  "w-full rounded-md border border-border bg-surface px-[9px] py-[7px] text-[10px]" +
  " text-ink focus:border-brand focus:outline-2" +
  " focus:outline-[rgb(89_102_206_/_12%)] focus:outline-offset-0";

const FIELD_TEXTAREA = `min-h-[86px] leading-[1.55] ${FIELD_CONTROL}`;

// `.decision-actions button, .bookmark-control > button`. Border *color* is left off: each
// decision button carries its own tone, which outranked this rule at 0,2,0 vs 0,1,1.
const DECISION_BUTTON =
  "inline-flex min-h-[34px] items-center justify-center gap-[5px] rounded-[5px] border" +
  " bg-surface px-2 text-[9px] font-semibold disabled:cursor-not-allowed" +
  " disabled:opacity-45";

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
    <section className={PANEL} aria-labelledby="human-review-title">
      <header className={PANEL_HEADER}>
        <div className="flex min-w-0 items-center gap-[9px]">
          <span className={PANEL_ICON} aria-hidden="true">
            <ShieldCheck size={18} />
          </span>
          <span className="grid min-w-0 gap-px">
            <p className="font-mono text-[8px] font-semibold uppercase text-muted">
              Human in the loop
            </p>
            <h2 id="human-review-title" className="text-[12px] font-[650]">
              사람 검토
            </h2>
          </span>
        </div>
        <span className={HUMAN_ONLY_BADGE}>사람만 최종 결정</span>
      </header>

      <div className="grid gap-[14px] p-[14px]">
        <label className="grid gap-1.5">
          <span className="text-[9px] font-semibold text-ink-secondary">
            최종 결정 사유
          </span>
          <textarea
            className={FIELD_TEXTAREA}
            required
            rows={4}
            value={reason}
            placeholder="Evidence와 인터뷰 내용을 근거로 판단 사유를 기록하세요."
            onChange={(event) => setReason(event.target.value)}
          />
        </label>

        <div
          className="grid grid-cols-3 gap-[5px] max-[520px]:grid-cols-[1fr]"
          aria-label="최종 결정"
        >
          <button
            className={`${DECISION_BUTTON} border-[rgb(5_150_105_/_30%)] text-success`}
            type="button"
            disabled={!reason}
            onClick={() => decide("advance")}
          >
            <CheckCircle2 size={16} aria-hidden="true" />
            진행 결정
          </button>
          <button
            className={`${DECISION_BUTTON} border-[rgb(249_115_22_/_30%)] text-warning`}
            type="button"
            disabled={!reason}
            onClick={() => decide("hold")}
          >
            <Clock3 size={16} aria-hidden="true" />
            보류 결정
          </button>
          <button
            className={`${DECISION_BUTTON} border-[rgb(220_38_38_/_28%)] text-danger`}
            type="button"
            disabled={!reason}
            onClick={() => decide("reject")}
          >
            <XCircle size={16} aria-hidden="true" />
            불합격 결정
          </button>
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-1.5 max-[520px]:grid-cols-[1fr]">
          <label className="grid gap-1.5">
            <span className="text-[9px] font-semibold text-ink-secondary">
              검토 메모
            </span>
            <input
              className={`min-h-[34px] ${FIELD_CONTROL}`}
              value={note}
              placeholder="팀과 공유할 메모"
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
          <button
            className={`${DECISION_BUTTON} border-border`}
            type="button"
            disabled={!note}
            onClick={() => api.addBookmark(invitationId, note)}
          >
            <Bookmark size={16} aria-hidden="true" />
            북마크 저장
          </button>
        </div>

        {message && (
          <p
            className="flex items-center gap-1.5 rounded-[5px] bg-success-soft p-[9px] text-[9px] text-success"
            role="status"
          >
            <CheckCircle2 size={15} aria-hidden="true" />
            {message}
          </p>
        )}

        <section className="border-t border-border-muted pt-[13px]">
          <h3 className="mb-[9px] flex items-center gap-1.5 text-[10px]">
            <History size={16} aria-hidden="true" />
            검토 이력
          </h3>
          {history.length === 0 ? (
            <p className="text-[9px] text-muted">
              아직 기록된 검토 이력이 없습니다.
            </p>
          ) : (
            <ol className="grid gap-[7px]">
              {history.map((entry) => (
                <li
                  key={entry.id}
                  className="grid gap-0.5 border-l-2 border-border pl-2"
                >
                  <strong className="text-[9px]">{entry.type}</strong>
                  <span className="text-[8px] text-muted">
                    {entry.createdBy} · {entry.createdAt}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section
          className="grid gap-2 rounded-md border border-border-muted bg-surface-muted p-2.5"
          aria-label="개인정보 삭제 확인"
        >
          <header className="flex items-center justify-between gap-2.5">
            <span className="flex items-center gap-[5px] text-[8px] text-muted">
              <ShieldCheck size={16} aria-hidden="true" />
              삭제 검증
            </span>
            <strong className="text-[8px]">
              삭제 확인 {deletion.verifiedTargets}/{deletion.expectedTargets}
            </strong>
          </header>
          <div
            className="h-1 overflow-hidden rounded-[2px] bg-surface-strong"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={deletion.expectedTargets}
            aria-valuenow={deletion.verifiedTargets}
          >
            <span
              className="block h-full bg-success"
              style={{ width: `${deletionProgress}%` }}
            />
          </div>
          <p className="text-[8px] text-muted">
            {deletionStatusLabel(deletion.status)}
          </p>
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
