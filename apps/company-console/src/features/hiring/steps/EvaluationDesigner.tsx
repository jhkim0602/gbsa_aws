import {
  BarChart3,
  ChevronDown,
  CircleHelp,
  Link2,
  ListChecks,
  Plus,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";

import { ICON_BUTTON } from "../../../app/styles/primitives";
import {
  Field,
  formInputClass,
  formTextareaClass,
  type FormVariant,
} from "../components/FormPrimitives";
import {
  createCriterionDraft,
  createRequirementDraft,
  type CriterionDraft,
  type HiringDraft,
  type HiringDraftUpdater,
  type JobRequirementDraft,
  type RequirementType,
} from "../types";

const priorityOptions = [
  { value: 1, label: "핵심" },
  { value: 2, label: "중요" },
  { value: 3, label: "참고" },
] as const;

// `.evaluation-designer` is declared twice; the later `gap: 48px` beats the first `44px`.
const DESIGNER = "grid gap-12 mw-620:gap-8";
const BLOCK =
  "grid gap-[22px] not-first:border-t not-first:border-t-border not-first:pt-9";
const BLOCK_HEADER = "flex items-start justify-between gap-6";
const BLOCK_EYEBROW = "font-mono text-[9px] font-[650] text-brand";
const BLOCK_TITLE = "mt-1 text-[17px] font-bold";
const BLOCK_TEXT = "mt-[5px] text-[10px] leading-[1.5] text-muted";
const BLOCK_COUNT =
  "pt-[18px] font-mono text-[10px] whitespace-nowrap text-muted";

// `.requirement-item` carries no rules of its own, so the row wrapper needs no class.
const WORKLIST = "border-t border-t-border";
const WORKLINE =
  "grid items-end gap-2.5 border-b border-b-border-muted py-[13px]" +
  " grid-cols-[28px_86px_minmax(220px,1.6fr)_90px_minmax(150px,0.9fr)_34px]" +
  " mw-780:grid-cols-[24px_82px_minmax(0,1fr)_34px]" +
  " mw-620:grid-cols-[24px_minmax(0,1fr)_34px]";
// The delete button keeps `ICON_BUTTON`'s 32px width and only grows taller.
const WORKLINE_DELETE =
  `${ICON_BUTTON} self-end h-[50px] mw-780:col-[4] mw-780:row-[1]` +
  " mw-620:col-[3]";
const WORKLINE_INDEX =
  "grid h-[34px] place-items-center font-mono text-[9px] text-subtle";

// `margin: 0` and `padding: 0` on the fieldset are what preflight already applies.
const KIND =
  "grid h-[34px] grid-cols-2 overflow-hidden rounded-sm border border-border mw-620:col-[2]";
const KIND_BUTTON = "text-[9px] not-first:border-l not-first:border-l-border";
const KIND_BUTTON_ACTIVE = `${KIND_BUTTON} bg-ink font-[650] text-white`;
const KIND_BUTTON_IDLE = `${KIND_BUTTON} bg-white text-muted`;

const REQUIREMENT_FIELD = "grid min-w-0 gap-[5px] mw-620:col-[2]";
const REQUIREMENT_FIELD_LATE = `${REQUIREMENT_FIELD} mw-780:col-[3]`;
const REQUIREMENT_LABEL =
  "flex items-center gap-1 text-[9px] font-semibold text-muted";
const REQUIREMENT_CONTROL =
  "w-full min-h-[34px] rounded-none border-b border-b-border bg-transparent px-2" +
  " text-[11px] text-ink";
const REQUIREMENT_STATEMENT = `${REQUIREMENT_CONTROL} h-[50px] resize-y py-2 leading-[1.45]`;

const INSERT =
  "group grid min-h-8 grid-cols-[minmax(18px,1fr)_28px_minmax(18px,1fr)]" +
  " items-center gap-2";
const INSERT_RULE =
  "h-px bg-border-muted group-has-[button:hover]:bg-[#5966ce59]";
const INSERT_BUTTON =
  "grid size-7 place-items-center rounded-full bg-transparent text-subtle" +
  " hover:bg-brand-soft hover:text-brand hover:outline-none";

const OVERVIEW =
  "grid grid-cols-[120px_minmax(0,1fr)] items-center gap-[22px] border-y" +
  " border-y-border bg-surface-muted px-[18px] py-4" +
  " mw-620:grid-cols-[minmax(0,1fr)]";
const OVERVIEW_TITLE =
  "flex items-center gap-[7px] text-[10px] font-[650] text-ink-secondary";
const OVERVIEW_BARS = "grid gap-[7px]";
const OVERVIEW_ROW =
  "grid grid-cols-[minmax(90px,130px)_minmax(120px,1fr)_30px] items-center gap-2.5";
const OVERVIEW_LABEL = "truncate text-[9px] text-muted";
const OVERVIEW_TRACK = "block h-1.5 overflow-hidden bg-surface-strong";
const OVERVIEW_FILL =
  "block h-full bg-brand transition-[width] duration-[120ms]";
const OVERVIEW_VALUE = "text-right font-mono";

const AXIS_LIST = "border-t border-t-border";
// `.criterion-axis-item` exists only to pull the trailing insert control up.
const AXIS_ITEM = "last:[&>:last-child]:-mb-4";
const AXIS =
  "grid grid-cols-[118px_minmax(0,1fr)] items-start gap-x-[22px] gap-y-[14px]" +
  " border-b border-b-border py-[22px] mw-780:grid-cols-[minmax(0,1fr)]";
const AXIS_HEADER = "flex items-center gap-2 self-start";
const AXIS_INDEX = "font-mono text-[9px] font-bold text-brand";
// `size-7` is emitted before `size-8`, so the smaller box has to come from `h-7 w-7`.
const AXIS_DELETE = `${ICON_BUTTON} ml-auto h-7 w-7`;
const AXIS_REQUIRED = "flex items-center gap-1 text-[9px] text-muted";

const AXIS_IDENTITY =
  "grid grid-cols-[minmax(160px,0.8fr)_minmax(220px,1.2fr)] gap-[18px]" +
  " mw-780:col-[1] mw-620:grid-cols-[minmax(0,1fr)]";
/*
 * `.criterion-axis__identity .form-field input` is declared after the wizard's own
 * `.form-field input` at equal specificity, so it wins in both contexts. Tailwind emits
 * `min-h-[38px]` and `text-[12px]` *before* the values they have to beat, so this cannot
 * compose onto `formInputClass` and is spelled out instead.
 */
const AXIS_IDENTITY_INPUT_BASE =
  "w-full min-h-[38px] p-0 text-[12px] text-ink placeholder:text-subtle" +
  " shadow-[inset_0_1px_#d0d7de33] focus:border-brand" +
  " focus:shadow-[0_0_0_3px_#5966ce1f]";
const axisIdentityInputClass = (variant: FormVariant) =>
  variant === "modal"
    ? `${AXIS_IDENTITY_INPUT_BASE} rounded-md border border-border bg-white`
    : `${AXIS_IDENTITY_INPUT_BASE} rounded-none border-b border-b-border bg-transparent`;

const AXIS_WEIGHT =
  "col-[2] grid grid-cols-[minmax(0,1fr)_54px] items-end gap-3 mw-780:col-[1]";
const AXIS_WEIGHT_LABEL = "grid gap-2";
const AXIS_WEIGHT_LABEL_TEXT =
  "flex items-center gap-[5px] text-[9px] font-semibold text-muted";
const AXIS_WEIGHT_RANGE =
  "h-[5px] w-full bg-surface-strong p-0 shadow-none accent-brand";
const AXIS_WEIGHT_INPUT =
  "h-[34px] w-full rounded-none border-b border-b-border bg-transparent px-1" +
  " text-right font-mono text-[12px] text-ink";

/*
 * `.criterion-advanced` and its `summary`/`__body` are each declared twice; only the later
 * half renders, which strips the card back to a pair of hairlines on a transparent ground.
 */
const ADVANCED =
  "group col-[2] overflow-hidden border-y border-y-border-muted mw-780:col-[1]";
const ADVANCED_SUMMARY =
  "grid min-h-[46px] cursor-pointer grid-cols-[minmax(0,1fr)_auto_16px]" +
  " items-center gap-2.5 p-0 list-none [&::-webkit-details-marker]:hidden" +
  " mw-620:grid-cols-[minmax(0,1fr)_16px]";
const ADVANCED_SUMMARY_TEXT =
  "inline-flex min-w-0 items-center gap-[7px] text-[10px] font-[650] text-ink-secondary";
const ADVANCED_SUMMARY_NOTE = "ml-auto text-[9px] text-[#1f8a70] mw-620:hidden";
const ADVANCED_CHEVRON =
  "text-muted transition-transform duration-[160ms] group-open:rotate-180";
const ADVANCED_BODY =
  "grid gap-[14px] border-t border-t-border-muted bg-surface pt-[18px] pb-1";
const GUIDE_NOTE =
  "border-l-2 border-l-[#1f8a70] bg-[#f3f8f6] px-3 py-2.5 text-[9px]" +
  " leading-[1.55] text-muted";
const GUIDE_HELP = "flex items-center gap-1.5 text-[9px] text-subtle";
const FIELD_GRID =
  "grid grid-cols-2 gap-[14px] mw-620:grid-cols-[minmax(0,1fr)]";
const FIELD_GRID_THREE = `${FIELD_GRID} grid-cols-3`;

export function EvaluationDesigner({
  draft,
  update,
  variant = "wizard",
}: {
  draft: HiringDraft;
  update: HiringDraftUpdater;
  variant?: FormVariant;
}) {
  const totalWeight = draft.criteria.reduce(
    (total, criterion) => total + criterion.weight,
    0,
  );

  function updateRequirement(id: string, patch: Partial<JobRequirementDraft>) {
    update(
      "jobRequirements",
      draft.jobRequirements.map((requirement) =>
        requirement.id === id ? { ...requirement, ...patch } : requirement,
      ),
    );
  }

  function addRequirement(afterIndex: number) {
    const nextIndex = nextDraftIndex(
      draft.jobRequirements.map((requirement) => requirement.id),
    );
    const next = createRequirementDraft(nextIndex);
    const linkedCriterion =
      draft.jobRequirements[afterIndex]?.criterionCode ??
      draft.criteria[0]?.code ??
      next.criterionCode;
    const requirements = [...draft.jobRequirements];
    requirements.splice(afterIndex + 1, 0, {
      ...next,
      criterionCode: linkedCriterion,
      priority: Math.min(afterIndex + 2, 3),
    });
    update("jobRequirements", requirements);
  }

  function removeRequirement(id: string) {
    if (draft.jobRequirements.length === 1) return;
    update(
      "jobRequirements",
      draft.jobRequirements.filter((requirement) => requirement.id !== id),
    );
  }

  function updateCriterion(id: string, patch: Partial<CriterionDraft>) {
    update(
      "criteria",
      draft.criteria.map((criterion) =>
        criterion.id === id ? { ...criterion, ...patch } : criterion,
      ),
    );
  }

  function addCriterion(afterIndex: number) {
    const nextIndex = nextCriterionIndex(draft.criteria);
    const criteria = [...draft.criteria];
    criteria.splice(afterIndex + 1, 0, createCriterionDraft(nextIndex));
    update("criteria", criteria);
  }

  function removeCriterion(id: string) {
    if (draft.criteria.length === 1) return;
    const removed = draft.criteria.find((criterion) => criterion.id === id);
    if (!removed) return;

    const criteria = draft.criteria.filter((criterion) => criterion.id !== id);
    const fallbackCode = criteria[0].code;
    update("criteria", criteria);
    update(
      "jobRequirements",
      draft.jobRequirements.map((requirement) =>
        requirement.criterionCode === removed.code
          ? { ...requirement, criterionCode: fallbackCode }
          : requirement,
      ),
    );
  }

  return (
    <div className={DESIGNER}>
      <section className={BLOCK} aria-labelledby="requirements-title">
        <header className={BLOCK_HEADER}>
          <div className="min-w-0">
            <span className={BLOCK_EYEBROW}>01 · 채용 조건</span>
            <h3 className={BLOCK_TITLE} id="requirements-title">
              필수·우대 자격요건
            </h3>
            <p className={BLOCK_TEXT}>
              채용공고의 문장처럼 자유롭게 적고, 면접에서 확인할 평가기준과
              연결합니다.
            </p>
          </div>
          <strong className={BLOCK_COUNT}>
            {draft.jobRequirements.length}개
          </strong>
        </header>

        <div className={WORKLIST}>
          {draft.jobRequirements.map((requirement, index) => (
            <div key={requirement.id}>
              <div className={WORKLINE}>
                <span className={WORKLINE_INDEX}>
                  {String(index + 1).padStart(2, "0")}
                </span>
                <RequirementKind
                  index={index}
                  value={requirement.requirementType}
                  onChange={(requirementType) =>
                    updateRequirement(requirement.id, { requirementType })
                  }
                />
                <label className={REQUIREMENT_FIELD}>
                  <span className={REQUIREMENT_LABEL}>
                    자격요건 {index + 1}
                  </span>
                  <textarea
                    aria-label={`요구사항 ${index + 1}`}
                    className={REQUIREMENT_STATEMENT}
                    placeholder={
                      index === 0
                        ? "예: 스스로 높은 기준을 세우고 끝까지 파고드는 분"
                        : "자격요건을 자유롭게 입력해 주세요."
                    }
                    rows={2}
                    value={requirement.statement}
                    onChange={(event) =>
                      updateRequirement(requirement.id, {
                        statement: event.target.value,
                      })
                    }
                  />
                </label>
                <label className={REQUIREMENT_FIELD_LATE}>
                  <span className={REQUIREMENT_LABEL}>중요도 {index + 1}</span>
                  <select
                    aria-label={`중요도 ${index + 1}`}
                    className={REQUIREMENT_CONTROL}
                    value={requirement.priority}
                    onChange={(event) =>
                      updateRequirement(requirement.id, {
                        priority: Number(event.target.value),
                      })
                    }
                  >
                    {priorityOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={REQUIREMENT_FIELD_LATE}>
                  <span className={REQUIREMENT_LABEL}>
                    <Link2 aria-hidden="true" size={12} />
                    연결 평가기준 {index + 1}
                  </span>
                  <select
                    aria-label={`연결 평가기준 ${index + 1}`}
                    className={REQUIREMENT_CONTROL}
                    value={requirement.criterionCode}
                    onChange={(event) =>
                      updateRequirement(requirement.id, {
                        criterionCode: event.target.value,
                      })
                    }
                  >
                    {draft.criteria.map((criterion, criterionIndex) => (
                      <option key={criterion.code} value={criterion.code}>
                        {criterion.name.trim() ||
                          `평가기준 ${criterionIndex + 1}`}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  aria-label={`요구사항 ${index + 1} 삭제`}
                  className={WORKLINE_DELETE}
                  disabled={draft.jobRequirements.length === 1}
                  title="요구사항 삭제"
                  type="button"
                  onClick={() => removeRequirement(requirement.id)}
                >
                  <Trash2 aria-hidden="true" size={14} />
                </button>
              </div>
              <InsertControl
                label="요구사항 추가"
                onClick={() => addRequirement(index)}
              />
            </div>
          ))}
        </div>
      </section>

      <section className={BLOCK} aria-labelledby="criteria-title">
        <header className={BLOCK_HEADER}>
          <div className="min-w-0">
            <span className={BLOCK_EYEBROW}>02 · 평가축</span>
            <h3 className={BLOCK_TITLE} id="criteria-title">
              평가기준과 가중치
            </h3>
            <p className={BLOCK_TEXT}>
              자격요건을 묶는 평가 주제를 만들고 면접과 리포트에서 강조할 비중을
              설정합니다.
            </p>
          </div>
          <strong className={BLOCK_COUNT}>합계 {totalWeight}</strong>
        </header>

        <CriterionOverview criteria={draft.criteria} total={totalWeight} />

        <div className={AXIS_LIST}>
          {draft.criteria.map((criterion, index) => (
            <div className={AXIS_ITEM} key={criterion.id}>
              <article className={AXIS}>
                <header className={AXIS_HEADER}>
                  <span className={AXIS_INDEX}>
                    축 {String(index + 1).padStart(2, "0")}
                  </span>
                  <label className={AXIS_REQUIRED}>
                    <input
                      checked={criterion.required}
                      className="accent-brand"
                      type="checkbox"
                      onChange={(event) =>
                        updateCriterion(criterion.id, {
                          required: event.target.checked,
                        })
                      }
                    />
                    필수
                  </label>
                  <button
                    aria-label={`평가기준 ${index + 1} 삭제`}
                    className={AXIS_DELETE}
                    disabled={draft.criteria.length === 1}
                    title="평가기준 삭제"
                    type="button"
                    onClick={() => removeCriterion(criterion.id)}
                  >
                    <Trash2 aria-hidden="true" size={14} />
                  </button>
                </header>

                <div className={AXIS_IDENTITY}>
                  <Field label={`평가기준 이름 ${index + 1}`} variant={variant}>
                    <input
                      required
                      aria-label={`평가기준 이름 ${index + 1}`}
                      className={axisIdentityInputClass(variant)}
                      placeholder={
                        index === 0 ? "예: 태도와 문화" : "예: 기술과 능력"
                      }
                      value={criterion.name}
                      onChange={(event) =>
                        updateCriterion(criterion.id, {
                          name: event.target.value,
                        })
                      }
                    />
                  </Field>
                  <Field label={`설명 ${index + 1}`} variant={variant}>
                    <input
                      aria-label={`설명 ${index + 1}`}
                      className={axisIdentityInputClass(variant)}
                      placeholder="이 기준이 확인하는 역량과 판단 관점"
                      value={criterion.description}
                      onChange={(event) =>
                        updateCriterion(criterion.id, {
                          description: event.target.value,
                        })
                      }
                    />
                  </Field>
                </div>

                <div className={AXIS_WEIGHT}>
                  <label className={AXIS_WEIGHT_LABEL}>
                    <span className={AXIS_WEIGHT_LABEL_TEXT}>
                      <SlidersHorizontal aria-hidden="true" size={12} />
                      가중치 {index + 1}
                    </span>
                    <input
                      aria-label={`가중치 ${index + 1}`}
                      className={AXIS_WEIGHT_RANGE}
                      max={100}
                      min={0}
                      step={5}
                      type="range"
                      value={criterion.weight}
                      onChange={(event) =>
                        updateCriterion(criterion.id, {
                          weight: Number(event.target.value),
                        })
                      }
                    />
                  </label>
                  <label className={AXIS_WEIGHT_LABEL}>
                    <span className="sr-only">
                      가중치 {index + 1} 직접 입력
                    </span>
                    <input
                      aria-label={`가중치 ${index + 1} 직접 입력`}
                      className={AXIS_WEIGHT_INPUT}
                      max={100}
                      min={0}
                      type="number"
                      value={criterion.weight}
                      onChange={(event) =>
                        updateCriterion(criterion.id, {
                          weight: clampWeight(event.target.value),
                        })
                      }
                    />
                  </label>
                </div>

                <CriterionGuide
                  criterion={criterion}
                  index={index}
                  variant={variant}
                  onChange={(patch) => updateCriterion(criterion.id, patch)}
                />
              </article>
              <InsertControl
                label="평가기준 추가"
                onClick={() => addCriterion(index)}
              />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function RequirementKind({
  index,
  value,
  onChange,
}: {
  index: number;
  value: RequirementType;
  onChange: (value: RequirementType) => void;
}) {
  return (
    <fieldset className={KIND}>
      <legend className="sr-only">요구사항 유형 {index + 1}</legend>
      {(["required", "preferred"] as const).map((type) => (
        <button
          aria-pressed={value === type}
          className={value === type ? KIND_BUTTON_ACTIVE : KIND_BUTTON_IDLE}
          key={type}
          type="button"
          onClick={() => onChange(type)}
        >
          {type === "required" ? "필수" : "우대"}
        </button>
      ))}
    </fieldset>
  );
}

function InsertControl({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <div className={INSERT}>
      <span className={INSERT_RULE} aria-hidden="true" />
      <button
        aria-label={label}
        className={INSERT_BUTTON}
        title={label}
        type="button"
        onClick={onClick}
      >
        <Plus aria-hidden="true" size={15} />
      </button>
      <span className={INSERT_RULE} aria-hidden="true" />
    </div>
  );
}

function CriterionOverview({
  criteria,
  total,
}: {
  criteria: CriterionDraft[];
  total: number;
}) {
  const scale = Math.max(
    total,
    ...criteria.map((criterion) => criterion.weight),
    1,
  );

  return (
    <div className={OVERVIEW}>
      <span className={OVERVIEW_TITLE}>
        <BarChart3 aria-hidden="true" size={16} />
        평가축 분포
      </span>
      <div className={OVERVIEW_BARS}>
        {criteria.map((criterion, index) => (
          <div className={OVERVIEW_ROW} key={criterion.id}>
            <span className={OVERVIEW_LABEL}>
              {criterion.name.trim() || `평가기준 ${index + 1}`}
            </span>
            <i className={OVERVIEW_TRACK}>
              <b
                className={OVERVIEW_FILL}
                style={{
                  width: `${Math.max((criterion.weight / scale) * 100, 0)}%`,
                }}
              />
            </i>
            <strong className={OVERVIEW_VALUE}>{criterion.weight}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function CriterionGuide({
  criterion,
  index,
  variant,
  onChange,
}: {
  criterion: CriterionDraft;
  index: number;
  variant: FormVariant;
  onChange: (patch: Partial<CriterionDraft>) => void;
}) {
  const inputClass = formInputClass(variant);
  const textareaClass = formTextareaClass(variant);

  return (
    <details className={ADVANCED}>
      <summary className={ADVANCED_SUMMARY}>
        <span className={ADVANCED_SUMMARY_TEXT}>
          <ListChecks aria-hidden="true" size={14} />
          질문·검증 가이드
        </span>
        <small className={ADVANCED_SUMMARY_NOTE}>
          AI 질문과 리포트 근거에 적용
        </small>
        <ChevronDown
          className={ADVANCED_CHEVRON}
          aria-hidden="true"
          size={15}
        />
      </summary>
      <div className={ADVANCED_BODY}>
        <p className={GUIDE_NOTE}>
          줄바꿈한 문장마다 하나의 검증 신호로 사용됩니다. 실제 경험, 본인 행동,
          판단 근거처럼 관찰 가능한 표현을 권장합니다.
        </p>
        <div className={FIELD_GRID}>
          <Field label={`확인할 요소 ${index + 1}`} variant={variant}>
            <textarea
              required
              aria-label={`확인할 요소 ${index + 1}`}
              className={textareaClass}
              rows={5}
              value={criterion.observableDimensions}
              onChange={(event) =>
                onChange({ observableDimensions: event.target.value })
              }
            />
          </Field>
          <Field label={`좋은 답변 신호 ${index + 1}`} variant={variant}>
            <textarea
              required
              aria-label={`좋은 답변 신호 ${index + 1}`}
              className={textareaClass}
              rows={5}
              value={criterion.strongAnswerSignals}
              onChange={(event) =>
                onChange({ strongAnswerSignals: event.target.value })
              }
            />
          </Field>
          <Field label={`추가 확인 신호 ${index + 1}`} variant={variant}>
            <textarea
              required
              aria-label={`추가 확인 신호 ${index + 1}`}
              className={textareaClass}
              rows={5}
              value={criterion.weakAnswerSignals}
              onChange={(event) =>
                onChange({ weakAnswerSignals: event.target.value })
              }
            />
          </Field>
          <Field label={`꼬리질문 방향 ${index + 1}`} variant={variant}>
            <textarea
              required
              aria-label={`꼬리질문 방향 ${index + 1}`}
              className={textareaClass}
              rows={5}
              value={criterion.followUpDirections}
              onChange={(event) =>
                onChange({ followUpDirections: event.target.value })
              }
            />
          </Field>
        </div>
        <div className={FIELD_GRID_THREE}>
          <Field label={`최대 꼬리질문 ${index + 1}`} variant={variant}>
            <input
              aria-label={`최대 꼬리질문 ${index + 1}`}
              className={inputClass}
              max={10}
              min={0}
              type="number"
              value={criterion.maxFollowUps}
              onChange={(event) =>
                onChange({ maxFollowUps: Number(event.target.value) })
              }
            />
          </Field>
          <Field label={`시간 예산(초) ${index + 1}`} variant={variant}>
            <input
              aria-label={`시간 예산(초) ${index + 1}`}
              className={inputClass}
              max={3600}
              min={30}
              step={30}
              type="number"
              value={criterion.timeBudgetSeconds}
              onChange={(event) =>
                onChange({ timeBudgetSeconds: Number(event.target.value) })
              }
            />
          </Field>
          <Field label={`판단 유보 기준 ${index + 1}`} variant={variant}>
            <input
              required
              aria-label={`판단 유보 기준 ${index + 1}`}
              className={inputClass}
              value={criterion.abstainGuidance}
              onChange={(event) =>
                onChange({ abstainGuidance: event.target.value })
              }
            />
          </Field>
        </div>
        <Field label={`공통 질문 ${index + 1}`} variant={variant}>
          <textarea
            required
            aria-label={`공통 질문 ${index + 1}`}
            className={textareaClass}
            rows={4}
            value={criterion.commonQuestions}
            onChange={(event) =>
              onChange({ commonQuestions: event.target.value })
            }
          />
        </Field>
        <p className={GUIDE_HELP}>
          <CircleHelp aria-hidden="true" size={13} />
          상세 가이드는 지원자에게 노출되지 않습니다.
        </p>
      </div>
    </details>
  );
}

function nextCriterionIndex(criteria: CriterionDraft[]) {
  return (
    criteria.reduce((max, criterion) => {
      const match = criterion.code.match(/^CRITERION_(\d+)$/);
      return Math.max(max, match ? Number(match[1]) : 0);
    }, 0) + 1
  );
}

function nextDraftIndex(ids: string[]) {
  return (
    ids.reduce((max, id) => {
      const match = id.match(/-(\d+)$/);
      return Math.max(max, match ? Number(match[1]) : 0);
    }, 0) + 1
  );
}

function clampWeight(value: string) {
  const parsed = Number(value);
  if (Number.isNaN(parsed)) return 0;
  return Math.min(100, Math.max(0, parsed));
}
