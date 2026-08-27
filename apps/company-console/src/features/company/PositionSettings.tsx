import {
  CalendarX2,
  CheckCircle2,
  LockKeyhole,
  Save,
  ServerCog,
  X,
} from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  BUTTON_SECONDARY_DANGER,
  formAlertClass,
  ICON_BUTTON,
} from "../../app/styles/primitives";
import {
  CriteriaStep,
  createDefaultCriteria,
  inferRequirementCriterionCode,
  initialHiringDraft,
  toCriteriaConfiguration,
  type HiringDraft,
} from "../hiring";
import {
  estimateInterviewCapacity,
  formatEstimatedKrw,
  MAX_GUARANTEED_INTERVIEW_CONCURRENCY,
} from "../hiring/interviewCapacityEstimate";
import type {
  CompanyCriterionVersion,
  CompanyOperationsApi,
  CompanyPosition,
} from "./types";

const BACKDROP =
  "fixed inset-0 z-100 grid place-items-center bg-[rgb(20_25_38_/_46%)] p-6" +
  " mw-720:items-end mw-720:p-0";
// At 720px the sheet drops its side and bottom borders and squares off its bottom corners.
const MODAL =
  "flex max-h-[calc(100vh-48px)] flex-col overflow-hidden rounded-lg border" +
  " border-border bg-surface shadow-[0_24px_72px_rgb(20_25_38_/_20%)]" +
  " mw-720:w-full mw-720:max-h-[92vh] mw-720:rounded-b-none mw-720:border-x-0" +
  " mw-720:border-b-0";
const MODAL_WIDTH = {
  standard: "w-[min(680px,100%)]",
  large: "w-[min(1080px,100%)]",
} as const;
const MODAL_HEADER =
  "flex items-start justify-between gap-5 border-b border-border p-[18px_20px]";
const MODAL_BODY = "overflow-y-auto";

/*
 * `.position-modal-form fieldset { padding: 0; border: 0; margin: 0 }` is exactly what
 * preflight already applies, so the fieldset carries no class.
 */
const FORM_GRID =
  "grid grid-cols-2 gap-4 p-5 mw-720:grid-cols-[minmax(0,1fr)]" +
  " mw-720:p-[18px_16px]";
const FORM_LABEL = "grid min-w-0 gap-[7px]";
const FORM_LABEL_TEXT = "text-[12px] font-[650]";
// `--color-link` resolves to `--color-brand`, so `focus:border-brand` is the same colour.
const FIELD_BASE =
  "w-full min-w-0 rounded-md border border-border bg-surface text-[13px]" +
  " text-ink focus:border-brand focus:outline-2 focus:outline-offset-1" +
  " focus:outline-[color-mix(in_srgb,var(--color-link)_18%,transparent)]";
const FIELD_CONTROL = `${FIELD_BASE} min-h-[42px] px-[11px]`;
const FIELD_TEXTAREA = `${FIELD_BASE} min-h-[118px] resize-y p-[11px] leading-[1.55]`;
const FORM_WIDE = "col-[1/-1] mw-720:col-[1]";
const FORM_NOTE = "mx-5 mb-[14px] text-[11px] text-muted";
const CAPACITY_NOTICE =
  "col-[1/-1] grid grid-cols-[auto_minmax(0,1fr)] gap-3 rounded-lg border" +
  " border-[color-mix(in_srgb,var(--color-link)_18%,var(--color-border))]" +
  " bg-[color-mix(in_srgb,var(--color-link)_4%,white)] p-3 mw-720:col-[1]";
const CANCELLATION_CONFIRM =
  "mx-5 mb-4 grid gap-3 rounded-lg border border-[color-mix(in_srgb,var(--color-danger)_28%,var(--color-border))]" +
  " bg-[color-mix(in_srgb,var(--color-danger)_4%,white)] p-4";

const MODAL_ACTIONS =
  "flex min-h-[66px] items-center justify-end gap-[9px] border-t border-border" +
  " bg-surface-muted p-[13px_20px] mw-720:flex-col mw-720:items-stretch" +
  " mw-720:p-[13px_16px] mw-720:[&_button]:w-full";
const LOCKED = "inline-flex items-center gap-[7px] text-[12px] text-muted";

export function PositionQuickEditModal({
  open,
  position,
  hasCriteria,
  api,
  onClose,
  onPositionUpdated,
}: {
  open: boolean;
  position: CompanyPosition;
  hasCriteria: boolean;
  api: CompanyOperationsApi;
  onClose(): void;
  onPositionUpdated(position: CompanyPosition, notice: string): void;
}) {
  const [form, setForm] = useState(() => positionForm(position));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [confirmingCancellation, setConfirmingCancellation] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(positionForm(position));
      setError("");
      setConfirmingCancellation(false);
    }
  }, [open, position]);

  if (!open) return null;

  const closed = position.status === "closed";
  const periodValid =
    !form.recruitmentStartAt ||
    !form.recruitmentEndAt ||
    form.recruitmentEndAt >= form.recruitmentStartAt;
  const capacityEstimate = estimateInterviewCapacity(form.interviewCapacity);

  async function persistPosition(
    status: "draft" | "active" | "closed",
    action: "save" | "activate" | "close" | "cancelReservation",
    interviewAt: string | null,
  ) {
    if (!periodValid) return;
    setSaving(true);
    setError("");
    try {
      const updated = await api.updatePosition({
        positionId: position.positionId,
        title: form.title.trim(),
        description: form.description.trim(),
        roleType: form.roleType || null,
        headcount: form.headcount || null,
        applicantCapacity: form.applicantCapacity || null,
        interviewCapacity: form.interviewCapacity || null,
        interviewAt,
        recruitmentStartAt: form.recruitmentStartAt || null,
        recruitmentEndAt: form.recruitmentEndAt || null,
        submissionRequirements: position.submissionRequirements,
        status,
        rowVersion: position.rowVersion,
      });
      onPositionUpdated(
        updated,
        action === "activate"
          ? "채용을 확정하고 운영을 시작했습니다."
          : action === "close"
            ? "채용을 마감했습니다."
            : action === "cancelReservation"
              ? "면접 예약을 취소했습니다. 예약 확장 계획도 함께 해제됩니다."
              : "포지션 정보를 저장했습니다.",
      );
      onClose();
    } catch (error) {
      setError(savePositionErrorMessage(error, action, hasCriteria));
    } finally {
      setSaving(false);
    }
  }

  function savePosition(
    event: Pick<FormEvent, "preventDefault">,
    status: "draft" | "active" | "closed",
    action: "save" | "activate" | "close",
  ) {
    event.preventDefault();
    return persistPosition(status, action, form.interviewAt || null);
  }

  return (
    <ModalShell
      title="포지션 간편 수정"
      description="공고와 운영 현황에 표시되는 기본 정보만 수정합니다."
      onClose={onClose}
    >
      <form
        onSubmit={(event) =>
          void savePosition(
            event,
            position.status as "draft" | "active" | "closed",
            "save",
          )
        }
      >
        <fieldset disabled={closed || saving}>
          <div className={FORM_GRID}>
            <label className={`${FORM_LABEL} ${FORM_WIDE}`}>
              <span className={FORM_LABEL_TEXT}>포지션명</span>
              <input
                className={FIELD_CONTROL}
                autoFocus
                required
                maxLength={200}
                value={form.title}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    title: event.target.value,
                  }))
                }
              />
            </label>
            <label className={FORM_LABEL}>
              <span className={FORM_LABEL_TEXT}>직무</span>
              <select
                className={FIELD_CONTROL}
                value={form.roleType}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    roleType: event.target.value,
                  }))
                }
              >
                <option value="개발">개발</option>
                <option value="데이터">데이터</option>
                <option value="인프라·보안">인프라·보안</option>
                <option value="제품·기획">제품·기획</option>
              </select>
            </label>
            <label className={FORM_LABEL}>
              <span className={FORM_LABEL_TEXT}>채용 인원</span>
              <input
                className={FIELD_CONTROL}
                type="number"
                min={1}
                max={MAX_GUARANTEED_INTERVIEW_CONCURRENCY}
                value={form.headcount}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    headcount: Number(event.target.value),
                  }))
                }
              />
            </label>
            <label className={FORM_LABEL}>
              <span className={FORM_LABEL_TEXT}>면접 정원</span>
              <input
                className={FIELD_CONTROL}
                type="number"
                min={1}
                max={MAX_GUARANTEED_INTERVIEW_CONCURRENCY}
                value={form.interviewCapacity}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    interviewCapacity: Number(event.target.value),
                  }))
                }
              />
            </label>
            <label className={FORM_LABEL}>
              <span className={FORM_LABEL_TEXT}>지원자 정원</span>
              <input
                className={FIELD_CONTROL}
                type="number"
                min={1}
                max={100000}
                value={form.applicantCapacity}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    applicantCapacity: Number(event.target.value),
                  }))
                }
              />
            </label>
            <aside
              aria-label="예약 오토스케일링 예상 비용"
              className={CAPACITY_NOTICE}
            >
              <span className="grid size-8 place-items-center rounded-full bg-brand-soft text-brand">
                <ServerCog aria-hidden="true" size={16} />
              </span>
              <div>
                <strong className="text-[11px] text-ink">
                  API {capacityEstimate.apiTasks}개 · Worker{" "}
                  {capacityEstimate.workerTasks}개 예약 · 추가 비용 약{" "}
                  {formatEstimatedKrw(
                    capacityEstimate.estimatedIncrementalCostKrw,
                  )}
                  원/회
                </strong>
                <p className="mt-1 text-[9px] leading-[1.5] text-muted">
                  API는 면접 15분 전부터 55분, Worker는 종료 5분 전부터 50분간
                  확보합니다. 실제 대기 작업량·환율에 따라 달라질 수 있습니다.
                </p>
              </div>
            </aside>
            <label className={FORM_LABEL}>
              <span className={FORM_LABEL_TEXT}>면접 시각</span>
              <input
                className={FIELD_CONTROL}
                type="datetime-local"
                value={form.interviewAt}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    interviewAt: event.target.value,
                  }))
                }
              />
            </label>
            <label className={FORM_LABEL}>
              <span className={FORM_LABEL_TEXT}>모집 시작일</span>
              <input
                className={FIELD_CONTROL}
                type="date"
                value={form.recruitmentStartAt}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    recruitmentStartAt: event.target.value,
                  }))
                }
              />
            </label>
            <label className={FORM_LABEL}>
              <span className={FORM_LABEL_TEXT}>모집 종료일</span>
              <input
                className={FIELD_CONTROL}
                type="date"
                min={form.recruitmentStartAt || undefined}
                value={form.recruitmentEndAt}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    recruitmentEndAt: event.target.value,
                  }))
                }
              />
            </label>
            <label className={`${FORM_LABEL} ${FORM_WIDE}`}>
              <span className={FORM_LABEL_TEXT}>포지션 설명</span>
              <textarea
                className={FIELD_TEXTAREA}
                required
                rows={5}
                maxLength={20000}
                value={form.description}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    description: event.target.value,
                  }))
                }
              />
            </label>
          </div>
        </fieldset>

        {!periodValid ? (
          <p className={formAlertClass("modalForm")} role="alert">
            모집 종료일은 시작일 이후여야 합니다.
          </p>
        ) : null}
        {error ? (
          <p className={formAlertClass("modalForm")} role="alert">
            {error}
          </p>
        ) : null}
        {!hasCriteria && position.status === "draft" ? (
          <p className={FORM_NOTE}>
            면접 기준을 저장한 뒤 채용을 확정할 수 있습니다.
          </p>
        ) : null}
        {confirmingCancellation ? (
          <section
            aria-label="면접 예약 취소 확인"
            className={CANCELLATION_CONFIRM}
          >
            <div>
              <strong className="text-[12px] text-danger">
                면접 예약 시각을 취소할까요?
              </strong>
              <p className="mt-1 text-[10px] leading-[1.55] text-muted">
                포지션과 지원자 초대는 유지됩니다. 미래 사전 확장만 취소되며,
                이미 진행 중인 면접 세션은 종료시키지 않습니다.
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <button
                className={BUTTON_SECONDARY}
                type="button"
                disabled={saving}
                onClick={() => setConfirmingCancellation(false)}
              >
                돌아가기
              </button>
              <button
                className={BUTTON_SECONDARY_DANGER}
                type="button"
                disabled={saving}
                onClick={() =>
                  void persistPosition(
                    position.status as "draft" | "active",
                    "cancelReservation",
                    null,
                  )
                }
              >
                <CalendarX2 size={15} aria-hidden="true" />
                예약 취소 확정
              </button>
            </div>
          </section>
        ) : null}

        <footer className={MODAL_ACTIONS}>
          {closed ? (
            <span className={LOCKED}>
              <LockKeyhole size={15} aria-hidden="true" />
              마감된 포지션은 수정할 수 없습니다.
            </span>
          ) : (
            <>
              {form.interviewAt && !confirmingCancellation ? (
                <button
                  className={BUTTON_SECONDARY_DANGER}
                  type="button"
                  disabled={saving}
                  onClick={() => setConfirmingCancellation(true)}
                >
                  <CalendarX2 size={15} aria-hidden="true" />
                  면접 예약 취소
                </button>
              ) : null}
              <button
                className={BUTTON_SECONDARY}
                type="submit"
                disabled={saving || !periodValid}
              >
                <Save size={15} aria-hidden="true" />
                변경 저장
              </button>
              {position.status === "draft" ? (
                <button
                  className={BUTTON_PRIMARY}
                  type="button"
                  disabled={saving || !periodValid || !hasCriteria}
                  onClick={(event) =>
                    void savePosition(event, "active", "activate")
                  }
                >
                  <CheckCircle2 size={15} aria-hidden="true" />
                  채용 확정
                </button>
              ) : (
                <button
                  className={BUTTON_SECONDARY_DANGER}
                  type="button"
                  disabled={saving}
                  onClick={(event) =>
                    void savePosition(event, "closed", "close")
                  }
                >
                  채용 마감
                </button>
              )}
            </>
          )}
        </footer>
      </form>
    </ModalShell>
  );
}

export function CriteriaEditModal({
  open,
  position,
  currentCriteria,
  api,
  onClose,
  onCriteriaUpdated,
}: {
  open: boolean;
  position: CompanyPosition;
  currentCriteria: CompanyCriterionVersion | null;
  api: CompanyOperationsApi;
  onClose(): void;
  onCriteriaUpdated(criteria: CompanyCriterionVersion, notice: string): void;
}) {
  const [draft, setDraft] = useState<HiringDraft>(() =>
    criterionDraft(position, currentCriteria),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setDraft(criterionDraft(position, currentCriteria));
      setError("");
    }
  }, [currentCriteria, open, position]);

  if (!open) return null;

  function update<K extends keyof HiringDraft>(key: K, value: HiringDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function saveCriteria(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.publishCriteria(
        position.positionId,
        toCriteriaConfiguration(draft),
      );
      const criteria = await api.listCriterionVersions(position.positionId);
      if (!criteria[0]) throw new Error("criteria_missing");
      onCriteriaUpdated(criteria[0], "면접 기준을 저장했습니다.");
      onClose();
    } catch {
      setError("면접 기준을 저장하지 못했습니다. 입력값을 확인해 주세요.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <ModalShell
      title="면접 기준 수정"
      description="지원자에게 동일하게 적용할 요구사항과 검증 기준을 수정합니다."
      size="large"
      onClose={onClose}
    >
      {error ? (
        <p className={formAlertClass("modalBody")} role="alert">
          {error}
        </p>
      ) : null}
      <CriteriaStep
        draft={draft}
        submitting={saving}
        submitLabel="변경 저장"
        variant="modal"
        update={update}
        onSubmit={(event) => void saveCriteria(event)}
      />
    </ModalShell>
  );
}

function ModalShell({
  title,
  description,
  size = "standard",
  onClose,
  children,
}: {
  title: string;
  description: string;
  size?: "standard" | "large";
  onClose(): void;
  children: ReactNode;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const frame = window.requestAnimationFrame(() => {
      // Scoped to the dialog now that `.position-modal` is gone from the markup.
      const autofocus =
        dialogRef.current?.querySelector<HTMLElement>("[autofocus]");
      (autofocus ?? closeButtonRef.current)?.focus();
    });
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("keydown", closeOnEscape);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  return (
    <div
      className={BACKDROP}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        ref={dialogRef}
        className={`${MODAL} ${MODAL_WIDTH[size]}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="position-modal-title"
        aria-describedby="position-modal-description"
      >
        <header className={MODAL_HEADER}>
          <div>
            <h2 className="text-[17px]" id="position-modal-title">
              {title}
            </h2>
            <p
              className="mt-1 text-[12px] text-muted"
              id="position-modal-description"
            >
              {description}
            </p>
          </div>
          <button
            ref={closeButtonRef}
            className={ICON_BUTTON}
            type="button"
            title="닫기"
            aria-label={`${title} 닫기`}
            onClick={onClose}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <div className={MODAL_BODY}>{children}</div>
      </section>
    </div>
  );
}

function savePositionErrorMessage(
  error: unknown,
  action: "save" | "activate" | "close" | "cancelReservation",
  hasCriteria: boolean,
) {
  const status =
    typeof error === "object" && error !== null && "status" in error
      ? (error as { status: unknown }).status
      : null;
  if (status === 409) {
    return "다른 곳에서 먼저 수정된 포지션입니다. 새로고침 후 다시 저장해 주세요.";
  }
  if (action === "activate" && !hasCriteria) {
    return "채용을 확정하려면 면접 기준을 먼저 저장해야 합니다.";
  }
  if (action === "cancelReservation") {
    return "면접 예약을 취소하지 못했습니다. 최신 일정을 다시 확인해 주세요.";
  }
  return "포지션 정보를 저장하지 못했습니다. 최신 값을 다시 확인해 주세요.";
}

function positionForm(position: CompanyPosition) {
  return {
    title: position.title,
    description: position.description,
    roleType: position.roleType ?? "개발",
    headcount: position.headcount ?? 1,
    applicantCapacity: position.applicantCapacity ?? 100,
    interviewCapacity: position.interviewCapacity ?? 1,
    interviewAt: toDateTimeLocalValue(position.interviewAt),
    recruitmentStartAt: position.recruitmentStartAt ?? "",
    recruitmentEndAt: position.recruitmentEndAt ?? "",
    submissionRequirements: position.submissionRequirements.map(
      (requirement) => ({
        materialType: requirement.materialType,
        label: requirement.materialType,
        description: "",
        required: requirement.required,
      }),
    ),
  };
}

function toDateTimeLocalValue(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const localTime = new Date(
    date.getTime() - date.getTimezoneOffset() * 60_000,
  );
  return localTime.toISOString().slice(0, 16);
}

function criterionDraft(
  position: CompanyPosition,
  criteria: CompanyCriterionVersion | null,
): HiringDraft {
  if (!criteria) {
    return {
      ...initialHiringDraft,
      ...positionForm(position),
    };
  }
  const criterionRows = createDefaultCriteria();
  const jobRequirements = criteria.jobRequirements.length
    ? criteria.jobRequirements.map((requirement, index) => ({
        id: `requirement-${criteria.versionId}-${index}`,
        ...requirement,
        priority: Math.min(index + 1, 5),
        criterionCode: inferRequirementCriterionCode(requirement.statement),
      }))
    : [
        {
          id: `requirement-${criteria.versionId}-legacy`,
          requirementType: "required" as const,
          statement: "",
          priority: 1,
          criterionCode: criterionRows[0].code,
        },
      ];
  return {
    ...initialHiringDraft,
    ...positionForm(position),
    descriptionCompleted: true,
    jobRequirements,
    criteria: criterionRows,
    prohibitedTopics: criteria.prohibitedTopics.join(", "),
    interviewDurationMinutes: criteria.interviewDurationMinutes,
    interviewLevel: criteria.interviewLevel,
    ...(criteria.personaDefinition
      ? {
          interviewerName: criteria.personaDefinition.name,
          interviewerTone: criteria.personaDefinition.tone,
          interviewerVoiceId: criteria.personaDefinition.voiceId,
        }
      : {}),
  };
}
