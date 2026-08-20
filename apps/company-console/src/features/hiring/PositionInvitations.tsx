import {
  ArrowLeft,
  CheckCircle2,
  CircleAlert,
  FileUp,
  PanelRightClose,
  PanelRightOpen,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Send,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  ASYNC_STATE,
  BUTTON_PRIMARY,
  BUTTON_QUIET,
  formAlertClass,
  ICON_BUTTON,
  INVITATION_APPLICANT_LINK,
  INVITATION_STATUS,
  INVITATION_TABLE,
  INVITATION_TABLE_BODY,
  INVITATION_TABLE_CELL_AT,
  INVITATION_TABLE_EMAIL,
  INVITATION_TABLE_HEAD,
  INVITATION_TABLE_HEAD_CELL,
  INVITATION_TABLE_IDENTITY_TEXT,
  INVITATION_TABLE_NAME,
  INVITATION_TABLE_ROW,
  INVITATION_TABLE_WRAP,
  invitationTone,
  PAGE_EYEBROW_IN_HEADER,
  PAGE_HEADER,
  PAGE_HEADER_TEXT,
  PAGE_HEADER_TITLE,
  RECIPIENT_AVATAR,
  SEARCH_FIELD,
} from "../../app/styles/primitives";
import { InvitationEmailEditor } from "./InvitationEmailEditor";
import type {
  InvitationEmailTemplateApi,
  InvitationEmailTemplateState,
} from "./invitationEmailTemplate";

export type InvitationStatus =
  | "invited"
  | "identity_verified"
  | "consented"
  | "materials_submitted"
  | "analyzing"
  | "ready"
  | "interviewing"
  | "interrupted"
  | "completed"
  | "reviewed"
  | "expired"
  | "revoked"
  | "deleted";

export type PositionInvitation = Readonly<{
  invitationId: string;
  positionId: string;
  competencyModelVersionId: string;
  applicantEmail: string;
  applicantDisplayName?: string | null;
  status: InvitationStatus;
  expiresAt: string;
  rowVersion: number;
  analysisStatus?: string | null;
  interviewStatus?: string | null;
  reportStatus?: string | null;
  interviewSessionId?: string | null;
}>;

export type InvitationApplicant = Readonly<{
  displayName: string;
  email: string;
}>;

type InvitationDraftRow = Readonly<{
  id: string;
  displayName: string;
  email: string;
}>;

type InvitationDraftState = "empty" | "valid" | "invalid" | "duplicate";

type ValidatedInvitationDraft = InvitationDraftRow &
  Readonly<{
    state: InvitationDraftState;
    message: string;
    applicant: InvitationApplicant | null;
  }>;

export type PositionInvitationApi = Readonly<{
  listInvitations(positionId: string): Promise<readonly PositionInvitation[]>;
  createInvitations(
    positionId: string,
    applicants: readonly InvitationApplicant[],
    expiresInDays: number,
  ): Promise<{
    acceptedCount: number;
    rejectedCount: number;
    invitations: readonly PositionInvitation[];
  }>;
}>;

type InvitationFilter =
  "all" | "waiting" | "progress" | "completed" | "attention";

export const invitationStatusMeta: Record<
  InvitationStatus,
  { label: string; stage: number; tone: string }
> = {
  invited: { label: "초대 발송", stage: 1, tone: "neutral" },
  identity_verified: { label: "본인 확인", stage: 2, tone: "progress" },
  consented: { label: "동의 완료", stage: 3, tone: "progress" },
  materials_submitted: { label: "자료 제출", stage: 4, tone: "progress" },
  analyzing: { label: "자료 분석", stage: 5, tone: "progress" },
  ready: { label: "면접 준비", stage: 6, tone: "ready" },
  interviewing: { label: "면접 진행", stage: 7, tone: "progress" },
  interrupted: { label: "재접속 필요", stage: 7, tone: "attention" },
  completed: { label: "면접 완료", stage: 8, tone: "completed" },
  reviewed: { label: "검토 완료", stage: 9, tone: "completed" },
  expired: { label: "만료", stage: 0, tone: "attention" },
  revoked: { label: "취소", stage: 0, tone: "attention" },
  deleted: { label: "삭제", stage: 0, tone: "muted" },
};

export const recruiterPhaseCount = 4;

export function invitationRecruiterPhase(status: InvitationStatus) {
  const internalStage = invitationStatusMeta[status].stage;
  if (internalStage <= 0) return 0;
  if (internalStage <= 3) return 1;
  if (internalStage <= 5) return 2;
  if (internalStage <= 7) return 3;
  return 4;
}

const waitingStatuses = new Set<InvitationStatus>([
  "invited",
  "identity_verified",
  "consented",
]);
const progressStatuses = new Set<InvitationStatus>([
  "materials_submitted",
  "analyzing",
  "ready",
  "interviewing",
  "interrupted",
]);
const completedStatuses = new Set<InvitationStatus>(["completed", "reviewed"]);
const attentionStatuses = new Set<InvitationStatus>(["expired", "revoked"]);
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
let draftRowSequence = 0;

/**
 * `.position-invitations__content` — its padding replaces `.page-content`'s outright, and
 * below 720px the narrower inset wins at every width the 680px `.page-content` rule covers.
 * The declared `gap` never applied: the container is a block, so it is not carried over.
 */
const CONTENT = "p-[18px_32px_0] mw-720:p-[14px_16px_0]";
/** `.position-invitations__layout` — the roster and the composer lay themselves out. */
const LAYOUT = "contents";
const WORKSPACE = "grid items-start gap-4";
const WORKSPACE_COLUMNS =
  "grid-cols-[minmax(0,1fr)_minmax(340px,410px)]" +
  " mw-1080:grid-cols-[minmax(0,1fr)_minmax(320px,360px)]" +
  " mw-900:grid-cols-[minmax(0,1fr)]";
const WORKSPACE_COLUMNS_COLLAPSED =
  "grid-cols-[minmax(0,1fr)_44px] mw-900:grid-cols-[minmax(0,1fr)]";
const ASIDE = "sticky top-[78px] min-w-0 mw-900:static";
const EXPAND =
  "grid min-h-[148px] place-items-center gap-[9px] rounded-[7px] border" +
  " border-border bg-surface p-[12px_8px] text-brand mw-900:min-h-[42px]" +
  " mw-900:grid-flow-col mw-900:justify-center";
const EXPAND_LABEL =
  "[writing-mode:vertical-rl] text-[11px] font-bold" +
  " mw-900:[writing-mode:horizontal-tb]";
/** `.invitation-roster` / `.invitation-composer` — a `.panel` flattened to a plain box. */
const CARD = "overflow-hidden rounded-lg border border-border bg-surface";
const CARD_HEADER =
  "flex min-h-18 items-center justify-between gap-[14px] border-b border-border" +
  " p-[14px_18px] mw-680:flex-col mw-680:items-stretch";
/** The aside narrows the composer, so its header stacks at every width. */
const CARD_HEADER_ASIDE =
  "flex min-h-18 flex-col items-start justify-between gap-[14px] border-b" +
  " border-border p-4";
const CARD_TITLE = "text-[15px]";
const CARD_TEXT = "mt-1 text-[11px] leading-[1.45] text-muted";
const ROSTER_ACTIONS = "flex flex-wrap items-center gap-[7px]";
const ROSTER_SEARCH_ICON = "absolute left-2.5 text-subtle";
const ROSTER_SEARCH_INPUT =
  "h-[38px] w-full rounded-[7px] border border-border bg-surface pr-2.5 pl-8" +
  " text-[12px]";
/** `.button-quiet` enlarged by `.invitation-roster__actions`, which outranks its 680px box. */
const ROSTER_REFRESH =
  "inline-flex min-h-9 rounded-[3px] bg-transparent px-2 text-[12px] font-semibold" +
  " text-brand hover:bg-brand-soft mw-680:border mw-680:border-border" +
  " mw-680:bg-surface mw-680:px-2.5";
const FILTER_TABS =
  "flex min-h-[46px] overflow-x-auto border-b border-border px-[18px]" +
  " mw-680:max-w-full";
const FILTER_TAB =
  "inline-flex flex-none items-center gap-1.5 border-b-2 border-b-transparent" +
  " bg-transparent px-[13px] text-[12px] text-muted" +
  " aria-pressed:border-b-brand aria-pressed:font-[650] aria-pressed:text-brand";
const FILTER_TAB_COUNT =
  "min-w-[19px] rounded-full bg-surface-strong px-[5px] py-px font-mono text-[9px]";
const EMPTY_COPY = "grid justify-items-center gap-[11px]";
const EMPTY_TEXT = "text-[12px]";
/** `.invitation-import-actions`; the aside grid outranks the two-column 680px one. */
const IMPORT_ACTIONS =
  "flex flex-wrap items-center gap-[7px] mw-680:grid mw-680:grid-cols-2";
const IMPORT_ACTIONS_ASIDE =
  "grid w-full grid-cols-[32px_minmax(0,1fr)_auto] items-center gap-[7px]";
/** `.button-secondary` shrunk by `.invitation-import-actions`, which outranks its base box. */
const IMPORT_BUTTON =
  "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg border" +
  " border-border bg-white px-[18px] text-[12px] font-semibold text-ink shadow-soft" +
  " hover:not-disabled:bg-surface-muted";
const IMPORT_LIMIT = "font-mono text-[8px] whitespace-nowrap text-subtle";
/** Alignment is per column, and `text-center` emits before `text-left`, so it stays out. */
const ENTRY_HEAD_CELL =
  "h-10 border-b border-b-border-muted bg-surface-muted p-[10px_14px]" +
  " font-mono text-[11px] font-semibold text-muted";
/** `th:nth-child(N)` — the draft table sizes its columns from the head row. */
const ENTRY_HEAD_CELL_AT = [
  `${ENTRY_HEAD_CELL} w-[54px] text-center text-subtle`,
  `${ENTRY_HEAD_CELL} w-[24%] text-left`,
  `${ENTRY_HEAD_CELL} w-[34%] text-left`,
  `${ENTRY_HEAD_CELL} w-[230px] text-left`,
  `${ENTRY_HEAD_CELL} w-12 text-center`,
] as const;
const ENTRY_INPUT =
  "h-[38px] w-full rounded-md border border-border bg-surface px-[9px] text-[12px]" +
  " text-ink focus:border-brand focus:outline-2 focus:outline-offset-0" +
  " focus:outline-[#5966ce1a]";
/**
 * The draft table is a real table on a page and a stack of cards in the workspace aside or
 * below 680px. `.invitation-workspace__aside` outranks the breakpoint, so the two layouts
 * are chosen here instead of layered — a utility cannot express that precedence.
 */
const ENTRY = {
  table: {
    wrap: "overflow-x-auto mw-680:overflow-visible",
    table:
      "w-full min-w-[760px] table-fixed border-collapse mw-680:block" +
      " mw-680:w-full mw-680:min-w-0",
    head: "mw-680:sr-only",
    body: "mw-680:grid",
    row:
      "mw-680:grid mw-680:grid-cols-[34px_minmax(0,1fr)_32px] mw-680:gap-[7px]" +
      " mw-680:border-b mw-680:border-b-border mw-680:p-2.5" +
      " mw-680:hover:bg-inherit",
    /** A tinted row ties with `tr:hover` and is declared later, so it keeps its tint. */
    tone: {
      empty: "hover:bg-[#fbfcfd]",
      valid: "hover:bg-[#fbfcfd]",
      invalid: "bg-[#dc262605]",
      duplicate: "bg-[#d9770608]",
    },
    cells: [
      "w-[54px] border-b border-b-border-muted p-[10px_12px] text-center font-mono" +
        " text-subtle mw-680:block mw-680:w-auto mw-680:[grid-area:1/1/3]" +
        " mw-680:border-0 mw-680:p-0 mw-680:pt-[9px] mw-680:text-center",
      "border-b border-b-border-muted p-[10px_12px] text-left mw-680:block" +
        " mw-680:border-0 mw-680:p-0 mw-680:col-[2]",
      "border-b border-b-border-muted p-[10px_12px] text-left mw-680:block" +
        " mw-680:border-0 mw-680:p-0 mw-680:col-[2]",
      "border-b border-b-border-muted p-[10px_12px] text-left mw-680:block" +
        " mw-680:border-0 mw-680:p-0 mw-680:pt-0.5 mw-680:col-[2]",
      "w-12 border-b border-b-border-muted p-[10px_12px] text-center mw-680:block" +
        " mw-680:w-auto mw-680:[grid-area:1/3/3] mw-680:border-0 mw-680:p-0" +
        " mw-680:pt-0.5 mw-680:text-left",
    ],
  },
  card: {
    wrap: "overflow-visible",
    table: "block w-full min-w-0 table-fixed border-collapse",
    head: "sr-only",
    body: "grid",
    row:
      "grid grid-cols-[30px_minmax(0,1fr)_30px] gap-[7px] border-b" +
      " border-b-border-muted p-3 hover:bg-inherit",
    tone: {
      empty: "",
      valid: "",
      invalid: "bg-[#dc262605]",
      duplicate: "bg-[#d9770608]",
    },
    cells: [
      "block border-0 p-0 pt-[9px] [grid-area:1/1/3] text-center font-mono text-subtle",
      "block border-0 p-0 col-[2] text-left",
      "block border-0 p-0 col-[2] text-left",
      "block border-0 p-0 pt-0.5 col-[2] text-left",
      "block border-0 p-0 [grid-area:1/3/3] text-left",
    ],
  },
} as const;
/** `.invitation-row-remove`'s own 28px box loses to the later `.icon-button`; its hover wins. */
const ENTRY_REMOVE =
  "inline-grid size-8 place-items-center rounded-md border border-border" +
  " bg-surface font-semibold text-muted hover:border-danger hover:bg-danger-soft" +
  " hover:text-danger disabled:cursor-not-allowed disabled:opacity-35";
const DRAFT_VALIDATION =
  "inline-flex items-center gap-1.5 text-[11px] leading-[1.35]";
/** Each state replaces the base colour, so the tones are complete variants. */
const DRAFT_VALIDATION_TONE = {
  empty: `${DRAFT_VALIDATION} text-subtle`,
  valid: `${DRAFT_VALIDATION} text-success`,
  invalid: `${DRAFT_VALIDATION} text-danger`,
  duplicate: `${DRAFT_VALIDATION} text-warning`,
} as const;
const MAILCARD =
  "rounded-[7px] border border-border bg-surface m-[0_14px_12px]";
const MAILCARD_TOP =
  "flex items-center gap-2.5 border-b border-b-border-muted p-[10px_12px]";
const MAILCARD_LOGO =
  "grid min-h-[30px] w-[46px] place-items-center rounded-[5px] border" +
  " border-dashed border-border bg-surface-muted";
const MAILCARD_LOGO_EMPTY = "text-center text-[8px] not-italic text-subtle";
const MAILCARD_LABEL = "block text-[8px] text-muted";
const MAILCARD_SUBJECT = "block truncate text-[10.5px] text-ink";
const MAILCARD_FOOT =
  "flex items-center gap-[7px] bg-surface-muted p-[7px_12px]";
const MAILCARD_FOOT_TEXT = "text-[9px] text-muted";
const MAILCARD_DOT = "size-[9px] rounded-full";
const MAILCARD_EDIT = `${BUTTON_QUIET} ml-auto`;
const FOOTER =
  "grid grid-cols-[minmax(0,1fr)_auto] items-end gap-4 bg-surface-muted" +
  " p-[14px_18px_16px] mw-680:flex mw-680:flex-col mw-680:items-stretch";
/** The aside keeps the grid at every width; only the 680px `align-items` still reaches it. */
const FOOTER_ASIDE =
  "grid grid-cols-[minmax(0,1fr)_auto] items-end gap-[13px] bg-surface-muted" +
  " p-[14px_16px_16px] mw-680:items-stretch";
const VALIDATION = "flex flex-wrap gap-[7px]";
const VALIDATION_ASIDE = "flex flex-wrap gap-1.5";
const VALIDATION_CHIP =
  "rounded-[3px] border border-transparent p-[4px_7px] text-[11px]";
/** Each tone replaces the background outright, so the base carries no colour of its own. */
const VALIDATION_CHIP_TONE = {
  neutral: `${VALIDATION_CHIP} bg-surface text-muted`,
  valid: `${VALIDATION_CHIP} bg-success-soft text-success`,
  warning: `${VALIDATION_CHIP} bg-warning-soft text-warning`,
} as const;
const ACTIONS =
  "flex items-center justify-end gap-3 mw-680:flex-col mw-680:items-stretch";
const ACTIONS_ASIDE = "flex flex-col items-stretch justify-end gap-3";
const DRAWER_SCRIM = "fixed inset-0 z-40 border-0 bg-[#0f172a52]";
const DRAWER =
  "fixed inset-y-0 right-0 z-41 grid w-[min(1080px,96vw)]" +
  " grid-rows-[auto_minmax(0,1fr)] bg-surface shadow-float";
const DRAWER_HEAD =
  "flex items-start gap-3 border-b border-b-border-muted p-[14px_16px]";
const DRAWER_TITLE = "text-[12px]";
const DRAWER_TEXT = "mt-[3px] text-[9px] text-muted";
const DRAWER_CLOSE = `${ICON_BUTTON} ml-auto`;
const PROGRESS =
  "flex min-w-[120px] items-center gap-2 mw-680:w-full mw-680:min-w-0";
const PROGRESS_TRACK =
  "h-[5px] w-[86px] overflow-hidden rounded-full bg-surface-strong" +
  " mw-680:w-auto mw-680:flex-auto";
const PROGRESS_FILL = "block h-full rounded-[inherit] bg-brand";
const PROGRESS_TEXT = "font-mono text-[9px]";
const ROW_COMPLETE = "text-[9px] text-subtle";

export function PositionInvitations({
  positionId,
  positionName,
  interviewAt,
  api,
  templateApi,
  embedded = false,
  view = "all",
}: {
  positionId: string;
  positionName?: string;
  interviewAt?: string | null;
  api: PositionInvitationApi;
  /** Omitted where the invitation email is not editable, e.g. read-only rosters. */
  templateApi?: InvitationEmailTemplateApi;
  embedded?: boolean;
  view?: "all" | "roster" | "invite" | "workspace";
}) {
  const [invitations, setInvitations] = useState<readonly PositionInvitation[]>(
    [],
  );
  const [draftRows, setDraftRows] = useState<readonly InvitationDraftRow[]>([
    createDraftRow(),
  ]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<InvitationFilter>("all");
  const [loading, setLoading] = useState(true);
  const [issuing, setIssuing] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [invitePanelOpen, setInvitePanelOpen] = useState(true);
  const [templateOpen, setTemplateOpen] = useState(false);
  const [emailTemplate, setEmailTemplate] =
    useState<InvitationEmailTemplateState | null>(null);
  const workspace = view === "workspace";
  const validatedDrafts = useMemo(
    () =>
      validateInvitationDrafts(
        draftRows,
        new Set(
          invitations.map((invitation) =>
            invitation.applicantEmail.toLocaleLowerCase("en-US"),
          ),
        ),
      ),
    [draftRows, invitations],
  );
  const validationSummary = useMemo(
    () => ({
      valid: validatedDrafts.filter((row) => row.state === "valid").length,
      invalid: validatedDrafts.filter((row) => row.state === "invalid").length,
      duplicate: validatedDrafts.filter((row) => row.state === "duplicate")
        .length,
      hasInput: validatedDrafts.some((row) => row.state !== "empty"),
    }),
    [validatedDrafts],
  );

  async function loadInvitations() {
    setError("");
    try {
      setInvitations(await api.listInvitations(positionId));
    } catch {
      setError(
        "지원자 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    api
      .listInvitations(positionId)
      .then((items) => {
        if (active) setInvitations(items);
      })
      .catch(() => {
        if (active) {
          setError(
            "지원자 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, positionId]);

  useEffect(() => {
    if (!templateApi) return;
    let active = true;
    templateApi
      .getPositionTemplate(positionId)
      .then((state) => {
        if (active) setEmailTemplate(state);
      })
      .catch(() => {
        // The mail card is informational; a failure must not block sending invitations.
      });
    return () => {
      active = false;
    };
  }, [positionId, templateApi]);

  const metrics = useMemo(
    () => ({
      total: invitations.length,
      waiting: invitations.filter((item) => waitingStatuses.has(item.status))
        .length,
      progress: invitations.filter((item) => progressStatuses.has(item.status))
        .length,
      completed: invitations.filter((item) =>
        completedStatuses.has(item.status),
      ).length,
      attention: invitations.filter((item) =>
        attentionStatuses.has(item.status),
      ).length,
    }),
    [invitations],
  );

  const filteredInvitations = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("ko-KR");
    return invitations.filter((invitation) => {
      const matchesQuery =
        !normalizedQuery ||
        invitation.applicantEmail
          .toLocaleLowerCase("ko-KR")
          .includes(normalizedQuery) ||
        (invitation.applicantDisplayName ?? "")
          .toLocaleLowerCase("ko-KR")
          .includes(normalizedQuery);
      if (!matchesQuery) return false;
      if (filter === "waiting") return waitingStatuses.has(invitation.status);
      if (filter === "progress") return progressStatuses.has(invitation.status);
      if (filter === "completed") {
        return completedStatuses.has(invitation.status);
      }
      if (filter === "attention") {
        return attentionStatuses.has(invitation.status);
      }
      return true;
    });
  }, [filter, invitations, query]);

  async function createInvitations(applicants: readonly InvitationApplicant[]) {
    setIssuing(true);
    setError("");
    setNotice("");
    try {
      const result = await api.createInvitations(
        positionId,
        applicants,
        resolveInvitationValidityDays(interviewAt),
      );
      setNotice(`${result.acceptedCount}명의 초대를 발송했습니다.`);
      setDraftRows([createDraftRow()]);
      await loadInvitations();
    } catch {
      setError(
        "초대 발송을 완료하지 못했습니다. 이메일 형식과 채용 관리 상태를 확인해 주세요.",
      );
    } finally {
      setIssuing(false);
    }
  }

  function updateDraftRow(
    id: string,
    field: "displayName" | "email",
    value: string,
  ) {
    setDraftRows((current) =>
      current.map((row) => (row.id === id ? { ...row, [field]: value } : row)),
    );
  }

  function addDraftRow() {
    setDraftRows((current) =>
      current.length >= 1000 ? current : [...current, createDraftRow()],
    );
  }

  function removeDraftRow(id: string) {
    setDraftRows((current) => {
      const next = current.filter((row) => row.id !== id);
      return next.length ? next : [createDraftRow()];
    });
  }

  async function importApplicants(file: File | undefined) {
    if (!file) return;
    setError("");
    setNotice("");
    try {
      const imported = parseInvitationImport(file.name, await file.text());
      if (!imported.length) {
        throw new Error("empty_import");
      }
      setDraftRows(
        imported
          .slice(0, 1000)
          .map((applicant) =>
            createDraftRow(applicant.displayName, applicant.email),
          ),
      );
      setNotice(
        `${Math.min(imported.length, 1000)}명을 불러왔습니다. 이메일 검증 결과를 확인해 주세요.`,
      );
    } catch {
      setError(
        "파일을 불러오지 못했습니다. CSV의 이름·이메일 열 또는 JSON 배열 형식을 확인해 주세요.",
      );
    }
  }

  const entry = workspace ? ENTRY.card : ENTRY.table;

  if (templateApi && templateOpen && view === "invite") {
    return (
      <section className="bg-surface" aria-label="초대 메일 수정">
        <header className="flex min-h-16 items-center gap-3 border-b border-border-muted px-5 py-3 mw-620:items-start">
          <button
            className={`${BUTTON_QUIET} shrink-0`}
            type="button"
            onClick={() => setTemplateOpen(false)}
          >
            <ArrowLeft size={14} aria-hidden="true" /> 명단으로
          </button>
          <div className="min-w-0 border-l border-border-muted pl-3">
            <h2 className="text-[14px] text-ink">초대 메일 설정</h2>
            <p className="mt-1 truncate text-[9px] text-muted">
              {positionName ?? "이 포지션"} 지원자에게 발송할 메일을 편집합니다.
            </p>
          </div>
        </header>
        <InvitationEmailEditor
          api={templateApi}
          layout="modal"
          scope={{ kind: "position", positionId, positionName }}
          onSaved={setEmailTemplate}
          onClose={() => setTemplateOpen(false)}
        />
      </section>
    );
  }

  return (
    <div>
      {!embedded ? (
        <header className={PAGE_HEADER}>
          <div>
            <p className={PAGE_EYEBROW_IN_HEADER}>Position applicants</p>
            <h1 className={PAGE_HEADER_TITLE}>지원자 관리</h1>
            <p className={PAGE_HEADER_TEXT}>
              {positionName ?? "선택한 포지션"}의 지원자와 면접 상태를
              관리합니다.
            </p>
          </div>
        </header>
      ) : null}

      <div className={view === "invite" ? "p-5 mw-720:p-3" : CONTENT}>
        {notice ? (
          <p className={formAlertClass("panel", "success")} role="status">
            {notice}
          </p>
        ) : null}
        {error ? (
          <p className={formAlertClass("panel")} role="alert">
            {error}
          </p>
        ) : null}

        <div
          className={
            workspace
              ? `${WORKSPACE} ${
                  invitePanelOpen
                    ? WORKSPACE_COLUMNS
                    : WORKSPACE_COLUMNS_COLLAPSED
                }`
              : LAYOUT
          }
        >
          {view !== "invite" ? (
            <section className={`${CARD} min-w-0`}>
              <header className={CARD_HEADER}>
                <div>
                  <h2 className={CARD_TITLE}>지원자 목록</h2>
                  <p className={CARD_TEXT}>
                    지원자별 본인 확인부터 면접 완료까지 현재 상태입니다.
                  </p>
                </div>
                <div className={ROSTER_ACTIONS}>
                  <label className={SEARCH_FIELD}>
                    <Search
                      className={ROSTER_SEARCH_ICON}
                      size={15}
                      aria-hidden="true"
                    />
                    <span className="sr-only">지원자 검색</span>
                    <input
                      className={ROSTER_SEARCH_INPUT}
                      aria-label="지원자 검색"
                      type="search"
                      value={query}
                      placeholder="이름 또는 이메일"
                      onChange={(event) => setQuery(event.target.value)}
                    />
                  </label>
                  <button
                    className={ROSTER_REFRESH}
                    type="button"
                    disabled={loading}
                    onClick={() => void loadInvitations()}
                  >
                    <RefreshCw size={14} aria-hidden="true" />
                    새로고침
                  </button>
                </div>
              </header>
              <div className={FILTER_TABS}>
                {(
                  [
                    ["all", "전체", metrics.total],
                    ["waiting", "응답 대기", metrics.waiting],
                    ["progress", "진행 중", metrics.progress],
                    ["completed", "완료", metrics.completed],
                    ["attention", "확인 필요", metrics.attention],
                  ] as const
                ).map(([value, label, count]) => (
                  <button
                    key={value}
                    type="button"
                    className={FILTER_TAB}
                    aria-pressed={filter === value}
                    onClick={() => setFilter(value)}
                  >
                    {label}
                    <span className={FILTER_TAB_COUNT}>{count}</span>
                  </button>
                ))}
              </div>
              {loading ? (
                <div className={ASYNC_STATE} role="status">
                  지원자 목록을 불러오는 중입니다.
                </div>
              ) : filteredInvitations.length ? (
                <InvitationTable
                  invitations={filteredInvitations}
                  issuing={issuing}
                  onReissue={(applicant) => void createInvitations([applicant])}
                />
              ) : (
                <div className={ASYNC_STATE}>
                  <Users size={24} aria-hidden="true" />
                  <div className={EMPTY_COPY}>
                    <strong>아직 지원자가 없습니다.</strong>
                    <p className={EMPTY_TEXT}>
                      {view === "roster"
                        ? "지원자 초대 도구에서 첫 지원자를 등록하세요."
                        : "초대 관리 패널에서 첫 지원자를 등록하세요."}
                    </p>
                  </div>
                </div>
              )}
            </section>
          ) : null}

          {workspace && !invitePanelOpen ? (
            <button
              className={EXPAND}
              type="button"
              aria-label="초대 패널 펼치기"
              title="초대 패널 펼치기"
              onClick={() => setInvitePanelOpen(true)}
            >
              <PanelRightOpen size={17} aria-hidden="true" />
              <span className={EXPAND_LABEL}>지원자 초대</span>
            </button>
          ) : null}

          {view !== "roster" && (!workspace || invitePanelOpen) ? (
            <aside className={workspace ? ASIDE : undefined}>
              <section className={CARD}>
                <header className={workspace ? CARD_HEADER_ASIDE : CARD_HEADER}>
                  <div>
                    {view === "invite" ? (
                      <p className="mb-1 text-[9px] font-bold tracking-[0.06em] text-brand uppercase">
                        01 · 지원자 명단
                      </p>
                    ) : null}
                    <h2 className={CARD_TITLE}>
                      {workspace ? "지원자 초대 관리" : "초대할 지원자"}
                    </h2>
                    <p className={CARD_TEXT}>
                      직접 입력하거나 CSV·JSON 파일을 불러오면 중복과 이메일
                      형식을 자동으로 확인합니다.
                    </p>
                  </div>
                  <div
                    className={
                      workspace ? IMPORT_ACTIONS_ASIDE : IMPORT_ACTIONS
                    }
                  >
                    {workspace ? (
                      <button
                        className={`${ICON_BUTTON} h-9 w-8`}
                        type="button"
                        title="초대 패널 접기"
                        aria-label="초대 패널 접기"
                        onClick={() => setInvitePanelOpen(false)}
                      >
                        <PanelRightClose size={16} aria-hidden="true" />
                      </button>
                    ) : null}
                    <label
                      className={`${IMPORT_BUTTON} relative cursor-pointer ${
                        workspace ? "w-full min-w-0" : "mw-680:w-full"
                      }`}
                    >
                      <FileUp size={14} aria-hidden="true" />
                      CSV·JSON 불러오기
                      <input
                        className="sr-only"
                        aria-label="CSV 또는 JSON 가져오기"
                        type="file"
                        accept=".csv,.json,text/csv,application/json"
                        onChange={(event) => {
                          const file = event.currentTarget.files?.[0];
                          void importApplicants(file);
                          event.currentTarget.value = "";
                        }}
                      />
                    </label>
                    <button
                      className={`${IMPORT_BUTTON} ${
                        workspace ? "w-full min-w-0" : "mw-680:w-full"
                      }`}
                      type="button"
                      disabled={draftRows.length >= 1000}
                      aria-label="지원자 행 추가"
                      onClick={addDraftRow}
                    >
                      <Plus size={14} aria-hidden="true" />행 추가
                    </button>
                    <span
                      className={`${IMPORT_LIMIT} ${
                        workspace ? "col-[1/-1]" : "mw-680:col-[1/-1]"
                      }`}
                    >
                      최대 1,000명 · CSV: 이름, 이메일 열 · JSON: applicants
                      배열
                    </span>
                  </div>
                </header>
                <div className={entry.wrap}>
                  <table className={entry.table}>
                    <thead className={entry.head}>
                      <tr>
                        <th className={ENTRY_HEAD_CELL_AT[0]} scope="col">
                          No.
                        </th>
                        <th className={ENTRY_HEAD_CELL_AT[1]} scope="col">
                          이름
                        </th>
                        <th className={ENTRY_HEAD_CELL_AT[2]} scope="col">
                          이메일
                        </th>
                        <th className={ENTRY_HEAD_CELL_AT[3]} scope="col">
                          검증 결과
                        </th>
                        <th className={ENTRY_HEAD_CELL_AT[4]} scope="col">
                          <span className="sr-only">행 삭제</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody className={entry.body}>
                      {validatedDrafts.map((row, index) => (
                        <tr
                          key={row.id}
                          className={`${entry.row} ${entry.tone[row.state]}`}
                        >
                          <td className={entry.cells[0]}>{index + 1}</td>
                          <td className={entry.cells[1]}>
                            <input
                              className={ENTRY_INPUT}
                              aria-label={`지원자 ${index + 1} 이름`}
                              value={row.displayName}
                              placeholder="홍길동"
                              maxLength={200}
                              onChange={(event) =>
                                updateDraftRow(
                                  row.id,
                                  "displayName",
                                  event.target.value,
                                )
                              }
                            />
                          </td>
                          <td className={entry.cells[2]}>
                            <input
                              className={ENTRY_INPUT}
                              aria-label={`지원자 ${index + 1} 이메일`}
                              value={row.email}
                              placeholder="hong@example.com"
                              inputMode="email"
                              maxLength={320}
                              onChange={(event) =>
                                updateDraftRow(
                                  row.id,
                                  "email",
                                  event.target.value,
                                )
                              }
                            />
                          </td>
                          <td className={entry.cells[3]}>
                            <DraftValidationStatus row={row} />
                          </td>
                          <td className={entry.cells[4]}>
                            <button
                              className={ENTRY_REMOVE}
                              type="button"
                              title="행 삭제"
                              aria-label={`지원자 ${index + 1} 행 삭제`}
                              onClick={() => removeDraftRow(row.id)}
                            >
                              <Trash2 size={14} aria-hidden="true" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {templateApi ? (
                  <div className={MAILCARD}>
                    <div className={MAILCARD_TOP}>
                      <span className={MAILCARD_LOGO}>
                        {emailTemplate?.logoUrl ? (
                          <img
                            src={emailTemplate.logoUrl}
                            alt="기업 로고"
                            height={22}
                          />
                        ) : (
                          <em className={MAILCARD_LOGO_EMPTY}>로고 없음</em>
                        )}
                      </span>
                      <div className="min-w-0">
                        <small className={MAILCARD_LABEL}>발송될 메일</small>
                        <strong className={MAILCARD_SUBJECT}>
                          {emailTemplate?.subject ??
                            "초대 메일 내용을 불러오는 중"}
                        </strong>
                      </div>
                    </div>
                    <div className={MAILCARD_FOOT}>
                      {emailTemplate ? (
                        <>
                          <i
                            className={MAILCARD_DOT}
                            style={{ background: emailTemplate.brandColor }}
                            aria-hidden="true"
                          />
                          <small className={MAILCARD_FOOT_TEXT}>
                            {emailTemplate.isPositionOverride
                              ? "이 포지션 전용 문구"
                              : "전사 기본 문구"}
                          </small>
                        </>
                      ) : null}
                      <button
                        className={MAILCARD_EDIT}
                        type="button"
                        onClick={() => setTemplateOpen(true)}
                      >
                        <Pencil size={13} aria-hidden="true" />
                        수정
                      </button>
                    </div>
                  </div>
                ) : null}

                <div className={workspace ? FOOTER_ASIDE : FOOTER}>
                  <div
                    className={workspace ? VALIDATION_ASIDE : VALIDATION}
                    aria-live="polite"
                  >
                    {validationSummary.hasInput ? (
                      <>
                        <span className={VALIDATION_CHIP_TONE.valid}>
                          발송 가능 {validationSummary.valid}명
                        </span>
                        <span
                          className={
                            validationSummary.invalid
                              ? VALIDATION_CHIP_TONE.warning
                              : VALIDATION_CHIP_TONE.neutral
                          }
                        >
                          확인 필요 {validationSummary.invalid}명
                        </span>
                        <span
                          className={
                            validationSummary.duplicate
                              ? VALIDATION_CHIP_TONE.warning
                              : VALIDATION_CHIP_TONE.neutral
                          }
                        >
                          중복 제외 {validationSummary.duplicate}명
                        </span>
                      </>
                    ) : (
                      <span className={VALIDATION_CHIP_TONE.neutral}>
                        이름과 이메일을 입력하면 검증 결과가 표시됩니다.
                      </span>
                    )}
                  </div>
                  <div className={workspace ? ACTIONS_ASIDE : ACTIONS}>
                    <span className="max-w-52 text-[9px] leading-[1.5] text-muted">
                      초대 링크는 포지션의 면접 예정 시각을 기준으로 자동
                      관리됩니다.
                    </span>
                    <button
                      className={`${BUTTON_PRIMARY} ${
                        workspace ? "w-full" : "mw-680:w-full"
                      }`}
                      type="button"
                      disabled={!validationSummary.valid || issuing}
                      onClick={() =>
                        void createInvitations(
                          validatedDrafts.flatMap((row) =>
                            row.applicant ? [row.applicant] : [],
                          ),
                        )
                      }
                    >
                      <Send size={15} aria-hidden="true" />
                      {issuing
                        ? "초대 발송 중"
                        : `${validationSummary.valid}명에게 초대 보내기`}
                    </button>
                  </div>
                </div>
              </section>
            </aside>
          ) : null}
        </div>
      </div>

      {templateApi && templateOpen ? (
        <>
          <button
            className={DRAWER_SCRIM}
            type="button"
            aria-label="초대 메일 수정 닫기"
            onClick={() => setTemplateOpen(false)}
          />
          <div
            className={DRAWER}
            role="dialog"
            aria-modal="true"
            aria-label="초대 메일 수정"
          >
            <header className={DRAWER_HEAD}>
              <div>
                <h2 className={DRAWER_TITLE}>초대 메일 수정</h2>
                <p className={DRAWER_TEXT}>
                  {positionName ?? "이 포지션"}에 보낼 초대 메일입니다.
                </p>
              </div>
              <button
                className={DRAWER_CLOSE}
                type="button"
                aria-label="초대 메일 수정 닫기"
                onClick={() => setTemplateOpen(false)}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </header>
            <InvitationEmailEditor
              api={templateApi}
              layout="drawer"
              scope={{ kind: "position", positionId, positionName }}
              onSaved={setEmailTemplate}
              onClose={() => setTemplateOpen(false)}
            />
          </div>
        </>
      ) : null}
    </div>
  );
}

function InvitationTable({
  invitations,
  issuing,
  onReissue,
}: {
  invitations: readonly PositionInvitation[];
  issuing: boolean;
  onReissue(applicant: InvitationApplicant): void;
}) {
  return (
    <div className={INVITATION_TABLE_WRAP}>
      <table className={INVITATION_TABLE}>
        <thead className={INVITATION_TABLE_HEAD}>
          <tr>
            <th className={INVITATION_TABLE_HEAD_CELL}>지원자</th>
            <th className={INVITATION_TABLE_HEAD_CELL}>현재 상태</th>
            <th className={INVITATION_TABLE_HEAD_CELL}>진행 단계</th>
            <th className={INVITATION_TABLE_HEAD_CELL}>링크 만료</th>
            <th className={INVITATION_TABLE_HEAD_CELL}>
              <span className="sr-only">작업</span>
            </th>
          </tr>
        </thead>
        <tbody className={INVITATION_TABLE_BODY}>
          {invitations.map((invitation) => {
            const status = invitationStatusMeta[invitation.status];
            const recruiterPhase = invitationRecruiterPhase(invitation.status);
            const displayName =
              invitation.applicantDisplayName ||
              invitation.applicantEmail.split("@")[0];
            const canReissue = attentionStatuses.has(invitation.status);
            return (
              <tr
                className={INVITATION_TABLE_ROW}
                key={invitation.invitationId}
              >
                <td className={INVITATION_TABLE_CELL_AT[0]} data-label="지원자">
                  <span className={RECIPIENT_AVATAR} aria-hidden="true">
                    {displayName.slice(0, 1).toLocaleUpperCase("ko-KR")}
                  </span>
                  <span className={INVITATION_TABLE_IDENTITY_TEXT}>
                    <Link
                      className={INVITATION_APPLICANT_LINK}
                      aria-label={`${displayName} 상세 보기`}
                      to={`/positions/${invitation.positionId}/applicants/${invitation.invitationId}`}
                    >
                      <strong className={INVITATION_TABLE_NAME}>
                        {displayName}
                      </strong>
                    </Link>
                    <small className={INVITATION_TABLE_EMAIL}>
                      {invitation.applicantEmail}
                    </small>
                  </span>
                </td>
                <td
                  className={INVITATION_TABLE_CELL_AT[1]}
                  data-label="현재 상태"
                >
                  <span
                    className={`${INVITATION_STATUS} ${invitationTone(
                      status.tone,
                    )}`}
                  >
                    {status.label}
                  </span>
                </td>
                <td
                  className={INVITATION_TABLE_CELL_AT[2]}
                  data-label="진행 단계"
                >
                  <div
                    className={PROGRESS}
                    aria-label={
                      recruiterPhase
                        ? `전체 4단계 중 ${recruiterPhase}단계`
                        : "채용 진행 단계 없음"
                    }
                  >
                    <span className={PROGRESS_TRACK}>
                      <i
                        className={PROGRESS_FILL}
                        style={{
                          width: `${(recruiterPhase / recruiterPhaseCount) * 100}%`,
                        }}
                      />
                    </span>
                    <small className={PROGRESS_TEXT}>
                      {recruiterPhase || "-"} / 4
                    </small>
                  </div>
                </td>
                <td
                  className={INVITATION_TABLE_CELL_AT[3]}
                  data-label="링크 만료"
                >
                  <time
                    className={PROGRESS_TEXT}
                    dateTime={invitation.expiresAt}
                  >
                    {formatDate(invitation.expiresAt)}
                  </time>
                </td>
                <td className={INVITATION_TABLE_CELL_AT[4]} data-label="작업">
                  {canReissue ? (
                    <button
                      className={BUTTON_QUIET}
                      type="button"
                      aria-label={`${displayName} 다시 초대`}
                      disabled={issuing}
                      onClick={() =>
                        onReissue({
                          displayName,
                          email: invitation.applicantEmail,
                        })
                      }
                    >
                      다시 초대
                    </button>
                  ) : (
                    <span className={ROW_COMPLETE}>정상</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DraftValidationStatus({ row }: { row: ValidatedInvitationDraft }) {
  if (row.state === "valid") {
    return (
      <span className={DRAFT_VALIDATION_TONE.valid}>
        <CheckCircle2 size={13} aria-hidden="true" />
        발송 가능
      </span>
    );
  }
  if (row.state === "invalid") {
    return (
      <span className={DRAFT_VALIDATION_TONE.invalid}>
        <CircleAlert size={13} aria-hidden="true" />
        {row.message}
      </span>
    );
  }
  if (row.state === "duplicate") {
    return (
      <span className={DRAFT_VALIDATION_TONE.duplicate}>
        <X size={13} aria-hidden="true" />
        {row.message}
      </span>
    );
  }
  return <span className={DRAFT_VALIDATION_TONE.empty}>입력 대기</span>;
}

function createDraftRow(displayName = "", email = ""): InvitationDraftRow {
  draftRowSequence += 1;
  return {
    id: `invitation-draft-${draftRowSequence}`,
    displayName,
    email,
  };
}

function validateInvitationDrafts(
  rows: readonly InvitationDraftRow[],
  existingEmails: ReadonlySet<string>,
): ValidatedInvitationDraft[] {
  const seenEmails = new Set<string>();
  return rows.map((row) => {
    const displayName = row.displayName.trim();
    const email = row.email.trim().toLocaleLowerCase("en-US");
    if (!displayName && !email) {
      return {
        ...row,
        state: "empty",
        message: "",
        applicant: null,
      };
    }
    if (!displayName) {
      return {
        ...row,
        state: "invalid",
        message: "이름을 입력하세요.",
        applicant: null,
      };
    }
    if (!emailPattern.test(email)) {
      return {
        ...row,
        state: "invalid",
        message: "이메일 형식을 확인하세요.",
        applicant: null,
      };
    }
    if (existingEmails.has(email)) {
      return {
        ...row,
        state: "duplicate",
        message: "이미 등록된 지원자",
        applicant: null,
      };
    }
    if (seenEmails.has(email)) {
      return {
        ...row,
        state: "duplicate",
        message: "입력 명단 내 중복",
        applicant: null,
      };
    }
    seenEmails.add(email);
    return {
      ...row,
      state: "valid",
      message: "발송 가능",
      applicant: { displayName, email },
    };
  });
}

export function parseInvitationImport(
  fileName: string,
  content: string,
): InvitationApplicant[] {
  if (fileName.toLocaleLowerCase("en-US").endsWith(".json")) {
    return parseInvitationJson(content);
  }
  return parseInvitationCsv(content);
}

function parseInvitationJson(content: string): InvitationApplicant[] {
  const parsed: unknown = JSON.parse(content);
  const records =
    typeof parsed === "object" &&
    parsed !== null &&
    !Array.isArray(parsed) &&
    "applicants" in parsed
      ? (parsed as { applicants?: unknown }).applicants
      : parsed;
  if (!Array.isArray(records)) {
    throw new Error("invalid_json_shape");
  }
  return records.slice(0, 1000).map((record) => {
    if (typeof record !== "object" || record === null) {
      return { displayName: "", email: "" };
    }
    const values = record as Record<string, unknown>;
    return {
      displayName: firstString(values, [
        "displayName",
        "display_name",
        "name",
        "fullName",
        "이름",
        "성명",
      ]),
      email: firstString(values, [
        "email",
        "e-mail",
        "emailAddress",
        "이메일",
        "메일",
      ]),
    };
  });
}

function parseInvitationCsv(content: string): InvitationApplicant[] {
  const rows = parseCsvRows(content.replace(/^\uFEFF/, "")).filter((row) =>
    row.some((cell) => cell.trim()),
  );
  if (!rows.length) return [];
  const normalizedHeader = rows[0].map(normalizeHeader);
  const nameIndex = normalizedHeader.findIndex((value) =>
    ["name", "fullname", "displayname", "이름", "성명"].includes(value),
  );
  const emailIndex = normalizedHeader.findIndex((value) =>
    ["email", "emailaddress", "이메일", "메일"].includes(value),
  );
  const hasHeader = nameIndex >= 0 || emailIndex >= 0;
  const resolvedNameIndex = nameIndex >= 0 ? nameIndex : 0;
  const resolvedEmailIndex = emailIndex >= 0 ? emailIndex : 1;
  return rows
    .slice(hasHeader ? 1 : 0, (hasHeader ? 1 : 0) + 1000)
    .map((row) => ({
      displayName: (row[resolvedNameIndex] ?? "").trim(),
      email: (row[resolvedEmailIndex] ?? "").trim(),
    }));
}

function parseCsvRows(content: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let value = "";
  let quoted = false;

  for (let index = 0; index < content.length; index += 1) {
    const character = content[index];
    if (character === '"') {
      if (quoted && content[index + 1] === '"') {
        value += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
      continue;
    }
    if (character === "," && !quoted) {
      row.push(value);
      value = "";
      continue;
    }
    if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && content[index + 1] === "\n") {
        index += 1;
      }
      row.push(value);
      rows.push(row);
      row = [];
      value = "";
      continue;
    }
    value += character;
  }
  row.push(value);
  rows.push(row);
  return rows;
}

function normalizeHeader(value: string) {
  return value
    .trim()
    .toLocaleLowerCase("en-US")
    .replace(/[\s_-]/g, "");
}

function firstString(record: Record<string, unknown>, keys: readonly string[]) {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string") return value.trim();
  }
  return "";
}

export function resolveInvitationValidityDays(interviewAt?: string | null) {
  if (!interviewAt) return 7;
  const milliseconds = new Date(interviewAt).getTime() - Date.now();
  if (!Number.isFinite(milliseconds)) return 7;
  return Math.max(1, Math.ceil(milliseconds / 86_400_000) + 1);
}

export function parseInvitationApplicants(value: string): {
  applicants: InvitationApplicant[];
  invalidLines: string[];
  duplicateCount: number;
} {
  const rows = parseInvitationCsv(
    value
      .split(/\r?\n/)
      .map((line) => line.replace(/\t/g, ","))
      .join("\n"),
  ).map((applicant) => createDraftRow(applicant.displayName, applicant.email));
  const validated = validateInvitationDrafts(rows, new Set());
  return {
    applicants: validated.flatMap((row) =>
      row.applicant ? [row.applicant] : [],
    ),
    invalidLines: validated
      .filter((row) => row.state === "invalid")
      .map((row) => [row.displayName, row.email].filter(Boolean).join(", ")),
    duplicateCount: validated.filter((row) => row.state === "duplicate").length,
  };
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
