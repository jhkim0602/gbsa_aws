import { ArrowLeft, ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="form-field">
      <label className="form-field__control">
        <span>
          <strong>{label}</strong>
        </span>
        {children}
      </label>
      {hint ? <small className="form-field__hint">{hint}</small> : null}
    </div>
  );
}

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
    <section
      className={className ? `form-section ${className}` : "form-section"}
    >
      <header>
        <span>{eyebrow}</span>
        <h3>{title}</h3>
        <p>{description}</p>
      </header>
      <div className="form-section__body">{children}</div>
    </section>
  );
}

export function FormActions({
  submitting,
  label,
  disabled = false,
  onBack,
}: {
  submitting: boolean;
  label: string;
  disabled?: boolean;
  onBack?: () => void;
}) {
  return (
    <footer className="form-actions">
      <span>입력 내용은 채용 draft에 자동 저장됩니다.</span>
      <div className="form-actions__buttons">
        {onBack ? (
          <button
            className="button-secondary"
            type="button"
            disabled={submitting}
            onClick={onBack}
          >
            <ArrowLeft size={14} aria-hidden="true" />
            이전
          </button>
        ) : null}
        <button
          className="button-primary"
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
