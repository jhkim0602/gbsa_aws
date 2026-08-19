/**
 * Utility strings for the class-based primitives that several features shared.
 *
 * Each string was resolved against the built bundle rather than source order, because
 * `components.css` is imported first and the feature stylesheets override it. Where a
 * primitive's box changed with its container, the container is a parameter — a descendant
 * selector did that implicitly, and a utility cannot.
 */

/** `.form-alert` — the inline error/success line above a form's actions. */
const FORM_ALERT_BASE =
  "rounded-md border px-[11px] py-[9px] text-[10px]" as const;

/**
 * The base rule sets `margin: 14px 24px 0`, but four of the five containers override it, so
 * spacing is chosen per call site rather than baked in.
 *
 * - `panel` — the base margin (`.hiring-panel`, `.template-editor__form`).
 * - `modalBody` — `.position-modal__body > .form-alert` → `16px 20px 0`.
 * - `modalForm` — `.position-modal-form > .form-alert` → `0 20px 14px`.
 * - `flush` — `.position-settings > .form-alert` → `0`.
 * - `workspace` — `.position-workspace__notice` → `14px 32px 0`, `12px 16px 0` at 720px.
 */
export type FormAlertPlacement =
  "panel" | "modalBody" | "modalForm" | "flush" | "workspace";

const FORM_ALERT_MARGIN: Record<FormAlertPlacement, string> = {
  panel: "mx-6 mt-[14px]",
  modalBody: "mx-5 mt-4",
  modalForm: "mx-5 mb-[14px]",
  flush: "",
  workspace: "mx-8 mt-[14px] mw-720:mx-4 mw-720:mt-3",
};

/** `.form-alert.is-success` replaces the danger border/background/text wholesale. */
const FORM_ALERT_TONE = {
  danger: "border-[#dc262640] bg-danger-soft text-danger",
  success: "border-[#1e9e6333] bg-success-soft text-success",
} as const;

export function formAlertClass(
  placement: FormAlertPlacement = "panel",
  tone: keyof typeof FORM_ALERT_TONE = "danger",
) {
  const margin = FORM_ALERT_MARGIN[placement];
  return `${FORM_ALERT_BASE} ${FORM_ALERT_TONE[tone]}${margin ? ` ${margin}` : ""}`;
}

/** `.button-primary` / `.button-secondary` — company-console only, see TAILWIND_MIGRATION.md. */
const BUTTON_BASE =
  "inline-flex min-h-10 items-center justify-center gap-1.5 rounded-lg px-[18px]" +
  " text-[14px] font-semibold shadow-soft";

export const BUTTON_PRIMARY =
  `${BUTTON_BASE} border border-brand bg-brand text-white` +
  " hover:not-disabled:bg-brand-strong";

export const BUTTON_SECONDARY =
  `${BUTTON_BASE} border border-border bg-white text-ink` +
  " hover:not-disabled:bg-surface-muted";

/**
 * `.button-secondary.is-danger` (company.css) replaces the border colour and text only.
 */
export const BUTTON_SECONDARY_DANGER =
  `${BUTTON_BASE} border bg-white shadow-soft hover:not-disabled:bg-surface-muted` +
  " border-[color-mix(in_srgb,var(--color-danger)_35%,var(--color-border))] text-danger";

/**
 * `.icon-button` — the hiring.css definition is what renders; the components.css one is
 * fully overridden. Its `:hover` still applies, so the hover state is kept.
 */
export const ICON_BUTTON =
  "inline-grid size-8 place-items-center rounded-md border border-border bg-surface" +
  " font-semibold text-muted hover:bg-surface-muted hover:text-ink" +
  " disabled:cursor-not-allowed disabled:opacity-35";

/** `.panel` */
export const PANEL = "rounded-xl border border-border bg-surface shadow-soft";

/** `.page-header` and its `h1`/`p` children. */
export const PAGE_HEADER =
  "flex min-h-[65px] items-center justify-between gap-5 px-8 pt-[30px] pb-[14px]" +
  " mw-680:items-start mw-680:p-4";
export const PAGE_HEADER_TITLE = "text-[28px] font-bold";
export const PAGE_HEADER_TEXT = "mt-0.5 text-[14px] leading-[1.5] text-muted";

/** `.page-content` */
export const PAGE_CONTENT = "px-8 pt-5 pb-12 mw-680:p-4";

/**
 * `.page-eyebrow` (hiring.css). Inside `.page-header` it loses colour, size and margin to
 * `.page-header p` (0,1,1 beats 0,1,0) — use `PAGE_EYEBROW_IN_HEADER` there.
 */
export const PAGE_EYEBROW =
  "mb-0.5 font-mono text-[9px] font-semibold uppercase text-brand";
export const PAGE_EYEBROW_IN_HEADER =
  "mt-0.5 font-mono text-[14px] leading-[1.5] font-semibold uppercase text-muted";

/** `.status-badge` and its tone modifiers, which replace the base background and text. */
export const STATUS_BADGE =
  "inline-flex min-h-5 items-center rounded-full px-2 font-mono text-[10px]" +
  " font-medium whitespace-nowrap";
export const STATUS_BADGE_TONE = {
  neutral: "bg-surface-strong text-muted",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
} as const;

/** `.async-state` / `.empty-state`; their `p` children are `text-[12px]`. */
export const ASYNC_STATE =
  "grid min-h-[260px] place-items-center p-[30px] text-center text-muted";

/** `.section-header` and its `p` child. */
export const SECTION_HEADER =
  "flex min-h-[57px] items-center justify-between gap-[14px] border-b border-border" +
  " px-[15px] py-[11px]";
export const SECTION_HEADER_TEXT = "mt-0.5 text-[9px] text-muted";

/** `.search-field`; its `svg` child is `absolute left-2.5 text-subtle`. */
export const SEARCH_FIELD =
  "relative flex w-[min(280px,100%)] items-center mw-680:w-full";

/** `.button-quiet` */
export const BUTTON_QUIET =
  "inline-flex min-h-7 rounded-[3px] bg-transparent px-2 text-[9px] font-semibold" +
  " text-brand hover:bg-brand-soft" +
  " mw-680:min-h-8 mw-680:border mw-680:border-border mw-680:bg-surface mw-680:px-2.5";

/** `.invitation-status` — hiring.css redefines the company.css version wholesale. */
export const INVITATION_STATUS =
  "inline-flex min-h-[26px] items-center rounded-md px-[9px] text-[11px] font-semibold";
/** `.is-muted` only replaces the text colour, so it keeps the base background. */
const INVITATION_STATUS_TONE = {
  neutral: "bg-surface-strong text-muted",
  progress: "bg-brand-soft text-brand",
  ready: "bg-brand-soft text-brand",
  completed: "bg-success-soft text-success",
  attention: "bg-warning-soft text-warning",
  muted: "bg-surface-strong text-subtle",
} as const;

/**
 * Both projection tables type `tone` as `string`, so the lookup is widened here rather than
 * at every call site. Neither table holds a tone outside this set.
 */
export function invitationTone(tone: string) {
  return INVITATION_STATUS_TONE[tone as keyof typeof INVITATION_STATUS_TONE];
}

/** `.recipient-avatar` — hiring.css enlarges the components.css box on top of it. */
export const RECIPIENT_AVATAR =
  "grid size-[38px] place-items-center rounded-[7px] border border-border" +
  " bg-surface-muted text-[13px] font-bold text-ink-secondary mw-680:size-9";

/**
 * `.invitation-table` — the roster table in `PositionInvitations` and the list in
 * `ApplicantManagement`. Below 680px it stops being a table and becomes a stack of cards:
 * the head is visually hidden, each row is a bordered box, and each cell prints its own
 * `data-label` through `::before`. Cells that carry their own label in the copy suppress it.
 *
 * The `td`/`th` rules are declared twice (components.css then hiring.css); only the winning
 * half is reproduced. The cell rules are per-position, so they live on the `td`, not here.
 */
export const INVITATION_TABLE_WRAP = "overflow-x-auto mw-680:overflow-visible";
export const INVITATION_TABLE =
  "w-full min-w-[760px] border-collapse mw-680:block mw-680:w-full mw-680:min-w-0";
export const INVITATION_TABLE_HEAD = "mw-680:sr-only";
export const INVITATION_TABLE_BODY = "mw-680:grid mw-680:gap-2.5 mw-680:p-3";
export const INVITATION_TABLE_ROW =
  "not-first:border-t not-first:border-t-border-muted hover:bg-surface-muted" +
  " mw-680:grid mw-680:grid-cols-[minmax(0,1fr)_auto] mw-680:gap-3" +
  " mw-680:rounded-[3px] mw-680:border mw-680:border-border mw-680:bg-surface" +
  " mw-680:p-[14px] mw-680:not-first:border-t-border mw-680:hover:bg-surface";
/** Every `td`: the desktop box, plus the card row and its `data-label` prefix. */
export const INVITATION_TABLE_CELL =
  "h-[62px] px-3.5 py-3 text-[12px] text-muted mw-680:flex mw-680:min-w-0" +
  " mw-680:items-center mw-680:justify-between mw-680:gap-2 mw-680:p-0" +
  " mw-680:before:flex-none mw-680:before:font-mono mw-680:before:text-[8px]" +
  " mw-680:before:text-subtle mw-680:before:content-[attr(data-label)]";
/** `th`, which the hidden head keeps only for screen readers. */
export const INVITATION_TABLE_HEAD_CELL =
  "h-10 border-b border-border px-3.5 py-2.5 text-left font-mono text-[11px]" +
  " font-medium text-muted";
/**
 * `td:first-child` — the avatar-and-identity cell. It stays a grid below 680px, because
 * `td:first-child` (0,2,1) outranks the `td` rule (0,1,1) that turns the others into flex
 * rows, and its 11px gap has to be restated at the breakpoint to outrank `mw-680:gap-2`.
 */
export const INVITATION_TABLE_IDENTITY =
  `${INVITATION_TABLE_CELL} grid min-w-[230px] grid-cols-[38px_minmax(0,1fr)]` +
  " items-center gap-[11px] mw-680:col-[1/-1] mw-680:grid" +
  " mw-680:grid-cols-[36px_minmax(0,1fr)] mw-680:gap-[11px] mw-680:border-b" +
  " mw-680:border-b-border-muted mw-680:pb-3 mw-680:before:hidden";
export const INVITATION_TABLE_IDENTITY_TEXT = "grid min-w-0 gap-0.5";
export const INVITATION_TABLE_NAME = "truncate text-[13px] mw-680:max-w-full";
export const INVITATION_TABLE_EMAIL = "mt-0.5 text-[11px] text-muted";
/**
 * `td:nth-child(N)` — how the card stacks below 680px. Both tables are five columns wide and
 * share the layout, so this is indexed by column rather than duplicated per table. Cells
 * whose copy already reads as its own label suppress the `data-label` prefix.
 */
export const INVITATION_TABLE_CELL_AT = [
  INVITATION_TABLE_IDENTITY,
  `${INVITATION_TABLE_CELL} mw-680:justify-start mw-680:before:hidden`,
  `${INVITATION_TABLE_CELL} mw-680:col-[1/-1] mw-680:flex-col mw-680:items-stretch`,
  `${INVITATION_TABLE_CELL} mw-680:col-[1]`,
  `${INVITATION_TABLE_CELL} mw-680:col-[2] mw-680:justify-end mw-680:before:hidden`,
] as const;
/** `.invitation-applicant-link` */
export const INVITATION_APPLICANT_LINK =
  "hover:text-brand hover:underline hover:underline-offset-[3px]";
