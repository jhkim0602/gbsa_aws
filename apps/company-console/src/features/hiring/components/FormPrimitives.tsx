import { ArrowRight } from "lucide-react";
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
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="form-section">
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
}: {
  submitting: boolean;
  label: string;
  disabled?: boolean;
}) {
  return (
    <footer className="form-actions">
      <span>입력한 값은 게시 전 서버에서 다시 검증됩니다.</span>
      <button
        className="button-primary"
        type="submit"
        disabled={submitting || disabled}
      >
        {submitting ? "처리 중" : label}
        {submitting ? null : <ArrowRight size={14} aria-hidden="true" />}
      </button>
    </footer>
  );
}
