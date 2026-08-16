import {
  ArrowLeft,
  BarChart3,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  FileCheck2,
  FileText,
  ListChecks,
  Mail,
  PlayCircle,
  UserRound,
  Video,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  invitationRecruiterPhase,
  invitationStatusMeta,
  recruiterPhaseCount,
} from "../hiring/PositionInvitations";
import type { CompanyInvitation, CompanyOperationsApi } from "./types";
import { useRecruitingOperations } from "./useRecruitingOperations";

type PositionedInvitation = CompanyInvitation & { positionTitle: string };
type ApplicantReportTab = "overview" | "materials" | "interview" | "analysis";

const reportTabs: ReadonlyArray<{
  id: ApplicantReportTab;
  label: string;
}> = [
  { id: "overview", label: "종합 개요" },
  { id: "materials", label: "제출 자료" },
  { id: "interview", label: "면접 기록" },
  { id: "analysis", label: "분석 리포트" },
];

const progressMilestones = [
  { label: "초대·본인 확인", detail: "접근과 동의" },
  { label: "자료 제출·분석", detail: "지원 자료 처리" },
  { label: "면접 준비·진행", detail: "실시간 면접" },
  { label: "결과 검토", detail: "분석과 사람 검토" },
] as const;

export function ApplicantDetail({
  positionId,
  invitationId,
  api,
}: {
  positionId: string;
  invitationId: string;
  api: CompanyOperationsApi;
}) {
  const { invitations, loading, error } = useRecruitingOperations(
    api,
    positionId,
  );
  const [selectedTab, setSelectedTab] =
    useState<ApplicantReportTab>("overview");
  const invitation = invitations.find(
    (item) =>
      item.positionId === positionId && item.invitationId === invitationId,
  );

  if (loading) {
    return (
      <div className="async-state" role="status">
        지원자 정보를 불러오는 중입니다.
      </div>
    );
  }
  if (error || !invitation) {
    return (
      <div className="async-state" role="alert">
        지원자 정보를 찾을 수 없습니다.
      </div>
    );
  }

  const displayName =
    invitation.applicantDisplayName || invitation.applicantEmail.split("@")[0];
  const status = invitationStatusMeta[invitation.status];
  const recruiterPhase = invitationRecruiterPhase(invitation.status);
  const reviewPath = invitation.interviewSessionId
    ? `/review/${invitation.interviewSessionId}?invitationId=${invitation.invitationId}`
    : null;

  function moveTab(direction: -1 | 1) {
    const currentIndex = reportTabs.findIndex((tab) => tab.id === selectedTab);
    const nextIndex =
      (currentIndex + direction + reportTabs.length) % reportTabs.length;
    const nextTab = reportTabs[nextIndex];
    setSelectedTab(nextTab.id);
    window.requestAnimationFrame(() => {
      document.getElementById(`applicant-report-tab-${nextTab.id}`)?.focus();
    });
  }

  return (
    <div className="applicant-detail applicant-report">
      <header className="applicant-report__masthead">
        <Link
          to={`/positions/${positionId}`}
          className="position-operations__back"
        >
          <ArrowLeft size={14} aria-hidden="true" />
          {invitation.positionTitle}
        </Link>

        <div className="applicant-report__identity">
          <span className="applicant-report__avatar" aria-hidden="true">
            {getInitial(displayName)}
          </span>
          <div className="applicant-report__identity-copy">
            <p>지원자 종합 리포트</p>
            <h1>{displayName}</h1>
            <div>
              <span>
                <Mail size={13} aria-hidden="true" />
                {invitation.applicantEmail}
              </span>
              <span>
                <BriefcaseBusiness size={13} aria-hidden="true" />
                {invitation.positionTitle}
              </span>
            </div>
          </div>
          <span className={`invitation-status is-${status.tone}`}>
            {status.label}
          </span>
        </div>
      </header>

      <section
        className="applicant-report__metrics"
        aria-label="지원자 처리 현황"
      >
        <article
          aria-label={`현재 채용 단계 ${recruiterPhaseCount}단계 중 ${recruiterPhase}단계`}
        >
          <span>현재 채용 단계</span>
          <strong>
            {recruiterPhase || "-"}
            <small>/{recruiterPhaseCount}</small>
          </strong>
          <em>{status.label}</em>
        </article>
        <article>
          <span>자료 분석</span>
          <strong>{formatProcessingState(invitation.analysisStatus)}</strong>
          <em>{materialStateDescription(invitation.analysisStatus)}</em>
        </article>
        <article>
          <span>면접</span>
          <strong>{formatInterviewState(invitation.interviewStatus)}</strong>
          <em>{reviewPath ? "세션 연결됨" : "진행 상태 확인"}</em>
        </article>
        <article>
          <span>리포트</span>
          <strong>{formatReportState(invitation.reportStatus)}</strong>
          <em>{reviewPath ? "검토 화면 연결" : "면접 완료 후 생성"}</em>
        </article>
      </section>

      <div className="applicant-report__workspace">
        <div
          className="applicant-report__tabs"
          role="tablist"
          aria-label="지원자 리포트 메뉴"
        >
          {reportTabs.map((tab) => (
            <button
              key={tab.id}
              id={`applicant-report-tab-${tab.id}`}
              type="button"
              role="tab"
              aria-selected={selectedTab === tab.id}
              aria-controls={`applicant-report-panel-${tab.id}`}
              tabIndex={selectedTab === tab.id ? 0 : -1}
              onClick={() => setSelectedTab(tab.id)}
              onKeyDown={(event) => {
                if (event.key === "ArrowLeft") {
                  event.preventDefault();
                  moveTab(-1);
                }
                if (event.key === "ArrowRight") {
                  event.preventDefault();
                  moveTab(1);
                }
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <section
          id={`applicant-report-panel-${selectedTab}`}
          className="applicant-report__panel"
          role="tabpanel"
          aria-labelledby={`applicant-report-tab-${selectedTab}`}
          tabIndex={0}
        >
          {selectedTab === "overview" ? (
            <OverviewPanel
              invitation={invitation}
              recruiterPhase={recruiterPhase}
              reviewPath={reviewPath}
            />
          ) : null}
          {selectedTab === "materials" ? (
            <MaterialsPanel invitation={invitation} />
          ) : null}
          {selectedTab === "interview" ? (
            <InterviewPanel invitation={invitation} reviewPath={reviewPath} />
          ) : null}
          {selectedTab === "analysis" ? (
            <AnalysisPanel invitation={invitation} reviewPath={reviewPath} />
          ) : null}
        </section>
      </div>
    </div>
  );
}

function OverviewPanel({
  invitation,
  recruiterPhase,
  reviewPath,
}: {
  invitation: PositionedInvitation;
  recruiterPhase: number;
  reviewPath: string | null;
}) {
  const currentMilestone = Math.max(recruiterPhase - 1, 0);

  return (
    <div className="applicant-report__overview">
      <section className="applicant-report__section">
        <header className="applicant-report__section-heading">
          <div>
            <span className="applicant-report__section-icon" aria-hidden="true">
              <ListChecks size={18} />
            </span>
            <div>
              <h2>지원 진행 요약</h2>
              <p>지원부터 검토까지의 현재 위치를 확인합니다.</p>
            </div>
          </div>
          <strong>
            {recruiterPhase || "-"} / {recruiterPhaseCount}
          </strong>
        </header>

        <ol className="applicant-report__progress">
          {progressMilestones.map((milestone, index) => {
            const progressState =
              index < currentMilestone
                ? "is-complete"
                : index === currentMilestone
                  ? "is-current"
                  : "is-pending";
            return (
              <li key={milestone.label} className={progressState}>
                <span aria-hidden="true">
                  {index < currentMilestone ? (
                    <CheckCircle2 size={17} />
                  ) : (
                    index + 1
                  )}
                </span>
                <div>
                  <strong>{milestone.label}</strong>
                  <small>{milestone.detail}</small>
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      <aside className="applicant-report__next-action">
        <span className="applicant-report__section-icon" aria-hidden="true">
          {reviewPath ? <BarChart3 size={18} /> : <CircleDashed size={18} />}
        </span>
        <div>
          <p>채용담당자 작업</p>
          <h2>
            {reviewPath
              ? "면접 결과를 검토하세요"
              : "지원자 진행을 기다리는 중입니다"}
          </h2>
          <span>
            {reviewPath
              ? "영상, 최종 답변과 기준별 분석을 확인할 수 있습니다."
              : "현재 단계가 완료되면 다음 검토 작업이 활성화됩니다."}
          </span>
        </div>
        {reviewPath ? (
          <Link className="button-primary" to={reviewPath}>
            검토 시작
            <ChevronRight size={15} aria-hidden="true" />
          </Link>
        ) : null}
      </aside>

      <section className="applicant-report__section applicant-report__facts">
        <header className="applicant-report__section-heading">
          <div>
            <span className="applicant-report__section-icon" aria-hidden="true">
              <UserRound size={18} />
            </span>
            <div>
              <h2>지원 정보</h2>
              <p>포지션과 초대 기준 정보를 확인합니다.</p>
            </div>
          </div>
        </header>
        <dl>
          <div>
            <dt>지원 포지션</dt>
            <dd>{invitation.positionTitle}</dd>
          </div>
          <div>
            <dt>이메일</dt>
            <dd>{invitation.applicantEmail}</dd>
          </div>
          <div>
            <dt>초대 만료</dt>
            <dd>{formatDateTime(invitation.expiresAt)}</dd>
          </div>
          <div>
            <dt>면접 세션</dt>
            <dd>{invitation.interviewSessionId ? "연결됨" : "대기"}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}

function MaterialsPanel({ invitation }: { invitation: PositionedInvitation }) {
  const ready = invitation.analysisStatus === "ready";

  return (
    <div className="applicant-report__single-column">
      <ContentHeader
        icon={<FileText size={18} />}
        title="제출 자료 처리 현황"
        description="면접 질문 생성에 사용할 지원 자료의 분석 상태입니다."
      />
      <StatusBlock
        ready={ready}
        readyIcon={<FileCheck2 size={24} />}
        title={ready ? "제출 자료 분석 완료" : "제출 자료 처리 중"}
        description={materialStateDescription(invitation.analysisStatus)}
        trailing={formatProcessingState(invitation.analysisStatus)}
      />
      <dl className="applicant-report__detail-list">
        <div>
          <dt>분석 상태</dt>
          <dd>{formatProcessingState(invitation.analysisStatus)}</dd>
        </div>
        <div>
          <dt>연결 평가기준</dt>
          <dd>{ready ? "면접 전략에 반영됨" : "분석 완료 후 연결"}</dd>
        </div>
      </dl>
    </div>
  );
}

function InterviewPanel({
  invitation,
  reviewPath,
}: {
  invitation: PositionedInvitation;
  reviewPath: string | null;
}) {
  return (
    <div className="applicant-report__single-column">
      <ContentHeader
        icon={<Video size={18} />}
        title="면접 기록과 응답"
        description="세션 상태와 영상·최종 답변 검토 가능 여부를 확인합니다."
      />
      <StatusBlock
        ready={Boolean(reviewPath)}
        readyIcon={<PlayCircle size={24} />}
        title={reviewPath ? "면접 기록 검토 가능" : "면접 기록 대기"}
        description={
          reviewPath
            ? "영상 재생과 질문별 최종 답변 타임라인을 확인할 수 있습니다."
            : "면접 세션이 완료되면 영상과 응답 기록이 연결됩니다."
        }
        trailing={
          reviewPath ? (
            <Link className="button-secondary" to={reviewPath}>
              면접 기록 열기
              <ChevronRight size={15} aria-hidden="true" />
            </Link>
          ) : null
        }
      />
      <dl className="applicant-report__detail-list">
        <div>
          <dt>면접 상태</dt>
          <dd>{formatInterviewState(invitation.interviewStatus)}</dd>
        </div>
        <div>
          <dt>세션 연결</dt>
          <dd>{invitation.interviewSessionId ? "연결됨" : "대기"}</dd>
        </div>
      </dl>
    </div>
  );
}

function AnalysisPanel({
  invitation,
  reviewPath,
}: {
  invitation: PositionedInvitation;
  reviewPath: string | null;
}) {
  const ready = invitation.reportStatus === "ready" && Boolean(reviewPath);

  return (
    <div className="applicant-report__single-column">
      <ContentHeader
        icon={<BarChart3 size={18} />}
        title="면접 분석 리포트"
        description="평가기준별 분석과 실제 답변 Evidence의 준비 상태입니다."
      />
      <StatusBlock
        ready={ready}
        readyIcon={<CheckCircle2 size={24} />}
        title={ready ? "분석 리포트 준비 완료" : "분석 리포트 대기"}
        description={
          ready
            ? "AI 분석과 답변 근거를 함께 확인하고 사람의 검토를 기록할 수 있습니다."
            : "면접 완료와 후처리 이후 분석 리포트가 생성됩니다."
        }
        trailing={
          ready && reviewPath ? (
            <Link className="button-primary" to={reviewPath}>
              전체 분석 리포트 열기
              <ChevronRight size={15} aria-hidden="true" />
            </Link>
          ) : null
        }
      />
      <dl className="applicant-report__detail-list">
        <div>
          <dt>리포트 상태</dt>
          <dd>{formatReportState(invitation.reportStatus)}</dd>
        </div>
        <div>
          <dt>검토 가능 범위</dt>
          <dd>{ready ? "영상·응답·기준별 분석" : "생성 대기"}</dd>
        </div>
      </dl>
    </div>
  );
}

function ContentHeader({
  icon,
  title,
  description,
}: {
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <header className="applicant-report__content-header">
      <span className="applicant-report__section-icon" aria-hidden="true">
        {icon}
      </span>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
    </header>
  );
}

function StatusBlock({
  ready,
  readyIcon,
  title,
  description,
  trailing,
}: {
  ready: boolean;
  readyIcon: ReactNode;
  title: string;
  description: string;
  trailing: ReactNode;
}) {
  return (
    <div
      className={`applicant-report__status-block ${ready ? "is-ready" : ""}`}
    >
      {ready ? readyIcon : <CircleDashed size={24} aria-hidden="true" />}
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
      {trailing ? <span>{trailing}</span> : null}
    </div>
  );
}

function getInitial(value: string) {
  return value.trim().slice(0, 1).toUpperCase() || "A";
}

function formatProcessingState(value?: string | null) {
  if (value === "ready") return "완료";
  if (value === "analyzing" || value === "processing") return "분석 중";
  if (value === "failed") return "확인 필요";
  return "대기";
}

function materialStateDescription(value?: string | null) {
  if (value === "ready") return "제출 자료가 면접 질문 생성에 연결되었습니다.";
  if (value === "analyzing" || value === "processing") {
    return "제출 자료를 분석하고 검색 가능한 형태로 처리하고 있습니다.";
  }
  if (value === "failed") return "처리하지 못한 자료를 확인해야 합니다.";
  return "지원자가 자료를 제출하면 분석이 시작됩니다.";
}

function formatInterviewState(value?: string | null) {
  if (value === "completed") return "완료";
  if (value === "interviewing") return "진행 중";
  if (value === "interrupted") return "재접속 필요";
  if (value === "ready") return "준비 완료";
  return "대기";
}

function formatReportState(value?: string | null) {
  if (value === "ready") return "분석 완료";
  if (value === "processing") return "생성 중";
  if (value === "failed") return "확인 필요";
  return "대기";
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
