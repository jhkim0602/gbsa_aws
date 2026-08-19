import { Check, CheckCircle2, FileText } from "lucide-react";
import { useRef, type FormEvent } from "react";

import { formAlertClass } from "../../../app/styles/primitives";
import {
  Field,
  formInputClass,
  FormActions,
  FormSection,
} from "../components/FormPrimitives";
import { RoleCategoryField } from "../role-selector/RoleCategoryField";
import { TechStackCombobox } from "../tech-stack-combobox";
import type {
  CriteriaHiringStep,
  HiringDraft,
  PositionHiringStep,
} from "../types";
import { ApplicantMaterials } from "./ApplicantMaterials";
import { EvaluationDesigner } from "./EvaluationDesigner";
import { InterviewDesigner } from "./InterviewDesigner";

type StepProps = {
  draft: HiringDraft;
  submitting: boolean;
  submitLabel?: string;
  update<K extends keyof HiringDraft>(key: K, value: HiringDraft[K]): void;
  onSubmit(event: FormEvent): void;
  onBack?: () => void;
};

const positionDescriptionMaxLength = 2000;

const positionDescriptionExample = `포지션 상세

## Build the Next Version
현재 회사 리브랜딩 및 홈페이지 개편이 진행 중입니다.
이에 최신 현황을 먼저 공유드립니다.

빌드잇(Buildit)은 지난 10년간 단 한 차례의 외부 투자 없이도,
국내 주요 대기업들과 함께 엔터프라이즈 솔루션을 개발하며 성장해온 기술 중심 기업입니다.

최근 빌드잇은 AI가 산업의 본질을 바꾸는 지금을 기회로 삼아,
AI 중심 소프트웨어 기업으로의 전략적 전환을 단계별로 진행 중입니다.
이에 따라 사업 구조와 조직 운영 방식을 새롭게 재정비하고 있습니다.

빌드잇은 현재 두 개의 사업 영역을 중심으로 향후 3년의 성장 기반을 구축하고 있습니다.
• Enterprise Business : 엔터프라이즈 솔루션 프로젝트 수행
• AI Agent Business : AI Agent 기반 프로세스 자동화 솔루션 제품화

이 변화는 단순한 확장이 아닌, 회사의 정체성을 다시 정의하는 AI 중심 리브랜딩 과정입니다.
자율, 책임, 성장, 연결이라는 핵심 가치를 기반으로 업무 방식과 개발 문화를 새롭게 설계하고 있습니다.

지금은 빌드잇이 가장 역동적으로 변화하는 시기입니다.
다음 버전의 빌드잇을 함께 '릴리즈'할 동료를 찾고 있습니다.

주요업무

[담당 포지션]
Junior Product Engineer (Backend 중심)

작은 팀에서 Backend 개발을 중심으로 서버 API, 비즈니스 로직 및 데이터 처리 기능 구현과 개선에 참여하고,
Frontend 영역까지 경험을 확장하는 역할

(기술 환경은 공고 하단 SW 개발팀 주요 기술 스택 참고)`;

// `.hiring-panel .position-config-section > header` outranks `.form-section > header`'s
// `display:none`, so these sections keep their headers — see FormPrimitives.
const POSITION_BASICS_GRID =
  "grid items-end gap-6" +
  " grid-cols-[minmax(260px,1.5fr)_minmax(150px,0.75fr)_minmax(150px,0.75fr)]" +
  " mw-780:grid-cols-[minmax(0,1fr)]";

const TECH_STACK =
  "mt-3 w-full max-w-[860px] [justify-self:start] border-t border-border-muted pt-7" +
  " mw-780:max-w-none";

const DESCRIPTION_EDITOR =
  "overflow-hidden rounded-md border border-border bg-surface" +
  " focus-within:border-brand focus-within:shadow-[0_0_0_3px_#5966ce1a]";

// `border: 0` and `border-radius: 0` come free from Preflight, and `font-family: inherit`
// from its `textarea { font: inherit }`.
const DESCRIPTION_TEXTAREA =
  "block min-h-[390px] w-full resize-y bg-surface p-6 text-[13px] leading-[1.85]" +
  " whitespace-pre-wrap text-ink outline-0 placeholder:text-subtle" +
  " mw-620:min-h-[330px] mw-620:px-[14px] mw-620:py-[18px] mw-620:text-[12px]";

const EDITOR_ACTION =
  "inline-flex min-h-[30px] items-center gap-1.5 rounded-sm border border-border" +
  " bg-surface px-2.5 text-[10px] font-semibold text-ink-secondary" +
  " hover:border-brand hover:bg-brand-soft hover:text-brand";

// `:hover:not(:disabled)` only sets border and text, so a completed button keeps its green
// fill on hover; `.is-complete` is declared after the hover rule at lower specificity, so
// the hover border/text still win over it.
const EDITOR_DONE =
  "inline-flex min-h-7 items-center gap-[5px] rounded-sm border px-[9px] text-[9px]" +
  " font-semibold hover:not-disabled:border-brand hover:not-disabled:text-brand" +
  " disabled:cursor-not-allowed disabled:opacity-45";

const COMPLETION =
  "grid min-h-[470px] content-center justify-items-center px-7 py-[50px] text-center";

export function PositionStep(props: StepProps & { stage: PositionHiringStep }) {
  const { draft, stage, submitting, update, onSubmit, onBack } = props;
  const periodValid =
    !draft.recruitmentStartAt ||
    !draft.recruitmentEndAt ||
    draft.recruitmentEndAt >= draft.recruitmentStartAt;
  const readyByStage: Record<PositionHiringStep, boolean> = {
    position: Boolean(
      draft.title.trim() &&
      draft.description.trim() &&
      draft.descriptionCompleted &&
      draft.roleType &&
      draft.recruitmentStartAt &&
      draft.recruitmentEndAt &&
      periodValid,
    ),
    application: draft.submissionRequirements.some(
      (requirement) => requirement.required,
    ),
  };

  return (
    <form className="grid" onSubmit={onSubmit}>
      {stage === "position" ? (
        <>
          <FormSection
            eyebrow="01 · 기본 정보"
            title="포지션명과 모집 기간"
            description="지원자에게 보이는 포지션 이름과 공고 운영 기간을 설정합니다."
          >
            <div className={POSITION_BASICS_GRID}>
              <Field label="포지션명">
                <input
                  autoFocus
                  className={formInputClass()}
                  required
                  maxLength={200}
                  value={draft.title}
                  placeholder="예: 백엔드 플랫폼 엔지니어"
                  onChange={(event) => update("title", event.target.value)}
                />
              </Field>
              <Field label="모집 시작일">
                <input
                  className={formInputClass()}
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
                  className={formInputClass()}
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
              <p className={formAlertClass()} role="alert">
                모집 종료일은 시작일 이후로 선택해 주세요.
              </p>
            ) : null}
          </FormSection>

          <FormSection
            eyebrow="02 · 직무와 기술"
            title="직무와 주요 기술 스택"
            description="직무와 기술 환경을 함께 설정해 면접 질문과 평가 기준의 방향을 정합니다."
          >
            <RoleCategoryField
              value={draft.roleType}
              onChange={(value, suggestedTitle) => {
                update("roleType", value);
                if (suggestedTitle) update("title", suggestedTitle);
              }}
            />
            <div className={TECH_STACK}>
              <Field
                label="주요 기술 스택"
                variant="prominent"
                hint="검색하거나 목록에 없는 기술을 직접 입력할 수 있습니다."
              >
                <TechStackCombobox
                  className="min-h-16 gap-2 px-3 py-3"
                  value={draft.techStack}
                  onChange={(value) => update("techStack", value)}
                  placeholder="예: Java, Spring Boot, AWS"
                />
              </Field>
            </div>
          </FormSection>

          <FormSection
            eyebrow="03 · 공고 본문"
            title="포지션 상세"
            description="회사 소개, 포지션 배경과 주요 업무를 하나의 본문으로 구성합니다."
          >
            <PositionDescriptionEditor
              value={draft.description}
              completed={draft.descriptionCompleted}
              onChange={(value) => {
                update("description", value);
                if (draft.descriptionCompleted) {
                  update("descriptionCompleted", false);
                }
              }}
              onCompletedChange={(completed) =>
                update("descriptionCompleted", completed)
              }
            />
          </FormSection>
        </>
      ) : null}

      {stage === "application" ? (
        <ApplicantMaterials draft={draft} update={update} />
      ) : null}

      <FormActions
        submitting={submitting}
        disabled={!readyByStage[stage]}
        label="다음"
        onBack={onBack}
      />
    </form>
  );
}

function PositionDescriptionEditor({
  value,
  completed,
  onChange,
  onCompletedChange,
}: {
  value: string;
  completed: boolean;
  onChange: (value: string) => void;
  onCompletedChange: (completed: boolean) => void;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function insertExample() {
    const textarea = textareaRef.current;
    const start = textarea?.selectionStart ?? value.length;
    const end = textarea?.selectionEnd ?? start;
    const before = value.slice(0, start);
    const after = value.slice(end);
    const prefix = before && !before.endsWith("\n\n") ? "\n\n" : "";
    const suffix = after && !after.startsWith("\n\n") ? "\n\n" : "";
    const inserted = `${prefix}${positionDescriptionExample}${suffix}`;
    const nextValue = `${before}${inserted}${after}`.slice(
      0,
      positionDescriptionMaxLength,
    );
    const nextCursor = Math.min(
      before.length + inserted.length,
      positionDescriptionMaxLength,
    );

    onChange(nextValue);
    const restoreSelection = () => {
      textarea?.focus();
      textarea?.setSelectionRange(nextCursor, nextCursor);
    };
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(restoreSelection);
    } else {
      restoreSelection();
    }
  }

  return (
    <div className={DESCRIPTION_EDITOR}>
      <header className="flex min-h-12 items-center justify-between gap-4 border-b border-border bg-surface-muted px-[14px]">
        <div className="flex items-center gap-[9px]">
          <strong className="text-[11px] font-[650]">포지션 상세</strong>
          <span className="text-[9px] text-success">지원자 공개</span>
        </div>
        <button
          aria-label="포지션 상세 예시 적용"
          className={EDITOR_ACTION}
          type="button"
          onClick={insertExample}
        >
          <FileText aria-hidden="true" size={15} />
          예시 적용
        </button>
      </header>
      <textarea
        ref={textareaRef}
        aria-label="포지션 설명"
        className={DESCRIPTION_TEXTAREA}
        required
        maxLength={positionDescriptionMaxLength}
        value={value}
        placeholder={
          "포지션 상세\n\n## Build the Next Version\n회사가 지금 해결하려는 문제와 변화의 배경을 작성해 주세요.\n\n주요업무\n\n[담당 포지션]\n역할과 책임 범위를 자유롭게 작성해 주세요."
        }
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
      <footer className="flex min-h-10 items-center justify-between border-t border-border-muted bg-surface-muted px-[14px] text-[9px] text-subtle">
        <output className="font-mono" aria-live="polite">
          {value.length} / {positionDescriptionMaxLength}
        </output>
        <button
          aria-label="포지션 상세 작성 완료"
          aria-pressed={completed}
          className={`${EDITOR_DONE} ${
            completed
              ? "border-[#1e9e634d] bg-success-soft text-success"
              : "border-border bg-surface text-muted"
          }`}
          disabled={!value.trim()}
          type="button"
          onClick={() => onCompletedChange(true)}
        >
          <Check aria-hidden="true" size={12} />
          작성 완료
        </button>
      </footer>
    </div>
  );
}

export function CriteriaStep(
  props: StepProps & { stage?: CriteriaHiringStep },
) {
  const { draft, stage, submitting, submitLabel, update, onSubmit, onBack } =
    props;
  const requirementsReady =
    draft.jobRequirements.length > 0 &&
    draft.jobRequirements.every(
      (requirement) =>
        requirement.statement.trim() && requirement.criterionCode,
    );
  const criteriaReady =
    draft.criteria.length > 0 &&
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
  const ready = !stage
    ? requirementsReady && criteriaReady
    : stage === "evaluation"
      ? requirementsReady && criteriaReady
      : draft.headcount > 0 &&
        draft.interviewCapacity > 0 &&
        Boolean(draft.interviewAt) &&
        !Number.isNaN(Date.parse(draft.interviewAt)) &&
        draft.interviewDurationMinutes >= 10 &&
        Boolean(draft.prohibitedTopics.trim());

  return (
    <form className="grid" onSubmit={onSubmit}>
      {!stage || stage === "evaluation" ? (
        <EvaluationDesigner draft={draft} update={update} />
      ) : null}
      {!stage || stage === "interview" ? (
        <InterviewDesigner draft={draft} update={update} />
      ) : null}
      <FormActions
        submitting={submitting}
        disabled={!ready}
        label={submitLabel ?? (stage === "interview" ? "포지션 게시" : "다음")}
        onBack={onBack}
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
    <div className={COMPLETION}>
      <span
        className="grid size-14 place-items-center rounded-[50%] bg-success-soft text-success"
        aria-hidden="true"
      >
        <CheckCircle2 size={25} />
      </span>
      <p className="mt-[18px] mb-1 font-mono text-[9px] uppercase text-success">
        Criteria published
      </p>
      <h2 className="text-[20px]">채용 기준을 게시했습니다.</h2>
      <small className="mt-2 text-[10px] text-muted">
        게시된 기준은 이 포지션의 지원자 면접에 동일하게 적용됩니다.
      </small>
      <div className="mt-[22px] flex flex-wrap justify-center gap-2 [&>span]:inline-flex [&>span]:items-center [&>span]:gap-[5px] [&>span]:rounded-full [&>span]:bg-success-soft [&>span]:px-2 [&>span]:py-[5px] [&>span]:text-[9px] [&>span]:text-success">
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
          className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-lg border border-brand bg-brand px-[18px] text-[14px] font-semibold text-white shadow-soft hover:not-disabled:bg-brand-strong"
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
