import {
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Plus,
  Settings2,
  Trash2,
} from "lucide-react";
import type { FormEvent } from "react";

import { Field, FormActions, FormSection } from "../components/FormPrimitives";
import {
  createCriterionDraft,
  createRequirementDraft,
  interviewLevelLabels,
  type CriterionDraft,
  type HiringDraft,
  type InterviewLevel,
  type JobRequirementDraft,
} from "../types";

const interviewLevelOptions = ["entry", "junior", "senior"] as const;

const roleOptions = [
  { value: "개발", label: "개발", description: "백엔드·프론트엔드·모바일" },
  { value: "데이터", label: "데이터", description: "데이터·AI·분석" },
  {
    value: "인프라·보안",
    label: "인프라·보안",
    description: "클라우드·DevOps·보안",
  },
  { value: "제품·기획", label: "제품·기획", description: "PM·PO·서비스 기획" },
] as const;

type StepProps = {
  draft: HiringDraft;
  submitting: boolean;
  submitLabel?: string;
  update<K extends keyof HiringDraft>(key: K, value: HiringDraft[K]): void;
  onSubmit(event: FormEvent): void;
};

export function PositionStep(props: StepProps) {
  const { draft, submitting, update, onSubmit } = props;
  const periodValid =
    !draft.recruitmentStartAt ||
    !draft.recruitmentEndAt ||
    draft.recruitmentEndAt >= draft.recruitmentStartAt;
  const ready = Boolean(
    draft.title.trim() &&
    draft.description.trim() &&
    draft.roleType &&
    draft.headcount > 0 &&
    draft.recruitmentStartAt &&
    draft.recruitmentEndAt &&
    periodValid,
  );

  return (
    <form className="workspace-form" onSubmit={onSubmit}>
      <FormSection
        eyebrow="01 · Position"
        title="어떤 사람을 찾고 있나요?"
        description="한 번에 필요한 정보만 결정하면 다음 설정에 자동으로 이어집니다."
      >
        <section className="position-decision">
          <span className="position-decision__number">1</span>
          <div>
            <h4>어떤 직무를 채용하나요?</h4>
            <p>가장 가까운 직무를 선택하고 포지션 이름을 적어주세요.</p>
          </div>
          <Field label="포지션명">
            <input
              required
              maxLength={200}
              value={draft.title}
              placeholder="예: 백엔드 플랫폼 엔지니어"
              onChange={(event) => update("title", event.target.value)}
            />
          </Field>
          <fieldset className="role-choice-grid">
            <legend>직무</legend>
            {roleOptions.map((option) => (
              <button
                key={option.value}
                className={draft.roleType === option.value ? "is-selected" : ""}
                type="button"
                aria-pressed={draft.roleType === option.value}
                onClick={() => update("roleType", option.value)}
              >
                <strong>{option.label}</strong>
                <small>{option.description}</small>
              </button>
            ))}
          </fieldset>
        </section>

        <section className="position-decision">
          <span className="position-decision__number">2</span>
          <div>
            <h4>얼마나, 언제까지 채용할까요?</h4>
            <p>운영 현황과 캘린더에 그대로 반영되는 값이에요.</p>
          </div>
          <div className="field-grid field-grid--three">
            <Field label="채용 인원">
              <input
                type="number"
                min={1}
                max={10000}
                value={draft.headcount}
                onChange={(event) =>
                  update("headcount", Number(event.target.value))
                }
              />
            </Field>
            <Field label="모집 시작일">
              <input
                required
                type="date"
                value={draft.recruitmentStartAt}
                onChange={(event) =>
                  update("recruitmentStartAt", event.target.value)
                }
              />
            </Field>
            <Field label="모집 종료일">
              <input
                required
                type="date"
                min={draft.recruitmentStartAt || undefined}
                value={draft.recruitmentEndAt}
                onChange={(event) =>
                  update("recruitmentEndAt", event.target.value)
                }
              />
            </Field>
          </div>
          {!periodValid ? (
            <p className="form-alert" role="alert">
              모집 종료일은 시작일 이후로 선택해 주세요.
            </p>
          ) : null}
        </section>

        <section className="position-decision">
          <span className="position-decision__number">3</span>
          <div>
            <h4>이 역할이 맡을 일을 알려주세요.</h4>
            <p>지원자와 평가 질문 생성에 필요한 업무·책임 범위를 적어주세요.</p>
          </div>
          <Field label="역할 범위">
            <textarea
              aria-label="포지션 설명"
              required
              rows={7}
              maxLength={20000}
              value={draft.description}
              placeholder={
                "예) 결제 트래픽을 안정적으로 처리하는 API를 설계하고,\n장애 원인을 분석해 운영 품질을 개선합니다."
              }
              onChange={(event) => update("description", event.target.value)}
            />
            <span className="field-character-count" aria-live="polite">
              {draft.description.length} / 20000
            </span>
          </Field>
        </section>
      </FormSection>
      <FormActions
        submitting={submitting}
        disabled={!ready}
        label="포지션 만들기"
      />
    </form>
  );
}

export function CriteriaStep(props: StepProps) {
  const {
    draft,
    submitting,
    submitLabel = "평가기준 게시",
    update,
    onSubmit,
  } = props;
  const weightTotal = draft.criteria.reduce(
    (total, criterion) => total + criterion.weight,
    0,
  );
  const ready =
    draft.jobRequirements.length > 0 &&
    draft.criteria.length > 0 &&
    draft.jobRequirements.every(
      (requirement) =>
        requirement.statement.trim() && requirement.criterionCode,
    ) &&
    draft.criteria.every(
      (criterion) =>
        criterion.name.trim() &&
        criterion.observableDimensions.trim() &&
        criterion.strongAnswerSignals.trim() &&
        criterion.weakAnswerSignals.trim() &&
        criterion.followUpDirections.trim() &&
        criterion.abstainGuidance.trim() &&
        criterion.commonQuestions.trim(),
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

  return (
    <form className="workspace-form" onSubmit={onSubmit}>
      <FormSection
        eyebrow="02 · Requirements"
        title="직무 요구사항"
        description="채용공고의 필수·우대사항을 적고 확인할 평가기준에 연결합니다."
      >
        <div className="requirement-list">
          {draft.jobRequirements.map((requirement, index) => (
            <div className="requirement-row" key={requirement.id}>
              <Field label={`구분 ${index + 1}`}>
                <select
                  value={requirement.requirementType}
                  onChange={(event) =>
                    updateRequirement(requirement.id, {
                      requirementType: event.target.value as
                        "required" | "preferred",
                    })
                  }
                >
                  <option value="required">필수</option>
                  <option value="preferred">우대</option>
                </select>
              </Field>
              <Field label={`요구사항 ${index + 1}`}>
                <input
                  required
                  value={requirement.statement}
                  placeholder="예: ECS 운영 장애 대응 경험"
                  onChange={(event) =>
                    updateRequirement(requirement.id, {
                      statement: event.target.value,
                    })
                  }
                />
              </Field>
              <Field label={`중요도 ${index + 1}`}>
                <select
                  value={requirement.priority}
                  onChange={(event) =>
                    updateRequirement(requirement.id, {
                      priority: Number(event.target.value),
                    })
                  }
                >
                  <option value={1}>높음</option>
                  <option value={2}>중간</option>
                  <option value={3}>보통</option>
                  <option value={4}>낮음</option>
                  <option value={5}>참고</option>
                </select>
              </Field>
              <Field label={`연결 평가기준 ${index + 1}`}>
                <select
                  value={requirement.criterionCode}
                  onChange={(event) =>
                    updateRequirement(requirement.id, {
                      criterionCode: event.target.value,
                    })
                  }
                >
                  {draft.criteria.map((criterion, criterionIndex) => (
                    <option key={criterion.id} value={criterion.code}>
                      {criterion.name || `평가기준 ${criterionIndex + 1}`}
                    </option>
                  ))}
                </select>
              </Field>
              <button
                aria-label={`요구사항 ${index + 1} 삭제`}
                className="icon-button"
                disabled={draft.jobRequirements.length === 1}
                title="요구사항 삭제"
                type="button"
                onClick={() =>
                  update(
                    "jobRequirements",
                    draft.jobRequirements.filter(
                      (item) => item.id !== requirement.id,
                    ),
                  )
                }
              >
                <Trash2 size={16} aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>
        <button
          className="button-secondary compact-command"
          type="button"
          onClick={() => {
            const next = draft.jobRequirements.length + 1;
            update("jobRequirements", [
              ...draft.jobRequirements,
              {
                ...createRequirementDraft(next),
                criterionCode: draft.criteria[0]?.code ?? `CRITERION_${next}`,
              },
            ]);
          }}
        >
          <Plus size={16} aria-hidden="true" />
          요구사항 추가
        </button>
      </FormSection>

      <FormSection
        eyebrow="03 · Criteria"
        title="평가기준과 검증 가이드"
        description="지원자의 실제 답변에서 무엇을 확인하고 어떻게 더 물을지 정합니다."
      >
        <div className="criterion-summary" aria-live="polite">
          <span>{draft.criteria.length}개 평가기준</span>
          <strong>가중치 합계 {weightTotal}</strong>
        </div>
        <div className="criterion-list">
          {draft.criteria.map((criterion, index) => (
            <section className="criterion-editor" key={criterion.id}>
              <header>
                <div>
                  <span>평가기준 {index + 1}</span>
                  <strong>{criterion.name || "이름을 입력하세요"}</strong>
                </div>
                <button
                  aria-label={`평가기준 ${index + 1} 삭제`}
                  className="icon-button"
                  disabled={draft.criteria.length === 1}
                  title="평가기준 삭제"
                  type="button"
                  onClick={() => {
                    const remaining = draft.criteria.filter(
                      (item) => item.id !== criterion.id,
                    );
                    update("criteria", remaining);
                    update(
                      "jobRequirements",
                      draft.jobRequirements.map((requirement) =>
                        requirement.criterionCode === criterion.code
                          ? {
                              ...requirement,
                              criterionCode: remaining[0]?.code ?? "",
                            }
                          : requirement,
                      ),
                    );
                  }}
                >
                  <Trash2 size={16} aria-hidden="true" />
                </button>
              </header>
              <div className="field-grid">
                <Field label={`평가기준 이름 ${index + 1}`}>
                  <input
                    required
                    value={criterion.name}
                    placeholder="예: 운영 문제 해결"
                    onChange={(event) =>
                      updateCriterion(criterion.id, {
                        name: event.target.value,
                      })
                    }
                  />
                </Field>
                <Field label={`설명 ${index + 1}`}>
                  <input
                    value={criterion.description}
                    placeholder="이 기준이 확인하는 역량"
                    onChange={(event) =>
                      updateCriterion(criterion.id, {
                        description: event.target.value,
                      })
                    }
                  />
                </Field>
                <Field label={`가중치 ${index + 1}`}>
                  <input
                    min={0}
                    type="number"
                    value={criterion.weight}
                    onChange={(event) =>
                      updateCriterion(criterion.id, {
                        weight: Number(event.target.value),
                      })
                    }
                  />
                </Field>
              </div>
              <label className="binary-control">
                <input
                  checked={criterion.required}
                  type="checkbox"
                  onChange={(event) =>
                    updateCriterion(criterion.id, {
                      required: event.target.checked,
                    })
                  }
                />
                필수 평가기준
              </label>
              <details className="criterion-advanced">
                <summary>
                  <span>
                    <Settings2 size={15} aria-hidden="true" />
                    질문·검증 가이드 세부 설정
                  </span>
                  <small>권장 기본값 적용됨</small>
                  <ChevronDown size={16} aria-hidden="true" />
                </summary>
                <div className="criterion-advanced__body">
                  <div className="evidence-rule-grid">
                    <Field
                      label={`확인할 요소 ${index + 1}`}
                      hint="한 줄에 하나씩 입력합니다."
                    >
                      <textarea
                        required
                        rows={4}
                        value={criterion.observableDimensions}
                        placeholder={
                          "실제 장애 상황\n원인 분석\n직접 수행한 복구\n재발 방지"
                        }
                        onChange={(event) =>
                          updateCriterion(criterion.id, {
                            observableDimensions: event.target.value,
                          })
                        }
                      />
                    </Field>
                    <Field label={`좋은 답변 신호 ${index + 1}`}>
                      <textarea
                        required
                        rows={4}
                        value={criterion.strongAnswerSignals}
                        placeholder="본인 행동과 판단 근거가 구체적임"
                        onChange={(event) =>
                          updateCriterion(criterion.id, {
                            strongAnswerSignals: event.target.value,
                          })
                        }
                      />
                    </Field>
                    <Field label={`추가 확인 신호 ${index + 1}`}>
                      <textarea
                        required
                        rows={4}
                        value={criterion.weakAnswerSignals}
                        placeholder="팀 활동이나 결과만 언급함"
                        onChange={(event) =>
                          updateCriterion(criterion.id, {
                            weakAnswerSignals: event.target.value,
                          })
                        }
                      />
                    </Field>
                    <Field label={`꼬리질문 방향 ${index + 1}`}>
                      <textarea
                        required
                        rows={4}
                        value={criterion.followUpDirections}
                        placeholder={"본인이 직접 수행한 행동\n복구 우선순위"}
                        onChange={(event) =>
                          updateCriterion(criterion.id, {
                            followUpDirections: event.target.value,
                          })
                        }
                      />
                    </Field>
                  </div>
                  <div className="field-grid field-grid--three">
                    <Field label={`최대 꼬리질문 ${index + 1}`}>
                      <input
                        max={3}
                        min={0}
                        type="number"
                        value={criterion.maxFollowUps}
                        onChange={(event) =>
                          updateCriterion(criterion.id, {
                            maxFollowUps: Number(event.target.value),
                          })
                        }
                      />
                    </Field>
                    <Field label={`시간 예산(초) ${index + 1}`}>
                      <input
                        max={1800}
                        min={60}
                        step={30}
                        type="number"
                        value={criterion.timeBudgetSeconds}
                        onChange={(event) =>
                          updateCriterion(criterion.id, {
                            timeBudgetSeconds: Number(event.target.value),
                          })
                        }
                      />
                    </Field>
                  </div>
                  <Field label={`판단 유보 기준 ${index + 1}`}>
                    <textarea
                      required
                      rows={2}
                      value={criterion.abstainGuidance}
                      onChange={(event) =>
                        updateCriterion(criterion.id, {
                          abstainGuidance: event.target.value,
                        })
                      }
                    />
                  </Field>
                  <Field
                    label={`공통 질문 ${index + 1}`}
                    hint="한 줄에 질문 하나를 입력합니다."
                  >
                    <textarea
                      required
                      rows={3}
                      value={criterion.commonQuestions}
                      placeholder="운영 장애를 해결한 경험을 설명해 주세요."
                      onChange={(event) =>
                        updateCriterion(criterion.id, {
                          commonQuestions: event.target.value,
                        })
                      }
                    />
                  </Field>
                </div>
              </details>
            </section>
          ))}
        </div>
        <button
          className="button-secondary compact-command"
          type="button"
          onClick={() => {
            const next = draft.criteria.length + 1;
            update("criteria", [...draft.criteria, createCriterionDraft(next)]);
          }}
        >
          <Plus size={16} aria-hidden="true" />
          평가기준 추가
        </button>
      </FormSection>

      <FormSection
        eyebrow="04 · Interview policy"
        title="면접 운영"
        description="면접 시간과 질문하면 안 되는 주제를 정합니다."
      >
        <div className="field-grid">
          <Field label="면접 시간(분)">
            <div className="input-with-icon">
              <Clock3 size={14} aria-hidden="true" />
              <input
                required
                type="number"
                min={10}
                max={120}
                value={draft.interviewDurationMinutes}
                onChange={(event) =>
                  update("interviewDurationMinutes", Number(event.target.value))
                }
              />
            </div>
          </Field>
          <Field
            label="면접 난이도"
            hint={interviewLevelLabels[draft.interviewLevel].hint}
          >
            <select
              value={draft.interviewLevel}
              onChange={(event) =>
                update("interviewLevel", event.target.value as InterviewLevel)
              }
            >
              {interviewLevelOptions.map((level) => (
                <option key={level} value={level}>
                  {interviewLevelLabels[level].name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="금지 주제" hint="쉼표로 구분합니다.">
            <input
              required
              value={draft.prohibitedTopics}
              placeholder="가족, 외모"
              onChange={(event) =>
                update("prohibitedTopics", event.target.value)
              }
            />
          </Field>
        </div>
      </FormSection>
      <FormActions
        submitting={submitting}
        disabled={!ready}
        label={submitLabel}
      />
    </form>
  );
}

export function CompletionState({
  onOpenPosition,
}: {
  onOpenPosition?: () => void;
}) {
  return (
    <div className="completion-state">
      <span aria-hidden="true">
        <CheckCircle2 size={25} />
      </span>
      <p>Criteria published</p>
      <h2>채용 기준을 게시했습니다.</h2>
      <small>
        게시된 기준은 이 포지션의 지원자 면접에 동일하게 적용됩니다.
      </small>
      <div>
        <span>
          <Check size={13} aria-hidden="true" />
          필수·우대 요구사항 연결
        </span>
        <span>
          <Check size={13} aria-hidden="true" />
          평가기준과 검증 가이드 게시
        </span>
        <span>
          <Check size={13} aria-hidden="true" />
          면접 운영 정책 고정
        </span>
      </div>
      {onOpenPosition ? (
        <button
          className="button-primary"
          type="button"
          onClick={onOpenPosition}
        >
          포지션 운영으로 이동
        </button>
      ) : null}
      <p className="sr-only" role="status">
        채용 기준을 게시했습니다.
      </p>
    </div>
  );
}
