import { Check, CheckCircle2 } from "lucide-react";
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
import { InlineInvitationEmailEditor } from "../InlineInvitationEmailEditor";
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

// `.hiring-panel .position-config-section > header` outranks `.form-section > header`'s
// `display:none`, so these sections keep their headers — see FormPrimitives.
const POSITION_BASICS_GRID =
  "grid items-end gap-6" +
  " grid-cols-[minmax(260px,1.5fr)_minmax(150px,0.75fr)_minmax(150px,0.75fr)]" +
  " mw-780:grid-cols-[minmax(0,1fr)]";

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
  const [validationMessage, setValidationMessage] = useState("");
  const formRef = useRef<HTMLFormElement>(null);
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
    setValidationMessage("");
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

  function showMissingField() {
    let message = "필수 입력값을 확인해 주세요.";
    let selector = "";

    if (stage === "application") {
      message = "지원자에게 요청할 필수 제출 자료를 하나 이상 선택해 주세요.";
      selector = 'input[type="checkbox"]';
    } else if (positionPage === "basics") {
      if (!draft.title.trim()) {
        message = "포지션명을 입력해 주세요.";
        selector = '[aria-label="포지션명"]';
      } else if (!draft.recruitmentStartAt) {
        message = "모집 시작일을 선택해 주세요.";
        selector = '[aria-label="모집 시작일"]';
      } else if (!draft.recruitmentEndAt) {
        message = "모집 종료일을 선택해 주세요.";
        selector = '[aria-label="모집 종료일"]';
      } else if (!periodValid) {
        message = "모집 종료일은 시작일 이후로 선택해 주세요.";
        selector = '[aria-label="모집 종료일"]';
      }
    } else if (!draft.description.trim()) {
      message = "메일 안의 포지션 상세를 입력해 주세요.";
      selector = '[aria-label="포지션 설명"]';
    } else if (!draft.descriptionCompleted) {
      message = "수정한 포지션 상세와 초대 메일을 먼저 저장해 주세요.";
      selector = '[data-validation-target="description-save"]';
    }

    setValidationMessage(message);
    const target = formRef.current?.querySelector<HTMLElement>(selector);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.focus({ preventScroll: true });
    target.setAttribute("aria-invalid", "true");
    target.style.outline = "2px solid #d64545";
    target.style.outlineOffset = "3px";
    window.setTimeout(() => {
      target.removeAttribute("aria-invalid");
      target.style.removeProperty("outline");
      target.style.removeProperty("outline-offset");
    }, 2400);
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
    <form ref={formRef} className="grid" onSubmit={handleSubmit}>
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
                    aria-label="포지션명"
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
                    aria-label="모집 시작일"
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
                    aria-label="모집 종료일"
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
              title="포지션 상세와 초대 메일"
              description="실제 메일 화면에서 내용을 클릭해 바로 수정합니다."
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
              <InlineInvitationEmailEditor
                api={invitationTemplateApi}
                descriptionCompleted={draft.descriptionCompleted}
                initialTemplate={draft.invitationEmailTemplate}
                positionDescription={draft.description}
                positionTitle={draft.title}
                onPositionDescriptionChange={(value) => {
                  update("description", value);
                  if (draft.descriptionCompleted) {
                    update("descriptionCompleted", false);
                  }
                }}
                onDescriptionCompleted={(completed) =>
                  update("descriptionCompleted", completed)
                }
                onTemplateSaved={(template) =>
                  update("invitationEmailTemplate", template)
                }
              />
            </FormSection>
          ) : null}
        </>
      ) : null}

      {stage === "application" ? (
        <ApplicantMaterials draft={draft} update={update} />
      ) : null}

      {validationMessage ? (
        <p
          className={`${formAlertClass()} fixed right-5 bottom-5 z-[80] max-w-[380px] shadow-lg mw-620:right-3 mw-620:bottom-3 mw-620:left-3`}
          role="alert"
        >
          {validationMessage}
        </p>
      ) : null}
      <FormActions
        submitting={submitting}
        disabled={!readyByStage[stage]}
        label="다음"
        onDisabledClick={showMissingField}
        onBack={canGoBack ? handleBack : undefined}
      />
    </form>
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
