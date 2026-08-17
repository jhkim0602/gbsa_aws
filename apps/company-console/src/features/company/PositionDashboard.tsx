import { ArrowRight, ClipboardCheck, Route, Target, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { interviewLevelLabels, invitationStatusMeta } from "../hiring";
import { summarizeApplicantPipeline } from "./applicantSummary";
import {
  countAttentionInvitations,
  countAwaitingInvitations,
  recruiterStages,
  type PositionTab,
} from "./positionWorkspaceModel";
import type {
  CompanyCriterionVersion,
  CompanyInvitation,
  CompanyPosition,
} from "./types";

export function PositionDashboard({
  position,
  invitations,
  criteria,
  phaseCounts,
  onOpenTab,
}: {
  position: CompanyPosition;
  invitations: readonly CompanyInvitation[];
  criteria: CompanyCriterionVersion | null;
  phaseCounts: readonly number[];
  onOpenTab(tab: PositionTab): void;
}) {
  const summary = summarizeApplicantPipeline(invitations);
  const attention = countAttentionInvitations(invitations);
  const awaiting = countAwaitingInvitations(invitations);
  const recentInvitations = invitations.slice(0, 5);

  return (
    <section
      className="position-dashboard"
      aria-labelledby="position-dashboard-title"
    >
      <header className="position-dashboard__heading">
        <div>
          <p>POSITION OVERVIEW</p>
          <h2 id="position-dashboard-title">지원자 운영 현황</h2>
          <span>현재 포지션의 지원자, 초대, 면접 준비 상태를 요약합니다.</span>
        </div>
        <button
          className="position-dashboard__detail"
          type="button"
          onClick={() => onOpenTab("statistics")}
          aria-label="지원자 통계 상세 보기"
        >
          통계 상세 보기
          <ArrowRight size={14} aria-hidden="true" />
        </button>
      </header>

      <div
        className="position-dashboard__metrics"
        aria-label="지원자 핵심 현황"
      >
        <DashboardMetric
          label="전체 지원자"
          value={summary.total}
          icon={<Users size={17} />}
        />
        <DashboardMetric
          label="진행 중"
          value={summary.inProgress}
          icon={<Route size={17} />}
        />
        <DashboardMetric
          label="검토 대기"
          value={summary.reviewPending}
          icon={<ClipboardCheck size={17} />}
        />
        <DashboardMetric
          label="검토 완료"
          value={summary.completed}
          icon={<Target size={17} />}
        />
        <div className="position-dashboard__target">
          <span>채용 목표</span>
          <strong>{position.headcount ?? "미정"}</strong>
          <small>{position.headcount ? "명" : ""}</small>
        </div>
      </div>

      <div className="position-dashboard__body">
        <section className="position-dashboard__applicants">
          <DashboardSectionHeader
            title="최근 지원자"
            description="최근 등록된 지원자의 현재 진행 상태입니다."
            actionLabel="지원자 목록 상세 보기"
            onAction={() => onOpenTab("applicants")}
          />
          {recentInvitations.length ? (
            <div className="position-dashboard__applicant-list">
              {recentInvitations.map((invitation) => {
                const displayName =
                  invitation.applicantDisplayName ||
                  invitation.applicantEmail.split("@")[0];
                const status = invitationStatusMeta[invitation.status];
                return (
                  <div key={invitation.invitationId}>
                    <span className="recipient-avatar" aria-hidden="true">
                      {displayName.slice(0, 1)}
                    </span>
                    <span>
                      <Link
                        to={`/positions/${position.positionId}/applicants/${invitation.invitationId}`}
                        aria-label={`${displayName} 종합 리포트`}
                      >
                        <strong>{displayName}</strong>
                      </Link>
                      <small>{invitation.applicantEmail}</small>
                    </span>
                    <span className={`invitation-status is-${status.tone}`}>
                      {status.label}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="position-dashboard__empty">
              등록된 지원자가 없습니다.
            </div>
          )}
        </section>

        <aside className="position-dashboard__side">
          <section className="position-dashboard__invites">
            <DashboardSectionHeader
              title="초대 현황"
              description="발송과 응답 대기 상태를 확인합니다."
              actionLabel="초대 관리 상세 보기"
              onAction={() => onOpenTab("applicants")}
            />
            <dl>
              <div>
                <dt>전체 등록</dt>
                <dd>{summary.total}명</dd>
              </div>
              <div>
                <dt>응답 대기</dt>
                <dd>{awaiting}명</dd>
              </div>
              <div>
                <dt>확인 필요</dt>
                <dd>{attention}명</dd>
              </div>
            </dl>
          </section>

          <section className="position-dashboard__stages">
            <DashboardSectionHeader
              title="단계 분포"
              description="네 단계 기준의 현재 인원입니다."
              actionLabel="면접 단계 상세 보기"
              onAction={() => onOpenTab("stages")}
            />
            <div>
              {recruiterStages.map((stage, index) => {
                const count = phaseCounts[index] ?? 0;
                const percentage = summary.total
                  ? Math.round((count / summary.total) * 100)
                  : 0;
                return (
                  <div key={stage.phase}>
                    <span>{stage.title}</span>
                    <i aria-label={`${stage.title} ${count}명`}>
                      <b style={{ width: `${percentage}%` }} />
                    </i>
                    <strong>{count}</strong>
                  </div>
                );
              })}
            </div>
          </section>
        </aside>
      </div>

      <section className="position-dashboard__criteria">
        <DashboardSectionHeader
          title="면접 기준 요약"
          description="현재 면접 질문과 검토에 적용되는 중점 항목입니다."
          actionLabel="포지션 정보 상세 보기"
          onAction={() => onOpenTab("information")}
        />
        {criteria ? (
          <div className="position-dashboard__criteria-grid">
            <div>
              <span>면접 시간</span>
              <strong>{criteria.interviewDurationMinutes}분</strong>
            </div>
            <div>
              <span>면접 난이도</span>
              <strong>
                {interviewLevelLabels[criteria.interviewLevel].name}
              </strong>
            </div>
            <div>
              <span>직무 요구사항</span>
              <strong>{criteria.jobRequirements.length}개</strong>
            </div>
            <div className="position-dashboard__criteria-list">
              {criteria.criteria.slice(0, 4).map((criterion) => (
                <span key={criterion.code}>
                  <b>{criterion.name}</b>
                  <small>가중치 {criterion.weight}</small>
                </span>
              ))}
            </div>
          </div>
        ) : (
          <div className="position-dashboard__empty">
            아직 저장된 면접 기준이 없습니다.
          </div>
        )}
      </section>
    </section>
  );
}

function DashboardMetric({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: ReactNode;
}) {
  return (
    <article aria-label={`${label} ${value}명`}>
      <span aria-hidden="true">{icon}</span>
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
      </div>
    </article>
  );
}

function DashboardSectionHeader({
  title,
  description,
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel: string;
  onAction(): void;
}) {
  return (
    <header className="position-dashboard__section-heading">
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      <button type="button" onClick={onAction} aria-label={actionLabel}>
        상세 보기
        <ArrowRight size={13} aria-hidden="true" />
      </button>
    </header>
  );
}
