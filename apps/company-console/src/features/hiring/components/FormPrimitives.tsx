import { ArrowLeft, ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

/**
 * These primitives render in two ancestor contexts that styled them differently:
 * `.hiring-panel` (the hiring wizard) and `.position-modal.is-large` (the criteria-edit
 * modal, which renders `CriteriaStep`). Descendant selectors resolved that automatically;
 * as utilities the caller has to declare it, which is what `variant` carries.
 *
 * `"prominent"` is the wizard's `.position-tech-stack` case, which enlarges the label and
 * hint. It cannot combine with the modal — `.position-tech-stack` only exists in
 * `PositionStep`, which the modal never renders.
 */
export type FormVariant = "wizard" | "modal" | "prominent";

// `.form-field input` is fully replaced inside `.hiring-panel`: transparent, bottom border
// only, square, 14px/52px. The base 34px/6px/11px boxed input renders only in the modal.
const INPUT_BASE =
  "w-full text-ink placeholder:text-subtle focus:border-brand" +
  " focus:shadow-[0_0_0_3px_#5966ce1f]";

export const formInputClass = (variant: FormVariant = "wizard") =>
  variant === "modal"
    ? `${INPUT_BASE} min-h-[34px] rounded-md border border-border bg-white px-2.5 py-[7px]` +
      " text-[11px] shadow-[inset_0_1px_#d0d7de33]"
    : `${INPUT_BASE} min-h-[52px] border-x-0 border-t-0 border-b border-border` +
      " bg-transparent px-0 py-[7px] text-[14px]";

// `.form-field textarea` keeps the input's box and adds resize/min-height/leading; the
// wizard zeroes its inline padding too (`.hiring-panel .form-field textarea`).
export const formTextareaClass = (variant: FormVariant = "wizard") =>
  `${formInputClass(variant)} min-h-[88px] resize-y leading-[1.55]` +
  (variant === "modal" ? "" : " px-0");

const LABEL: Record<FormVariant, string> = {
  // `.form-field__control > span strong` — the base, reached only through the modal.
  modal: "text-[10px] font-semibold",
  // `.hiring-panel .form-field__control > span > strong` lifts it to 11px.
  wizard: "text-[11px] font-semibold",
  // `.hiring-panel .position-tech-stack ...` lifts it again to 15px/700.
  prominent: "text-[15px] font-bold",
};

// `.form-field__hint` is 8px/-2px; `.position-tech-stack .form-field__hint` is 10px/+8px.
const HINT: Record<FormVariant, string> = {
  modal: "-mt-0.5 text-[8px]",
  wizard: "-mt-0.5 text-[8px]",
  prominent: "mt-2 text-[10px]",
};

export function Field({
  label,
  hint,
  variant = "wizard",
  children,
}: {
  label: string;
  hint?: string;
  variant?: FormVariant;
  children: ReactNode;
}) {
  return (
    <div className="grid min-w-0 gap-1.5">
      <label className="grid min-w-0 gap-1.5">
        <span className="flex min-w-0 items-baseline gap-2">
          <strong className={`${LABEL[variant]} text-ink-secondary`}>
            {label}
          </strong>
        </span>
        {children}
      </label>
      {hint ? (
        <small className={`${HINT[variant]} leading-[1.45] text-subtle`}>
          {hint}
        </small>
      ) : null}
    </div>
  );
}

// `.hiring-panel .form-section` zeroes the padding and hides the header, but
// `.hiring-panel .position-config-section > header` (0,2,1) is declared after that
// `display:none` at equal specificity, so the header does render. Every call site passes
// `position-config-section`, and the modal never reaches `FormSection` at all, so the
// wizard's padding and header styling are the only ones that can apply — which also makes
// `.position-modal.is-large .form-section` dead.
const SECTION =
  "pt-[38px] pb-11 first:pt-3 [&+&]:border-t [&+&]:border-t-border" +
  " mw-620:pt-[30px] mw-620:pb-9 mw-620:first:pt-1";

export function FormSection({
  eyebrow,
  title,
  description,
  className,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={className ? `${SECTION} ${className}` : SECTION}>
      <header className="mb-[30px] grid grid-cols-[minmax(0,1fr)] items-start gap-[5px] mw-620:mb-6">
        <span className="col-start-1 font-mono text-[9px] font-bold uppercase text-brand">
          {eyebrow}
        </span>
        <h3 className="col-start-1 text-[22px] leading-[1.3] font-bold text-ink mw-620:text-[19px]">
          {title}
        </h3>
        <p className="col-start-1 text-[11px] leading-[1.6] text-muted">
          {description}
        </p>
      </header>
      <div className="grid gap-5">{children}</div>
    </section>
  );
}

// `.hiring-panel .form-actions` strips the bar back to a bare row 48px below the form and
// hides the autosave note; the note keeps `visibility:hidden` down to 620px, where it
// becomes `display:none`. The modal keeps the original bordered 58px bar.
const ACTIONS: Record<"wizard" | "modal", string> = {
  wizard:
    "mt-12 flex items-center justify-between gap-[18px]" +
    " mw-620:flex-row mw-620:items-stretch",
  modal:
    "flex min-h-[58px] items-center justify-between gap-[18px] border-t border-border" +
    " bg-surface-muted px-6 py-3 mw-620:flex-col mw-620:items-stretch mw-620:px-4",
};

export function FormActions({
  submitting,
  label,
  disabled = false,
  variant = "wizard",
  onBack,
}: {
  submitting: boolean;
  label: string;
  disabled?: boolean;
  variant?: "wizard" | "modal";
  onBack?: () => void;
}) {
  return (
    <footer className={ACTIONS[variant]}>
      <span
        className={`text-[9px] text-muted ${
          variant === "wizard" ? "invisible mw-620:hidden" : ""
        }`}
      >
        입력 내용은 채용 draft에 자동 저장됩니다.
      </span>
      <div className="ml-auto flex gap-2 mw-620:w-full mw-620:[&>button]:flex-1">
        {onBack ? (
          <button
            className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-lg border border-border bg-white px-[18px] text-[14px] font-semibold text-ink shadow-soft hover:not-disabled:bg-surface-muted"
            type="button"
            disabled={submitting}
            onClick={onBack}
          >
            <ArrowLeft size={14} aria-hidden="true" />
            이전
          </button>
        ) : null}
        <button
          // `.form-actions .button-primary { width: 100% }` at 620px is not scoped to the
          // modal, so it applies in the wizard too.
          className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-lg border border-brand bg-brand px-[18px] text-[14px] font-semibold text-white shadow-soft hover:not-disabled:bg-brand-strong mw-620:w-full"
          type="submit"
          disabled={submitting || disabled}
        >
          {submitting ? "처리 중" : label}
          {submitting ? null : <ArrowRight size={14} aria-hidden="true" />}
        </button>
      </div>
    </footer>
  );
}
