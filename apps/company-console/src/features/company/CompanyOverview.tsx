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
    <div className="company-overview">
      <header className="page-header dashboard-heading">
        <div>
          <h1>채용 운영 대시보드</h1>
          <p>포지션, 면접, 검토 현황과 최근 운영 기록을 한눈에 확인하세요.</p>
        </div>
        <Link className="button-primary" to="/hiring">
          <Plus size={16} aria-hidden="true" />새 채용 관리
        </Link>
      </header>

      <div className="page-content company-overview__content">
        {loading ? (
          <div className="async-state panel" role="status">
            <p>채용 운영 현황을 불러오는 중입니다.</p>
          </div>
        ) : error ? (
          <div className="async-state panel" role="alert">
            <p>채용 운영 데이터를 불러오지 못했습니다.</p>
          </div>
        ) : (
          <>
            <section className="operations-metrics" aria-label="채용 핵심 지표">
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

            <div className="operations-dashboard-grid">
              <main className="operations-dashboard-main">
                <section className="panel dashboard-position-status">
                  <header className="section-header">
                    <div>
                      <h2>포지션 현황</h2>
                      <p>포지션별 지원자와 면접·검토 진행 상태입니다.</p>
                    </div>
                    <Link to="/positions">전체 포지션</Link>
                  </header>

                  <div className="dashboard-position-summary">
                    <span>
                      운영 중 <strong>{activePositions.length}</strong>
                    </span>
                    <span>
                      초안{" "}
                      <strong>
                        {
                          positions.filter(
                            (position) => position.status === "draft",
                          ).length
                        }
                      </strong>
                    </span>
                    <span>
                      종료{" "}
                      <strong>
                        {
                          positions.filter(
                            (position) => position.status === "closed",
                          ).length
                        }
                      </strong>
                    </span>
                  </div>

                  {positions.length ? (
                    <div className="dashboard-position-list">
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

                <section className="panel priority-applicants">
                  <header className="section-header">
                    <div>
                      <h2>오늘 확인할 업무</h2>
                      <p>검토 대기 또는 운영 확인이 필요한 지원자입니다.</p>
                    </div>
                  </header>
                  {priorityInvitations.length ? (
                    <div className="priority-applicant-list">
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

              <aside className="operations-dashboard-side">
                <section className="panel recent-activity">
                  <header className="section-header">
                    <div>
                      <h2>최근 활동</h2>
                      <p>실제 생성 시점이 기록된 채용 운영 내역입니다.</p>
                    </div>
                  </header>
                  {recentActivities.length ? (
                    <ol className="recent-activity-list">
                      {recentActivities.map((activity) => (
                        <li key={activity.id}>
                          <span
                            className={`recent-activity__icon is-${activity.kind}`}
                            aria-hidden="true"
                          >
                            <BriefcaseBusiness size={15} />
                          </span>
                          <div>
                            <Link to={activity.to}>{activity.label}</Link>
                            <small>{activity.detail}</small>
                          </div>
                          <time dateTime={activity.occurredAt}>
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

                <section className="panel stage-distribution">
                  <header className="section-header">
                    <div>
                      <h2>지원자 단계</h2>
                      <p>전체 {summary.total}명의 현재 분포입니다.</p>
                    </div>
                  </header>
                  <div className="stage-distribution__list">
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
                  <Link className="panel-link-button" to="/positions">
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
  tone?: "purple" | "blue" | "green" | "orange";
}) {
  return (
    <article
      aria-label={`${label} ${value}${unit}`}
      className={`panel operations-metric is-${tone}`}
    >
      <span aria-hidden="true">{icon}</span>
      <div>
        <small>{label}</small>
        <strong>
          {value}
          <em>{unit}</em>
        </strong>
        <p>{detail}</p>
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
    <Link
      className="dashboard-position-row"
      to={`/positions/${position.positionId}`}
    >
      <span className="dashboard-position-row__icon" aria-hidden="true">
        <BriefcaseBusiness size={16} />
      </span>
      <div className="dashboard-position-row__content">
        <div>
          <strong>{position.title}</strong>
          <span className={`status-badge ${statusTone(position.status)}`}>
            {statusLabel(position.status)}
          </span>
        </div>
        <small>{position.description}</small>
      </div>
      <dl className="dashboard-position-row__stats">
        <div>
          <dt>지원자</dt>
          <dd>{invitations.length}</dd>
        </div>
        <div>
          <dt>면접 중</dt>
          <dd>{interviews}</dd>
        </div>
        <div>
          <dt>검토 대기</dt>
          <dd>{reviews}</dd>
        </div>
        <div>
          <dt>완료</dt>
          <dd>{completed}</dd>
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
    <Link to={position ? `/positions/${position.positionId}` : "/positions"}>
      <span className="priority-applicant__avatar" aria-hidden="true">
        {displayApplicant(invitation).slice(0, 1)}
      </span>
      <span>
        <strong>{displayApplicant(invitation)}</strong>
        <small>{position?.title ?? invitation.positionTitle}</small>
      </span>
      <span className={`invitation-status is-${status.tone}`}>
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
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      <i aria-label={`${label} ${ratio}%`}>
        <span style={{ width: `${ratio}%` }} />
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
    <div className="operations-empty">
      <CheckCircle2 size={22} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
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
