import { useEffect, useRef, useState } from "react";

import { HiringProgress, workflowSteps } from "./components/HiringProgress";
import {
  CompletionState,
  CriteriaStep,
  PositionStep,
} from "./steps/HiringSteps";
import {
  initialHiringDraft,
  type CriteriaConfiguration,
  type HiringDraft,
  type HiringResourceIds,
  type HiringStep,
  type HiringWorkspaceApi,
} from "./types";

const stepCopy = {
  position: {
    eyebrow: "새 채용 포지션",
    title: "포지션 만들기",
    description:
      "역할 정보를 입력하면 면접에서 확인할 기준 설정으로 이어집니다.",
  },
  criteria: {
    eyebrow: "채용 기준",
    title: "면접 기준 설정",
    description:
      "직무 요구사항과 확인할 내용을 연결해 게시 가능한 기준으로 만듭니다.",
  },
} as const;

export function HiringWorkspace({
  api,
  onOpenPosition,
}: {
  api: HiringWorkspaceApi;
  onOpenPosition?: (positionId: string) => void;
}) {
  const [step, setStep] = useState<HiringStep>("position");
  const [draft, setDraft] = useState<HiringDraft>(initialHiringDraft);
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

  return (
    <div className="hiring-workspace">
      <header className="page-header">
        <div>
          <p className="page-eyebrow">
            {step === "complete" ? "설정 완료" : stepCopy[step].eyebrow}
          </p>
          <h1 ref={headingRef} tabIndex={-1}>
            {step === "complete" ? "채용 기준 게시 완료" : stepCopy[step].title}
          </h1>
          <p>
            {step === "complete"
              ? "이제 포지션 운영 화면에서 지원자를 초대할 수 있습니다."
              : stepCopy[step].description}
          </p>
        </div>
        <span className="status-badge is-warning">
          {step === "complete" ? "complete" : `step ${activeStep + 1}`}
        </span>
      </header>

      <div className="page-content hiring-layout">
        <HiringProgress step={step} />
        <section className="panel hiring-panel">
          {error ? (
            <p className="form-alert" role="alert">
              {error}
            </p>
          ) : null}
          {step === "position" ? (
            <PositionStep
              {...commonStepProps}
              onSubmit={(event) => {
                event.preventDefault();
                void execute(async () => {
                  const created = await api.createPosition({
                    title: draft.title,
                    description: draft.description,
                    roleType: draft.roleType,
                    headcount: draft.headcount,
                    recruitmentStartAt: draft.recruitmentStartAt || undefined,
                    recruitmentEndAt: draft.recruitmentEndAt || undefined,
                  });
                  setIds((current) => ({
                    ...current,
                    positionId: created.positionId,
                  }));
                  setStep("criteria");
                });
              }}
            />
          ) : null}
          {step === "criteria" ? (
            <CriteriaStep
              {...commonStepProps}
              onSubmit={(event) => {
                event.preventDefault();
                void execute(async () => {
                  const published = await api.publishCriteria(
                    ids.positionId,
                    toCriteriaConfiguration(draft),
                  );
                  setIds((current) => ({
                    ...current,
                    versionId: published.versionId,
                  }));
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
    criteria: draft.criteria.map((criterion) => ({
      code: criterion.code,
      name: criterion.name.trim(),
      description: criterion.description.trim() || criterion.name.trim(),
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
    })),
    prohibitedTopics: splitCommaSeparated(draft.prohibitedTopics),
    interviewDurationMinutes: draft.interviewDurationMinutes,
  };
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
