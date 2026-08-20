import {
  ArrowRight,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  ClipboardCheck,
  FileCheck2,
  PlayCircle,
  Plus,
  ScanSearch,
  Video,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ASYNC_STATE,
  BUTTON_PRIMARY,
  INVITATION_STATUS,
  invitationTone,
  PAGE_CONTENT,
  PAGE_HEADER,
  PAGE_HEADER_TEXT,
  PAGE_HEADER_TITLE,
  PANEL,
  SECTION_HEADER,
  SECTION_HEADER_TEXT,
  STATUS_BADGE,
  STATUS_BADGE_TONE,
} from "../../app/styles/primitives";
import { statusLabel, statusTone } from "./companyFormatters";
import { displayApplicant, invitationProjection } from "./recruitingState";
import type {
  CompanyInvitationStatus,
  CompanyOperationsApi,
  CompanyPosition,
} from "./types";
import {
  type PositionedInvitation,
  useRecruitingOperations,
} from "./useRecruitingOperations";

const ACTIVE_POSITION_STATUSES = new Set(["active", "open", "published"]);
const LIVE_INTERVIEW_STATUSES = new Set(["interviewing"]);
const REVIEW_PENDING_STATUSES = new Set(["completed"]);
const COMPLETED_INTERVIEW_STATUSES = new Set(["reviewed"]);

const HEADING = `${PAGE_HEADER} pb-2.5 mw-680:flex-col`;
const CONTENT = `${PAGE_CONTENT} grid gap-[18px] pt-3`;
const SECTION_HEADER_LINK =
  "inline-flex items-center gap-1 text-[10px] font-semibold text-brand";
const SECTION_HEADER_TITLE = "text-[13px]";
const OVERVIEW_PANEL = `${PANEL} min-w-0 overflow-hidden`;

const METRICS = "grid grid-cols-4 gap-3 mw-760:grid-cols-2";
const METRIC =
  `${PANEL} grid min-w-0 grid-cols-[38px_minmax(0,1fr)] items-start gap-[11px] p-4` +
  " mw-620:grid-cols-[32px_minmax(0,1fr)] mw-620:p-3";
const METRIC_MARK =
  "grid size-[38px] place-items-center rounded-[10px] [&_svg]:size-[18px]" +
  " mw-620:size-8";
const METRIC_TONE = {
  purple: "bg-brand-soft text-brand",
  blue: "bg-[#edf5ff] text-[#3478d4]",
  green: "bg-success-soft text-success",
  orange: "bg-warning-soft text-warning",
} as const;

const TOP_GRID =
  "grid grid-cols-[minmax(0,3fr)_minmax(230px,1fr)] items-start gap-[14px]" +
  " mw-860:grid-cols-[minmax(0,1fr)]";
const POSITION_SUMMARY =
  "flex flex-wrap gap-2 border-b border-b-border-muted bg-surface-muted px-[15px] py-3";
const POSITION_SUMMARY_PILL =
  "inline-flex min-h-[26px] items-center gap-[5px] rounded-full border" +
  " border-border-muted bg-surface px-[9px] text-[9px] text-muted";

const POSITION_ROW =
  "grid min-h-19 grid-cols-[34px_minmax(0,1fr)_minmax(250px,auto)_16px]" +
  " items-center gap-3 px-[15px] py-3 text-inherit not-first:border-t" +
  " not-first:border-t-border-muted hover:bg-surface-muted" +
  " mw-760:grid-cols-[34px_minmax(0,1fr)_16px]";
const ROW_STATS =
  "grid min-w-[250px] grid-cols-[repeat(4,minmax(48px,1fr))]" +
  " mw-760:col-[2/-1] mw-760:w-full mw-760:min-w-0 mw-760:grid-cols-4";

const CALENDAR_WEEK =
  "grid grid-cols-7 border-b border-border-muted bg-surface-muted px-2 py-2";
const CALENDAR_GRID = "grid grid-cols-7 p-2";
const CALENDAR_DAY =
  "grid min-h-[54px] content-start gap-1 border-r border-b border-border-muted" +
  " p-1 nth-[7n]:border-r-0";
const CALENDAR_EVENT_TONE = {
  start: "bg-[#dfe5ff] text-[#4250b5]",
  interview: "bg-[#dff5ea] text-[#16774b]",
  end: "bg-[#fff0da] text-[#a45c08]",
} as const;

const ACTIVITY_ROW =
  "group grid min-h-[68px] grid-cols-[38px_minmax(150px,0.8fr)_minmax(220px,1.4fr)_minmax(130px,0.8fr)_auto_16px]" +
  " items-center gap-3 px-4 py-3 text-inherit" +
  " not-first:border-t not-first:border-t-border-muted hover:bg-surface-muted" +
  " mw-860:grid-cols-[38px_minmax(0,1fr)_auto_16px]";
const ACTIVITY_TONE = {
  neutral: "bg-surface-strong text-muted",
  progress: "bg-[#edf5ff] text-[#3478d4]",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
} as const;

const EMPTY =
  "flex min-h-22 items-center justify-center gap-[11px] p-[18px] text-left text-muted";

export function CompanyOverview({ api }: { api: CompanyOperationsApi }) {
  const { positions, invitations, loading, error, lastUpdatedAt } =
    useRecruitingOperations(api, undefined, 15_000);
  const [calendarMonth, setCalendarMonth] = useState(() =>
    startOfMonth(new Date()),
  );

  const activePositions = positions.filter((position) =>
    ACTIVE_POSITION_STATUSES.has(position.status),
  );
  const interviewsInProgress = invitations.filter((invitation) =>
    LIVE_INTERVIEW_STATUSES.has(invitation.status),
  );
  const reviewsPending = invitations.filter((invitation) =>
    REVIEW_PENDING_STATUSES.has(invitation.status),
  );
  const completedInterviews = invitations.filter((invitation) =>
    COMPLETED_INTERVIEW_STATUSES.has(invitation.status),
  );

  const invitationsByPosition = useMemo(() => {
    const grouped = new Map<string, PositionedInvitation[]>();
    for (const invitation of invitations) {
      const group = grouped.get(invitation.positionId) ?? [];
      group.push(invitation);
      grouped.set(invitation.positionId, group);
    }
    return grouped;
  }, [invitations]);
  const calendarEvents = useMemo(
    () => buildCalendarEvents(positions),
    [positions],
  );
  const applicantActivities = useMemo(
    () => buildApplicantActivities(invitations).slice(0, 12),
    [invitations],
  );

  return (
    <div>
      <header className={HEADING}>
        <div>
          <h1 className={PAGE_HEADER_TITLE}>채용 운영 대시보드</h1>
          <p className={PAGE_HEADER_TEXT}>
            포지션 일정과 지원자 면접 흐름을 한 화면에서 확인하세요.
          </p>
        </div>
        <Link className={BUTTON_PRIMARY} to="/hiring">
          <Plus size={16} aria-hidden="true" />새 채용 관리
        </Link>
      </header>

      <div className={CONTENT}>
        {loading ? (
          <div className={`${PANEL} ${ASYNC_STATE}`} role="status">
            <p className="text-[12px]">채용 운영 현황을 불러오는 중입니다.</p>
          </div>
        ) : error ? (
          <div className={`${PANEL} ${ASYNC_STATE}`} role="alert">
            <p className="text-[12px]">
              채용 운영 데이터를 불러오지 못했습니다.
            </p>
          </div>
        ) : (
          <>
            <section className={METRICS} aria-label="채용 핵심 지표">
              <OperationsMetric
                icon={<BriefcaseBusiness />}
                label="활성 포지션"
                value={activePositions.length}
                unit="개"
                detail={`전체 ${positions.length}개 포지션`}
              />
              <OperationsMetric
                icon={<Video />}
                label="진행 중인 면접"
                value={interviewsInProgress.length}
                unit="건"
                detail="현재 면접 세션"
                tone="blue"
              />
              <OperationsMetric
                icon={<ClipboardCheck />}
                label="검토 대기"
                value={reviewsPending.length}
                unit="건"
                detail="담당자 판단 대기"
                tone="orange"
              />
              <OperationsMetric
                icon={<CheckCircle2 />}
                label="완료된 면접"
                value={completedInterviews.length}
                unit="건"
                detail="담당자 검토 완료"
                tone="green"
              />
            </section>

            <div className={TOP_GRID}>
              <section className={OVERVIEW_PANEL}>
                <header className={SECTION_HEADER}>
                  <div>
                    <h2 className={SECTION_HEADER_TITLE}>포지션 현황</h2>
                    <p className={SECTION_HEADER_TEXT}>
                      포지션별 지원자와 면접·검토 상태입니다.
                    </p>
                  </div>
                  <Link className={SECTION_HEADER_LINK} to="/positions">
                    전체 포지션 <ArrowRight size={13} aria-hidden="true" />
                  </Link>
                </header>

                <div className={POSITION_SUMMARY}>
                  <PositionSummaryPill
                    label="운영 중"
                    value={activePositions.length}
                  />
                  <PositionSummaryPill
                    label="초안"
                    value={countPositions(positions, "draft")}
                  />
                  <PositionSummaryPill
                    label="종료"
                    value={countPositions(positions, "closed")}
                  />
                </div>

                {positions.length ? (
                  <div className="grid">
                    {positions.slice(0, 6).map((position) => (
                      <PositionStatusRow
                        key={position.positionId}
                        position={position}
                        invitations={
                          invitationsByPosition.get(position.positionId) ?? []
                        }
                      />
                    ))}
                  </div>
                ) : (
                  <DashboardEmpty
                    title="등록된 포지션이 없습니다."
                    description="새 채용 관리를 시작하면 포지션 운영 상태가 표시됩니다."
                  />
                )}
              </section>

              <RecruitmentCalendar
                month={calendarMonth}
                events={calendarEvents}
                onMonthChange={setCalendarMonth}
              />
            </div>

            <section className={OVERVIEW_PANEL} aria-live="polite">
              <header className={SECTION_HEADER}>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className={SECTION_HEADER_TITLE}>지원자 실시간 로그</h2>
                    <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-2 py-1 text-[8px] font-bold text-success">
                      <i className="size-1.5 rounded-full bg-success" /> LIVE
                    </span>
                  </div>
                  <p className={SECTION_HEADER_TEXT}>
                    면접 시작·종료와 자료 분석, 담당자 검토 상태를 최신순으로
                    확인합니다.
                  </p>
                </div>
                <span className="text-[9px] text-muted">
                  {lastUpdatedAt
                    ? `${formatClock(lastUpdatedAt)} 동기화 · 15초 자동 갱신`
                    : "동기화 중"}
                </span>
              </header>

              {applicantActivities.length ? (
                <div className="grid [content-visibility:auto]">
                  {applicantActivities.map((activity) => (
                    <ApplicantActivityRow
                      key={activity.invitation.invitationId}
                      activity={activity}
                    />
                  ))}
                </div>
              ) : (
                <DashboardEmpty
                  title="아직 지원자 활동이 없습니다."
                  description="지원자가 자료를 제출하거나 면접을 시작하면 이곳에 표시됩니다."
                />
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

function OperationsMetric({
  icon,
  label,
  value,
  unit,
  detail,
  tone = "purple",
}: {
  icon: ReactNode;
  label: string;
  value: number;
  unit: "개" | "건";
  detail: string;
  tone?: keyof typeof METRIC_TONE;
}) {
  return (
    <article aria-label={`${label} ${value}${unit}`} className={METRIC}>
      <span
        className={`${METRIC_MARK} ${METRIC_TONE[tone]}`}
        aria-hidden="true"
      >
        {icon}
      </span>
      <div className="grid min-w-0 gap-0.5">
        <small className="truncate text-[9px] text-muted">{label}</small>
        <strong className="font-mono text-[23px] leading-[1.15] text-ink">
          {value}
          <em className="ml-[3px] font-sans text-[10px] font-semibold not-italic text-muted">
            {unit}
          </em>
        </strong>
        <p className="text-[9px] text-muted">{detail}</p>
      </div>
    </article>
  );
}

function PositionSummaryPill({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <span className={POSITION_SUMMARY_PILL}>
      {label}
      <strong className="font-mono text-[10px] text-ink">{value}</strong>
    </span>
  );
}

function PositionStatusRow({
  position,
  invitations,
}: {
  position: CompanyPosition;
  invitations: readonly PositionedInvitation[];
}) {
  const interviews = invitations.filter((invitation) =>
    LIVE_INTERVIEW_STATUSES.has(invitation.status),
  ).length;
  const reviews = invitations.filter((invitation) =>
    REVIEW_PENDING_STATUSES.has(invitation.status),
  ).length;
  const completed = invitations.filter((invitation) =>
    COMPLETED_INTERVIEW_STATUSES.has(invitation.status),
  ).length;

  return (
    <Link className={POSITION_ROW} to={`/positions/${position.positionId}`}>
      <span
        className="grid size-[34px] place-items-center rounded-[10px] bg-brand-soft text-brand"
        aria-hidden="true"
      >
        <BriefcaseBusiness size={16} />
      </span>
      <div className="grid min-w-0 gap-1">
        <div className="flex min-w-0 items-center gap-2">
          <strong className="truncate text-[11px]">{position.title}</strong>
          <span
            className={`${STATUS_BADGE} ${STATUS_BADGE_TONE[statusTone(position.status)]}`}
          >
            {statusLabel(position.status)}
          </span>
        </div>
        <small className="truncate text-[9px] text-muted">
          {position.description}
        </small>
      </div>
      <dl className={ROW_STATS}>
        <PositionRowStat label="지원자" value={invitations.length} />
        <PositionRowStat label="면접 중" value={interviews} />
        <PositionRowStat label="검토 대기" value={reviews} />
        <PositionRowStat label="완료" value={completed} />
      </dl>
      <ArrowRight size={15} aria-hidden="true" />
    </Link>
  );
}

function PositionRowStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="grid gap-0.5 border-l border-l-border-muted px-2.5 text-center">
      <dt className="text-[8px] text-muted">{label}</dt>
      <dd className="font-mono text-[12px] font-bold text-ink">{value}</dd>
    </div>
  );
}

type CalendarEvent = Readonly<{
  id: string;
  dateKey: string;
  kind: "start" | "interview" | "end";
  label: string;
  position: CompanyPosition;
}>;

function RecruitmentCalendar({
  month,
  events,
  onMonthChange,
}: {
  month: Date;
  events: readonly CalendarEvent[];
  onMonthChange(month: Date): void;
}) {
  const days = calendarDays(month);
  const eventsByDate = useMemo(() => {
    const grouped = new Map<string, CalendarEvent[]>();
    for (const event of events) {
      const group = grouped.get(event.dateKey) ?? [];
      group.push(event);
      grouped.set(event.dateKey, group);
    }
    return grouped;
  }, [events]);
  const todayKey = toDateKey(new Date());

  return (
    <section className={OVERVIEW_PANEL} aria-label="채용 일정 캘린더">
      <header className="flex min-h-[61px] items-center justify-between gap-3 border-b border-border-muted px-3 py-3">
        <div>
          <h2 className={SECTION_HEADER_TITLE}>채용 캘린더</h2>
          <p className="mt-1 text-[8px] text-muted">모집·면접 주요 일정</p>
        </div>
        <div className="flex items-center gap-1">
          <button
            className="grid size-7 place-items-center rounded-md border border-border bg-surface text-muted hover:text-brand"
            type="button"
            aria-label="이전 달"
            onClick={() => onMonthChange(addMonths(month, -1))}
          >
            <ChevronLeft size={13} aria-hidden="true" />
          </button>
          <strong className="min-w-16 text-center font-mono text-[10px] text-ink">
            {formatMonth(month)}
          </strong>
          <button
            className="grid size-7 place-items-center rounded-md border border-border bg-surface text-muted hover:text-brand"
            type="button"
            aria-label="다음 달"
            onClick={() => onMonthChange(addMonths(month, 1))}
          >
            <ChevronRight size={13} aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className={CALENDAR_WEEK} aria-hidden="true">
        {["일", "월", "화", "수", "목", "금", "토"].map((day) => (
          <span
            className="text-center text-[8px] font-semibold text-muted"
            key={day}
          >
            {day}
          </span>
        ))}
      </div>
      <div className={CALENDAR_GRID}>
        {days.map((day) => {
          const dateKey = toDateKey(day);
          const dayEvents = eventsByDate.get(dateKey) ?? [];
          const inMonth = day.getMonth() === month.getMonth();
          return (
            <div
              className={`${CALENDAR_DAY} ${inMonth ? "bg-surface" : "bg-surface-muted/60"}`}
              key={dateKey}
            >
              <time
                className={`grid size-4 place-items-center rounded-full text-[8px] ${
                  dateKey === todayKey
                    ? "bg-brand font-bold text-white"
                    : inMonth
                      ? "text-ink-secondary"
                      : "text-subtle"
                }`}
                dateTime={dateKey}
              >
                {day.getDate()}
              </time>
              <div className="grid gap-0.5">
                {dayEvents.slice(0, 3).map((event) => (
                  <Link
                    className={`block min-h-3 truncate rounded-[2px] px-1 text-[7px] font-semibold leading-3 ${CALENDAR_EVENT_TONE[event.kind]}`}
                    key={event.id}
                    title={`${event.position.title} · ${event.label}`}
                    aria-label={`${event.position.title} ${event.label}`}
                    to={`/positions/${event.position.positionId}`}
                  >
                    {event.label}
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <footer className="flex flex-wrap gap-x-3 gap-y-1 border-t border-border-muted px-3 py-2.5 text-[8px] text-muted">
        <CalendarLegend tone="bg-[#6675dc]" label="모집 시작" />
        <CalendarLegend tone="bg-[#28a66f]" label="면접" />
        <CalendarLegend tone="bg-[#d78b2c]" label="모집 마감" />
      </footer>
    </section>
  );
}

function CalendarLegend({ tone, label }: { tone: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <i className={`h-1.5 w-3 rounded-[2px] ${tone}`} /> {label}
    </span>
  );
}

type ApplicantActivity = Readonly<{
  invitation: PositionedInvitation;
  title: string;
  detail: string;
  tone: keyof typeof ACTIVITY_TONE;
}>;

function ApplicantActivityRow({ activity }: { activity: ApplicantActivity }) {
  const { invitation } = activity;
  const status = invitationProjection(invitation.status);
  return (
    <Link
      className={ACTIVITY_ROW}
      to={`/positions/${invitation.positionId}/applicants/${invitation.invitationId}`}
      aria-label={`${displayApplicant(invitation)} ${activity.title}`}
    >
      <span
        className={`grid size-[38px] place-items-center rounded-[11px] ${ACTIVITY_TONE[activity.tone]}`}
        aria-hidden="true"
      >
        <ActivityIcon status={invitation.status} />
      </span>
      <span className="grid min-w-0 gap-0.5">
        <strong className="truncate text-[11px] text-ink">
          {displayApplicant(invitation)}
        </strong>
        <small className="truncate text-[8px] text-muted">
          {invitation.applicantEmail}
        </small>
      </span>
      <span className="grid min-w-0 gap-0.5 mw-860:col-[2/4] mw-860:row-[2]">
        <strong className="truncate text-[10px] text-ink-secondary">
          {activity.title}
        </strong>
        <small className="truncate text-[8px] text-muted">
          {activity.detail}
        </small>
      </span>
      <span className="truncate text-[9px] text-muted mw-860:hidden">
        {invitation.positionTitle}
      </span>
      <span className={`${INVITATION_STATUS} ${invitationTone(status.tone)}`}>
        {status.label}
      </span>
      <ArrowRight
        className="text-subtle group-hover:text-brand"
        size={14}
        aria-hidden="true"
      />
    </Link>
  );
}

function ActivityIcon({ status }: { status: CompanyInvitationStatus }) {
  if (status === "interviewing") return <PlayCircle size={18} />;
  if (status === "completed" || status === "reviewed") {
    return <CheckCircle2 size={18} />;
  }
  if (status === "materials_submitted" || status === "analyzing") {
    return <FileCheck2 size={18} />;
  }
  if (status === "interrupted" || status === "expired") {
    return <CircleAlert size={18} />;
  }
  return <ScanSearch size={18} />;
}

function DashboardEmpty({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className={EMPTY}>
      <CheckCircle2 size={22} aria-hidden="true" />
      <div>
        <strong className="text-[11px] text-ink">{title}</strong>
        <p className="mt-[3px] text-[9px]">{description}</p>
      </div>
    </div>
  );
}

function buildCalendarEvents(
  positions: readonly CompanyPosition[],
): CalendarEvent[] {
  return positions.flatMap((position) => {
    const items: CalendarEvent[] = [];
    if (position.recruitmentStartAt) {
      items.push({
        id: `${position.positionId}-start`,
        dateKey: position.recruitmentStartAt,
        kind: "start",
        label: "시작",
        position,
      });
    }
    if (position.interviewAt) {
      items.push({
        id: `${position.positionId}-interview`,
        dateKey: toDateKey(new Date(position.interviewAt)),
        kind: "interview",
        label: "면접",
        position,
      });
    }
    if (position.recruitmentEndAt) {
      items.push({
        id: `${position.positionId}-end`,
        dateKey: position.recruitmentEndAt,
        kind: "end",
        label: "마감",
        position,
      });
    }
    return items;
  });
}

function buildApplicantActivities(
  invitations: readonly PositionedInvitation[],
): ApplicantActivity[] {
  return [...invitations]
    .sort(
      (left, right) =>
        right.rowVersion - left.rowVersion ||
        displayApplicant(left).localeCompare(displayApplicant(right), "ko-KR"),
    )
    .map((invitation) => {
      const copy = ACTIVITY_COPY[invitation.status];
      return {
        invitation,
        title: copy.title,
        detail: copy.detail,
        tone: copy.tone,
      };
    });
}

const ACTIVITY_COPY: Record<
  CompanyInvitationStatus,
  Pick<ApplicantActivity, "title" | "detail" | "tone">
> = {
  invited: {
    title: "초대 메일이 발송되었습니다.",
    detail: "지원자 응답을 기다리고 있습니다.",
    tone: "neutral",
  },
  identity_verified: {
    title: "본인 확인을 완료했습니다.",
    detail: "개인정보 활용 동의 단계로 이동했습니다.",
    tone: "progress",
  },
  consented: {
    title: "정보 활용 동의를 완료했습니다.",
    detail: "포지션별 요청 자료를 제출할 수 있습니다.",
    tone: "progress",
  },
  materials_submitted: {
    title: "필수 제출 자료를 등록했습니다.",
    detail: "설정된 자료를 기준으로 AI 분석을 준비합니다.",
    tone: "progress",
  },
  analyzing: {
    title: "지원 자료 분석을 시작했습니다.",
    detail: "면접 질문 생성을 위한 근거를 추출하고 있습니다.",
    tone: "progress",
  },
  ready: {
    title: "면접 준비가 완료되었습니다.",
    detail: "지원자가 예정된 면접을 시작할 수 있습니다.",
    tone: "success",
  },
  interviewing: {
    title: "AI 면접을 시작했습니다.",
    detail: "현재 실시간 면접 세션이 진행 중입니다.",
    tone: "progress",
  },
  interrupted: {
    title: "면접 연결이 중단되었습니다.",
    detail: "지원자의 재접속 여부를 확인해 주세요.",
    tone: "warning",
  },
  completed: {
    title: "AI 면접을 종료했습니다.",
    detail: "분석 리포트가 생성되어 담당자 검토를 기다립니다.",
    tone: "success",
  },
  reviewed: {
    title: "담당자 검토를 완료했습니다.",
    detail: "최종 판단과 근거가 기록되었습니다.",
    tone: "success",
  },
  expired: {
    title: "지원자 초대가 만료되었습니다.",
    detail: "필요하면 새 초대를 발송해 주세요.",
    tone: "warning",
  },
  revoked: {
    title: "지원자 초대를 취소했습니다.",
    detail: "해당 초대 링크는 더 이상 사용할 수 없습니다.",
    tone: "warning",
  },
  deleted: {
    title: "지원자 데이터 삭제를 완료했습니다.",
    detail: "보존 정책에 따라 관련 자료가 정리되었습니다.",
    tone: "neutral",
  },
};

function countPositions(positions: readonly CompanyPosition[], status: string) {
  return positions.filter((position) => position.status === status).length;
}

function startOfMonth(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), 1);
}

function addMonths(value: Date, amount: number) {
  return new Date(value.getFullYear(), value.getMonth() + amount, 1);
}

function calendarDays(month: Date) {
  const first = startOfMonth(month);
  const start = new Date(
    first.getFullYear(),
    first.getMonth(),
    1 - first.getDay(),
  );
  return Array.from(
    { length: 42 },
    (_, index) =>
      new Date(start.getFullYear(), start.getMonth(), start.getDate() + index),
  );
}

function toDateKey(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatMonth(value: Date) {
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
  }).format(value);
}

function formatClock(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}
