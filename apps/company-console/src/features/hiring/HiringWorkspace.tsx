import { useEffect, useRef, useState } from "react";

import {
  formAlertClass,
  PAGE_CONTENT,
  PAGE_EYEBROW_IN_HEADER,
  PAGE_HEADER,
  PAGE_HEADER_TEXT,
  PAGE_HEADER_TITLE,
} from "../../app/styles/primitives";
import { HiringProgress, workflowSteps } from "./components/HiringProgress";
import {
  CompletionState,
  CriteriaStep,
  PositionStep,
} from "./steps/HiringSteps";
import {
  initialHiringDraft,
  type CriteriaConfiguration,
  type CriteriaHiringStep,
  type HiringDraft,
  type HiringResourceIds,
  type HiringStep,
  type HiringWorkspaceApi,
  type PositionHiringStep,
} from "./types";

const stepCopy = {
  position: {
    eyebrow: "1 / 4 · 포지션 정보",
    title: "어떤 포지션을 채용하나요?",
    description: "직무, 역할, 채용 목표와 모집 일정을 설정합니다.",
  },
  application: {
    eyebrow: "2 / 4 · 지원자 제출",
    title: "지원자에게 무엇을 요청할까요?",
    description: "면접 준비에 필요한 필수 제출 자료를 선택합니다.",
  },
  evaluation: {
    eyebrow: "3 / 4 · 평가 설계",
    title: "어떤 기준으로 평가할까요?",
    description: "필수·우대 자격요건과 평가 가중치를 설정합니다.",
  },
  interview: {
    eyebrow: "4 / 4 · 면접 운영",
    title: "면접은 어떻게 진행할까요?",
    description: "시간과 난이도를 확인한 뒤 포지션을 게시합니다.",
  },
} as const;

// `.hiring-layout` is declared three times; the merged winner is a centred single-column grid
// capped at 920px with a 28px gap, which the 880px `minmax(0,1fr)` override cannot reach
// because the later base declaration wins at equal specificity.
const HIRING_LAYOUT =
  "grid w-[min(100%,920px)] max-w-[920px] grid-cols-[minmax(0,920px)] items-start" +
  " justify-center gap-7 mx-auto";

// `.hiring-panel` cancels every visual property `.panel` sets, so only its box model remains.
const HIRING_PANEL = "min-w-0 overflow-visible";

const positionSteps: PositionHiringStep[] = ["position", "application"];
const criteriaSteps: CriteriaHiringStep[] = ["evaluation", "interview"];
const hiringDraftStorageKey = "iep.company-console.hiring-draft.v1";
const hiringDraftStorageVersion = 1;

function readStoredDraft(): HiringDraft {
  if (typeof window === "undefined" || import.meta.env.MODE === "test") {
    return initialHiringDraft;
  }

  try {
    const stored = window.localStorage.getItem(hiringDraftStorageKey);
    if (!stored) return initialHiringDraft;

    const parsed = JSON.parse(stored) as {
      version?: number;
      draft?: Partial<HiringDraft>;
    };
    if (parsed.version !== hiringDraftStorageVersion || !parsed.draft) {
      return initialHiringDraft;
    }

    const restored = {
      ...initialHiringDraft,
      ...parsed.draft,
      techStack: Array.isArray(parsed.draft.techStack)
        ? parsed.draft.techStack.filter(
            (technology): technology is string =>
              typeof technology === "string",
          )
        : [],
      descriptionCompleted: parsed.draft.descriptionCompleted === true,
    };
    return {
      ...restored,
      criteria: normalizeCriterionWeights(restored.criteria),
    };
  } catch {
    return initialHiringDraft;
  }
}

export function HiringWorkspace({
  api,
  onOpenPosition,
}: {
  api: HiringWorkspaceApi;
  onOpenPosition?: (positionId: string) => void;
}) {
  const [step, setStep] = useState<HiringStep>("position");
  const [draft, setDraft] = useState<HiringDraft>(readStoredDraft);
  const [ids, setIds] = useState<HiringResourceIds>({
    positionId: "",
    versionId: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
  }, [step]);

  useEffect(() => {
    if (typeof window === "undefined" || import.meta.env.MODE === "test") {
      return;
    }

    try {
      window.localStorage.setItem(
        hiringDraftStorageKey,
        JSON.stringify({
          version: hiringDraftStorageVersion,
          draft,
        }),
      );
    } catch {
      // The form remains usable when storage is blocked or full.
    }
  }, [draft]);

  const activeStep =
    step === "complete"
      ? workflowSteps.length
      : workflowSteps.findIndex((item) => item.id === step);

  function update<K extends keyof HiringDraft>(key: K, value: HiringDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function execute(action: () => Promise<void>) {
    setSubmitting(true);
    setError("");
    try {
      await action();
    } catch {
      setError("요청을 완료하지 못했습니다. 입력과 API 연결을 확인해 주세요.");
    } finally {
      setSubmitting(false);
    }
  }

  const commonStepProps = {
    draft,
    submitting,
    update,
  };

  function move(offset: -1 | 1) {
    const currentIndex = workflowSteps.findIndex((item) => item.id === step);
    const target = workflowSteps[currentIndex + offset];
    if (target) {
      setError("");
      setStep(target.id);
    }
  }

  return (
    <div className="min-w-0">
      <header className={PAGE_HEADER}>
        <div>
          {/* `.page-eyebrow` loses colour, size and margin to `.page-header p`
              (0,1,1 beats 0,1,0), so this renders 14px/muted, not 9px/brand. */}
          <p className={PAGE_EYEBROW_IN_HEADER}>
            {step === "complete" ? "설정 완료" : stepCopy[step].eyebrow}
          </p>
          <h1 className={PAGE_HEADER_TITLE} ref={headingRef} tabIndex={-1}>
            {step === "complete" ? "채용 기준 게시 완료" : stepCopy[step].title}
          </h1>
          <p className={PAGE_HEADER_TEXT}>
            {step === "complete"
              ? "이제 포지션 운영 화면에서 지원자를 초대할 수 있습니다."
              : stepCopy[step].description}
          </p>
        </div>
        {/* `.hiring-workspace > .page-header .status-badge { display: none }` — this badge
            has never rendered on this screen. */}
        <span className="hidden">
          {step === "complete" ? "complete" : `step ${activeStep + 1}`}
        </span>
      </header>

      <div className={`${PAGE_CONTENT} ${HIRING_LAYOUT}`}>
        <HiringProgress step={step} />
        <section className={HIRING_PANEL}>
          {error ? (
            <p className={formAlertClass()} role="alert">
              {error}
            </p>
          ) : null}
          {positionSteps.includes(step as PositionHiringStep) ? (
            <PositionStep
              {...commonStepProps}
              stage={step as PositionHiringStep}
              onBack={step === "position" ? undefined : () => move(-1)}
              onSubmit={(event) => {
                event.preventDefault();
                move(1);
              }}
            />
          ) : null}
          {criteriaSteps.includes(step as CriteriaHiringStep) ? (
            <CriteriaStep
              {...commonStepProps}
              stage={step as CriteriaHiringStep}
              onBack={() => move(-1)}
              onSubmit={(event) => {
                event.preventDefault();
                if (step !== "interview") {
                  move(1);
                  return;
                }
                void execute(async () => {
                  let positionId = ids.positionId;
                  if (!positionId) {
                    const created = await api.createPosition({
                      title: draft.title,
                      description: draft.description,
                      roleType: draft.roleType,
                      headcount: draft.headcount,
                      interviewCapacity: draft.interviewCapacity,
                      interviewAt: draft.interviewAt || undefined,
                      recruitmentStartAt: draft.recruitmentStartAt || undefined,
                      recruitmentEndAt: draft.recruitmentEndAt || undefined,
                      submissionRequirements: draft.submissionRequirements.map(
                        (requirement) => ({
                          materialType: requirement.materialType,
                          required: requirement.required,
                          enabled: requirement.required,
                        }),
                      ),
                    });
                    positionId = created.positionId;
                    setIds((current) => ({
                      ...current,
                      positionId,
                    }));
                  }
                  const published = await api.publishCriteria(
                    positionId,
                    toCriteriaConfiguration(draft),
                  );
                  setIds((current) => ({
                    ...current,
                    versionId: published.versionId,
                  }));
                  if (typeof window !== "undefined") {
                    try {
                      window.localStorage.removeItem(hiringDraftStorageKey);
                    } catch {
                      // Publishing must not fail because local storage is unavailable.
                    }
                  }
                  setStep("complete");
                });
              }}
            />
          ) : null}
          {step === "complete" ? (
            <CompletionState
              onOpenPosition={
                onOpenPosition && ids.positionId
                  ? () => onOpenPosition(ids.positionId)
                  : undefined
              }
            />
          ) : null}
        </section>
      </div>
    </div>
  );
}

export function toCriteriaConfiguration(
  draft: HiringDraft,
): CriteriaConfiguration {
  return {
    jobRequirements: draft.jobRequirements.map((requirement) => ({
      requirementType: requirement.requirementType,
      statement: requirement.statement.trim(),
      priority: requirement.priority,
      criterionCode: requirement.criterionCode,
    })),
    criteria: draft.criteria.map((criterion) => {
      const linkedRequirement = draft.jobRequirements.find(
        (requirement) => requirement.criterionCode === criterion.code,
      );
      const evaluationAxis =
        linkedRequirement?.statement.trim() || criterion.name.trim();

      return {
        code: criterion.code,
        name: evaluationAxis,
        description: criterion.description.trim() || evaluationAxis,
        weight: criterion.weight,
        required: criterion.required,
        verificationGuide: {
          observableDimensions: splitLines(criterion.observableDimensions),
          strongAnswerSignals: splitLines(criterion.strongAnswerSignals),
          weakAnswerSignals: splitLines(criterion.weakAnswerSignals),
          followUpDirections: splitLines(criterion.followUpDirections),
          maxFollowUps: criterion.maxFollowUps,
          timeBudgetSeconds: criterion.timeBudgetSeconds,
        },
        abstainGuidance: criterion.abstainGuidance.trim(),
        commonQuestions: splitLines(criterion.commonQuestions),
      };
    }),
    prohibitedTopics: splitCommaSeparated(draft.prohibitedTopics),
    interviewDurationMinutes: draft.interviewDurationMinutes,
    interviewLevel: draft.interviewLevel,
    personaDefinition: {
      name: draft.interviewerName,
      tone: draft.interviewerTone,
      voiceId: draft.interviewerVoiceId,
    },
  };
}

function normalizeCriterionWeights(criteria: HiringDraft["criteria"]) {
  if (criteria.length === 0) return criteria;
  const total = criteria.reduce((sum, criterion) => sum + criterion.weight, 0);
  if (total === 100) return criteria;
  if (total <= 0) {
    return distributeEvenly(criteria);
  }
  return distributeByRatio(criteria, 100, total);
}

function distributeEvenly(criteria: HiringDraft["criteria"]) {
  const base = Math.floor(100 / criteria.length);
  let remainder = 100 - base * criteria.length;
  return criteria.map((criterion) => ({
    ...criterion,
    weight: base + (remainder-- > 0 ? 1 : 0),
  }));
}

function distributeByRatio(
  criteria: HiringDraft["criteria"],
  targetTotal: number,
  currentTotal: number,
) {
  let assigned = 0;
  return criteria.map((criterion, index) => {
    const weight =
      index === criteria.length - 1
        ? targetTotal - assigned
        : Math.round((criterion.weight / currentTotal) * targetTotal);
    assigned += weight;
    return { ...criterion, weight };
  });
}

function splitLines(value: string) {
  return value
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function splitCommaSeparated(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
