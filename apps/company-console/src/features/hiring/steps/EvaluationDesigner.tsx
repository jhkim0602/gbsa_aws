import {
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import { Plus, Trash2 } from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

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
  type CriterionImportance,
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

const CRITERIA_LAYOUT =
  "grid grid-cols-[minmax(0,1fr)_220px] items-start gap-5 mw-680:grid-cols-1";
const REQUIREMENT_LIST =
  "overflow-hidden rounded-lg border border-border bg-surface shadow-[0_1px_2px_#10182808]";
const REQUIREMENT_LIST_HEADER =
  "flex h-10 items-center justify-between gap-3 border-b border-border-muted bg-surface-muted px-3";
const REQUIREMENT_LIST_TITLE = "text-[9px] font-semibold text-ink";
const TYPE_COUNTS =
  "inline-flex items-center gap-1 text-[8px] font-normal text-subtle";
const TYPE_COUNT_REQUIRED = "font-mono font-semibold text-brand";
const TYPE_COUNT_PREFERRED = "font-mono font-semibold text-success";
const REQUIREMENT_ROWS = "grid";
const REQUIREMENT_ROW =
  "grid min-h-12 grid-cols-[24px_68px_minmax(120px,1fr)_112px_32px] items-center gap-2" +
  " border-b border-border-muted px-2 py-1.5 last:border-b-0 hover:bg-surface-muted/60" +
  " mw-520:min-h-20 mw-520:grid-cols-[20px_64px_minmax(0,1fr)_32px] mw-520:items-center";
const REQUIREMENT_INDEX =
  "inline-flex items-center gap-1 font-mono text-[8px] text-subtle";
const REQUIREMENT_DOT = "size-1.5 shrink-0 rounded-full";
const TYPE_SEGMENT =
  "grid h-7 w-[68px] grid-cols-2 overflow-hidden rounded-md border border-border bg-white";
const TYPE_OPTION =
  "text-[8px] font-semibold text-muted transition-colors not-first:border-l not-first:border-border" +
  " hover:bg-surface-muted focus-visible:z-1 focus-visible:outline-none focus-visible:ring-2" +
  " focus-visible:ring-brand/20";
const TYPE_OPTION_REQUIRED_ACTIVE = `${TYPE_OPTION} bg-brand-soft text-brand`;
const TYPE_OPTION_PREFERRED_ACTIVE = `${TYPE_OPTION} bg-success-soft text-success`;
const REQUIREMENT_DELETE = `${ICON_BUTTON} h-8 w-8 border-transparent bg-transparent mw-520:col-start-4 mw-520:row-start-1`;
const REQUIREMENT_ADD =
  "inline-flex h-9 w-full items-center justify-center gap-1 border-t border-border-muted" +
  " text-[9px] font-semibold text-muted hover:bg-brand-soft hover:text-brand";

const STATEMENT =
  "h-8 min-w-0 w-full rounded-md border border-transparent bg-transparent px-2 text-[10px] text-ink" +
  " outline-none placeholder:text-subtle" +
  " hover:border-border focus:border-brand focus:bg-white" +
  " focus:shadow-[0_0_0_3px_#5966ce1f]";
const IMPORTANCE_CELL =
  "grid min-w-0 items-center mw-520:col-[2/5] mw-520:row-start-2";
const IMPORTANCE_SEGMENT =
  "grid h-7 grid-cols-3 overflow-hidden rounded-md border border-border bg-white";
const IMPORTANCE_OPTION =
  "px-1 text-[8px] font-medium text-muted transition-colors not-first:border-l" +
  " not-first:border-border hover:bg-brand-soft hover:text-brand focus-visible:z-1" +
  " focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/20";
const IMPORTANCE_OPTION_ACTIVE =
  "bg-brand text-white hover:bg-brand hover:text-white";
const DONUT_CARD =
  "sticky top-4 grid gap-3 rounded-xl border border-border bg-surface p-4 shadow-[0_8px_24px_#1018280a]" +
  " mw-680:static mw-680:grid-cols-[180px_minmax(0,1fr)] mw-520:grid-cols-1";
const DONUT_HEADER = "grid gap-0.5 mw-680:col-[1/-1]";
const DONUT_TITLE = "text-[10px] font-semibold text-ink";
const DONUT_HINT = "text-[8px] leading-[1.45] text-muted";
const DONUT_CHART = "relative h-[170px]";
const DONUT_CENTER =
  "pointer-events-none absolute inset-0 grid place-content-center text-center";
const DONUT_LEGEND = "grid content-start gap-1";
const DONUT_LEGEND_ITEM =
  "grid grid-cols-[8px_minmax(0,1fr)_30px] items-center gap-1.5 text-[8px] text-muted";
const DONUT_LEGEND_DOT = "size-2 rounded-[2px]";
const DONUT_LEGEND_LABEL = "truncate";
// The scoring axes are their own block rather than a row inside a criterion: they apply to
// every criterion at once, so putting them beside one would read as belonging to it.
const AXIS_BLOCK = "grid gap-5 border-t border-border pt-7";
const AXIS_LAYOUT =
  "grid grid-cols-[minmax(0,1fr)_330px] items-stretch gap-6 mw-680:grid-cols-1";
const AXIS_STORY = "grid content-center gap-5 py-2";
const AXIS_STORY_HEADER = "grid gap-1.5";
const AXIS_STORY_TITLE = "text-[18px] font-bold leading-[1.35] text-ink";
const AXIS_STORY_DESCRIPTION = "text-[10px] leading-[1.7] text-muted";
const AXIS_STEPS = "grid gap-2";
const AXIS_STEP =
  "grid grid-cols-[26px_minmax(0,1fr)] gap-2.5 rounded-md border border-border-muted" +
  " bg-surface-muted/60 px-3 py-2";
const AXIS_STEP_NUMBER = "font-mono text-[8px] font-semibold text-brand";
const AXIS_STEP_TITLE = "text-[10px] font-semibold text-ink";
const AXIS_STEP_DESCRIPTION = "mt-0.5 text-[9px] leading-[1.5] text-muted";
const AXIS_NOTE =
  "border-l-2 border-brand pl-3 text-[9px] leading-[1.55] text-ink-secondary";
const AXIS_CONTROL =
  "grid rounded-xl border border-border bg-surface px-3 pt-3 pb-3 shadow-[0_8px_24px_#1018280a]";
const AXIS_CONTROL_HEADER = "flex items-center justify-between gap-3 px-1";
const AXIS_CONTROL_TITLE = "text-[10px] font-semibold text-ink";
const AXIS_CONTROL_HINT = "mt-0.5 text-[8px] text-muted";
const AXIS_AUTO_BADGE =
  "rounded-full bg-brand-soft px-2.5 py-1 text-[8px] font-semibold text-brand";
const AXIS_BAR_LIST = "grid gap-1 px-1 pb-1";
const AXIS_BAR_ROW =
  "grid grid-cols-[56px_minmax(0,1fr)_36px] items-center gap-2";
const AXIS_BAR_LABEL = "text-[9px] font-medium text-ink-secondary";
const AXIS_BAR = "relative h-7";
const AXIS_BAR_TRACK =
  "absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 overflow-hidden rounded-full bg-surface-strong";
const AXIS_BAR_FILL = "block h-full rounded-full bg-brand";
const AXIS_BAR_THUMB =
  "absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-brand bg-white shadow-sm";
const AXIS_BAR_INPUT =
  "absolute inset-0 h-full w-full cursor-pointer opacity-0";
const AXIS_BAR_VALUE = "text-right text-[8px] font-semibold text-muted";

const axisEvaluationSteps = [
  {
    title: "답변 근거 분해",
    description: "상황·행동·판단 근거·결과를 분리해 실제 경험을 구조화합니다.",
  },
  {
    title: "다섯 관점으로 검증",
    description: "정확성, 깊이, 기본기, 본인 기여, 설명력을 함께 확인합니다.",
  },
  {
    title: "근거 기반 종합 판단",
    description: "담당자가 설정한 관점의 비중을 적용해 최종 평가를 구성합니다.",
  },
] as const;

const PENTAGON_WIDTH = 330;
const PENTAGON_HEIGHT = 220;
const PENTAGON_CENTER_X = 165;
const PENTAGON_CENTER_Y = 100;
const PENTAGON_RADIUS = 70;

type AxisPreferenceScores = Record<AssessmentAxisKey, number>;

const requirementGroupMetadata = [
  {
    type: "required",
    label: "필수 자격",
    empty: "필수 자격요건을 추가해 주세요.",
    placeholder: "예: 대규모 트래픽 시스템 설계·운영 경험",
    color: "#5966ce",
  },
  {
    type: "preferred",
    label: "우대 사항",
    empty: "우대 사항이 있다면 추가해 주세요.",
    placeholder: "예: 기술 문서를 작성하고 공유한 경험",
    color: "#1e9e63",
  },
] as const satisfies ReadonlyArray<{
  type: RequirementType;
  label: string;
  empty: string;
  placeholder: string;
  color: string;
}>;

const requiredChartColors = ["#5966ce", "#7480dc", "#929be7", "#adb4ef"];
const preferredChartColors = ["#1e9e63", "#48b381", "#70c69e", "#98d8bb"];
const importanceOptions = [
  { value: "low", label: "낮음", points: 1 },
  { value: "medium", label: "보통", points: 2 },
  { value: "high", label: "높음", points: 4 },
] as const satisfies ReadonlyArray<{
  value: CriterionImportance;
  label: string;
  points: number;
}>;
const importancePoints: Record<CriterionImportance, number> = {
  low: 1,
  medium: 2,
  high: 4,
};

type EvaluationItem = {
  requirement: JobRequirementDraft;
  criterion: CriterionDraft;
  index: number;
};

type WeightChartItem = EvaluationItem & {
  color: string;
  label: string;
};

export function EvaluationDesigner({
  draft,
  update,
}: {
  draft: HiringDraft;
  update: HiringDraftUpdater;
  variant?: FormVariant;
}) {
  const inputRefs = useRef(new Map<string, HTMLInputElement>());
  const pendingFocusId = useRef<string | null>(null);
  const evaluationItems: EvaluationItem[] = draft.jobRequirements.flatMap(
    (requirement, index) => {
      const criterion =
        draft.criteria.find(
          (candidate) => candidate.code === requirement.criterionCode,
        ) ?? draft.criteria[index];
      return criterion ? [{ requirement, criterion, index }] : [];
    },
  );
  const chartItems = toWeightChartItems(evaluationItems);
  const requiredCount = evaluationItems.filter(
    ({ requirement }) => requirement.requirementType === "required",
  ).length;
  const preferredCount = evaluationItems.length - requiredCount;

  useEffect(() => {
    const id = pendingFocusId.current;
    if (!id) return;
    inputRefs.current.get(id)?.focus();
    pendingFocusId.current = null;
  }, [draft.jobRequirements.length]);

  function updateRequirement(id: string, patch: Partial<JobRequirementDraft>) {
    update(
      "jobRequirements",
      draft.jobRequirements.map((requirement) =>
        requirement.id === id ? { ...requirement, ...patch } : requirement,
      ),
    );
  }

  function setRequirementType(
    requirement: JobRequirementDraft,
    criterion: CriterionDraft,
    requirementType: RequirementType,
  ) {
    if (requirement.requirementType === requirementType) return;
    updateRequirement(requirement.id, { requirementType });
    update(
      "criteria",
      draft.criteria.map((item) =>
        item.id === criterion.id
          ? { ...item, required: requirementType === "required" }
          : item,
      ),
    );
  }

  function updateImportance(id: string, importance: CriterionImportance) {
    update(
      "criteria",
      normalizeImportanceWeights(
        draft.criteria.map((criterion) =>
          criterion.id === id ? { ...criterion, importance } : criterion,
        ),
      ),
    );
  }

  function addEvaluationItem(requirementType: RequirementType) {
    const criterionIndex = nextCriterionIndex(draft.criteria);
    const criterion = createCriterionDraft(criterionIndex);
    const requirementIndex = nextDraftIndex(
      draft.jobRequirements.map((requirement) => requirement.id),
    );
    const insertionIndex = nextRequirementInsertionIndex(
      draft.jobRequirements,
      requirementType,
    );
    const requirement = {
      ...createRequirementDraft(requirementIndex),
      requirementType,
      criterionCode: criterion.code,
      priority: insertionIndex + 1,
    };
    const criteria = [...draft.criteria];
    const requirements = [...draft.jobRequirements];
    criteria.splice(insertionIndex, 0, {
      ...criterion,
      required: requirementType === "required",
    });
    requirements.splice(insertionIndex, 0, requirement);
    pendingFocusId.current = requirement.id;
    update("criteria", normalizeImportanceWeights(criteria));
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
      normalizeImportanceWeights(
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
            필수·우대를 선택하고 상대적인 중요도만 정하세요. 실제 평가 가중치는
            자동으로 환산되어 항상 합계 100%를 유지합니다.
          </p>
        </div>
      </header>

      <div className={CRITERIA_LAYOUT}>
        <section className={REQUIREMENT_LIST} aria-label="자격요건 편집">
          <header className={REQUIREMENT_LIST_HEADER}>
            <div>
              <strong className={REQUIREMENT_LIST_TITLE}>자격요건 목록</strong>
              <span className="ml-2 text-[8px] text-subtle">
                Enter로 다음 항목 추가
              </span>
            </div>
            <span className={TYPE_COUNTS}>
              <b className={TYPE_COUNT_REQUIRED}>필 {requiredCount}</b>
              <i aria-hidden="true">·</i>
              <b className={TYPE_COUNT_PREFERRED}>우 {preferredCount}</b>
            </span>
          </header>

          <div
            aria-label="자격요건 목록"
            className={REQUIREMENT_ROWS}
            role="list"
          >
            {evaluationItems.map(
              ({ requirement, criterion, index }, rowIndex) => {
                const metadata = getRequirementMetadata(
                  requirement.requirementType,
                );
                const nextSameType = evaluationItems
                  .slice(rowIndex + 1)
                  .find(
                    (item) =>
                      item.requirement.requirementType ===
                      requirement.requirementType,
                  );
                const importance = resolveImportance(criterion, draft.criteria);
                return (
                  <article
                    className={REQUIREMENT_ROW}
                    key={requirement.id}
                    role="listitem"
                  >
                    <span className={REQUIREMENT_INDEX}>
                      <i
                        aria-hidden="true"
                        className={REQUIREMENT_DOT}
                        style={{
                          backgroundColor: chartItems[rowIndex]?.color,
                        }}
                      />
                      {String(rowIndex + 1).padStart(2, "0")}
                    </span>

                    <div
                      aria-label={`자격요건 ${index + 1} 구분`}
                      className={TYPE_SEGMENT}
                      role="group"
                    >
                      <button
                        aria-pressed={
                          requirement.requirementType === "required"
                        }
                        className={
                          requirement.requirementType === "required"
                            ? TYPE_OPTION_REQUIRED_ACTIVE
                            : TYPE_OPTION
                        }
                        type="button"
                        onClick={() =>
                          setRequirementType(requirement, criterion, "required")
                        }
                      >
                        필수
                      </button>
                      <button
                        aria-pressed={
                          requirement.requirementType === "preferred"
                        }
                        className={
                          requirement.requirementType === "preferred"
                            ? TYPE_OPTION_PREFERRED_ACTIVE
                            : TYPE_OPTION
                        }
                        type="button"
                        onClick={() =>
                          setRequirementType(
                            requirement,
                            criterion,
                            "preferred",
                          )
                        }
                      >
                        우대
                      </button>
                    </div>

                    <input
                      required
                      aria-label={`자격요건 ${index + 1}`}
                      className={STATEMENT}
                      placeholder={metadata.placeholder}
                      ref={(element) => {
                        if (element) {
                          inputRefs.current.set(requirement.id, element);
                        } else {
                          inputRefs.current.delete(requirement.id);
                        }
                      }}
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
                        if (nextSameType) {
                          inputRefs.current
                            .get(nextSameType.requirement.id)
                            ?.focus();
                          return;
                        }
                        addEvaluationItem(requirement.requirementType);
                      }}
                    />

                    <div className={IMPORTANCE_CELL}>
                      <div
                        aria-label={`자격요건 ${index + 1} 중요도`}
                        className={IMPORTANCE_SEGMENT}
                        role="group"
                      >
                        {importanceOptions.map((option) => (
                          <button
                            aria-pressed={importance === option.value}
                            className={`${IMPORTANCE_OPTION} ${
                              importance === option.value
                                ? IMPORTANCE_OPTION_ACTIVE
                                : ""
                            }`}
                            key={option.value}
                            type="button"
                            onClick={() =>
                              updateImportance(criterion.id, option.value)
                            }
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                      <output
                        aria-label={`자격요건 ${index + 1} 자동 가중치`}
                        className="sr-only"
                      >
                        {criterion.weight}%
                      </output>
                    </div>

                    <button
                      aria-label={`자격요건 ${index + 1} 삭제`}
                      className={REQUIREMENT_DELETE}
                      disabled={evaluationItems.length === 1}
                      title="자격요건 삭제"
                      type="button"
                      onClick={() =>
                        removeEvaluationItem(requirement, criterion)
                      }
                    >
                      <Trash2 aria-hidden="true" size={14} />
                    </button>
                  </article>
                );
              },
            )}
          </div>

          <button
            aria-label="자격요건 행 추가"
            className={REQUIREMENT_ADD}
            type="button"
            onClick={() =>
              addEvaluationItem(
                evaluationItems.at(-1)?.requirement.requirementType ??
                  "required",
              )
            }
          >
            <Plus aria-hidden="true" size={12} />
            자격요건 추가
          </button>
        </section>

        <WeightOverview items={chartItems} />
      </div>

      <ScoringAxisWeights
        weights={draft.axisWeights}
        onChange={(weights) => update("axisWeights", weights)}
      />
    </section>
  );
}

function WeightOverview({ items }: { items: WeightChartItem[] }) {
  const chartData = items.map((item) => ({
    item,
    name: item.label,
    value: item.criterion.weight,
  }));

  return (
    <aside className={DONUT_CARD} aria-labelledby="weight-overview-title">
      <header className={DONUT_HEADER}>
        <h4 className={DONUT_TITLE} id="weight-overview-title">
          자동 평가 비중
        </h4>
        <p className={DONUT_HINT}>
          왼쪽에서 선택한 중요도를 원형 비중으로 자동 환산합니다.
        </p>
      </header>

      <div
        className={DONUT_CHART}
        role="img"
        aria-label="자격요건별 자동 가중치 원그래프"
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              cx="50%"
              cy="50%"
              data={chartData}
              dataKey="value"
              innerRadius={48}
              isAnimationActive={false}
              nameKey="name"
              outerRadius={72}
              paddingAngle={items.length > 1 ? 2 : 0}
              stroke="#ffffff"
              strokeWidth={2}
            >
              {items.map((item) => (
                <Cell fill={item.color} key={item.criterion.id} />
              ))}
            </Pie>
            <Tooltip content={<WeightTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className={DONUT_CENTER} aria-hidden="true">
          <strong className="font-mono text-[15px] text-ink">
            {items.length}
          </strong>
          <span className="text-[8px] text-muted">평가 항목</span>
        </div>
      </div>

      <div className={DONUT_LEGEND}>
        {items.map((item) => (
          <span className={DONUT_LEGEND_ITEM} key={item.criterion.id}>
            <i
              aria-hidden="true"
              className={DONUT_LEGEND_DOT}
              style={{ backgroundColor: item.color }}
            />
            <span className={DONUT_LEGEND_LABEL}>{item.label}</span>
            <b className="text-right font-mono text-ink">
              {item.criterion.weight}%
            </b>
          </span>
        ))}
      </div>
    </aside>
  );
}

function WeightTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload?: { item?: WeightChartItem } }>;
}) {
  const item = payload?.[0]?.payload?.item;
  if (!active || !item) return null;
  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2 shadow-float">
      <strong className="block max-w-60 text-[10px] leading-[1.45] text-ink">
        {item.label}
      </strong>
      <p className="mt-1 text-[9px] text-muted">
        {item.requirement.requirementType === "required"
          ? "필수 자격"
          : "우대 사항"}{" "}
        · <b className="font-mono text-brand">{item.criterion.weight}%</b>
      </p>
    </div>
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
 * The UI keeps five independent preference scores so adjusting one control does not move the
 * other four. Before updating the draft, those scores are normalized to the API's existing
 * percentage contract, which still totals 100.
 */
function ScoringAxisWeights({
  weights,
  onChange,
}: {
  weights: AxisWeightDraft;
  onChange: (weights: AxisWeightDraft) => void;
}) {
  const [preferenceScores, setPreferenceScores] =
    useState<AxisPreferenceScores>(() => axisPreferencesFromWeights(weights));
  const preferenceScoresRef = useRef(preferenceScores);
  const [selectedAxis, setSelectedAxis] =
    useState<AssessmentAxisKey>("correctness");
  const [draggingAxis, setDraggingAxis] = useState<AssessmentAxisKey | null>(
    null,
  );
  const dataPoints = assessmentAxisKeys.map((key, index) =>
    pointOnPentagonAxis(index, preferenceScores[key] / 100),
  );

  function setPreference(key: AssessmentAxisKey, requested: number) {
    const score = Math.round(Math.min(100, Math.max(0, requested)) / 5) * 5;
    const next = { ...preferenceScoresRef.current, [key]: score };
    preferenceScoresRef.current = next;
    setPreferenceScores(next);
    onChange(normalizeAxisPreferences(next));
  }

  function setWeightFromPointer(
    key: AssessmentAxisKey,
    event: ReactPointerEvent<SVGElement>,
  ) {
    const svg = event.currentTarget.closest("svg");
    if (!svg) return;
    const bounds = svg.getBoundingClientRect();
    if (bounds.width === 0 || bounds.height === 0) return;
    const x = ((event.clientX - bounds.left) / bounds.width) * PENTAGON_WIDTH;
    const y = ((event.clientY - bounds.top) / bounds.height) * PENTAGON_HEIGHT;
    const axisIndex = assessmentAxisKeys.indexOf(key);
    const outer = pointOnPentagonAxis(axisIndex, 1);
    const unitX = (outer.x - PENTAGON_CENTER_X) / PENTAGON_RADIUS;
    const unitY = (outer.y - PENTAGON_CENTER_Y) / PENTAGON_RADIUS;
    const projected =
      ((x - PENTAGON_CENTER_X) * unitX + (y - PENTAGON_CENTER_Y) * unitY) /
      PENTAGON_RADIUS;
    const ratio = Math.min(1, Math.max(0, projected));
    setPreference(key, ratio * 100);
  }

  function beginAxisDrag(
    key: AssessmentAxisKey,
    event: ReactPointerEvent<SVGElement>,
  ) {
    event.preventDefault();
    setSelectedAxis(key);
    setDraggingAxis(key);
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setWeightFromPointer(key, event);
  }

  return (
    <section className={AXIS_BLOCK} aria-labelledby="scoring-axis-title">
      <div className={AXIS_LAYOUT}>
        <div className={AXIS_STORY}>
          <header className={AXIS_STORY_HEADER}>
            <span className={EYEBROW}>채점축</span>
            <h3 className={AXIS_STORY_TITLE} id="scoring-axis-title">
              WhyYou는 답변의 근거를
              <br />
              다섯 방향으로 읽습니다
            </h3>
            <p className={AXIS_STORY_DESCRIPTION}>
              단순 키워드나 인상으로 점수를 매기지 않습니다. 지원자가 말한
              사실과 행동을 근거 단위로 정리한 뒤, 서로 다른 다섯 관점에서
              일관성을 확인합니다.
            </p>
          </header>

          <ol className={AXIS_STEPS}>
            {axisEvaluationSteps.map((step, index) => (
              <li className={AXIS_STEP} key={step.title}>
                <span className={AXIS_STEP_NUMBER}>
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <strong className={AXIS_STEP_TITLE}>{step.title}</strong>
                  <p className={AXIS_STEP_DESCRIPTION}>{step.description}</p>
                </div>
              </li>
            ))}
          </ol>

          <p className={AXIS_NOTE}>
            각 막대는 서로 독립적으로 움직입니다. 실제 평가 비중은 시스템이
            내부에서 자동 환산하므로 합계를 맞출 필요가 없습니다.
          </p>
        </div>

        <div
          aria-label="답변 평가 관점 오각형"
          className={AXIS_CONTROL}
          role="group"
        >
          <header className={AXIS_CONTROL_HEADER}>
            <div>
              <h4 className={AXIS_CONTROL_TITLE}>평가 관점 조정</h4>
              <p className={AXIS_CONTROL_HINT}>
                오각형이나 아래 막대를 각각 조절하세요
              </p>
            </div>
            <span className={AXIS_AUTO_BADGE}>자동 환산</span>
          </header>

          <svg
            className="mt-1 w-full touch-none select-none"
            viewBox={`0 0 ${PENTAGON_WIDTH} ${PENTAGON_HEIGHT}`}
            onPointerLeave={() => setDraggingAxis(null)}
            onPointerMove={(event) => {
              if (draggingAxis) setWeightFromPointer(draggingAxis, event);
            }}
            onPointerUp={() => setDraggingAxis(null)}
          >
            {[0.25, 0.5, 0.75, 1].map((ratio) => (
              <polygon
                fill={ratio === 1 ? "#f8f9fb" : "none"}
                key={ratio}
                points={pentagonPoints(ratio)}
                stroke={ratio === 1 ? "#d9dce5" : "#e8eaf0"}
                strokeWidth={ratio === 1 ? 1.2 : 1}
              />
            ))}

            {assessmentAxisKeys.map((key, index) => {
              const outer = pointOnPentagonAxis(index, 1);
              return (
                <line
                  key={key}
                  stroke={
                    selectedAxis === key ? "rgba(89,102,206,0.55)" : "#e2e4eb"
                  }
                  strokeWidth={selectedAxis === key ? 1.5 : 1}
                  x1={PENTAGON_CENTER_X}
                  x2={outer.x}
                  y1={PENTAGON_CENTER_Y}
                  y2={outer.y}
                />
              );
            })}

            <polygon
              fill="rgba(89,102,206,0.11)"
              points={dataPoints.map(({ x, y }) => `${x},${y}`).join(" ")}
              stroke="rgba(89,102,206,0.78)"
              strokeLinejoin="round"
              strokeWidth="2"
            />

            {assessmentAxisKeys.map((key, index) => {
              const outer = pointOnPentagonAxis(index, 1);
              return (
                <line
                  aria-hidden="true"
                  className="cursor-pointer transition-[stroke] duration-150 hover:stroke-[rgba(89,102,206,0.14)]"
                  key={`${key}-hit-area`}
                  stroke="rgba(89,102,206,0.045)"
                  strokeWidth="22"
                  x1={PENTAGON_CENTER_X}
                  x2={outer.x}
                  y1={PENTAGON_CENTER_Y}
                  y2={outer.y}
                  onPointerDown={(event) => beginAxisDrag(key, event)}
                />
              );
            })}

            {assessmentAxisKeys.map((key, index) => {
              const point = dataPoints[index];
              return (
                <circle
                  aria-hidden="true"
                  className="cursor-grab"
                  cx={point.x}
                  cy={point.y}
                  fill={selectedAxis === key ? "#5966ce" : "#ffffff"}
                  key={`${key}-handle`}
                  r={selectedAxis === key ? 6 : 5}
                  stroke="#5966ce"
                  strokeWidth="2"
                  onPointerDown={(event) => beginAxisDrag(key, event)}
                />
              );
            })}

            {assessmentAxisKeys.map((key, index) => {
              const labelPoint = pointOnPentagonAxis(index, 1.34);
              const textAnchor =
                labelPoint.x < PENTAGON_CENTER_X - 12
                  ? "end"
                  : labelPoint.x > PENTAGON_CENTER_X + 12
                    ? "start"
                    : "middle";
              return (
                <text
                  className="cursor-pointer"
                  fill={selectedAxis === key ? "#5966ce" : "#4c5068"}
                  fontSize="9"
                  fontWeight={selectedAxis === key ? 700 : 500}
                  key={`${key}-label`}
                  textAnchor={textAnchor}
                  x={labelPoint.x}
                  y={labelPoint.y}
                  onClick={() => setSelectedAxis(key)}
                >
                  <tspan x={labelPoint.x}>{assessmentAxisLabels[key]}</tspan>
                  <tspan
                    dy="12"
                    fill={selectedAxis === key ? "#5966ce" : "#9295a8"}
                    fontFamily="monospace"
                    fontSize="8"
                    x={labelPoint.x}
                  >
                    {axisStrengthLabel(preferenceScores[key])}
                  </tspan>
                </text>
              );
            })}

            <circle
              cx={PENTAGON_CENTER_X}
              cy={PENTAGON_CENTER_Y}
              fill="#5966ce"
              r="2.5"
            />
          </svg>

          <div className={AXIS_BAR_LIST}>
            {assessmentAxisKeys.map((key) => (
              <label className={AXIS_BAR_ROW} key={`${key}-bar`}>
                <span className={AXIS_BAR_LABEL}>
                  {assessmentAxisLabels[key]}
                </span>
                <span className={AXIS_BAR}>
                  <span className={AXIS_BAR_TRACK} aria-hidden="true">
                    <i
                      className={AXIS_BAR_FILL}
                      style={{ width: `${preferenceScores[key]}%` }}
                    />
                  </span>
                  <i
                    aria-hidden="true"
                    className={AXIS_BAR_THUMB}
                    style={{
                      left: `${Math.min(98, Math.max(2, preferenceScores[key]))}%`,
                    }}
                  />
                  <input
                    aria-label={`${assessmentAxisLabels[key]} 관점 강도`}
                    className={AXIS_BAR_INPUT}
                    max={100}
                    min={0}
                    step={5}
                    type="range"
                    value={preferenceScores[key]}
                    onChange={(event) =>
                      setPreference(key, Number(event.target.value))
                    }
                    onFocus={() => setSelectedAxis(key)}
                    onPointerDown={() => setSelectedAxis(key)}
                  />
                </span>
                <output className={AXIS_BAR_VALUE}>
                  {axisStrengthLabel(preferenceScores[key])}
                </output>
              </label>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function pointOnPentagonAxis(index: number, ratio: number) {
  const angle = -Math.PI / 2 + (index * Math.PI * 2) / 5;
  return {
    x: PENTAGON_CENTER_X + Math.cos(angle) * PENTAGON_RADIUS * ratio,
    y: PENTAGON_CENTER_Y + Math.sin(angle) * PENTAGON_RADIUS * ratio,
  };
}

function pentagonPoints(ratio: number) {
  return assessmentAxisKeys
    .map((_, index) => {
      const point = pointOnPentagonAxis(index, ratio);
      return `${point.x},${point.y}`;
    })
    .join(" ");
}

function axisPreferencesFromWeights(
  weights: AxisWeightDraft,
): AxisPreferenceScores {
  const totalWeight = assessmentAxisKeys.reduce(
    (sum, key) => sum + Math.max(0, weights[key]),
    0,
  );
  if (totalWeight <= 0) {
    return Object.fromEntries(
      assessmentAxisKeys.map((key) => [key, 50]),
    ) as AxisPreferenceScores;
  }
  const averageWeight = totalWeight / assessmentAxisKeys.length;
  return Object.fromEntries(
    assessmentAxisKeys.map((key) => [
      key,
      Math.min(
        100,
        Math.round(((Math.max(0, weights[key]) / averageWeight) * 50) / 5) * 5,
      ),
    ]),
  ) as AxisPreferenceScores;
}

function normalizeAxisPreferences(
  preferences: AxisPreferenceScores,
): AxisWeightDraft {
  const total = assessmentAxisKeys.reduce(
    (sum, key) => sum + Math.max(0, preferences[key]),
    0,
  );
  if (total <= 0) {
    return {
      correctness: 20,
      depth: 20,
      fundamentals: 20,
      ownership: 20,
      communication: 20,
    };
  }
  const exactWeights = assessmentAxisKeys.map(
    (key) => (Math.max(0, preferences[key]) / total) * 100,
  );
  const normalized = exactWeights.map(Math.floor);
  let remainder = 100 - normalized.reduce((sum, value) => sum + value, 0);
  const remainderOrder = exactWeights
    .map((weight, index) => ({ fraction: weight - Math.floor(weight), index }))
    .sort(
      (left, right) =>
        right.fraction - left.fraction || left.index - right.index,
    );
  for (let cursor = 0; remainder > 0; cursor += 1) {
    normalized[remainderOrder[cursor % remainderOrder.length].index] += 1;
    remainder -= 1;
  }
  return Object.fromEntries(
    assessmentAxisKeys.map((key, index) => [key, normalized[index]]),
  ) as AxisWeightDraft;
}

function axisStrengthLabel(score: number) {
  if (score === 0) return "제외";
  if (score <= 35) return "낮게";
  if (score <= 75) return "보통";
  return "높게";
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

function nextRequirementInsertionIndex(
  requirements: JobRequirementDraft[],
  requirementType: RequirementType,
) {
  let lastMatchingIndex = -1;
  requirements.forEach((requirement, index) => {
    if (requirement.requirementType === requirementType) {
      lastMatchingIndex = index;
    }
  });
  if (lastMatchingIndex >= 0) return lastMatchingIndex + 1;
  if (requirementType === "preferred") return requirements.length;
  const firstPreferredIndex = requirements.findIndex(
    (requirement) => requirement.requirementType === "preferred",
  );
  return firstPreferredIndex >= 0 ? firstPreferredIndex : requirements.length;
}

function getRequirementMetadata(requirementType: RequirementType) {
  return requirementGroupMetadata.find(
    (metadata) => metadata.type === requirementType,
  )!;
}

function toWeightChartItems(items: EvaluationItem[]): WeightChartItem[] {
  let requiredIndex = 0;
  let preferredIndex = 0;
  return items.map((item) => {
    const required = item.requirement.requirementType === "required";
    const groupIndex = required ? requiredIndex++ : preferredIndex++;
    const colors = required ? requiredChartColors : preferredChartColors;
    const fallbackLabel = `${required ? "필수 자격" : "우대 사항"} ${groupIndex + 1}`;
    return {
      ...item,
      color: colors[groupIndex % colors.length],
      label: item.requirement.statement.trim() || fallbackLabel,
    };
  });
}

function resolveImportance(
  criterion: CriterionDraft,
  criteria: CriterionDraft[],
): CriterionImportance {
  if (criterion.importance) return criterion.importance;
  if (criteria.length <= 1) return "medium";
  const evenShare = 100 / criteria.length;
  if (criterion.weight < evenShare * 0.75) return "low";
  if (criterion.weight > evenShare * 1.25) return "high";
  return "medium";
}

function normalizeImportanceWeights(criteria: CriterionDraft[]) {
  if (criteria.length === 0) return criteria;
  const resolved = criteria.map((criterion) => ({
    ...criterion,
    importance: resolveImportance(criterion, criteria),
  }));
  const totalPoints = resolved.reduce(
    (sum, criterion) => sum + importancePoints[criterion.importance],
    0,
  );
  const exactWeights = resolved.map(
    (criterion) => (importancePoints[criterion.importance] / totalPoints) * 100,
  );
  const weights = exactWeights.map(Math.floor);
  let remainder = 100 - weights.reduce((sum, weight) => sum + weight, 0);
  const remainderOrder = exactWeights
    .map((weight, index) => ({ fraction: weight - Math.floor(weight), index }))
    .sort(
      (left, right) =>
        right.fraction - left.fraction || left.index - right.index,
    );
  for (let cursor = 0; remainder > 0; cursor += 1) {
    weights[remainderOrder[cursor % remainderOrder.length].index] += 1;
    remainder -= 1;
  }
  return resolved.map((criterion, index) => ({
    ...criterion,
    weight: weights[index],
  }));
}
