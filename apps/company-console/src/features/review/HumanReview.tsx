import { AlertCircle, CheckCircle2, FileText, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { reviewErrorMessage } from "./reviewErrors";
import type { ReviewApi, ReviewRecruitingState } from "./types";

const PANEL = "overflow-hidden rounded-md border border-border bg-surface";
const PANEL_HEADER =
  "flex min-h-[58px] items-center justify-between gap-3 border-b border-border-muted px-[14px] py-3";
const PANEL_ICON =
  "grid size-[30px] flex-[0_0_30px] place-items-center rounded-md border border-border-muted bg-surface-muted text-brand-strong";
const FIELD_CONTROL =
  "w-full rounded-md border border-border bg-surface px-[9px] py-[7px] text-[10px] text-ink focus:border-brand focus:outline-2 focus:outline-[rgb(89_102_206_/_12%)] focus:outline-offset-0";
const ACTION_BUTTON =
  "inline-flex min-h-[36px] items-center justify-center gap-1.5 rounded-md bg-brand px-3 text-[9px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45";

export function HumanReview({
  api,
  invitationId,
  recruitingState,
}: {
  api: ReviewApi;
  invitationId: string;
  recruitingState: ReviewRecruitingState | null;
}) {
  const [note, setNote] = useState("");
  const [selectedStageId, setSelectedStageId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setSelectedStageId(recruitingState?.recruitingStageId ?? "");
  }, [recruitingState?.recruitingStageId]);

  async function saveNote() {
    const saved = await run(
      () => api.addNote(invitationId, note),
      "메모를 저장했습니다.",
      "메모를 저장하지 못했습니다.",
    );
    if (saved) setNote("");
  }

  async function saveFinalDecision() {
    if (!api.saveFinalDecisionStage || !selectedStageId) return;
    await run(
      () => api.saveFinalDecisionStage?.(selectedStageId) ?? Promise.resolve(),
      "최종 결정을 저장했습니다.",
      "최종 결정을 저장하지 못했습니다.",
    );
  }

  async function run(
    write: () => Promise<void>,
    confirmation: string,
    failure: string,
  ): Promise<boolean> {
    if (busy) return false;
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await write();
      setMessage(confirmation);
      return true;
    } catch (cause) {
      console.error("review write failed", cause);
      setError(reviewErrorMessage(cause, failure));
      return false;
    } finally {
      setBusy(false);
    }
  }

  const currentStage = recruitingState?.stages.find(
    (stage) => stage.recruitingStageId === recruitingState.recruitingStageId,
  );

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
        <span className="rounded-full bg-brand-soft px-2 py-1 text-[8px] font-semibold text-brand">
          사람만 최종 결정
        </span>
      </header>

      <div className="grid gap-4 p-[14px]">
        <section className="grid gap-2" aria-labelledby="review-note-title">
          <div className="flex items-center gap-1.5 text-ink-secondary">
            <FileText size={15} aria-hidden="true" />
            <h3 id="review-note-title" className="text-[10px] font-semibold">
              메모
            </h3>
          </div>
          <textarea
            className={`min-h-[86px] resize-y leading-[1.55] ${FIELD_CONTROL}`}
            rows={4}
            value={note}
            aria-label="검토 메모"
            placeholder="지원자에 대해 공유할 메모를 입력하세요."
            onChange={(event) => setNote(event.target.value)}
          />
          <button
            className={`${ACTION_BUTTON} justify-self-end`}
            type="button"
            disabled={!note.trim() || busy}
            onClick={() => void saveNote()}
          >
            메모 저장
          </button>
        </section>

        <section
          className="grid gap-2 border-t border-border-muted pt-4"
          aria-labelledby="final-decision-title"
        >
          <div className="flex items-center justify-between gap-2">
            <h3 id="final-decision-title" className="text-[10px] font-semibold">
              최종 결정
            </h3>
            <span className="text-[8px] text-muted">
              현재 단계 · {currentStage?.name ?? "불러오는 중"}
            </span>
          </div>
          <select
            className={FIELD_CONTROL}
            aria-label="최종 결정 채용 단계"
            value={selectedStageId}
            disabled={!recruitingState || busy}
            onChange={(event) => setSelectedStageId(event.target.value)}
          >
            <option value="">채용 단계를 선택하세요</option>
            {[...(recruitingState?.stages ?? [])]
              .sort((left, right) => left.sortOrder - right.sortOrder)
              .map((stage) => (
                <option
                  key={stage.recruitingStageId}
                  value={stage.recruitingStageId}
                >
                  {stage.name}
                </option>
              ))}
          </select>
          <button
            className={ACTION_BUTTON}
            type="button"
            title={
              api.saveFinalDecisionStage
                ? undefined
                : "최종 결정 저장은 채용 단계 쓰기 연동 후 활성화됩니다."
            }
            disabled={!selectedStageId || busy || !api.saveFinalDecisionStage}
            onClick={() => void saveFinalDecision()}
          >
            최종 결정 저장
          </button>
        </section>

        {message ? (
          <p
            className="flex items-center gap-1.5 rounded-md bg-success-soft p-2 text-[9px] text-success"
            role="status"
          >
            <CheckCircle2 size={14} aria-hidden="true" /> {message}
          </p>
        ) : null}
        {error ? (
          <p
            className="flex items-center gap-1.5 rounded-md bg-danger-soft p-2 text-[9px] text-danger"
            role="alert"
          >
            <AlertCircle size={14} aria-hidden="true" /> {error}
          </p>
        ) : null}
      </div>
    </section>
  );
}
