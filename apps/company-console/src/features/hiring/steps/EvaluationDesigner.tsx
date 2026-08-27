import { useEffect, useRef } from "react";

import { Plus, Trash2 } from "lucide-react";

import { ICON_BUTTON } from "../../../app/styles/primitives";
import type { FormVariant } from "../components/FormPrimitives";
import {
  createRequirementDraft,
  inferRequirementCriterionCode,
  type HiringDraft,
  type HiringDraftUpdater,
  type JobRequirementDraft,
  type RequirementType,
} from "../types";

const DESIGNER = "grid gap-7";
const HEADER =
  "flex items-start justify-between gap-6 border-b border-border pb-5 mw-620:flex-col";
const EYEBROW = "font-mono text-[12px] font-[650] text-brand";
const TITLE = "mt-1 text-[26px] font-bold text-ink mw-620:text-[23px]";
const DESCRIPTION =
  "mt-1.5 max-w-[620px] text-[14px] leading-[1.65] text-muted mw-620:text-[13px]";

const CRITERIA_LAYOUT =
  "grid grid-cols-[minmax(0,1fr)_260px] items-start gap-5 mw-680:grid-cols-1";
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
  "grid min-h-12 grid-cols-[24px_68px_minmax(120px,1fr)_32px] items-center gap-2" +
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
const CRITERIA_OVERVIEW =
  "sticky top-4 grid gap-3 rounded-xl border border-border bg-surface p-4 shadow-[0_8px_24px_#1018280a] mw-680:static";

const requirementGroupMetadata = [
  {
    type: "required",
    label: "필수 자격",
    empty: "필수 자격요건을 추가해 주세요.",
    placeholder: "예: 대규모 트래픽 시스템 설계·운영 경험",
  },
  {
    type: "preferred",
    label: "우대 사항",
    empty: "우대 사항이 있다면 추가해 주세요.",
    placeholder: "예: 기술 문서를 작성하고 공유한 경험",
  },
] as const satisfies ReadonlyArray<{
  type: RequirementType;
  label: string;
  empty: string;
  placeholder: string;
}>;

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
  const requiredCount = draft.jobRequirements.filter(
    (requirement) => requirement.requirementType === "required",
  ).length;
  const preferredCount = draft.jobRequirements.length - requiredCount;

  useEffect(() => {
    const id = pendingFocusId.current;
    if (!id) return;
    inputRefs.current.get(id)?.focus();
    pendingFocusId.current = null;
  }, [draft.jobRequirements.length]);

  function updateRequirement(id: string, patch: Partial<JobRequirementDraft>) {
    const normalizedPatch =
      typeof patch.statement === "string"
        ? {
            ...patch,
            criterionCode: inferRequirementCriterionCode(patch.statement),
          }
        : patch;
    update(
      "jobRequirements",
      draft.jobRequirements.map((requirement) =>
        requirement.id === id
          ? { ...requirement, ...normalizedPatch }
          : requirement,
      ),
    );
  }

  function setRequirementType(
    requirement: JobRequirementDraft,
    requirementType: RequirementType,
  ) {
    if (requirement.requirementType === requirementType) return;
    updateRequirement(requirement.id, { requirementType });
  }

  function addEvaluationItem(requirementType: RequirementType) {
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
      priority: Math.min(insertionIndex + 1, 5),
    };
    const requirements = [...draft.jobRequirements];
    requirements.splice(insertionIndex, 0, requirement);
    pendingFocusId.current = requirement.id;
    update(
      "jobRequirements",
      requirements.map((item, index) => ({
        ...item,
        priority: Math.min(index + 1, 5),
      })),
    );
  }

  function removeEvaluationItem(requirement: JobRequirementDraft) {
    if (draft.jobRequirements.length === 1) return;
    update(
      "jobRequirements",
      draft.jobRequirements
        .filter((item) => item.id !== requirement.id)
        .map((item, index) => ({
          ...item,
          priority: Math.min(index + 1, 5),
        })),
    );
  }

  return (
    <section className={DESIGNER} aria-labelledby="evaluation-design-title">
      <header className={HEADER}>
        <div className="min-w-0">
          <span className={EYEBROW}>면접 결과 평가</span>
          <h3 className={TITLE} id="evaluation-design-title">
            필수·우대 자격요건
          </h3>
          <p className={DESCRIPTION}>
            작성한 각 항목이 면접 질문과 최종 리포트의 평가축이 됩니다. 제출
            자료와 면접 답변을 함께 확인해 항목별 충족도를 보여줍니다.
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
            {draft.jobRequirements.map((requirement, index) => {
              const metadata = getRequirementMetadata(
                requirement.requirementType,
              );
              const nextSameType = draft.jobRequirements
                .slice(index + 1)
                .find(
                  (item) =>
                    item.requirementType === requirement.requirementType,
                );
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
                        backgroundColor:
                          requirement.requirementType === "required"
                            ? "#5966ce"
                            : "#1e9e63",
                      }}
                    />
                    {String(index + 1).padStart(2, "0")}
                  </span>

                  <div
                    aria-label={`자격요건 ${index + 1} 구분`}
                    className={TYPE_SEGMENT}
                    role="group"
                  >
                    <button
                      aria-pressed={requirement.requirementType === "required"}
                      className={
                        requirement.requirementType === "required"
                          ? TYPE_OPTION_REQUIRED_ACTIVE
                          : TYPE_OPTION
                      }
                      type="button"
                      onClick={() =>
                        setRequirementType(requirement, "required")
                      }
                    >
                      필수
                    </button>
                    <button
                      aria-pressed={requirement.requirementType === "preferred"}
                      className={
                        requirement.requirementType === "preferred"
                          ? TYPE_OPTION_PREFERRED_ACTIVE
                          : TYPE_OPTION
                      }
                      type="button"
                      onClick={() =>
                        setRequirementType(requirement, "preferred")
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
                        inputRefs.current.get(nextSameType.id)?.focus();
                        return;
                      }
                      addEvaluationItem(requirement.requirementType);
                    }}
                  />

                  <button
                    aria-label={`자격요건 ${index + 1} 삭제`}
                    className={REQUIREMENT_DELETE}
                    disabled={draft.jobRequirements.length === 1}
                    title="자격요건 삭제"
                    type="button"
                    onClick={() => removeEvaluationItem(requirement)}
                  >
                    <Trash2 aria-hidden="true" size={14} />
                  </button>
                </article>
              );
            })}
          </div>

          <button
            aria-label="자격요건 행 추가"
            className={REQUIREMENT_ADD}
            type="button"
            onClick={() =>
              addEvaluationItem(
                draft.jobRequirements.at(-1)?.requirementType ?? "required",
              )
            }
          >
            <Plus aria-hidden="true" size={12} />
            자격요건 추가
          </button>
        </section>

        <RequirementFlowOverview requirements={draft.jobRequirements} />
      </div>
    </section>
  );
}

function RequirementFlowOverview({
  requirements,
}: {
  requirements: HiringDraft["jobRequirements"];
}) {
  const example =
    requirements.find((requirement) => requirement.statement.trim()) ??
    requirements[0];
  const isRequired = example?.requirementType !== "preferred";
  const exampleStatement =
    example?.statement.trim() || "대규모 트래픽 시스템 설계·운영 경험";
  const exampleTypeLabel = isRequired ? "필수 사항" : "우대 사항";
  const steps = [
    {
      title: "알맞은 면접 기준에 연결",
      description:
        "문장 내용에 따라 기술·프로젝트·협업 중 가장 가까운 기준에 자동으로 연결합니다.",
    },
    {
      title: "제출 자료에서 근거 찾기",
      description:
        "이력서·포트폴리오 등에서 이 경험과 관련된 내용을 먼저 찾습니다.",
    },
    {
      title: "면접에서 다시 확인",
      description: isRequired
        ? "관련 근거가 있으면 우대 사항보다 먼저 확인할 수 있게 질문 순서를 앞당깁니다."
        : "관련 근거가 있으면 필수 사항 다음 순서로 실제 경험을 확인합니다.",
    },
    {
      title: "리포트에 따로 표시",
      description:
        "충족·일부 충족·미충족·판단 보류 중 하나로 결과를 보여줍니다.",
    },
  ] as const;

  return (
    <aside
      className={CRITERIA_OVERVIEW}
      aria-labelledby="requirement-flow-title"
    >
      <header className="grid gap-1">
        <h4
          className="text-[10px] font-semibold text-ink"
          id="requirement-flow-title"
        >
          자격요건을 적으면 이렇게 동작해요
        </h4>
        <p className="text-[8px] leading-[1.5] text-muted">
          작성한 필수·우대 항목 하나하나가 리포트의 평가축이 됩니다.
        </p>
      </header>

      <div className="grid gap-1.5 rounded-md border border-brand/20 bg-brand-soft/45 px-2.5 py-2.5">
        <span className="font-mono text-[8px] font-semibold text-brand">
          {exampleTypeLabel} 예시
        </span>
        <strong className="line-clamp-3 text-[9px] leading-[1.55] text-ink">
          “{exampleStatement}”
        </strong>
        <span className="text-[8px] leading-[1.45] text-muted">
          이렇게 입력하면 아래 순서로 확인합니다.
        </span>
      </div>

      <ol className="grid gap-1.5" aria-label="자격요건 처리 순서">
        {steps.map((step, index) => (
          <li
            className="grid grid-cols-[18px_minmax(0,1fr)] gap-2 rounded-md border border-border-muted bg-surface-muted/60 px-2 py-2"
            key={step.title}
          >
            <span className="font-mono text-[8px] font-semibold text-brand">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="grid gap-0.5">
              <strong className="text-[8px] text-ink">{step.title}</strong>
              <small className="text-[8px] leading-[1.45] text-muted">
                {step.description}
              </small>
            </span>
          </li>
        ))}
      </ol>

      <p className="border-l-2 border-brand pl-2.5 text-[8px] leading-[1.5] text-ink-secondary">
        리포트에는 충족·부분 충족·미충족·판단 불가 상태만 표시합니다. 자료와
        답변에 근거가 없으면 판단 불가로 남깁니다.
      </p>
    </aside>
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
