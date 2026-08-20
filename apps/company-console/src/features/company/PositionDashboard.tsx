import { ArrowRight, ClipboardCheck, Route, Target, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  INVITATION_STATUS,
  invitationTone,
  RECIPIENT_AVATAR,
} from "../../app/styles/primitives";
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

const DASHBOARD =
  "grid overflow-hidden rounded-lg border border-border bg-surface";

const HEADING =
  "flex min-h-18 items-center justify-between gap-[18px] border-b" +
  " border-border-muted px-5 py-4 mw-720:min-h-auto mw-720:flex-col" +
  " mw-720:items-stretch mw-720:gap-3 mw-720:px-4 mw-720:py-[14px]";
const HEADING_EYEBROW =
  "text-[9px] font-bold tracking-[0.06em] text-brand uppercase";
const HEADING_TEXT = "mt-[3px] block text-[11px] leading-[1.5] text-muted";
const HEADING_ACTION =
  "inline-flex min-h-[34px] flex-none items-center justify-center gap-1.5" +
  " rounded-md border border-border bg-surface px-3 text-[11px] font-[650]" +
  " whitespace-nowrap hover:border-brand hover:bg-brand-soft hover:text-brand" +
  " mw-720:w-full";

// The metric articles and the target card share one padding rule. The right border is not
// shared: the target zeroes it, and only the articles carry the `nth-child` overrides, which
// count against the metrics row and so have to live on the child.
const METRIC_CELL = "min-w-0 p-[14px_16px] mw-720:p-3";
const METRICS =
  "grid grid-cols-5 border-b border-border-muted mw-1050:grid-cols-3" +
  " mw-760:grid-cols-2";
const METRIC =
  `${METRIC_CELL} grid grid-cols-[38px_minmax(0,1fr)] items-center gap-[11px]` +
  " border-r border-r-border-muted" +
  " mw-1050:nth-[-n+3]:border-b mw-1050:nth-[-n+3]:border-b-border-muted" +
  " mw-1050:nth-3:border-r-0" +
  " mw-760:nth-[-n+4]:border-b mw-760:nth-[-n+4]:border-b-border-muted" +
  " mw-760:nth-3:border-r mw-760:nth-[2n]:border-r-0" +
  " mw-720:grid-cols-[32px_minmax(0,1fr)] mw-720:gap-2.5";
const METRIC_ICON =
  "grid size-[38px] place-items-center rounded-panel bg-brand-soft text-brand" +
  " mw-720:size-8";
const METRIC_LABEL = "truncate text-[10px] text-muted";
const METRIC_VALUE = "truncate font-mono text-[23px] leading-[1.15]";
const TARGET =
  `${METRIC_CELL} grid grid-cols-[auto_minmax(0,1fr)] content-center` +
  " gap-x-[5px] gap-y-0.5 bg-surface-muted mw-1050:col-[2/-1] mw-760:col-[1/-1]";

const BODY =
  "grid grid-cols-[minmax(0,1.6fr)_minmax(260px,0.4fr)]" +
  " mw-1050:grid-cols-[minmax(0,1fr)]";
const APPLICANTS =
  "flex min-w-0 flex-col border-r border-r-border-muted mw-1050:border-r-0" +
  " mw-1050:border-b mw-1050:border-b-border-muted";
const SIDE =
  "grid min-w-0 content-start mw-1050:grid-cols-2" +
  " mw-720:grid-cols-[minmax(0,1fr)]";
const INVITES =
  "min-w-0 border-b border-b-border-muted mw-1050:border-r" +
  " mw-1050:border-r-border-muted mw-1050:border-b-0 mw-720:border-r-0" +
  " mw-720:border-b";

const SECTION_HEADING =
  "flex min-h-[58px] items-center justify-between gap-3 border-b" +
  " border-border-muted px-5 py-3 mw-720:min-h-[52px] mw-720:gap-2.5" +
  " mw-720:px-4";
const SECTION_HEADING_ACTION =
  "inline-flex min-h-[30px] flex-none items-center justify-center gap-1" +
  " rounded-md border border-border-muted bg-surface px-2.5 text-[10px]" +
  " font-[650] whitespace-nowrap text-brand hover:border-brand" +
  " hover:bg-brand-soft hover:text-brand-strong";

const APPLICANT_ROW =
  "grid min-h-14 grid-cols-[38px_minmax(0,1fr)_minmax(62px,auto)] items-center" +
  " gap-3 px-5 py-2 not-first:border-t not-first:border-t-border-muted" +
  " hover:bg-surface-muted mw-720:grid-cols-[38px_minmax(0,1fr)_auto]" +
  " mw-720:gap-2.5 mw-720:px-4";
const EMPTY =
  "flex min-h-23 flex-auto items-center justify-center px-5 py-[18px]" +
  " text-center text-[11px] text-muted mw-720:px-4";

// `dl > div` in the invite panel and `> div > div` in the stage panel are the same row box.
const SIDE_ROW =
  "grid min-h-10 items-center gap-2.5 px-5 not-first:border-t" +
  " not-first:border-t-border-muted mw-720:px-4";
const INVITES_ROW = `${SIDE_ROW} grid-cols-[minmax(0,1fr)_auto]`;
const STAGE_ROW =
  `${SIDE_ROW} grid-cols-[78px_minmax(0,1fr)_minmax(26px,auto)]` +
  " mw-720:grid-cols-[74px_minmax(0,1fr)_minmax(26px,auto)]";
const SIDE_LABEL = "truncate text-[10px] text-muted";
const SIDE_VALUE =
  "text-right font-mono text-[12px] font-[650] whitespace-nowrap";
const STAGE_TRACK =
  "block h-1.5 min-w-0 overflow-hidden rounded-sm bg-surface-strong";
const STAGE_FILL = "block h-full min-w-[3px] rounded-[inherit] bg-brand";

const CRITERIA_GRID =
  "grid grid-cols-[repeat(3,132px)_minmax(0,1fr)] mw-1050:grid-cols-3" +
  " mw-760:grid-cols-[minmax(0,1fr)]";
const CRITERIA_CELL =
  `${METRIC_CELL} grid content-center gap-1 border-r border-r-border-muted` +
  " mw-1050:nth-3:border-r-0 mw-760:border-r-0 mw-760:border-b" +
  " mw-760:border-b-border-muted";
const CRITERIA_VALUE = "truncate font-mono text-[15px]";
const CRITERIA_LIST =
  "grid min-w-0 grid-cols-2 gap-2 px-5 py-[14px] mw-1050:col-[1/-1]" +
  " mw-1050:border-t mw-1050:border-t-border-muted mw-760:border-t-0" +
  " mw-720:grid-cols-[minmax(0,1fr)] mw-720:px-4 mw-720:py-3";
const CRITERIA_CHIP =
  "grid min-w-0 gap-0.5 rounded-md border border-border-muted bg-surface-muted" +
  " px-[11px] py-2";

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
    <section className={DASHBOARD} aria-labelledby="position-dashboard-title">
      <header className={HEADING}>
        <div className="min-w-0">
          <p className={HEADING_EYEBROW}>POSITION OVERVIEW</p>
          <h2
            className="mt-[3px] text-[15px] leading-[1.4]"
            id="position-dashboard-title"
          >
            지원자 운영 현황
          </h2>
          <span className={HEADING_TEXT}>
            현재 포지션의 지원자, 초대, 면접 준비 상태를 요약합니다.
          </span>
        </div>
        <button
          className={HEADING_ACTION}
          type="button"
          onClick={() => onOpenTab("statistics")}
          aria-label="지원자 통계 상세 보기"
        >
          통계 상세 보기
          <ArrowRight size={14} aria-hidden="true" />
        </button>
      </header>

      <div className={METRICS} aria-label="지원자 핵심 현황">
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
        <div className={TARGET}>
          <span className={`${METRIC_LABEL} col-[1/-1]`}>채용 목표</span>
          <strong className={METRIC_VALUE}>
            {position.headcount ?? "미정"}
          </strong>
          <small className="self-end pb-1 text-[10px] text-muted">
            {position.headcount ? "명" : ""}
          </small>
        </div>
      </div>

      <div className={BODY}>
        <section className={APPLICANTS}>
          <DashboardSectionHeader
            title="최근 지원자"
            description="최근 등록된 지원자의 현재 진행 상태입니다."
            actionLabel="지원자 목록 상세 보기"
            onAction={() => onOpenTab("applicants")}
          />
          {recentInvitations.length ? (
            <div className="grid">
              {recentInvitations.map((invitation) => {
                const displayName =
                  invitation.applicantDisplayName ||
                  invitation.applicantEmail.split("@")[0];
                const status = invitationStatusMeta[invitation.status];
                return (
                  <div className={APPLICANT_ROW} key={invitation.invitationId}>
                    <span className={RECIPIENT_AVATAR} aria-hidden="true">
                      {displayName.slice(0, 1)}
                    </span>
                    <span className="grid min-w-0 gap-0.5">
                      <Link
                        className="block min-w-0 hover:text-brand"
                        to={`/positions/${position.positionId}/applicants/${invitation.invitationId}`}
                        aria-label={`${displayName} 종합 리포트`}
                      >
                        <strong className="block truncate text-[12px]">
                          {displayName}
                        </strong>
                      </Link>
                      <small className="font-mono text-[10px] text-muted">
                        {invitation.applicantEmail}
                      </small>
                    </span>
                    <span
                      className={`${INVITATION_STATUS} ${invitationTone(
                        status.tone,
                      )} justify-self-end`}
                    >
                      {status.label}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className={EMPTY}>등록된 지원자가 없습니다.</div>
          )}
        </section>

        <aside className={SIDE}>
          <section className={INVITES}>
            <DashboardSectionHeader
              title="초대 현황"
              description="발송과 응답 대기 상태를 확인합니다."
              actionLabel="초대 관리 상세 보기"
              onAction={() => onOpenTab("applicants")}
            />
            <dl className="grid py-1.5">
              <div className={INVITES_ROW}>
                <dt className={SIDE_LABEL}>전체 등록</dt>
                <dd className={SIDE_VALUE}>{summary.total}명</dd>
              </div>
              <div className={INVITES_ROW}>
                <dt className={SIDE_LABEL}>응답 대기</dt>
                <dd className={SIDE_VALUE}>{awaiting}명</dd>
              </div>
              <div className={INVITES_ROW}>
                <dt className={SIDE_LABEL}>확인 필요</dt>
                <dd className={SIDE_VALUE}>{attention}명</dd>
              </div>
            </dl>
          </section>

          <section className="min-w-0">
            <DashboardSectionHeader
              title="단계 분포"
              description="네 단계 기준의 현재 인원입니다."
              actionLabel="면접 단계 상세 보기"
              onAction={() => onOpenTab("stages")}
            />
            <div className="grid py-1.5">
              {recruiterStages.map((stage, index) => {
                const count = phaseCounts[index] ?? 0;
                const percentage = summary.total
                  ? Math.round((count / summary.total) * 100)
                  : 0;
                return (
                  <div className={STAGE_ROW} key={stage.phase}>
                    <span className={SIDE_LABEL}>{stage.title}</span>
                    <i
                      className={STAGE_TRACK}
                      aria-label={`${stage.title} ${count}명`}
                    >
                      <b
                        className={STAGE_FILL}
                        style={{ width: `${percentage}%` }}
                      />
                    </i>
                    <strong className="text-right font-mono text-[12px]">
                      {count}
                    </strong>
                  </div>
                );
              })}
            </div>
          </section>
        </aside>
      </div>

      <section className="border-t border-t-border-muted">
        <DashboardSectionHeader
          title="면접 기준 요약"
          description="현재 면접 질문과 검토에 적용되는 중점 항목입니다."
          actionLabel="포지션 정보 상세 보기"
          onAction={() => onOpenTab("information")}
        />
        {criteria ? (
          <div className={CRITERIA_GRID}>
            <div className={CRITERIA_CELL}>
              <span className={SIDE_LABEL}>면접 시간</span>
              <strong className={CRITERIA_VALUE}>
                {criteria.interviewDurationMinutes}분
              </strong>
            </div>
            <div className={CRITERIA_CELL}>
              <span className={SIDE_LABEL}>면접 난이도</span>
              <strong className={CRITERIA_VALUE}>
                {interviewLevelLabels[criteria.interviewLevel].name}
              </strong>
            </div>
            <div className={CRITERIA_CELL}>
              <span className={SIDE_LABEL}>직무 요구사항</span>
              <strong className={CRITERIA_VALUE}>
                {criteria.jobRequirements.length}개
              </strong>
            </div>
            <div className={CRITERIA_LIST}>
              {criteria.criteria.slice(0, 4).map((criterion) => (
                <span className={CRITERIA_CHIP} key={criterion.code}>
                  <b className="truncate text-[11px] font-[650]">
                    {criterion.name}
                  </b>
                  <small className="truncate font-mono text-[10px] text-muted">
                    가중치 {criterion.weight}
                  </small>
                </span>
              ))}
            </div>
          </div>
        ) : (
          <div className={EMPTY}>아직 저장된 면접 기준이 없습니다.</div>
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
    <article className={METRIC} aria-label={`${label} ${value}명`}>
      <span className={METRIC_ICON} aria-hidden="true">
        {icon}
      </span>
      <div className="grid min-w-0 gap-0.5">
        <small className={METRIC_LABEL}>{label}</small>
        <strong className={METRIC_VALUE}>{value}</strong>
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
    <header className={SECTION_HEADING}>
      <div className="min-w-0">
        <h3 className="text-[13px] leading-[1.4]">{title}</h3>
        <p className="mt-[3px] text-[10px] leading-[1.5] text-muted">
          {description}
        </p>
      </div>
      <button
        className={SECTION_HEADING_ACTION}
        type="button"
        onClick={onAction}
        aria-label={actionLabel}
      >
        상세 보기
        <ArrowRight size={13} aria-hidden="true" />
      </button>
    </header>
  );
}
