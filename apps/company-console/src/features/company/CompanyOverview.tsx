import {
  ArrowRight,
  BriefcaseBusiness,
  CheckCircle2,
  ClipboardCheck,
  Plus,
  Video,
} from "lucide-react";
import type { ReactNode } from "react";
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
import {
  formatActivityTime,
  statusLabel,
  statusTone,
} from "./companyFormatters";
import {
  displayApplicant,
  invitationProjection,
  summarizeInvitations,
} from "./recruitingState";
import type { CompanyOperationsApi, CompanyPosition } from "./types";
import {
  type PositionedInvitation,
  useRecruitingOperations,
} from "./useRecruitingOperations";

const ACTIVE_POSITION_STATUSES = new Set(["active", "open", "published"]);
const LIVE_INTERVIEW_STATUSES = new Set(["interviewing"]);
const REVIEW_PENDING_STATUSES = new Set(["completed"]);
const COMPLETED_INTERVIEW_STATUSES = new Set(["reviewed"]);

// `.dashboard-heading` and `.company-overview__content` only adjust the shared page padding.
const HEADING = `${PAGE_HEADER} pb-2.5`;
const CONTENT = `${PAGE_CONTENT} grid gap-[22px] pt-3`;
const SECTION_HEADER_LINK =
  "inline-flex items-center gap-1 text-[10px] text-brand";
// `.panel h2` is `13px` inside `.section-header`.
const SECTION_HEADER_TITLE = "text-[13px]";
// `.company-overview .panel` keeps the shared box; only `.dashboard-*` panels clip content.
const OVERVIEW_PANEL = `${PANEL} overflow-hidden`;

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
const METRIC_LABEL = "truncate text-[9px] text-muted";
const METRIC_VALUE = "font-mono text-[23px] leading-[1.15] text-ink";
const METRIC_UNIT =
  "ml-[3px] font-sans text-[10px] font-semibold not-italic text-muted";

const DASHBOARD_GRID =
  "grid grid-cols-[minmax(0,1fr)_270px] items-start gap-[14px]" +
  " mw-1050:grid-cols-[minmax(0,1fr)]";
const DASHBOARD_MAIN = "grid gap-[14px]";
const DASHBOARD_SIDE =
  "grid gap-[14px] mw-1050:grid-cols-2 mw-620:grid-cols-[minmax(0,1fr)]";

const POSITION_SUMMARY =
  "flex gap-2 border-b border-b-border-muted bg-surface-muted px-[15px] py-3";
const POSITION_SUMMARY_PILL =
  "inline-flex min-h-[26px] items-center gap-[5px] rounded-full border" +
  " border-border-muted bg-surface px-[9px] text-[9px] text-muted";
const POSITION_SUMMARY_VALUE = "font-mono text-[10px] text-ink";

const POSITION_ROW =
  "grid min-h-19 items-center gap-3 px-[15px] py-3 text-inherit" +
  " grid-cols-[34px_minmax(0,1fr)_minmax(250px,auto)_16px]" +
  " not-first:border-t not-first:border-t-border-muted hover:bg-surface-muted" +
  " mw-760:grid-cols-[34px_minmax(0,1fr)_16px]";
const ROW_MARK =
  "grid size-[34px] place-items-center rounded-[10px] bg-brand-soft text-brand";
const ROW_CONTENT = "grid min-w-0 gap-1";
const ROW_TITLE_LINE = "flex min-w-0 items-center gap-2";
const ROW_TITLE = "truncate text-[11px]";
const ROW_TEXT = "text-[9px] text-muted";
const ROW_STATS =
  "grid min-w-[250px] grid-cols-[repeat(4,minmax(48px,1fr))]" +
  " mw-760:col-[2/-1] mw-760:w-full mw-760:min-w-0 mw-760:grid-cols-4";
const ROW_STAT =
  "grid gap-0.5 border-l border-l-border-muted px-2.5 text-center";
const ROW_STAT_LABEL = "text-[8px] text-muted";
const ROW_STAT_VALUE = "font-mono text-[12px] font-bold text-ink";

const PRIORITY_ROW =
  "grid min-h-[62px] grid-cols-[34px_minmax(0,1fr)_auto_16px] items-center" +
  " gap-2.5 px-[15px] py-2.5 text-inherit not-first:border-t" +
  " not-first:border-t-border-muted hover:bg-surface-muted" +
  " mw-620:grid-cols-[34px_minmax(0,1fr)_auto] mw-620:[&>svg]:hidden";
const PRIORITY_AVATAR =
  "grid size-[34px] place-items-center rounded-[10px] bg-brand-soft text-[11px]" +
  " font-bold text-brand";
const PRIORITY_IDENTITY = "grid min-w-0 gap-0.5";
const PRIORITY_NAME = "truncate text-[11px]";
const PRIORITY_POSITION = "text-[9px] text-muted";

// `list-style: none` and the zeroed margin are what preflight already applies to `ol`.
const ACTIVITY_LIST = "grid py-1";
const ACTIVITY_ITEM =
  "grid grid-cols-[30px_minmax(0,1fr)] gap-2.5 px-[14px] py-[11px]" +
  " not-first:border-t not-first:border-t-border-muted";
/*
 * The markup passed `is-${activity.kind}`, but the only `.is-position` rule in the bundle is
 * scoped to `.template-scope`, so every activity icon rendered in the base purple.
 */
const ACTIVITY_MARK =
  "grid size-[30px] place-items-center rounded-[9px] bg-brand-soft text-brand";
const ACTIVITY_BODY = "grid min-w-0 gap-0.5";
const ACTIVITY_LINK = "truncate text-[10px] font-[650] text-ink";
const ACTIVITY_TEXT = "text-[8px] text-muted";
const ACTIVITY_TIME = "col-[2] mt-0.5 truncate text-[8px] text-muted";

const STAGE_LIST = "grid gap-[13px] p-[15px]";
const STAGE_ROW =
  "grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2.5 gap-y-1.5";
const STAGE_LABEL = "text-[9px] text-muted";
const STAGE_VALUE = "font-mono text-[10px]";
const STAGE_TRACK =
  "col-[1/-1] block h-[5px] overflow-hidden rounded-full bg-surface-strong";
const STAGE_FILL = "block h-full rounded-[inherit] bg-brand";

const PANEL_LINK =
  "m-[0_14px_14px] flex min-h-[34px] items-center justify-between rounded-lg" +
  " border border-border bg-surface px-[11px] text-[9px] font-[650] text-ink" +
  " hover:border-brand hover:text-brand";

const EMPTY =
  "flex min-h-22 items-center justify-center gap-[11px] p-[18px] text-left" +
  " text-muted";
const EMPTY_TITLE = "text-[11px] text-ink";
const EMPTY_TEXT = "mt-[3px] text-[9px]";

export function CompanyOverview({ api }: { api: CompanyOperationsApi }) {
  const { positions, invitations, loading, error } =
    useRecruitingOperations(api);
  const summary = summarizeInvitations(invitations);
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
  const priorityInvitations = invitations
    .filter((invitation) =>
      ["review", "attention"].includes(
        invitationProjection(invitation.status).stage,
      ),
    )
    .slice(0, 6);
  const recentActivities = buildRecentActivities(positions).slice(0, 6);

  return (
    <div>
      <header className={HEADING}>
        <div>
          <h1 className={PAGE_HEADER_TITLE}>채용 운영 대시보드</h1>
          <p className={PAGE_HEADER_TEXT}>
            포지션, 면접, 검토 현황과 최근 운영 기록을 한눈에 확인하세요.
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
                detail="현재 실시간 면접 세션"
                tone="blue"
              />
              <OperationsMetric
                icon={<ClipboardCheck />}
                label="검토 대기"
                value={reviewsPending.length}
                unit="건"
                detail="사람의 판단이 필요합니다"
                tone="orange"
              />
              <OperationsMetric
                icon={<CheckCircle2 />}
                label="완료된 면접"
                value={completedInterviews.length}
                unit="건"
                detail="사람 검토까지 완료"
                tone="green"
              />
            </section>

            <div className={DASHBOARD_GRID}>
              <main className={DASHBOARD_MAIN}>
                <section className={OVERVIEW_PANEL}>
                  <header className={SECTION_HEADER}>
                    <div>
                      <h2 className={SECTION_HEADER_TITLE}>포지션 현황</h2>
                      <p className={SECTION_HEADER_TEXT}>
                        포지션별 지원자와 면접·검토 진행 상태입니다.
                      </p>
                    </div>
                    <Link className={SECTION_HEADER_LINK} to="/positions">
                      전체 포지션
                    </Link>
                  </header>

                  <div className={POSITION_SUMMARY}>
                    <span className={POSITION_SUMMARY_PILL}>
                      운영 중{" "}
                      <strong className={POSITION_SUMMARY_VALUE}>
                        {activePositions.length}
                      </strong>
                    </span>
                    <span className={POSITION_SUMMARY_PILL}>
                      초안{" "}
                      <strong className={POSITION_SUMMARY_VALUE}>
                        {
                          positions.filter(
                            (position) => position.status === "draft",
                          ).length
                        }
                      </strong>
                    </span>
                    <span className={POSITION_SUMMARY_PILL}>
                      종료{" "}
                      <strong className={POSITION_SUMMARY_VALUE}>
                        {
                          positions.filter(
                            (position) => position.status === "closed",
                          ).length
                        }
                      </strong>
                    </span>
                  </div>

                  {positions.length ? (
                    <div className="grid">
                      {positions.slice(0, 6).map((position) => (
                        <PositionStatusRow
                          key={position.positionId}
                          position={position}
                          invitations={invitations.filter(
                            (invitation) =>
                              invitation.positionId === position.positionId,
                          )}
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

                <section className={OVERVIEW_PANEL}>
                  <header className={SECTION_HEADER}>
                    <div>
                      <h2 className={SECTION_HEADER_TITLE}>오늘 확인할 업무</h2>
                      <p className={SECTION_HEADER_TEXT}>
                        검토 대기 또는 운영 확인이 필요한 지원자입니다.
                      </p>
                    </div>
                  </header>
                  {priorityInvitations.length ? (
                    <div className="grid">
                      {priorityInvitations.map((invitation) => (
                        <PriorityApplicant
                          key={invitation.invitationId}
                          invitation={invitation}
                          positions={positions}
                        />
                      ))}
                    </div>
                  ) : (
                    <DashboardEmpty
                      title="지금 바로 처리할 업무가 없습니다."
                      description="면접 완료나 재접속 필요 상태가 생기면 여기에 표시됩니다."
                    />
                  )}
                </section>
              </main>

              <aside className={DASHBOARD_SIDE}>
                <section className={OVERVIEW_PANEL}>
                  <header className={SECTION_HEADER}>
                    <div>
                      <h2 className={SECTION_HEADER_TITLE}>최근 활동</h2>
                      <p className={SECTION_HEADER_TEXT}>
                        실제 생성 시점이 기록된 채용 운영 내역입니다.
                      </p>
                    </div>
                  </header>
                  {recentActivities.length ? (
                    <ol className={ACTIVITY_LIST}>
                      {recentActivities.map((activity) => (
                        <li className={ACTIVITY_ITEM} key={activity.id}>
                          <span className={ACTIVITY_MARK} aria-hidden="true">
                            <BriefcaseBusiness size={15} />
                          </span>
                          <div className={ACTIVITY_BODY}>
                            <Link className={ACTIVITY_LINK} to={activity.to}>
                              {activity.label}
                            </Link>
                            <small className={ACTIVITY_TEXT}>
                              {activity.detail}
                            </small>
                          </div>
                          <time
                            className={ACTIVITY_TIME}
                            dateTime={activity.occurredAt}
                          >
                            {formatActivityTime(activity.occurredAt)}
                          </time>
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <DashboardEmpty
                      title="최근 활동이 없습니다."
                      description="포지션을 만들면 활동 기록이 표시됩니다."
                    />
                  )}
                </section>

                <section className={OVERVIEW_PANEL}>
                  <header className={SECTION_HEADER}>
                    <div>
                      <h2 className={SECTION_HEADER_TITLE}>지원자 단계</h2>
                      <p className={SECTION_HEADER_TEXT}>
                        전체 {summary.total}명의 현재 분포입니다.
                      </p>
                    </div>
                  </header>
                  <div className={STAGE_LIST}>
                    <StageDistributionRow
                      label="응답 대기"
                      value={summary.waiting}
                      total={summary.total}
                    />
                    <StageDistributionRow
                      label="자료 준비"
                      value={summary.materials}
                      total={summary.total}
                    />
                    <StageDistributionRow
                      label="면접 준비·진행"
                      value={summary.interview}
                      total={summary.total}
                    />
                    <StageDistributionRow
                      label="검토 대기"
                      value={summary.review}
                      total={summary.total}
                    />
                    <StageDistributionRow
                      label="검토 완료"
                      value={summary.reviewed}
                      total={summary.total}
                    />
                  </div>
                  <Link className={PANEL_LINK} to="/positions">
                    지원자 운영 보기 <ArrowRight size={14} aria-hidden="true" />
                  </Link>
                </section>
              </aside>
            </div>
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
        <small className={METRIC_LABEL}>{label}</small>
        <strong className={METRIC_VALUE}>
          {value}
          <em className={METRIC_UNIT}>{unit}</em>
        </strong>
        <p className="text-[9px] text-muted">{detail}</p>
      </div>
    </article>
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
      <span className={ROW_MARK} aria-hidden="true">
        <BriefcaseBusiness size={16} />
      </span>
      <div className={ROW_CONTENT}>
        <div className={ROW_TITLE_LINE}>
          <strong className={ROW_TITLE}>{position.title}</strong>
          <span
            className={`${STATUS_BADGE} ${STATUS_BADGE_TONE[statusTone(position.status)]}`}
          >
            {statusLabel(position.status)}
          </span>
        </div>
        <small className={ROW_TEXT}>{position.description}</small>
      </div>
      <dl className={ROW_STATS}>
        <div className={ROW_STAT}>
          <dt className={ROW_STAT_LABEL}>지원자</dt>
          <dd className={ROW_STAT_VALUE}>{invitations.length}</dd>
        </div>
        <div className={ROW_STAT}>
          <dt className={ROW_STAT_LABEL}>면접 중</dt>
          <dd className={ROW_STAT_VALUE}>{interviews}</dd>
        </div>
        <div className={ROW_STAT}>
          <dt className={ROW_STAT_LABEL}>검토 대기</dt>
          <dd className={ROW_STAT_VALUE}>{reviews}</dd>
        </div>
        <div className={ROW_STAT}>
          <dt className={ROW_STAT_LABEL}>완료</dt>
          <dd className={ROW_STAT_VALUE}>{completed}</dd>
        </div>
      </dl>
      <ArrowRight size={15} aria-hidden="true" />
    </Link>
  );
}

function PriorityApplicant({
  invitation,
  positions,
}: {
  invitation: PositionedInvitation;
  positions: readonly CompanyPosition[];
}) {
  const status = invitationProjection(invitation.status);
  const position = positions.find(
    (item) => item.positionId === invitation.positionId,
  );

  return (
    <Link
      className={PRIORITY_ROW}
      to={position ? `/positions/${position.positionId}` : "/positions"}
    >
      <span className={PRIORITY_AVATAR} aria-hidden="true">
        {displayApplicant(invitation).slice(0, 1)}
      </span>
      <span className={PRIORITY_IDENTITY}>
        <strong className={PRIORITY_NAME}>
          {displayApplicant(invitation)}
        </strong>
        <small className={PRIORITY_POSITION}>
          {position?.title ?? invitation.positionTitle}
        </small>
      </span>
      <span className={`${INVITATION_STATUS} ${invitationTone(status.tone)}`}>
        {status.label}
      </span>
      <ArrowRight size={15} aria-hidden="true" />
    </Link>
  );
}

function StageDistributionRow({
  label,
  value,
  total,
}: {
  label: string;
  value: number;
  total: number;
}) {
  const ratio = total ? Math.round((value / total) * 100) : 0;

  return (
    <div className={STAGE_ROW}>
      <span className={STAGE_LABEL}>{label}</span>
      <strong className={STAGE_VALUE}>{value}</strong>
      <i className={STAGE_TRACK} aria-label={`${label} ${ratio}%`}>
        <span className={STAGE_FILL} style={{ width: `${ratio}%` }} />
      </i>
    </div>
  );
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
        <strong className={EMPTY_TITLE}>{title}</strong>
        <p className={EMPTY_TEXT}>{description}</p>
      </div>
    </div>
  );
}

type RecentActivity = Readonly<{
  id: string;
  kind: "position";
  label: string;
  detail: string;
  occurredAt: string;
  to: string;
}>;

function buildRecentActivities(
  positions: readonly CompanyPosition[],
): RecentActivity[] {
  const activities: RecentActivity[] = positions.map((position) => ({
    id: `position-${position.positionId}`,
    kind: "position" as const,
    label: `${position.title} 포지션 생성`,
    detail: statusLabel(position.status),
    occurredAt: position.createdAt,
    to: `/positions/${position.positionId}`,
  }));

  return [...activities].sort(
    (left, right) =>
      new Date(right.occurredAt).getTime() -
      new Date(left.occurredAt).getTime(),
  );
}
