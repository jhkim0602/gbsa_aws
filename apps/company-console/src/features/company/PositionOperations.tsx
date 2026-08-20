import {
  ArrowLeft,
  BarChart3,
  BriefcaseBusiness,
  ClipboardCheck,
  FileText,
  GaugeCircle,
  Info,
  LayoutDashboard,
  ListChecks,
  PencilLine,
  Route,
  Target,
  Timer,
  UserRoundCheck,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";

import {
  interviewLevelLabels,
  PositionInvitations,
  type InvitationEmailTemplateApi,
  type PositionInvitationApi,
} from "../hiring";
import {
  ASYNC_STATE,
  BUTTON_SECONDARY,
  formAlertClass,
  STATUS_BADGE,
  STATUS_BADGE_TONE,
} from "../../app/styles/primitives";
import { summarizeApplicantPipeline } from "./applicantSummary";
import { statusLabel, statusTone } from "./companyFormatters";
import { PositionDashboard } from "./PositionDashboard";
import { CriteriaEditModal, PositionQuickEditModal } from "./PositionSettings";
import {
  countRecruiterPhases,
  recruiterStages,
  type PositionTab,
} from "./positionWorkspaceModel";
import type {
  CompanyCriterionVersion,
  CompanyInvitation,
  CompanyOperationsApi,
  CompanyPosition,
} from "./types";
import { useRecruitingOperations } from "./useRecruitingOperations";

const ROOT = "min-h-full bg-[#f6f7fa] pb-10";
const HEADER =
  "flex min-h-[158px] items-end justify-between gap-6 border-b border-b-border" +
  " bg-surface p-[24px_32px] mw-720:min-h-auto mw-720:flex-col" +
  " mw-720:items-stretch mw-720:p-[18px_16px]";
const IDENTITY = "flex min-w-0 items-start gap-[14px] mw-720:items-start";
const ICON =
  "grid size-11 flex-none place-items-center rounded-lg border" +
  " border-[color-mix(in_srgb,var(--color-link)_18%,var(--color-border))]" +
  " bg-brand-soft text-brand";
const TITLE_LINE = "flex min-w-0 flex-wrap items-center gap-2.5";
const TITLE =
  "[overflow-wrap:anywhere] text-[26px] leading-[1.25] text-ink" +
  " mw-720:text-[21px]";
const DESCRIPTION =
  "mt-[5px] max-w-[760px] text-[13px] leading-[1.55] text-muted";
const META = "mt-[11px] flex flex-wrap items-center gap-2";
// Each entry is separated by a hairline, so the first one drops its rule and inset.
const META_ITEM =
  "border-l border-l-border pl-[9px] text-[12px] text-muted first:border-l-0" +
  " first:pl-0";
const EDIT_BUTTON = `${BUTTON_SECONDARY} flex-none mw-720:w-full`;

/*
 * `.position-tabs` is declared four times; the sticky bar, the 96% surface and the 4px stack
 * order are the survivors, and only the gap and inset come from the workspace-scoped pair.
 */
const TABS =
  "sticky top-0 z-4 flex min-w-0 gap-[34px] overflow-x-auto border-b" +
  " border-b-border bg-[color-mix(in_srgb,var(--color-surface)_96%,transparent)]" +
  " px-8 backdrop-blur-[10px] mw-720:gap-6 mw-720:px-4";
// The underline is an always-present `::after` that only takes a colour when selected.
const TAB =
  "relative inline-flex min-h-[54px] flex-none items-center gap-2 bg-transparent" +
  " p-0 text-[13px] font-[650] text-muted after:absolute after:inset-x-0" +
  " after:-bottom-px after:h-0.5 after:content-[''] aria-selected:text-brand" +
  " aria-selected:after:bg-brand";
const TAB_COUNT =
  "grid h-5 min-w-5 place-items-center rounded-[10px] bg-surface-strong px-[5px]" +
  " text-[10px]";

const CONTENT = "grid gap-[14px] p-[22px_32px_44px] mw-720:p-[14px_12px_32px]";
const PANEL_GROUP = "grid gap-[18px]";
/*
 * Every panel on this page is flattened by a shared override — no shadow, an 8px radius and
 * a clipped box — so the flattened form is the primitive rather than `PANEL` plus patches.
 */
const SUB_PANEL = "overflow-hidden rounded-lg border border-border bg-surface";

const SUMMARY =
  "grid grid-cols-[repeat(4,minmax(130px,1fr))_auto] overflow-hidden rounded-lg" +
  " border border-border bg-surface m-[18px_32px_0] mw-1050:grid-cols-2" +
  " mw-720:m-[14px_16px_0] mw-480:grid-cols-[minmax(0,1fr)]";
/*
 * The dividers follow the grid: vertical while the row is four wide, horizontal for the
 * second row at 1050px, and horizontal only once the grid is a single column.
 */
const SUMMARY_ITEM =
  "grid min-h-18 grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-2.5" +
  " p-[12px_16px] not-first:border-l not-first:border-l-border-muted" +
  " mw-1050:nth-3:border-l-0 mw-1050:nth-3:border-t" +
  " mw-1050:nth-3:border-t-border-muted mw-1050:nth-4:border-t" +
  " mw-1050:nth-4:border-t-border-muted mw-720:min-h-[62px]" +
  " mw-720:grid-cols-[24px_minmax(0,1fr)_auto] mw-720:p-[10px_12px]" +
  " mw-480:not-first:border-t mw-480:not-first:border-t-border-muted" +
  " mw-480:not-first:border-l-0";
const SUMMARY_LABEL = "text-[12px] text-muted";
const SUMMARY_VALUE =
  "[font-variant-numeric:tabular-nums] text-[22px] text-ink mw-720:text-[19px]";
// The goal reads as a trailing note beside the counts, then wraps under them at 1050px.
const SUMMARY_GOAL =
  "flex min-w-[132px] items-center justify-center border-l border-l-border" +
  " bg-surface-muted p-[12px_16px] text-[12px] text-muted mw-1050:col-[1/-1]" +
  " mw-1050:border-t mw-1050:border-t-border mw-1050:border-l-0";
const SUMMARY_GOAL_VALUE = "ml-[5px] text-ink";

const STATS_GRID =
  "grid grid-cols-[minmax(0,1.6fr)_minmax(260px,0.4fr)] gap-[18px]" +
  " mw-1040:grid-cols-[minmax(0,1fr)]";
const SECTION_HEADING =
  "flex min-h-18 items-center justify-between gap-[18px] border-b" +
  " border-b-border-muted p-[16px_20px] mw-720:flex-col mw-720:items-start";
const SECTION_HEADING_TITLE = "text-[15px] leading-[1.4] text-ink";
const SECTION_HEADING_TEXT = "mt-[3px] text-[12px] leading-[1.5] text-muted";
const SECTION_HEADING_COUNT = "text-[12px] font-[650] text-muted";
const SECTION_HEADING_BUTTON = `${BUTTON_SECONDARY} mw-720:w-full`;

const BARS = "grid p-[8px_20px_18px]";
const BAR_ROW =
  "grid min-h-[54px] grid-cols-[120px_minmax(120px,1fr)_48px_42px] items-center" +
  " gap-3 border-b border-b-border-muted last:border-b-0" +
  " mw-720:grid-cols-[92px_minmax(80px,1fr)_38px]";
const BAR_TRACK = "h-[7px] overflow-hidden rounded bg-surface-strong";
const BAR_FILL = "block h-full min-w-[3px] rounded-[inherit] bg-brand";
// The percentage is the column the 720px grid drops, so it hides rather than reflows.
const BAR_PERCENT = "text-right text-[12px] text-muted mw-720:hidden";

const ATTENTION = `${SUB_PANEL} flex flex-col`;
const ATTENTION_VALUE = "m-[28px_20px_0] text-[34px] text-ink";
const ATTENTION_LABEL = "m-[3px_20px_0] text-[12px] text-muted";
const ATTENTION_TEXT =
  "m-[auto_20px_20px] text-[12px] leading-[1.6] text-muted";

// `list-style: none` and the zeroed padding are what preflight already applies to `ol`.
const STAGE_LIST =
  "grid grid-cols-4 mw-1040:grid-cols-2 mw-720:grid-cols-[minmax(0,1fr)]";
/*
 * The four stages sit in one row divided vertically; at 1040px the grid halves and the first
 * row gains a bottom rule, and at 720px the column stack leaves only bottom rules.
 */
const STAGE =
  "grid min-w-0 min-h-[164px] grid-cols-[34px_minmax(0,1fr)] content-start gap-3" +
  " border-r border-r-border-muted p-[22px_20px] last:border-r-0" +
  " mw-1040:nth-2:border-r-0 mw-1040:nth-[-n+2]:border-b" +
  " mw-1040:nth-[-n+2]:border-b-border-muted mw-720:min-h-auto" +
  " mw-720:border-r-0 mw-720:border-b mw-720:border-b-border-muted" +
  " mw-720:last:border-b-0";
const STAGE_MARK =
  "grid size-8 place-items-center rounded-full border border-border bg-brand-soft" +
  " text-[12px] font-[750] text-brand";
const STAGE_TITLE = "text-[14px]";
const STAGE_TEXT = "mt-[5px] text-[11px] leading-[1.55] text-muted";
const STAGE_COUNT = "col-[2] mt-[14px] text-[20px] text-ink";

const FOCUS_ROW =
  "flex items-center justify-between gap-6 border-b border-b-border-muted" +
  " p-[17px_20px] last:border-b-0";
/** Shared by the focus list and the criterion headers in the information tab. */
const CRITERION_BADGE =
  "inline-flex min-h-[22px] items-center rounded bg-brand-soft px-[7px]" +
  " text-[10px] font-bold text-brand";
const FOCUS_TITLE = "ml-[9px] text-[13px]";
const FOCUS_TEXT = "mt-[5px] text-[12px] text-muted";
const FOCUS_WEIGHT =
  "grid size-[42px] flex-none place-items-center rounded-[7px] bg-surface-muted" +
  " text-[13px] text-ink";

const EMPTY_COPY = "grid justify-items-center gap-[11px]";
const EMPTY_TEXT = "text-[12px]";

const FACTS = "grid grid-cols-4 mw-720:grid-cols-[minmax(0,1fr)]";
const FACT =
  "border-r border-r-border-muted p-[18px_20px] last:border-r-0" +
  " mw-720:border-r-0 mw-720:border-b mw-720:border-b-border-muted" +
  " mw-720:last:border-b-0";
const FACT_LABEL = "text-[11px] text-muted";
const FACT_VALUE = "mt-1.5 text-[14px] font-[680] text-ink";

const CRITERIA_BODY = "grid";
const CRITERIA_SECTION = "border-b border-b-border-muted p-5 last:border-b-0";
const CRITERIA_SECTION_TITLE = "mb-[13px] text-[13px] text-ink";

const REQUIREMENT_LIST = "grid gap-2";
const REQUIREMENT =
  "grid min-h-[46px] grid-cols-[42px_minmax(0,1fr)_auto] items-center gap-[11px]" +
  " rounded-md border border-border-muted bg-surface-muted p-[9px_12px]" +
  " mw-720:grid-cols-[42px_minmax(0,1fr)]";
const REQUIREMENT_TAG =
  "inline-flex min-h-[22px] items-center justify-center rounded text-[10px]" +
  " font-bold";
// Each tone replaces both the background and the text, so they are complete variants.
const REQUIREMENT_TAG_TONE = {
  required: `${REQUIREMENT_TAG} bg-[color-mix(in_srgb,var(--color-danger)_9%,white)] text-danger`,
  preferred: `${REQUIREMENT_TAG} bg-success-soft text-success`,
} as const;
const REQUIREMENT_TEXT = "min-w-0 text-[12px]";
// The priority note tucks under the statement once the trailing column is gone.
const REQUIREMENT_NOTE = "text-[10px] text-muted mw-720:col-[2]";
const INFORMATION_EMPTY = "text-[12px] text-muted";

const CRITERION_LIST = "grid rounded-md border border-border-muted";
const CRITERION =
  "border-b border-b-border-muted p-[17px_18px] last:border-b-0";
const CRITERION_HEADER =
  "flex items-start justify-between gap-[18px] mw-720:flex-col";
const CRITERION_TITLE = "ml-[9px] text-[13px]";
const CRITERION_TEXT = "mt-[5px] text-[12px] text-muted";
const CRITERION_WEIGHT = "flex-none text-[11px] text-muted";
const CRITERION_GUIDE =
  "mt-[15px] grid grid-cols-2 gap-[9px_18px] border-t border-t-border-muted" +
  " pt-[14px] mw-720:grid-cols-[minmax(0,1fr)]";
const CRITERION_GUIDE_ROW = "grid grid-cols-[84px_minmax(0,1fr)] gap-2";
const CRITERION_GUIDE_LABEL = "text-[11px] leading-[1.55] text-muted";
const CRITERION_GUIDE_VALUE = "text-[11px] leading-[1.55] text-ink";

const POLICY_GRID =
  "grid grid-cols-4 mw-1040:grid-cols-2 mw-720:grid-cols-[minmax(0,1fr)]";
/*
 * The icon spans both text rows, so each cell is a two-row grid; its dividers follow the
 * same four → two → one column progression as the stage list.
 */
const POLICY =
  "grid grid-cols-[24px_minmax(0,1fr)] items-center gap-[3px_8px] border-r" +
  " border-r-border-muted p-[18px_20px] last:border-r-0" +
  " mw-1040:even:border-r-0 mw-1040:nth-[-n+2]:border-b" +
  " mw-1040:nth-[-n+2]:border-b-border-muted mw-720:border-r-0 mw-720:border-b" +
  " mw-720:border-b-border-muted mw-720:last:border-b-0";
const POLICY_ICON = "[grid-row:1/3] text-brand";
const POLICY_LABEL = "text-[10px] text-muted";
const POLICY_VALUE = "min-w-0 [overflow-wrap:anywhere] text-[12px]";

const positionTabs: ReadonlyArray<{
  id: PositionTab;
  label: string;
  icon: typeof Users;
}> = [
  { id: "overview", label: "대시보드", icon: LayoutDashboard },
  { id: "applicants", label: "지원자 목록", icon: Users },
  { id: "statistics", label: "지원자 통계", icon: BarChart3 },
  { id: "stages", label: "면접 단계", icon: Route },
  { id: "information", label: "포지션 정보", icon: Info },
];

export function PositionOperations({
  positionId,
  api,
  invitationApi,
  templateApi,
}: {
  positionId: string;
  api: CompanyOperationsApi;
  invitationApi: PositionInvitationApi;
  templateApi: InvitationEmailTemplateApi;
}) {
  const { positions, invitations, loading, error } = useRecruitingOperations(
    api,
    positionId,
  );
  const fetchedPosition = positions.find(
    (item) => item.positionId === positionId,
  );
  const [revisedPosition, setRevisedPosition] =
    useState<CompanyPosition | null>(null);
  const [criteria, setCriteria] = useState<readonly CompanyCriterionVersion[]>(
    [],
  );
  const [criteriaLoading, setCriteriaLoading] = useState(true);
  const [criteriaError, setCriteriaError] = useState("");
  const [activeTab, setActiveTab] = useState<PositionTab>("overview");
  const [quickEditOpen, setQuickEditOpen] = useState(false);
  const [criteriaEditOpen, setCriteriaEditOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const position =
    revisedPosition?.positionId === positionId
      ? revisedPosition
      : fetchedPosition;
  const positionInvitations = invitations.filter(
    (item) => item.positionId === positionId,
  );
  const summary = summarizeApplicantPipeline(positionInvitations);
  const currentCriteria =
    criteria.find((item) => item.status === "published") ?? criteria[0] ?? null;

  useEffect(() => {
    setRevisedPosition(null);
    setActiveTab("overview");
    setQuickEditOpen(false);
    setCriteriaEditOpen(false);
    setNotice("");
  }, [positionId]);

  useEffect(() => {
    let active = true;
    setCriteriaLoading(true);
    setCriteriaError("");
    api
      .listCriterionVersions(positionId)
      .then((items) => {
        if (active) setCriteria(items);
      })
      .catch(() => {
        if (active) setCriteriaError("면접 기준을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (active) setCriteriaLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, positionId]);

  const phaseCounts = useMemo(
    () => countRecruiterPhases(positionInvitations),
    [positionInvitations],
  );

  if (loading) {
    return (
      <div className={ASYNC_STATE} role="status">
        포지션 운영 정보를 불러오는 중입니다.
      </div>
    );
  }
  if (error || !position) {
    return (
      <div className={ASYNC_STATE} role="alert">
        포지션 운영 정보를 불러올 수 없습니다.
      </div>
    );
  }

  function selectTab(index: number) {
    const tab = positionTabs[index];
    if (!tab) return;
    setActiveTab(tab.id);
    window.requestAnimationFrame(() => {
      document.getElementById(`position-tab-${tab.id}`)?.focus();
    });
  }

  function openTab(tab: PositionTab) {
    setActiveTab(tab);
    window.requestAnimationFrame(() => {
      document.getElementById(`position-tab-${tab}`)?.focus();
    });
  }

  function handleTabKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      selectTab((index + 1) % positionTabs.length);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      selectTab((index - 1 + positionTabs.length) % positionTabs.length);
    } else if (event.key === "Home") {
      event.preventDefault();
      selectTab(0);
    } else if (event.key === "End") {
      event.preventDefault();
      selectTab(positionTabs.length - 1);
    }
  }

  return (
    <div className={ROOT}>
      <header className={HEADER}>
        <div className="min-w-0">
          <Link
            to="/positions"
            className="mb-[9px] inline-flex items-center gap-[5px] text-[9px] text-muted"
          >
            <ArrowLeft size={14} aria-hidden="true" />
            채용 포지션
          </Link>
          <div className={IDENTITY}>
            <span className={ICON} aria-hidden="true">
              <BriefcaseBusiness size={21} />
            </span>
            <div className="min-w-0">
              <div className={TITLE_LINE}>
                <h1 className={TITLE}>{position.title}</h1>
                <span
                  className={`${STATUS_BADGE} ${STATUS_BADGE_TONE[statusTone(position.status)]}`}
                >
                  {statusLabel(position.status)}
                </span>
              </div>
              <p className={DESCRIPTION}>{position.description}</p>
              <div className={META}>
                <span className={META_ITEM}>
                  {position.roleType ?? "직무 미지정"}
                </span>
                <span className={META_ITEM}>
                  채용 목표 {position.headcount ?? "미정"}명
                </span>
                <span className={META_ITEM}>
                  {formatRecruitingPeriod(position)}
                </span>
                <span className={META_ITEM}>지원자 {summary.total}명</span>
              </div>
            </div>
          </div>
        </div>
        <button
          className={EDIT_BUTTON}
          type="button"
          disabled={position.status === "closed"}
          onClick={() => setQuickEditOpen(true)}
        >
          <PencilLine size={15} aria-hidden="true" />
          간편 수정
        </button>
      </header>

      {notice ? (
        <p className={formAlertClass("workspace", "success")} role="status">
          {notice}
        </p>
      ) : null}

      <div className={TABS} role="tablist" aria-label="포지션 운영 메뉴">
        {positionTabs.map((tab, index) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              id={`position-tab-${tab.id}`}
              className={TAB}
              type="button"
              role="tab"
              aria-label={tab.label}
              aria-selected={activeTab === tab.id}
              aria-controls={`position-panel-${tab.id}`}
              tabIndex={activeTab === tab.id ? 0 : -1}
              onClick={() => setActiveTab(tab.id)}
              onKeyDown={(event) => handleTabKeyDown(event, index)}
            >
              <Icon size={16} aria-hidden="true" />
              {tab.label}
              {tab.id === "applicants" ? (
                <span className={TAB_COUNT}>{summary.total}</span>
              ) : null}
            </button>
          );
        })}
      </div>

      <main className={CONTENT}>
        {activeTab === "overview" ? (
          <section
            id="position-panel-overview"
            role="tabpanel"
            aria-labelledby="position-tab-overview"
          >
            <PositionDashboard
              position={position}
              invitations={positionInvitations}
              criteria={currentCriteria}
              phaseCounts={phaseCounts}
              onOpenTab={openTab}
            />
          </section>
        ) : null}

        {activeTab === "applicants" ? (
          <section
            id="position-panel-applicants"
            role="tabpanel"
            aria-labelledby="position-tab-applicants"
          >
            <PositionInvitations
              embedded
              view="workspace"
              positionId={positionId}
              positionName={position.title}
              api={invitationApi}
              templateApi={templateApi}
            />
          </section>
        ) : null}

        {activeTab === "statistics" ? (
          <section
            id="position-panel-statistics"
            role="tabpanel"
            aria-labelledby="position-tab-statistics"
            className={PANEL_GROUP}
          >
            <PositionSummary summary={summary} headcount={position.headcount} />
            <ApplicantStatistics
              invitations={positionInvitations}
              phaseCounts={phaseCounts}
            />
          </section>
        ) : null}

        {activeTab === "stages" ? (
          <section
            id="position-panel-stages"
            role="tabpanel"
            aria-labelledby="position-tab-stages"
            className={PANEL_GROUP}
          >
            <InterviewStages
              counts={phaseCounts}
              total={summary.total}
              criteria={currentCriteria}
            />
          </section>
        ) : null}

        {activeTab === "information" ? (
          <section
            id="position-panel-information"
            role="tabpanel"
            aria-labelledby="position-tab-information"
            className={PANEL_GROUP}
          >
            <PositionInformation
              position={position}
              criteria={currentCriteria}
              loading={criteriaLoading}
              error={criteriaError}
              onEditPosition={() => setQuickEditOpen(true)}
              onEditCriteria={() => setCriteriaEditOpen(true)}
            />
          </section>
        ) : null}
      </main>

      <PositionQuickEditModal
        open={quickEditOpen}
        position={position}
        hasCriteria={Boolean(currentCriteria)}
        api={api}
        onClose={() => setQuickEditOpen(false)}
        onPositionUpdated={(updated, message) => {
          setRevisedPosition(updated);
          setNotice(message);
        }}
      />
      <CriteriaEditModal
        open={criteriaEditOpen}
        position={position}
        currentCriteria={currentCriteria}
        api={api}
        onClose={() => setCriteriaEditOpen(false)}
        onCriteriaUpdated={(updated, message) => {
          setCriteria((items) => [
            updated,
            ...items.filter((item) => item.versionId !== updated.versionId),
          ]);
          setNotice(message);
        }}
      />
    </div>
  );
}

function PositionSummary({
  summary,
  headcount,
}: {
  summary: ReturnType<typeof summarizeApplicantPipeline>;
  headcount?: number | null;
}) {
  return (
    <section className={SUMMARY} aria-label="포지션 지원자 요약">
      <article
        className={SUMMARY_ITEM}
        aria-label={`전체 지원자 ${summary.total}명`}
      >
        <Users className="text-muted" size={18} aria-hidden="true" />
        <span className={SUMMARY_LABEL}>전체 지원자</span>
        <strong className={SUMMARY_VALUE}>{summary.total}</strong>
      </article>
      <article
        className={SUMMARY_ITEM}
        aria-label={`진행 중인 지원자 ${summary.inProgress}명`}
      >
        <UserRoundCheck className="text-muted" size={18} aria-hidden="true" />
        <span className={SUMMARY_LABEL}>진행 중</span>
        <strong className={SUMMARY_VALUE}>{summary.inProgress}</strong>
      </article>
      <article
        className={SUMMARY_ITEM}
        aria-label={`검토 대기 지원자 ${summary.reviewPending}명`}
      >
        <ClipboardCheck className="text-muted" size={18} aria-hidden="true" />
        <span className={SUMMARY_LABEL}>검토 대기</span>
        <strong className={SUMMARY_VALUE}>{summary.reviewPending}</strong>
      </article>
      <article
        className={SUMMARY_ITEM}
        aria-label={`완료된 지원자 ${summary.completed}명`}
      >
        <BriefcaseBusiness
          className="text-muted"
          size={18}
          aria-hidden="true"
        />
        <span className={SUMMARY_LABEL}>검토 완료</span>
        <strong className={SUMMARY_VALUE}>{summary.completed}</strong>
      </article>
      <p className={SUMMARY_GOAL}>
        <Target size={14} aria-hidden="true" />
        채용 목표{" "}
        <strong className={SUMMARY_GOAL_VALUE}>{headcount ?? "미정"}명</strong>
      </p>
    </section>
  );
}

function ApplicantStatistics({
  invitations,
  phaseCounts,
}: {
  invitations: readonly CompanyInvitation[];
  phaseCounts: readonly number[];
}) {
  const total = invitations.length;
  const attention = invitations.filter((item) =>
    ["interrupted", "expired", "revoked"].includes(item.status),
  ).length;

  return (
    <div className={STATS_GRID}>
      <section className={SUB_PANEL}>
        <header className={SECTION_HEADING}>
          <div>
            <h2 className={SECTION_HEADING_TITLE}>단계별 지원자 분포</h2>
            <p className={SECTION_HEADING_TEXT}>
              현재 지원자가 위치한 채용 단계입니다.
            </p>
          </div>
          <span className={SECTION_HEADING_COUNT}>총 {total}명</span>
        </header>
        <div className={BARS}>
          {recruiterStages.map((stage, index) => {
            const count = phaseCounts[index] ?? 0;
            const percentage = total ? Math.round((count / total) * 100) : 0;
            return (
              <div className={BAR_ROW} key={stage.phase}>
                <span className="text-[12px]">{stage.title}</span>
                <div
                  className={BAR_TRACK}
                  aria-label={`${stage.title} ${count}명`}
                >
                  <i className={BAR_FILL} style={{ width: `${percentage}%` }} />
                </div>
                <strong className="text-[12px]">{count}명</strong>
                <small className={BAR_PERCENT}>{percentage}%</small>
              </div>
            );
          })}
        </div>
      </section>
      <section className={ATTENTION}>
        <header className={SECTION_HEADING}>
          <div>
            <h2 className={SECTION_HEADING_TITLE}>운영 확인 항목</h2>
            <p className={SECTION_HEADING_TEXT}>
              재접속, 만료 또는 취소 상태를 우선 확인합니다.
            </p>
          </div>
        </header>
        <strong className={ATTENTION_VALUE}>{attention}</strong>
        <span className={ATTENTION_LABEL}>확인이 필요한 지원자</span>
        <p className={ATTENTION_TEXT}>
          {attention
            ? "지원자 목록에서 확인 필요 필터를 선택해 상태를 점검하세요."
            : "현재 별도로 확인할 지원자가 없습니다."}
        </p>
      </section>
    </div>
  );
}

function InterviewStages({
  counts,
  total,
  criteria,
}: {
  counts: readonly number[];
  total: number;
  criteria: CompanyCriterionVersion | null;
}) {
  return (
    <>
      <section className={SUB_PANEL}>
        <header className={SECTION_HEADING}>
          <div>
            <h2 className={SECTION_HEADING_TITLE}>지원자 면접 흐름</h2>
            <p className={SECTION_HEADING_TEXT}>
              채용담당자가 확인하는 네 단계로 진행 상황을 정리합니다.
            </p>
          </div>
          <span className={SECTION_HEADING_COUNT}>지원자 {total}명</span>
        </header>
        <ol className={STAGE_LIST}>
          {recruiterStages.map((stage, index) => (
            <li className={STAGE} key={stage.phase}>
              <span className={STAGE_MARK}>{stage.phase}</span>
              <div>
                <strong className={STAGE_TITLE}>{stage.title}</strong>
                <p className={STAGE_TEXT}>{stage.description}</p>
              </div>
              <b className={STAGE_COUNT}>{counts[index] ?? 0}명</b>
            </li>
          ))}
        </ol>
      </section>
      <section className={SUB_PANEL}>
        <header className={SECTION_HEADING}>
          <div>
            <h2 className={SECTION_HEADING_TITLE}>면접에서 확인할 중점</h2>
            <p className={SECTION_HEADING_TEXT}>
              기업이 설정한 평가기준을 면접 질문과 검토에 동일하게 적용합니다.
            </p>
          </div>
        </header>
        {criteria ? (
          <div className="grid">
            {criteria.criteria.map((criterion) => (
              <article className={FOCUS_ROW} key={criterion.code}>
                <div className="min-w-0">
                  <span className={CRITERION_BADGE}>
                    {criterion.required ? "필수" : "선택"}
                  </span>
                  <strong className={FOCUS_TITLE}>{criterion.name}</strong>
                  <p className={FOCUS_TEXT}>{criterion.description}</p>
                </div>
                <b className={FOCUS_WEIGHT}>{criterion.weight}</b>
              </article>
            ))}
          </div>
        ) : (
          <div className={ASYNC_STATE}>
            <ListChecks size={22} aria-hidden="true" />
            <div className={EMPTY_COPY}>
              <strong>저장된 면접 기준이 없습니다.</strong>
              <p className={EMPTY_TEXT}>
                포지션 정보에서 면접 기준을 입력하세요.
              </p>
            </div>
          </div>
        )}
      </section>
    </>
  );
}

function PositionInformation({
  position,
  criteria,
  loading,
  error,
  onEditPosition,
  onEditCriteria,
}: {
  position: CompanyPosition;
  criteria: CompanyCriterionVersion | null;
  loading: boolean;
  error: string;
  onEditPosition(): void;
  onEditCriteria(): void;
}) {
  return (
    <>
      <section className={SUB_PANEL}>
        <header className={SECTION_HEADING}>
          <div>
            <h2 className={SECTION_HEADING_TITLE}>포지션 기본 정보</h2>
            <p className={SECTION_HEADING_TEXT}>
              공고와 운영 현황에 표시되는 현재 값입니다.
            </p>
          </div>
          {position.status !== "closed" ? (
            <button
              className={SECTION_HEADING_BUTTON}
              type="button"
              onClick={onEditPosition}
            >
              <PencilLine size={14} aria-hidden="true" />
              기본 정보 수정
            </button>
          ) : null}
        </header>
        <dl className={FACTS}>
          <div className={FACT}>
            <dt className={FACT_LABEL}>직무</dt>
            <dd className={FACT_VALUE}>{position.roleType ?? "미지정"}</dd>
          </div>
          <div className={FACT}>
            <dt className={FACT_LABEL}>채용 목표</dt>
            <dd className={FACT_VALUE}>{position.headcount ?? "미정"}명</dd>
          </div>
          <div className={FACT}>
            <dt className={FACT_LABEL}>모집 기간</dt>
            <dd className={FACT_VALUE}>{formatRecruitingPeriod(position)}</dd>
          </div>
          <div className={FACT}>
            <dt className={FACT_LABEL}>운영 상태</dt>
            <dd className={FACT_VALUE}>{statusLabel(position.status)}</dd>
          </div>
        </dl>
      </section>

      <section className={SUB_PANEL}>
        <header className={SECTION_HEADING}>
          <div>
            <h2 className={SECTION_HEADING_TITLE}>현재 적용 중인 면접 기준</h2>
            <p className={SECTION_HEADING_TEXT}>
              지원자 질문과 답변 검토에 사용하는 기업 설정값입니다.
            </p>
          </div>
          {position.status !== "closed" ? (
            <button
              className={SECTION_HEADING_BUTTON}
              type="button"
              onClick={onEditCriteria}
            >
              <FileText size={14} aria-hidden="true" />
              면접 기준 수정
            </button>
          ) : null}
        </header>

        {loading ? (
          <div className={ASYNC_STATE} role="status">
            면접 기준을 불러오는 중입니다.
          </div>
        ) : error ? (
          <div className={ASYNC_STATE} role="alert">
            {error}
          </div>
        ) : criteria ? (
          <div className={CRITERIA_BODY}>
            <section className={CRITERIA_SECTION}>
              <h3 className={CRITERIA_SECTION_TITLE}>직무 요구사항</h3>
              {criteria.jobRequirements.length ? (
                <ul className={REQUIREMENT_LIST}>
                  {criteria.jobRequirements.map((requirement, index) => (
                    <li
                      className={REQUIREMENT}
                      key={`${requirement.criterionCode}-${index}`}
                    >
                      <span
                        className={
                          REQUIREMENT_TAG_TONE[
                            requirement.requirementType === "required"
                              ? "required"
                              : "preferred"
                          ]
                        }
                      >
                        {requirement.requirementType === "required"
                          ? "필수"
                          : "우대"}
                      </span>
                      <strong className={REQUIREMENT_TEXT}>
                        {requirement.statement}
                      </strong>
                      <small className={REQUIREMENT_NOTE}>
                        중요도 {priorityLabel(requirement.priority)}
                      </small>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className={INFORMATION_EMPTY}>
                  등록된 직무 요구사항이 없습니다.
                </p>
              )}
            </section>

            <section className={CRITERIA_SECTION}>
              <h3 className={CRITERIA_SECTION_TITLE}>평가기준과 검증 가이드</h3>
              <div className={CRITERION_LIST}>
                {criteria.criteria.map((criterion) => (
                  <article className={CRITERION} key={criterion.code}>
                    <header className={CRITERION_HEADER}>
                      <div>
                        <span className={CRITERION_BADGE}>
                          {criterion.required ? "필수" : "선택"}
                        </span>
                        <strong className={CRITERION_TITLE}>
                          {criterion.name}
                        </strong>
                        <p className={CRITERION_TEXT}>
                          {criterion.description}
                        </p>
                      </div>
                      <b className={CRITERION_WEIGHT}>
                        가중치 {criterion.weight}
                      </b>
                    </header>
                    <dl className={CRITERION_GUIDE}>
                      <div className={CRITERION_GUIDE_ROW}>
                        <dt className={CRITERION_GUIDE_LABEL}>확인 요소</dt>
                        <dd className={CRITERION_GUIDE_VALUE}>
                          {criterion.verificationGuide.observableDimensions.join(
                            " · ",
                          )}
                        </dd>
                      </div>
                      <div className={CRITERION_GUIDE_ROW}>
                        <dt className={CRITERION_GUIDE_LABEL}>
                          좋은 답변 신호
                        </dt>
                        <dd className={CRITERION_GUIDE_VALUE}>
                          {criterion.verificationGuide.strongAnswerSignals.join(
                            " · ",
                          )}
                        </dd>
                      </div>
                      <div className={CRITERION_GUIDE_ROW}>
                        <dt className={CRITERION_GUIDE_LABEL}>
                          추가 확인 신호
                        </dt>
                        <dd className={CRITERION_GUIDE_VALUE}>
                          {criterion.verificationGuide.weakAnswerSignals.join(
                            " · ",
                          )}
                        </dd>
                      </div>
                      <div className={CRITERION_GUIDE_ROW}>
                        <dt className={CRITERION_GUIDE_LABEL}>꼬리질문 방향</dt>
                        <dd className={CRITERION_GUIDE_VALUE}>
                          {criterion.verificationGuide.followUpDirections.join(
                            " · ",
                          )}
                        </dd>
                      </div>
                    </dl>
                  </article>
                ))}
              </div>
            </section>
          </div>
        ) : (
          <div className={ASYNC_STATE}>
            <ListChecks size={22} aria-hidden="true" />
            <div className={EMPTY_COPY}>
              <strong>저장된 면접 기준이 없습니다.</strong>
              <p className={EMPTY_TEXT}>
                면접 기준을 입력해야 채용을 확정할 수 있습니다.
              </p>
            </div>
          </div>
        )}
      </section>

      {criteria ? (
        <section className={SUB_PANEL}>
          <header className={SECTION_HEADING}>
            <div>
              <h2 className={SECTION_HEADING_TITLE}>면접 운영 정책</h2>
              <p className={SECTION_HEADING_TEXT}>
                면접 진행 시간과 질문 제한 범위입니다.
              </p>
            </div>
          </header>
          <div className={POLICY_GRID}>
            <span className={POLICY}>
              <Timer className={POLICY_ICON} size={17} aria-hidden="true" />
              <small className={POLICY_LABEL}>면접 시간</small>
              <strong className={POLICY_VALUE}>
                {criteria.interviewDurationMinutes}분
              </strong>
            </span>
            <span className={POLICY}>
              <GaugeCircle
                className={POLICY_ICON}
                size={17}
                aria-hidden="true"
              />
              <small className={POLICY_LABEL}>면접 난이도</small>
              <strong className={POLICY_VALUE}>
                {interviewLevelLabels[criteria.interviewLevel].name}
              </strong>
            </span>
            <span className={POLICY}>
              <ClipboardCheck
                className={POLICY_ICON}
                size={17}
                aria-hidden="true"
              />
              <small className={POLICY_LABEL}>평가기준</small>
              <strong className={POLICY_VALUE}>
                {criteria.criteria.length}개
              </strong>
            </span>
            <span className={POLICY}>
              <Info className={POLICY_ICON} size={17} aria-hidden="true" />
              <small className={POLICY_LABEL}>금지 주제</small>
              <strong className={POLICY_VALUE}>
                {criteria.prohibitedTopics.length
                  ? criteria.prohibitedTopics.join(", ")
                  : "등록 없음"}
              </strong>
            </span>
          </div>
        </section>
      ) : null}
    </>
  );
}

function formatRecruitingPeriod(position: CompanyPosition) {
  if (!position.recruitmentStartAt && !position.recruitmentEndAt) {
    return "상시 채용";
  }
  const start = position.recruitmentStartAt
    ? formatDate(position.recruitmentStartAt)
    : "시작일 미정";
  const end = position.recruitmentEndAt
    ? formatDate(position.recruitmentEndAt)
    : "종료일 미정";
  return `${start} - ${end}`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(`${value}T00:00:00`));
}

function priorityLabel(priority: number) {
  return ["높음", "중간", "보통", "낮음", "참고"][priority - 1] ?? priority;
}
