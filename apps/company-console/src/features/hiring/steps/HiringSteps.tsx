import { Check, CheckCircle2, FileText } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { BUTTON_PRIMARY, formAlertClass } from "../../../app/styles/primitives";
import {
  Field,
  formInputClass,
  FormActions,
  FormSection,
  type FormVariant,
} from "../components/FormPrimitives";
import { RoleCategoryField } from "../role-selector/RoleCategoryField";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../tech-stack-combobox/dialog";
import { MAX_GUARANTEED_INTERVIEW_CONCURRENCY } from "../interviewCapacityEstimate";
import { InvitationEmailEditor } from "../InvitationEmailEditor";
import type { InvitationEmailTemplateApi } from "../invitationEmailTemplate";
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

export const POSITION_DESCRIPTION_MAX_LENGTH = 400;

const positionDescriptionExample = `우리 팀은 기업 고객이 사용하는 AI 기반 업무 자동화 서비스를 만들고 있습니다.
이번 포지션은 서버 API, 비즈니스 로직과 데이터 처리 기능을 구현하고 안정적으로 운영합니다.
기획자와 프론트엔드 개발자와 협업하며 제품 개선 전 과정에 참여합니다.
사용자가 믿고 사용할 수 있는 서비스를 함께 만들 분을 찾습니다.`;

// `.hiring-panel .position-config-section > header` outranks `.form-section > header`'s
// `display:none`, so these sections keep their headers — see FormPrimitives.
const POSITION_BASICS_GRID =
  "grid items-end gap-6" +
  " grid-cols-[minmax(260px,1.5fr)_minmax(150px,0.75fr)_minmax(150px,0.75fr)]" +
  " mw-780:grid-cols-[minmax(0,1fr)]";

const DESCRIPTION_EDITOR =
  "overflow-hidden rounded-md border border-border bg-surface" +
  " focus-within:border-brand focus-within:shadow-[0_0_0_3px_#5966ce1a]";

// `border: 0` and `border-radius: 0` come free from Preflight, and `font-family: inherit`
// from its `textarea { font: inherit }`.
const DESCRIPTION_TEXTAREA =
  "block min-h-[132px] w-full resize-y bg-surface px-5 py-4 text-[13px] leading-[1.8]" +
  " whitespace-pre-wrap text-ink outline-0 placeholder:text-subtle" +
  " mw-620:min-h-[148px] mw-620:px-[14px] mw-620:py-[14px] mw-620:text-[12px]";

const INVITATION_TEMPLATE_SECTION =
  "mt-7 overflow-hidden rounded-md border border-border bg-surface";

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

type PositionPage = "basics" | "description";

const positionPageOrder: PositionPage[] = ["basics", "description"];

export function PositionStep(
  props: StepProps & {
    stage: PositionHiringStep;
    invitationTemplateApi?: InvitationEmailTemplateApi;
  },
) {
  const {
    draft,
    stage,
    submitting,
    update,
    onSubmit,
    onBack,
    invitationTemplateApi,
  } = props;
  const [positionPage, setPositionPage] = useState<PositionPage>("basics");
  const [rolePickerOpen, setRolePickerOpen] = useState(false);
  const [pendingRoleTitle, setPendingRoleTitle] = useState(draft.title);
  const [pendingRoleType, setPendingRoleType] = useState(draft.roleType);
  const roleTitleInputRef = useRef<HTMLInputElement>(null);
  const periodValid =
    !draft.recruitmentStartAt ||
    !draft.recruitmentEndAt ||
    draft.recruitmentEndAt >= draft.recruitmentStartAt;
  const readyByPositionPage: Record<PositionPage, boolean> = {
    basics: Boolean(
      draft.title.trim() &&
      draft.roleType &&
      draft.recruitmentStartAt &&
      draft.recruitmentEndAt &&
      periodValid,
    ),
    description: Boolean(
      draft.description.trim() && draft.descriptionCompleted,
    ),
  };
  const readyByStage: Record<PositionHiringStep, boolean> = {
    position: readyByPositionPage[positionPage],
    application: draft.submissionRequirements.some(
      (requirement) => requirement.required,
    ),
  };

  function openRolePicker() {
    setPendingRoleTitle(draft.title);
    setPendingRoleType(draft.roleType);
    setRolePickerOpen(true);
  }

  function closeRolePicker() {
    setRolePickerOpen(false);
  }

  function applyRoleSelection() {
    const title = pendingRoleTitle.trim();
    if (!title || !pendingRoleType) return;
    update("title", title);
    update("roleType", pendingRoleType);
    closeRolePicker();
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (stage === "application") {
      onSubmit(event);
      return;
    }

    const currentIndex = positionPageOrder.indexOf(positionPage);
    const nextPage = positionPageOrder[currentIndex + 1];
    if (nextPage) {
      setPositionPage(nextPage);
      return;
    }
    onSubmit(event);
  }

  function handleBack() {
    if (stage === "application") {
      onBack?.();
      return;
    }

    const currentIndex = positionPageOrder.indexOf(positionPage);
    const previousPage = positionPageOrder[currentIndex - 1];
    if (previousPage) setPositionPage(previousPage);
  }

  const canGoBack =
    stage === "application" || positionPage !== positionPageOrder[0];

  return (
    <form className="grid" onSubmit={handleSubmit}>
      {stage === "position" ? (
        <>
          {positionPage === "basics" ? (
            <FormSection
              eyebrow="01 · 기본 정보"
              title="포지션명과 모집 기간"
              description="포지션명을 눌러 직무를 선택하고 공고 운영 기간을 설정합니다."
            >
              <div className={POSITION_BASICS_GRID}>
                <Field label="포지션명">
                  <input
                    aria-expanded={rolePickerOpen}
                    aria-haspopup="dialog"
                    className={formInputClass()}
                    required
                    maxLength={200}
                    value={draft.title}
                    placeholder="예: 백엔드 플랫폼 엔지니어"
                    onClick={openRolePicker}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === "ArrowDown") {
                        event.preventDefault();
                        openRolePicker();
                      }
                    }}
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
              <Dialog
                open={rolePickerOpen}
                onOpenChange={(open) => {
                  if (open) openRolePicker();
                  else closeRolePicker();
                }}
              >
                <DialogContent
                  className="max-h-[90vh] gap-0 overflow-hidden p-0 sm:max-w-[980px]"
                  onOpenAutoFocus={(event) => {
                    event.preventDefault();
                    roleTitleInputRef.current?.focus();
                    roleTitleInputRef.current?.select();
                  }}
                >
                  <DialogHeader className="border-b border-border px-6 py-5 pr-14">
                    <span className="font-mono text-[9px] font-bold text-brand uppercase">
                      직무 선택
                    </span>
                    <DialogTitle className="text-xl font-bold text-ink">
                      찾아보세요!
                    </DialogTitle>
                    <DialogDescription className="text-[11px] leading-5 text-muted">
                      포지션명을 직접 수정하거나 아래에서 세부 직무를 선택해
                      주세요.
                    </DialogDescription>
                  </DialogHeader>

                  <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-3 border-b border-border-muted px-6 py-4 mw-520:grid-cols-[minmax(0,1fr)]">
                    <label className="grid gap-2 text-[11px] font-semibold text-ink">
                      포지션명 수정
                      <input
                        ref={roleTitleInputRef}
                        className={formInputClass()}
                        maxLength={200}
                        value={pendingRoleTitle}
                        placeholder="예: 백엔드 플랫폼 엔지니어"
                        onChange={(event) =>
                          setPendingRoleTitle(event.target.value)
                        }
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            applyRoleSelection();
                          }
                        }}
                      />
                    </label>
                    <button
                      className={`${BUTTON_PRIMARY} min-w-[92px] mw-520:w-full`}
                      disabled={
                        !pendingRoleTitle.trim() || !pendingRoleType.trim()
                      }
                      type="button"
                      onClick={applyRoleSelection}
                    >
                      적용하기
                    </button>
                  </div>

                  <div className="min-h-0 overflow-y-auto">
                    <RoleCategoryField
                      value={pendingRoleType}
                      onRequestClose={closeRolePicker}
                      onChange={(value, suggestedTitle) => {
                        setPendingRoleType(value);
                        if (suggestedTitle) setPendingRoleTitle(suggestedTitle);
                      }}
                    />
                  </div>
                </DialogContent>
              </Dialog>
            </FormSection>
          ) : null}

          {positionPage === "description" ? (
            <FormSection
              eyebrow="02 · 공고 본문"
              title="포지션 상세"
              description="지원자가 빠르게 이해할 수 있도록 포지션을 3~4줄로 요약합니다."
            >
              <aside className="grid gap-1.5 rounded-lg border border-brand/20 bg-brand-soft px-4 py-3 text-[11px] leading-5 text-ink-secondary">
                <strong className="text-ink">이 내용은 어디에 쓰이나요?</strong>
                <p>
                  지원자가 읽는 채용 공고와 포지션 안내에 사용됩니다. 면접
                  질문이나 점수에는 직접 반영되지 않으며, 질문 생성과 평가는
                  다음 단계에서 작성하는 필수·우대 자격요건을 기준으로
                  진행합니다.
                </p>
              </aside>
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
              {invitationTemplateApi ? (
                <section className={INVITATION_TEMPLATE_SECTION}>
                  <header className="grid gap-1 border-b border-border-muted bg-surface-muted px-4 py-3">
                    <strong className="text-[12px] text-ink">
                      초대 메일 템플릿
                    </strong>
                    <p className="text-[10px] leading-5 text-muted">
                      포지션 게시 후 지원자를 초대할 때 사용하는 전사 공통
                      메일을 여기서 미리 설정합니다.
                    </p>
                  </header>
                  <InvitationEmailEditor
                    api={invitationTemplateApi}
                    scope={{ kind: "company" }}
                  />
                </section>
              ) : null}
            </FormSection>
          ) : null}
        </>
      ) : null}

      {stage === "application" ? (
        <ApplicantMaterials draft={draft} update={update} />
      ) : null}

      <FormActions
        submitting={submitting}
        disabled={!readyByStage[stage]}
        label="다음"
        onBack={canGoBack ? handleBack : undefined}
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
    const nextValue = positionDescriptionExample.slice(
      0,
      POSITION_DESCRIPTION_MAX_LENGTH,
    );
    const nextCursor = nextValue.length;

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
        maxLength={POSITION_DESCRIPTION_MAX_LENGTH}
        value={value}
        placeholder={
          "회사와 팀, 주요 업무, 협업 방식, 찾는 동료를 3~4줄로 간략하게 설명해 주세요."
        }
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
      <footer className="flex min-h-10 items-center justify-between border-t border-border-muted bg-surface-muted px-[14px] text-[9px] text-subtle">
        <output className="font-mono" aria-live="polite">
          {value.length} / {POSITION_DESCRIPTION_MAX_LENGTH}
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

/*
 * `CriteriaStep` is the one step the criteria-edit modal renders too, and the modal has no
 * `.hiring-panel` ancestor — so the form controls and the action bar keep their unscoped boxes
 * there. A descendant selector picked that up implicitly; as utilities the caller declares it.
 */
export function CriteriaStep(
  props: StepProps & {
    stage?: CriteriaHiringStep;
    variant?: Extract<FormVariant, "wizard" | "modal">;
  },
) {
  const {
    draft,
    stage,
    submitting,
    submitLabel,
    variant = "wizard",
    update,
    onSubmit,
    onBack,
  } = props;
  const requirementsReady =
    draft.jobRequirements.length > 0 &&
    draft.jobRequirements.every(
      (requirement) =>
        requirement.statement.trim() && requirement.criterionCode,
    );
  const criteriaReady =
    draft.criteria.length > 0 &&
    draft.criteria.every((criterion) => criterion.weight >= 0) &&
    draft.criteria.reduce((total, criterion) => total + criterion.weight, 0) ===
      100;
  const ready = !stage
    ? requirementsReady && criteriaReady
    : stage === "evaluation"
      ? requirementsReady && criteriaReady
      : draft.headcount > 0 &&
        draft.interviewCapacity > 0 &&
        draft.interviewCapacity <= MAX_GUARANTEED_INTERVIEW_CONCURRENCY &&
        Boolean(draft.interviewAt) &&
        !Number.isNaN(Date.parse(draft.interviewAt));

  return (
    <form className="grid" onSubmit={onSubmit}>
      {!stage || stage === "evaluation" ? (
        <EvaluationDesigner draft={draft} update={update} variant={variant} />
      ) : null}
      {!stage || stage === "interview" ? (
        <InterviewDesigner draft={draft} update={update} />
      ) : null}
      <FormActions
        submitting={submitting}
        disabled={!ready}
        label={submitLabel ?? (stage === "interview" ? "포지션 게시" : "다음")}
        variant={variant}
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
          필수·우대 자격요건 설정
        </span>
        <span>
          <Check size={13} aria-hidden="true" />
          자격요건 충족도 별도 판정
        </span>
        <span>
          <Check size={13} aria-hidden="true" />
          질문·검증 가이드 자동 적용
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
