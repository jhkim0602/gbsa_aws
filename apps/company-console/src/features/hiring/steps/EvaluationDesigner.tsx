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

import { Field } from "../components/FormPrimitives";
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

export function EvaluationDesigner({
  draft,
  update,
}: {
  draft: HiringDraft;
  update: HiringDraftUpdater;
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
    <div className="evaluation-designer">
      <section
        className="evaluation-block"
        aria-labelledby="requirements-title"
      >
        <header className="evaluation-block__header">
          <div>
            <span>01 · 채용 조건</span>
            <h3 id="requirements-title">필수·우대 자격요건</h3>
            <p>
              채용공고의 문장처럼 자유롭게 적고, 면접에서 확인할 평가기준과
              연결합니다.
            </p>
          </div>
          <strong>{draft.jobRequirements.length}개</strong>
        </header>

        <div className="requirement-worklist">
          {draft.jobRequirements.map((requirement, index) => (
            <div className="requirement-item" key={requirement.id}>
              <div className="requirement-workline">
                <span className="requirement-workline__index">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <RequirementKind
                  index={index}
                  value={requirement.requirementType}
                  onChange={(requirementType) =>
                    updateRequirement(requirement.id, { requirementType })
                  }
                />
                <label className="requirement-statement">
                  <span>자격요건 {index + 1}</span>
                  <textarea
                    aria-label={`요구사항 ${index + 1}`}
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
                <label className="requirement-priority">
                  <span>중요도 {index + 1}</span>
                  <select
                    aria-label={`중요도 ${index + 1}`}
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
                <label className="requirement-link">
                  <span>
                    <Link2 aria-hidden="true" size={12} />
                    연결 평가기준 {index + 1}
                  </span>
                  <select
                    aria-label={`연결 평가기준 ${index + 1}`}
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
                  className="icon-button"
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

      <section className="evaluation-block" aria-labelledby="criteria-title">
        <header className="evaluation-block__header">
          <div>
            <span>02 · 평가축</span>
            <h3 id="criteria-title">평가기준과 가중치</h3>
            <p>
              자격요건을 묶는 평가 주제를 만들고 면접과 리포트에서 강조할 비중을
              설정합니다.
            </p>
          </div>
          <strong>합계 {totalWeight}</strong>
        </header>

        <CriterionOverview criteria={draft.criteria} total={totalWeight} />

        <div className="criterion-axis-list">
          {draft.criteria.map((criterion, index) => (
            <div className="criterion-axis-item" key={criterion.id}>
              <article className="criterion-axis">
                <header>
                  <span>축 {String(index + 1).padStart(2, "0")}</span>
                  <label className="axis-required">
                    <input
                      checked={criterion.required}
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
                    className="icon-button"
                    disabled={draft.criteria.length === 1}
                    title="평가기준 삭제"
                    type="button"
                    onClick={() => removeCriterion(criterion.id)}
                  >
                    <Trash2 aria-hidden="true" size={14} />
                  </button>
                </header>

                <div className="criterion-axis__identity">
                  <Field label={`평가기준 이름 ${index + 1}`}>
                    <input
                      required
                      aria-label={`평가기준 이름 ${index + 1}`}
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
                  <Field label={`설명 ${index + 1}`}>
                    <input
                      aria-label={`설명 ${index + 1}`}
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

                <div className="criterion-axis__weight">
                  <label>
                    <span>
                      <SlidersHorizontal aria-hidden="true" size={12} />
                      가중치 {index + 1}
                    </span>
                    <input
                      aria-label={`가중치 ${index + 1}`}
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
                  <label className="criterion-axis__weight-value">
                    <span className="sr-only">
                      가중치 {index + 1} 직접 입력
                    </span>
                    <input
                      aria-label={`가중치 ${index + 1} 직접 입력`}
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
    <fieldset className="requirement-kind">
      <legend className="sr-only">요구사항 유형 {index + 1}</legend>
      {(["required", "preferred"] as const).map((type) => (
        <button
          aria-pressed={value === type}
          className={value === type ? "is-active" : ""}
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
    <div className="inline-insert">
      <span aria-hidden="true" />
      <button aria-label={label} title={label} type="button" onClick={onClick}>
        <Plus aria-hidden="true" size={15} />
      </button>
      <span aria-hidden="true" />
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
    <div className="criterion-axis-overview">
      <span className="criterion-axis-overview__title">
        <BarChart3 aria-hidden="true" size={16} />
        평가축 분포
      </span>
      <div className="criterion-axis-overview__bars">
        {criteria.map((criterion, index) => (
          <div key={criterion.id}>
            <span>{criterion.name.trim() || `평가기준 ${index + 1}`}</span>
            <i>
              <b
                style={{
                  width: `${Math.max((criterion.weight / scale) * 100, 0)}%`,
                }}
              />
            </i>
            <strong>{criterion.weight}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function CriterionGuide({
  criterion,
  index,
  onChange,
}: {
  criterion: CriterionDraft;
  index: number;
  onChange: (patch: Partial<CriterionDraft>) => void;
}) {
  return (
    <details className="criterion-advanced">
      <summary>
        <span>
          <ListChecks aria-hidden="true" size={14} />
          질문·검증 가이드
        </span>
        <small>AI 질문과 리포트 근거에 적용</small>
        <ChevronDown aria-hidden="true" size={15} />
      </summary>
      <div className="criterion-advanced__body">
        <p className="criterion-guide-note">
          줄바꿈한 문장마다 하나의 검증 신호로 사용됩니다. 실제 경험, 본인 행동,
          판단 근거처럼 관찰 가능한 표현을 권장합니다.
        </p>
        <div className="field-grid">
          <Field label={`확인할 요소 ${index + 1}`}>
            <textarea
              required
              aria-label={`확인할 요소 ${index + 1}`}
              rows={5}
              value={criterion.observableDimensions}
              onChange={(event) =>
                onChange({ observableDimensions: event.target.value })
              }
            />
          </Field>
          <Field label={`좋은 답변 신호 ${index + 1}`}>
            <textarea
              required
              aria-label={`좋은 답변 신호 ${index + 1}`}
              rows={5}
              value={criterion.strongAnswerSignals}
              onChange={(event) =>
                onChange({ strongAnswerSignals: event.target.value })
              }
            />
          </Field>
          <Field label={`추가 확인 신호 ${index + 1}`}>
            <textarea
              required
              aria-label={`추가 확인 신호 ${index + 1}`}
              rows={5}
              value={criterion.weakAnswerSignals}
              onChange={(event) =>
                onChange({ weakAnswerSignals: event.target.value })
              }
            />
          </Field>
          <Field label={`꼬리질문 방향 ${index + 1}`}>
            <textarea
              required
              aria-label={`꼬리질문 방향 ${index + 1}`}
              rows={5}
              value={criterion.followUpDirections}
              onChange={(event) =>
                onChange({ followUpDirections: event.target.value })
              }
            />
          </Field>
        </div>
        <div className="field-grid field-grid--three">
          <Field label={`최대 꼬리질문 ${index + 1}`}>
            <input
              aria-label={`최대 꼬리질문 ${index + 1}`}
              max={10}
              min={0}
              type="number"
              value={criterion.maxFollowUps}
              onChange={(event) =>
                onChange({ maxFollowUps: Number(event.target.value) })
              }
            />
          </Field>
          <Field label={`시간 예산(초) ${index + 1}`}>
            <input
              aria-label={`시간 예산(초) ${index + 1}`}
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
          <Field label={`판단 유보 기준 ${index + 1}`}>
            <input
              required
              aria-label={`판단 유보 기준 ${index + 1}`}
              value={criterion.abstainGuidance}
              onChange={(event) =>
                onChange({ abstainGuidance: event.target.value })
              }
            />
          </Field>
        </div>
        <Field label={`공통 질문 ${index + 1}`}>
          <textarea
            required
            aria-label={`공통 질문 ${index + 1}`}
            rows={4}
            value={criterion.commonQuestions}
            onChange={(event) =>
              onChange({ commonQuestions: event.target.value })
            }
          />
        </Field>
        <p className="criterion-guide-help">
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
