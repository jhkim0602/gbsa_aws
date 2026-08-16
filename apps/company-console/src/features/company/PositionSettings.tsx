import { CheckCircle2, LockKeyhole, Save, X } from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import {
  CriteriaStep,
  initialHiringDraft,
  toCriteriaConfiguration,
  type HiringDraft,
} from "../hiring";
import type {
  CompanyCriterionVersion,
  CompanyOperationsApi,
  CompanyPosition,
} from "./types";

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

  useEffect(() => {
    if (open) {
      setForm(positionForm(position));
      setError("");
    }
  }, [open, position]);

  if (!open) return null;

  const closed = position.status === "closed";
  const periodValid =
    !form.recruitmentStartAt ||
    !form.recruitmentEndAt ||
    form.recruitmentEndAt >= form.recruitmentStartAt;

  async function savePosition(
    event: Pick<FormEvent, "preventDefault">,
    status: "draft" | "active" | "closed",
    action: "save" | "activate" | "close",
  ) {
    event.preventDefault();
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
        recruitmentStartAt: form.recruitmentStartAt || null,
        recruitmentEndAt: form.recruitmentEndAt || null,
        status,
        rowVersion: position.rowVersion,
      });
      onPositionUpdated(
        updated,
        action === "activate"
          ? "채용을 확정하고 운영을 시작했습니다."
          : action === "close"
            ? "채용을 마감했습니다."
            : "포지션 정보를 저장했습니다.",
      );
      onClose();
    } catch (error) {
      setError(savePositionErrorMessage(error, action, hasCriteria));
    } finally {
      setSaving(false);
    }
  }

  return (
    <ModalShell
      title="포지션 간편 수정"
      description="공고와 운영 현황에 표시되는 기본 정보만 수정합니다."
      onClose={onClose}
    >
      <form
        className="position-modal-form"
        onSubmit={(event) =>
          void savePosition(
            event,
            position.status as "draft" | "active" | "closed",
            "save",
          )
        }
      >
        <fieldset disabled={closed || saving}>
          <div className="position-modal-form__grid">
            <label className="position-modal-form__wide">
              <span>포지션명</span>
              <input
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
            <label>
              <span>직무</span>
              <select
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
            <label>
              <span>채용 인원</span>
              <input
                type="number"
                min={1}
                max={10000}
                value={form.headcount}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    headcount: Number(event.target.value),
                  }))
                }
              />
            </label>
            <label>
              <span>모집 시작일</span>
              <input
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
            <label>
              <span>모집 종료일</span>
              <input
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
            <label className="position-modal-form__wide">
              <span>포지션 설명</span>
              <textarea
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
          <p className="form-alert" role="alert">
            모집 종료일은 시작일 이후여야 합니다.
          </p>
        ) : null}
        {error ? (
          <p className="form-alert" role="alert">
            {error}
          </p>
        ) : null}
        {!hasCriteria && position.status === "draft" ? (
          <p className="position-modal-form__note">
            면접 기준을 저장한 뒤 채용을 확정할 수 있습니다.
          </p>
        ) : null}

        <footer className="position-modal-actions">
          {closed ? (
            <span className="position-settings__locked">
              <LockKeyhole size={15} aria-hidden="true" />
              마감된 포지션은 수정할 수 없습니다.
            </span>
          ) : (
            <>
              <button
                className="button-secondary"
                type="submit"
                disabled={saving || !periodValid}
              >
                <Save size={15} aria-hidden="true" />
                변경 저장
              </button>
              {position.status === "draft" ? (
                <button
                  className="button-primary"
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
                  className="button-secondary is-danger"
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
        <p className="form-alert" role="alert">
          {error}
        </p>
      ) : null}
      <CriteriaStep
        draft={draft}
        submitting={saving}
        submitLabel="변경 저장"
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
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const frame = window.requestAnimationFrame(() => {
      const autofocus = document.querySelector<HTMLElement>(
        ".position-modal [autofocus]",
      );
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
      className="position-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className={`position-modal is-${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="position-modal-title"
        aria-describedby="position-modal-description"
      >
        <header className="position-modal__header">
          <div>
            <h2 id="position-modal-title">{title}</h2>
            <p id="position-modal-description">{description}</p>
          </div>
          <button
            ref={closeButtonRef}
            className="icon-button"
            type="button"
            title="닫기"
            aria-label={`${title} 닫기`}
            onClick={onClose}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <div className="position-modal__body">{children}</div>
      </section>
    </div>
  );
}

function savePositionErrorMessage(
  error: unknown,
  action: "save" | "activate" | "close",
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
  return "포지션 정보를 저장하지 못했습니다. 최신 값을 다시 확인해 주세요.";
}

function positionForm(position: CompanyPosition) {
  return {
    title: position.title,
    description: position.description,
    roleType: position.roleType ?? "개발",
    headcount: position.headcount ?? 1,
    recruitmentStartAt: position.recruitmentStartAt ?? "",
    recruitmentEndAt: position.recruitmentEndAt ?? "",
  };
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
  const criterionRows = criteria.criteria.map((criterion, index) => ({
    id: `criterion-${criteria.versionId}-${index}`,
    code: criterion.code,
    name: criterion.name,
    description: criterion.description,
    weight: criterion.weight,
    required: criterion.required,
    observableDimensions:
      criterion.verificationGuide.observableDimensions.join("\n"),
    strongAnswerSignals:
      criterion.verificationGuide.strongAnswerSignals.join("\n"),
    weakAnswerSignals: criterion.verificationGuide.weakAnswerSignals.join("\n"),
    followUpDirections:
      criterion.verificationGuide.followUpDirections.join("\n"),
    maxFollowUps: criterion.verificationGuide.maxFollowUps,
    timeBudgetSeconds: criterion.verificationGuide.timeBudgetSeconds,
    abstainGuidance: criterion.abstainGuidance,
    commonQuestions: criterion.commonQuestions.join("\n"),
  }));
  const jobRequirements = criteria.jobRequirements.length
    ? criteria.jobRequirements.map((requirement, index) => ({
        id: `requirement-${criteria.versionId}-${index}`,
        ...requirement,
      }))
    : [
        {
          id: `requirement-${criteria.versionId}-legacy`,
          requirementType: "required" as const,
          statement: "",
          priority: 1,
          criterionCode: criterionRows[0]?.code ?? "CRITERION_1",
        },
      ];
  return {
    ...positionForm(position),
    jobRequirements,
    criteria: criterionRows,
    prohibitedTopics: criteria.prohibitedTopics.join(", "),
    interviewDurationMinutes: criteria.interviewDurationMinutes,
  };
}
