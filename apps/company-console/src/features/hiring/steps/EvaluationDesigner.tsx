import { Plus, SlidersHorizontal, Trash2 } from "lucide-react";

import { ICON_BUTTON } from "../../../app/styles/primitives";
import type { FormVariant } from "../components/FormPrimitives";
import {
  assessmentAxisKeys,
  assessmentAxisLabels,
  createCriterionDraft,
  createRequirementDraft,
  type AssessmentAxisKey,
  type AxisWeightDraft,
  type CriterionDraft,
  type HiringDraft,
  type HiringDraftUpdater,
  type JobRequirementDraft,
  type RequirementType,
} from "../types";

const DESIGNER = "grid gap-7";
const HEADER =
  "flex items-start justify-between gap-6 border-b border-border pb-5 mw-620:flex-col";
const EYEBROW = "font-mono text-[9px] font-[650] text-brand";
const TITLE = "mt-1 text-[18px] font-bold text-ink";
const DESCRIPTION =
  "mt-1.5 max-w-[620px] text-[11px] leading-[1.65] text-muted";
const TOTAL =
  "flex shrink-0 items-baseline gap-1 rounded-full bg-brand-soft px-3 py-2 text-brand";

const ITEM_LIST = "grid gap-3";
const ITEM =
  "overflow-hidden rounded-md border border-border bg-surface shadow-[0_1px_2px_#10182808]";
const ITEM_HEADER =
  "flex min-h-[54px] items-center gap-3 border-b border-border-muted bg-surface-muted px-4";
const ITEM_INDEX = "font-mono text-[9px] font-bold text-brand";
const ITEM_DELETE = `${ICON_BUTTON} ml-auto h-8 w-8`;

const KIND =
  "grid h-8 grid-cols-2 overflow-hidden rounded-sm border border-border bg-white";
const KIND_BUTTON = "min-w-[76px] px-3 text-[9px] transition-colors";
const KIND_BUTTON_ACTIVE = `${KIND_BUTTON} bg-ink font-[650] text-white`;
const KIND_BUTTON_IDLE = `${KIND_BUTTON} text-muted hover:bg-brand-soft hover:text-brand`;
const KIND_HINT = "text-[9px] text-muted mw-620:hidden";

const ITEM_BODY =
  "grid grid-cols-[minmax(280px,1fr)_minmax(220px,0.55fr)] items-end gap-6 px-5 py-4" +
  " mw-620:grid-cols-[minmax(0,1fr)]";
const FIELD_LABEL = "grid gap-2";
const FIELD_LABEL_TEXT = "text-[9px] font-semibold text-muted";
const STATEMENT =
  "h-9 w-full rounded-md border border-border bg-white px-3 text-[12px] text-ink" +
  " outline-none placeholder:text-subtle" +
  " focus:border-brand focus:shadow-[0_0_0_3px_#5966ce1f]";
const WEIGHT = "grid grid-cols-[minmax(0,1fr)_58px] items-end gap-4";
const WEIGHT_LABEL = "grid gap-2";
const WEIGHT_LABEL_TEXT =
  "flex items-center gap-1.5 text-[9px] font-semibold text-muted";
const WEIGHT_RANGE =
  "h-9 w-full cursor-pointer bg-transparent p-0 shadow-none accent-brand";
const WEIGHT_INPUT =
  "h-9 w-full rounded-md border border-border bg-white px-2 text-right font-mono" +
  " text-[11px] text-ink outline-none focus:border-brand";

// The scoring axes are their own block rather than a row inside a criterion: they apply to
// every criterion at once, so putting them beside one would read as belonging to it.
const AXIS_BLOCK = "grid gap-5 border-t border-border pt-7";
const AXIS_LIST = "grid gap-1";
// Fixed label column so five sliders line up and none of them shifts while one is dragged.
const AXIS_ROW =
  "grid grid-cols-[92px_minmax(0,1fr)_58px] items-center gap-4" +
  " border-b border-border-muted py-1.5 last:border-b-0 mw-620:grid-cols-[76px_minmax(0,1fr)_52px]";
const AXIS_LABEL = "text-[11px] text-ink";

const ADD_BUTTON =
  "inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-md border" +
  " border-dashed border-border bg-surface text-[10px] font-semibold text-muted" +
  " hover:border-brand hover:bg-brand-soft hover:text-brand";

const typeDescriptions: Record<RequirementType, string> = {
  required: "직무 수행에 반드시 필요한 경험·역량",
  preferred: "있다면 더 높게 평가할 태도·경험",
};

export function EvaluationDesigner({
  draft,
  update,
}: {
  draft: HiringDraft;
  update: HiringDraftUpdater;
  variant?: FormVariant;
}) {
  const totalWeight = draft.criteria.reduce(
    (total, criterion) => total + criterion.weight,
    0,
  );
  const evaluationItems = draft.jobRequirements.flatMap(
    (requirement, index) => {
      const criterion =
        draft.criteria.find(
          (candidate) => candidate.code === requirement.criterionCode,
        ) ?? draft.criteria[index];
      return criterion ? [{ requirement, criterion }] : [];
    },
  );

  function updateRequirement(id: string, patch: Partial<JobRequirementDraft>) {
    update(
      "jobRequirements",
      draft.jobRequirements.map((requirement) =>
        requirement.id === id ? { ...requirement, ...patch } : requirement,
      ),
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

  function updateWeight(id: string, weight: number) {
    update("criteria", rebalanceWeights(draft.criteria, id, weight));
  }

  function updateKind(
    requirement: JobRequirementDraft,
    criterion: CriterionDraft,
    requirementType: RequirementType,
  ) {
    updateRequirement(requirement.id, { requirementType });
    updateCriterion(criterion.id, { required: requirementType === "required" });
  }

  function addEvaluationItem(afterIndex: number) {
    const criterionIndex = nextCriterionIndex(draft.criteria);
    const criterion = createCriterionDraft(criterionIndex);
    const requirementIndex = nextDraftIndex(
      draft.jobRequirements.map((requirement) => requirement.id),
    );
    const requirement = {
      ...createRequirementDraft(requirementIndex),
      criterionCode: criterion.code,
      priority: afterIndex + 2,
    };
    const criteria = [...draft.criteria];
    const requirements = [...draft.jobRequirements];
    criteria.splice(afterIndex + 1, 0, {
      ...criterion,
      required: requirement.requirementType === "required",
    });
    requirements.splice(afterIndex + 1, 0, requirement);
    update("criteria", rebalanceWeights(criteria, criterion.id, 20));
    update(
      "jobRequirements",
      requirements.map((item, index) => ({ ...item, priority: index + 1 })),
    );
  }

  function removeEvaluationItem(
    requirement: JobRequirementDraft,
    criterion: CriterionDraft,
  ) {
    if (evaluationItems.length === 1) return;
    update(
      "jobRequirements",
      draft.jobRequirements
        .filter((item) => item.id !== requirement.id)
        .map((item, index) => ({ ...item, priority: index + 1 })),
    );
    update(
      "criteria",
      normalizeWeights(
        draft.criteria.filter((item) => item.id !== criterion.id),
      ),
    );
  }

  return (
    <section className={DESIGNER} aria-labelledby="evaluation-design-title">
      <header className={HEADER}>
        <div className="min-w-0">
          <span className={EYEBROW}>면접 결과 평가</span>
          <h3 className={TITLE} id="evaluation-design-title">
            자격요건과 평가 가중치
          </h3>
          <p className={DESCRIPTION}>
            필수·우대 자격요건을 입력하고 면접 결과에 반영할 가중치를
            설정하세요. 입력한 자격요건은 내부 평가기준으로 자동 사용됩니다.
          </p>
        </div>
        <strong className={TOTAL}>
          <span className="text-[9px] font-semibold">가중치 합계</span>
          <span className="font-mono text-[15px]">{totalWeight}</span>
        </strong>
      </header>

      <div className={ITEM_LIST}>
        {evaluationItems.map(({ requirement, criterion }, index) => (
          <article className={ITEM} key={requirement.id}>
            <header className={ITEM_HEADER}>
              <span className={ITEM_INDEX}>
                항목 {String(index + 1).padStart(2, "0")}
              </span>
              <RequirementKind
                index={index}
                value={requirement.requirementType}
                onChange={(requirementType) =>
                  updateKind(requirement, criterion, requirementType)
                }
              />
              <span className={KIND_HINT}>
                {typeDescriptions[requirement.requirementType]}
              </span>
              <button
                aria-label={`자격요건 ${index + 1} 삭제`}
                className={ITEM_DELETE}
                disabled={evaluationItems.length === 1}
                title="자격요건 삭제"
                type="button"
                onClick={() => removeEvaluationItem(requirement, criterion)}
              >
                <Trash2 aria-hidden="true" size={14} />
              </button>
            </header>

            <div className={ITEM_BODY}>
              <label className={FIELD_LABEL}>
                <span className={FIELD_LABEL_TEXT}>
                  {requirement.requirementType === "required"
                    ? "필수 자격요건"
                    : "우대 사항"}{" "}
                  {index + 1}
                </span>
                <input
                  required
                  aria-label={`자격요건 ${index + 1}`}
                  className={STATEMENT}
                  placeholder={
                    requirement.requirementType === "required"
                      ? "예: 대규모 트래픽을 고려한 시스템 설계·운영 경험"
                      : "예: 스스로 기준을 세우고 끝까지 파고드는 태도"
                  }
                  type="text"
                  value={requirement.statement}
                  onChange={(event) =>
                    updateRequirement(requirement.id, {
                      statement: event.target.value,
                    })
                  }
                  onKeyDown={(event) => {
                    if (event.key !== "Enter") return;
                    event.preventDefault();
                    event.currentTarget.blur();
                  }}
                />
              </label>

              <div className={WEIGHT}>
                <label className={WEIGHT_LABEL}>
                  <span className={WEIGHT_LABEL_TEXT}>
                    <SlidersHorizontal aria-hidden="true" size={12} />
                    결과 점수 반영 가중치
                  </span>
                  <input
                    aria-label={`가중치 ${index + 1}`}
                    className={WEIGHT_RANGE}
                    max={100}
                    min={0}
                    step={5}
                    type="range"
                    value={criterion.weight}
                    onChange={(event) =>
                      updateWeight(criterion.id, Number(event.target.value))
                    }
                  />
                </label>
                <label className={WEIGHT_LABEL}>
                  <span className="sr-only">가중치 {index + 1} 직접 입력</span>
                  <input
                    aria-label={`가중치 ${index + 1} 직접 입력`}
                    className={WEIGHT_INPUT}
                    max={100}
                    min={0}
                    step={1}
                    type="number"
                    value={criterion.weight}
                    onChange={(event) =>
                      updateWeight(
                        criterion.id,
                        clampWeight(event.target.value),
                      )
                    }
                  />
                </label>
              </div>
            </div>
          </article>
        ))}
      </div>

      <button
        className={ADD_BUTTON}
        type="button"
        onClick={() => addEvaluationItem(evaluationItems.length - 1)}
      >
        <Plus aria-hidden="true" size={15} />
        자격요건 추가
      </button>

      <ScoringAxisWeights
        weights={draft.axisWeights}
        onChange={(weights) => update("axisWeights", weights)}
      />
    </section>
  );
}

/**
 * The five axes every answer is scored on, and how much each counts here.
 *
 * Separate from the criteria above, and deliberately not editable per criterion: the axes
 * describe how an engineering answer is *read*, and what this company values is already
 * expressed by which 평가기준 exist and what they weigh against each other. A recruiter cannot
 * add or remove an axis, because each one carries the guidance the scoring prompt is built
 * from — see `shared/assessment_axes.py`.
 *
 * Weights are percentages totalling 100, on the same rule as the criteria, and dragging one
 * redistributes the rest so the number on the slider is always the share it carries.
 */
function ScoringAxisWeights({
  weights,
  onChange,
}: {
  weights: AxisWeightDraft;
  onChange: (weights: AxisWeightDraft) => void;
}) {
  const total = assessmentAxisKeys.reduce((sum, key) => sum + weights[key], 0);

  function setWeight(key: AssessmentAxisKey, requested: number) {
    onChange(rebalanceAxisWeights(weights, key, requested));
  }

  return (
    <section className={AXIS_BLOCK} aria-labelledby="scoring-axis-title">
      <header className={HEADER}>
        <div className="min-w-0">
          <span className={EYEBROW}>채점축</span>
          <h3 className={TITLE} id="scoring-axis-title">
            답변을 읽는 다섯 가지 축
          </h3>
          <p className={DESCRIPTION}>
            위 평가기준은 모두 아래 다섯 축으로 채점됩니다. 축은 추가·삭제할 수
            없고, 이 포지션에서 어느 축을 더 볼지 비중만 조절합니다. 0으로 두면
            그 축은 보지 않습니다.
          </p>
        </div>
        <strong className={TOTAL}>
          <span className="text-[9px] font-semibold">비중 합계</span>
          <span className="font-mono text-[15px]">{total}</span>
        </strong>
      </header>

      <div className={AXIS_LIST}>
        {assessmentAxisKeys.map((key) => (
          <div className={AXIS_ROW} key={key}>
            <span className={AXIS_LABEL}>{assessmentAxisLabels[key]}</span>
            <input
              aria-label={`${assessmentAxisLabels[key]} 비중`}
              className={WEIGHT_RANGE}
              max={100}
              min={0}
              step={5}
              type="range"
              value={weights[key]}
              onChange={(event) => setWeight(key, Number(event.target.value))}
            />
            <input
              aria-label={`${assessmentAxisLabels[key]} 비중 직접 입력`}
              className={WEIGHT_INPUT}
              max={100}
              min={0}
              type="number"
              value={weights[key]}
              onChange={(event) => setWeight(key, Number(event.target.value))}
            />
          </div>
        ))}
      </div>
    </section>
  );
}

/**
 * Set one axis to the requested share and spread the remainder over the other four.
 *
 * Mirrors `rebalanceWeights` for the criteria: the untouched axes keep their ratios to each
 * other and are only scaled, so nudging 깊이 up does not flatten a weighting the recruiter
 * already shaped. The total stays 100, which is what the domain requires
 * (`axis_weights_name_every_scoring_axis`).
 */
function rebalanceAxisWeights(
  weights: AxisWeightDraft,
  changed: AssessmentAxisKey,
  requested: number,
): AxisWeightDraft {
  const changedWeight = Math.round(Math.min(100, Math.max(0, requested || 0)));
  const others = assessmentAxisKeys.filter((key) => key !== changed);
  const currentTotal = others.reduce(
    (sum, key) => sum + Math.max(0, weights[key]),
    0,
  );
  const remaining = 100 - changedWeight;
  const shares = others.map((key) =>
    currentTotal > 0
      ? Math.max(0, weights[key]) / currentTotal
      : 1 / others.length,
  );
  const distributed = shares.map((share) => Math.floor(share * remaining));
  let leftover = remaining - distributed.reduce((sum, value) => sum + value, 0);
  for (let index = 0; leftover > 0; index = (index + 1) % distributed.length) {
    distributed[index] += 1;
    leftover -= 1;
  }

  const next = { ...weights, [changed]: changedWeight } as AxisWeightDraft;
  others.forEach((key, index) => {
    next[key] = distributed[index];
  });
  return next;
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
      <legend className="sr-only">평가 구분 {index + 1}</legend>
      {(["required", "preferred"] as const).map((type) => (
        <button
          aria-pressed={value === type}
          className={value === type ? KIND_BUTTON_ACTIVE : KIND_BUTTON_IDLE}
          key={type}
          type="button"
          onClick={() => onChange(type)}
        >
          {type === "required" ? "필수 자격" : "우대 사항"}
        </button>
      ))}
    </fieldset>
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
  return Math.round(Math.min(100, Math.max(0, parsed)));
}

function rebalanceWeights(
  criteria: CriterionDraft[],
  changedId: string,
  requestedWeight: number,
) {
  if (criteria.length <= 1) {
    return criteria.map((criterion) => ({ ...criterion, weight: 100 }));
  }

  const changedWeight = Math.round(Math.min(100, Math.max(0, requestedWeight)));
  const others = criteria.filter((criterion) => criterion.id !== changedId);
  const remainingWeight = 100 - changedWeight;
  const distributed = distributeWeight(others, remainingWeight);
  const distributedById = new Map(
    distributed.map((criterion) => [criterion.id, criterion.weight]),
  );
  return criteria.map((criterion) => ({
    ...criterion,
    weight:
      criterion.id === changedId
        ? changedWeight
        : (distributedById.get(criterion.id) ?? 0),
  }));
}

function normalizeWeights(criteria: CriterionDraft[]) {
  return distributeWeight(criteria, 100);
}

function distributeWeight(criteria: CriterionDraft[], targetTotal: number) {
  if (criteria.length === 0) return criteria;
  const currentTotal = criteria.reduce(
    (sum, criterion) => sum + Math.max(0, criterion.weight),
    0,
  );
  const ratios = criteria.map((criterion) =>
    currentTotal > 0
      ? Math.max(0, criterion.weight) / currentTotal
      : 1 / criteria.length,
  );
  const weights = ratios.map((ratio) => Math.floor(ratio * targetTotal));
  let remainder =
    targetTotal - weights.reduce((sum, weight) => sum + weight, 0);
  for (let index = 0; remainder > 0; index = (index + 1) % weights.length) {
    weights[index] += 1;
    remainder -= 1;
  }
  return criteria.map((criterion, index) => ({
    ...criterion,
    weight: weights[index],
  }));
}
