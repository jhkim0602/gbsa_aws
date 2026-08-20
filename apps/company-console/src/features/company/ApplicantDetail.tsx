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
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ASYNC_STATE,
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  INVITATION_STATUS,
  invitationTone,
} from "../../app/styles/primitives";
import {
  invitationRecruiterPhase,
  invitationStatusMeta,
  recruiterPhaseCount,
} from "../hiring/PositionInvitations";
import type {
  CompanyInvitation,
  CompanyOperationsApi,
  CompanySubmission,
} from "./types";
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

// `.applicant-detail`'s 16px gap survives, but `.applicant-report` zeroes it on this element.
const REPORT = "grid gap-0 bg-[#f7f8fb] pb-12";
const MASTHEAD =
  "border-b border-b-border bg-surface p-[22px_32px_26px]" +
  " mw-620:p-[18px_16px_20px]";
// `.applicant-report__masthead .position-operations__back` only grows the base link.
const BACK_LINK =
  "mb-[18px] inline-flex items-center gap-[5px] text-[12px] text-muted" +
  " mw-620:mb-[14px]";
const IDENTITY =
  "grid grid-cols-[56px_minmax(0,1fr)_auto] items-center gap-4" +
  " mw-620:grid-cols-[46px_minmax(0,1fr)] mw-620:gap-3";
const AVATAR =
  "grid size-14 place-items-center rounded-lg border border-[#ccd3f7]" +
  " bg-[#eef0ff] text-[18px] font-[750] text-[#3f51c6] mw-620:size-[46px]";
const IDENTITY_COPY = "min-w-0";
const IDENTITY_EYEBROW = "mb-1 text-[11px] font-bold text-brand";
const IDENTITY_NAME = "text-[25px] leading-[1.2] text-ink mw-620:text-[21px]";
const IDENTITY_META =
  "mt-2 flex items-center gap-4 text-[12px] text-muted" +
  " mw-620:mt-[7px] mw-620:grid mw-620:gap-[5px]";
const IDENTITY_META_ITEM = "inline-flex min-w-0 items-center gap-1.5";
// `.applicant-report__identity > .invitation-status` only moves at 620px.
const IDENTITY_STATUS = "mw-620:col-[2] mw-620:justify-self-start";

const METRICS =
  "grid grid-cols-4 overflow-hidden rounded-lg border border-border" +
  " bg-surface m-[18px_32px_0] mw-900:grid-cols-2 mw-620:m-[12px_16px_0]";
/*
 * At 900px the grid is two wide, so the second cell drops its divider and the first row gains
 * a bottom one. `last:border-r-0` is emitted after the base width, so it still wins there.
 */
const METRIC =
  "grid content-center min-h-[98px] border-r border-r-border-muted p-[16px_20px]" +
  " last:border-r-0 mw-900:nth-2:border-r-0 mw-900:nth-[-n+2]:border-b" +
  " mw-900:nth-[-n+2]:border-b-border-muted mw-620:min-h-22 mw-620:p-[13px_14px]";
const METRIC_LABEL = "text-[11px] font-[650] text-muted";
const METRIC_VALUE =
  "mt-1.5 text-[21px] leading-[1.1] text-ink mw-620:text-[18px]";
const METRIC_UNIT = "ml-0.5 text-[12px] font-semibold text-muted";
const METRIC_NOTE = "mt-1.5 truncate text-[11px] not-italic text-ink-secondary";

const WORKSPACE =
  "overflow-hidden rounded-lg border border-border bg-surface" +
  " m-[16px_32px_0] mw-620:m-[12px_16px_0]";
const TABS =
  "flex min-h-13 gap-7 overflow-x-auto border-b border-b-border px-[22px]" +
  " mw-620:gap-[22px] mw-620:px-4";
// The underline is an always-present `::after` that only takes a colour when selected.
const TAB =
  "relative flex-none bg-transparent px-0.5 text-[13px] font-[650] text-muted" +
  " after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:content-['']" +
  " aria-selected:text-brand aria-selected:after:bg-brand" +
  " focus-visible:outline-2 focus-visible:outline-offset-[-3px]" +
  " focus-visible:outline-brand";
const PANEL =
  "min-h-[360px] p-[22px] outline-none mw-620:min-h-[340px] mw-620:p-4";

const OVERVIEW =
  "grid grid-cols-[minmax(0,1.55fr)_minmax(250px,0.75fr)] gap-4" +
  " mw-900:grid-cols-[minmax(0,1fr)]";
const SECTION = "rounded-[7px] border border-border-muted bg-surface";
const SECTION_HEADING =
  "flex min-h-18 items-center justify-between border-b border-b-border-muted" +
  " p-[14px_16px] mw-620:items-start";
const SECTION_HEADING_GROUP = "flex gap-[11px]";
const SECTION_TITLE = "text-[14px] text-ink";
const SECTION_TEXT = "mt-1 text-[11px] text-muted";
const SECTION_COUNT = "text-[15px] text-brand";
const SECTION_ICON =
  "grid size-[34px] flex-none place-items-center rounded-[7px]" +
  " bg-brand-soft text-brand";

// `list-style: none` and the zeroed margin are what preflight already applies to `ol`.
const PROGRESS =
  "grid grid-cols-4 p-[24px_18px] mw-620:grid-cols-[minmax(0,1fr)]" +
  " mw-620:gap-3 mw-620:p-[18px_16px]";
/*
 * The connector between milestones is each item's `::before`, drawn from the previous marker
 * to this one — so the first item hides it. Below 620px the list turns vertical and the
 * connector becomes a short vertical stub above the marker.
 */
const MILESTONE =
  "relative grid min-w-0 justify-items-center gap-2 text-center" +
  " before:absolute before:top-[15px] before:-left-1/2 before:right-1/2" +
  " before:h-0.5 before:content-[''] first:before:hidden" +
  " mw-620:grid-cols-[30px_minmax(0,1fr)] mw-620:gap-2.5 mw-620:text-left" +
  " mw-620:[place-items:center_start]" +
  " mw-620:before:inset-[-12px_auto_auto_14px] mw-620:before:h-3" +
  " mw-620:before:w-0.5";
const MILESTONE_DONE = `${MILESTONE} before:bg-[#8d9ae8]`;
const MILESTONE_TODO = `${MILESTONE} before:bg-border-muted`;
const MILESTONE_MARK =
  "z-1 grid size-[30px] place-items-center rounded-full text-[11px] font-bold";
const MILESTONE_MARK_TONE = {
  complete: `${MILESTONE_MARK} border border-[#4f61d7] bg-[#4f61d7] text-white`,
  // The current marker keeps the filled ground but thickens its ring instead.
  current: `${MILESTONE_MARK} border-4 border-[#dfe3ff] bg-[#4f61d7] text-white`,
  pending: `${MILESTONE_MARK} border border-border bg-surface text-muted`,
} as const;
const MILESTONE_TEXT = "mw-620:min-w-0";
const MILESTONE_LABEL = "block [overflow-wrap:anywhere] text-[11px] text-ink";
const MILESTONE_DETAIL = "mt-[3px] block text-[10px] text-muted";

/*
 * `.applicant-report__next-action` shares the section box, then becomes a column card. At
 * 900px it turns into an icon-copy-action row, and at 620px back to a top-aligned flex.
 */
const NEXT_ACTION =
  `${SECTION} flex flex-col items-start gap-[14px] bg-[#f8f9ff] p-[18px]` +
  " mw-900:grid mw-900:grid-cols-[34px_minmax(0,1fr)_auto] mw-900:items-center" +
  " mw-620:flex mw-620:items-start";
const NEXT_ACTION_EYEBROW = "text-[10px] font-[750] text-brand";
const NEXT_ACTION_TITLE = "mt-[5px] text-[15px] leading-[1.35] text-ink";
const NEXT_ACTION_TEXT = "mt-[7px] block text-[11px] leading-[1.55] text-muted";
const NEXT_ACTION_BUTTON = `${BUTTON_PRIMARY} mt-auto w-full mw-900:mt-0 mw-900:w-auto mw-620:w-full`;

const FACTS = `${SECTION} col-[1/-1]`;
const FACT_LIST = "grid grid-cols-4 mw-620:grid-cols-[minmax(0,1fr)]";
const FACT =
  "min-w-0 border-r border-r-border-muted p-[14px_16px] last:border-r-0" +
  " mw-620:border-r-0 mw-620:border-b mw-620:border-b-border-muted" +
  " mw-620:last:border-b-0";
const FACT_LABEL = "text-[10px] text-muted";
const FACT_VALUE =
  "mt-1.5 [overflow-wrap:anywhere] text-[12px] font-[650] text-ink";

const SINGLE_COLUMN = "grid gap-4";
// The later `.applicant-report__content-header` strips the heading box back to one hairline.
const CONTENT_HEADER =
  "flex min-h-auto items-center justify-start gap-[11px]" +
  " border-b border-b-border-muted p-[0_0_18px]";

const STATUS_BLOCK =
  "grid min-h-[110px] grid-cols-[32px_minmax(0,1fr)_auto] items-center gap-[14px]" +
  " rounded-[7px] border border-border-muted p-5" +
  " mw-620:grid-cols-[28px_minmax(0,1fr)] mw-620:p-4";
const STATUS_BLOCK_TONE = {
  ready: "bg-[#f7fbf8] text-success",
  waiting: "bg-[#fafbfc] text-muted",
} as const;
const STATUS_BLOCK_TITLE = "text-[14px] text-ink";
const STATUS_BLOCK_TEXT = "mt-[5px] text-[11px] leading-[1.55] text-muted";
// The trailing slot holds either a label or a button, and stretches at 620px.
const STATUS_BLOCK_TRAILING =
  "text-[12px] font-[650] text-ink-secondary mw-620:col-[1/-1]";
const STATUS_BLOCK_BUTTON = `${BUTTON_SECONDARY} mw-620:w-full`;

const DETAIL_LIST =
  "grid grid-cols-2 overflow-hidden rounded-[7px] border border-border-muted" +
  " mw-620:grid-cols-[minmax(0,1fr)]";

const REPORT_EMPTY = "text-[9px] leading-[1.6] text-muted";

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
  const [submissions, setSubmissions] = useState<readonly CompanySubmission[]>(
    [],
  );
  const [submissionsLoading, setSubmissionsLoading] = useState(true);
  const invitation = invitations.find(
    (item) =>
      item.positionId === positionId && item.invitationId === invitationId,
  );

  useEffect(() => {
    let active = true;
    setSubmissionsLoading(true);
    api
      .listSubmissions(invitationId)
      .then((items) => {
        if (active) setSubmissions(items);
      })
      .catch(() => {
        if (active) setSubmissions([]);
      })
      .finally(() => {
        if (active) setSubmissionsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, invitationId]);

  if (loading) {
    return (
      <div className={ASYNC_STATE} role="status">
        지원자 정보를 불러오는 중입니다.
      </div>
    );
  }
  if (error || !invitation) {
    return (
      <div className={ASYNC_STATE} role="alert">
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
    <div className={REPORT}>
      <header className={MASTHEAD}>
        <Link to={`/positions/${positionId}`} className={BACK_LINK}>
          <ArrowLeft size={14} aria-hidden="true" />
          {invitation.positionTitle}
        </Link>

        <div className={IDENTITY}>
          <span className={AVATAR} aria-hidden="true">
            {getInitial(displayName)}
          </span>
          <div className={IDENTITY_COPY}>
            <p className={IDENTITY_EYEBROW}>지원자 종합 리포트</p>
            <h1 className={IDENTITY_NAME}>{displayName}</h1>
            <div className={IDENTITY_META}>
              <span className={IDENTITY_META_ITEM}>
                <Mail size={13} aria-hidden="true" />
                {invitation.applicantEmail}
              </span>
              <span className={IDENTITY_META_ITEM}>
                <BriefcaseBusiness size={13} aria-hidden="true" />
                {invitation.positionTitle}
              </span>
            </div>
          </div>
          <span
            className={`${INVITATION_STATUS} ${invitationTone(status.tone)} ${IDENTITY_STATUS}`}
          >
            {status.label}
          </span>
        </div>
      </header>

      <section className={METRICS} aria-label="지원자 처리 현황">
        <article
          className={METRIC}
          aria-label={`현재 채용 단계 ${recruiterPhaseCount}단계 중 ${recruiterPhase}단계`}
        >
          <span className={METRIC_LABEL}>현재 채용 단계</span>
          <strong className={METRIC_VALUE}>
            {recruiterPhase || "-"}
            <small className={METRIC_UNIT}>/{recruiterPhaseCount}</small>
          </strong>
          <em className={METRIC_NOTE}>{status.label}</em>
        </article>
        <article className={METRIC}>
          <span className={METRIC_LABEL}>자료 분석</span>
          <strong className={METRIC_VALUE}>
            {formatProcessingState(invitation.analysisStatus)}
          </strong>
          <em className={METRIC_NOTE}>
            {materialStateDescription(invitation.analysisStatus)}
          </em>
        </article>
        <article className={METRIC}>
          <span className={METRIC_LABEL}>면접</span>
          <strong className={METRIC_VALUE}>
            {formatInterviewState(invitation.interviewStatus)}
          </strong>
          <em className={METRIC_NOTE}>
            {reviewPath ? "세션 연결됨" : "진행 상태 확인"}
          </em>
        </article>
        <article className={METRIC}>
          <span className={METRIC_LABEL}>리포트</span>
          <strong className={METRIC_VALUE}>
            {formatReportState(invitation.reportStatus)}
          </strong>
          <em className={METRIC_NOTE}>
            {reviewPath ? "검토 화면 연결" : "면접 완료 후 생성"}
          </em>
        </article>
      </section>

      <div className={WORKSPACE}>
        <div className={TABS} role="tablist" aria-label="지원자 리포트 메뉴">
          {reportTabs.map((tab) => (
            <button
              key={tab.id}
              className={TAB}
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
          className={PANEL}
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
            <MaterialsPanel
              invitation={invitation}
              submissions={submissions}
              loading={submissionsLoading}
            />
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
    <div className={OVERVIEW}>
      <section className={SECTION}>
        <header className={SECTION_HEADING}>
          <div className={SECTION_HEADING_GROUP}>
            <span className={SECTION_ICON} aria-hidden="true">
              <ListChecks size={18} />
            </span>
            <div>
              <h2 className={SECTION_TITLE}>지원 진행 요약</h2>
              <p className={SECTION_TEXT}>
                지원부터 검토까지의 현재 위치를 확인합니다.
              </p>
            </div>
          </div>
          <strong className={SECTION_COUNT}>
            {recruiterPhase || "-"} / {recruiterPhaseCount}
          </strong>
        </header>

        <ol className={PROGRESS}>
          {progressMilestones.map((milestone, index) => {
            const progressState =
              index < currentMilestone
                ? "complete"
                : index === currentMilestone
                  ? "current"
                  : "pending";
            return (
              <li
                key={milestone.label}
                className={
                  progressState === "pending" ? MILESTONE_TODO : MILESTONE_DONE
                }
              >
                <span
                  className={MILESTONE_MARK_TONE[progressState]}
                  aria-hidden="true"
                >
                  {index < currentMilestone ? (
                    <CheckCircle2 size={17} />
                  ) : (
                    index + 1
                  )}
                </span>
                <div className={MILESTONE_TEXT}>
                  <strong className={MILESTONE_LABEL}>{milestone.label}</strong>
                  <small className={MILESTONE_DETAIL}>{milestone.detail}</small>
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      <aside className={NEXT_ACTION}>
        <span className={SECTION_ICON} aria-hidden="true">
          {reviewPath ? <BarChart3 size={18} /> : <CircleDashed size={18} />}
        </span>
        <div>
          <p className={NEXT_ACTION_EYEBROW}>채용담당자 작업</p>
          <h2 className={NEXT_ACTION_TITLE}>
            {reviewPath
              ? "면접 결과를 검토하세요"
              : "지원자 진행을 기다리는 중입니다"}
          </h2>
          <span className={NEXT_ACTION_TEXT}>
            {reviewPath
              ? "영상, 최종 답변과 기준별 분석을 확인할 수 있습니다."
              : "현재 단계가 완료되면 다음 검토 작업이 활성화됩니다."}
          </span>
        </div>
        {reviewPath ? (
          <Link className={NEXT_ACTION_BUTTON} to={reviewPath}>
            검토 시작
            <ChevronRight size={15} aria-hidden="true" />
          </Link>
        ) : null}
      </aside>

      <section className={FACTS}>
        <header className={SECTION_HEADING}>
          <div className={SECTION_HEADING_GROUP}>
            <span className={SECTION_ICON} aria-hidden="true">
              <UserRound size={18} />
            </span>
            <div>
              <h2 className={SECTION_TITLE}>지원 정보</h2>
              <p className={SECTION_TEXT}>
                포지션과 초대 기준 정보를 확인합니다.
              </p>
            </div>
          </div>
        </header>
        <dl className={FACT_LIST}>
          <div className={FACT}>
            <dt className={FACT_LABEL}>지원 포지션</dt>
            <dd className={FACT_VALUE}>{invitation.positionTitle}</dd>
          </div>
          <div className={FACT}>
            <dt className={FACT_LABEL}>이메일</dt>
            <dd className={FACT_VALUE}>{invitation.applicantEmail}</dd>
          </div>
          <div className={FACT}>
            <dt className={FACT_LABEL}>초대 만료</dt>
            <dd className={FACT_VALUE}>
              {formatDateTime(invitation.expiresAt)}
            </dd>
          </div>
          <div className={FACT}>
            <dt className={FACT_LABEL}>면접 세션</dt>
            <dd className={FACT_VALUE}>
              {invitation.interviewSessionId ? "연결됨" : "대기"}
            </dd>
          </div>
        </dl>
      </section>
    </div>
  );
}

function MaterialsPanel({
  invitation,
  submissions,
  loading,
}: {
  invitation: PositionedInvitation;
  submissions: readonly CompanySubmission[];
  loading: boolean;
}) {
  const ready = invitation.analysisStatus === "ready";

  return (
    <div className={SINGLE_COLUMN}>
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
      <section className={SECTION}>
        <header className={SECTION_HEADING}>
          <div className={SECTION_HEADING_GROUP}>
            <span className={SECTION_ICON} aria-hidden="true">
              <FileText size={18} />
            </span>
            <div>
              <h2 className={SECTION_TITLE}>제출된 원본 자료</h2>
              <p className={SECTION_TEXT}>
                지원자가 제출한 자료와 워커 처리 상태를 확인합니다.
              </p>
            </div>
          </div>
          <strong className={SECTION_COUNT}>{submissions.length}건</strong>
        </header>
        {loading ? (
          <p className={REPORT_EMPTY} role="status">
            제출 자료를 불러오는 중입니다.
          </p>
        ) : submissions.length > 0 ? (
          <div className="divide-y divide-border border-y border-border">
            {submissions.map((submission) => (
              <article
                className="flex items-center justify-between gap-4 py-3"
                key={submission.submissionId}
              >
                <div className="min-w-0">
                  <strong className="block text-sm text-ink">
                    {materialLabel(submission.materialType)}
                  </strong>
                  <span className="mt-1 block truncate text-xs text-muted">
                    {submission.originalFilename ??
                      submission.sourceUrl ??
                      "제출 자료"}
                  </span>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="text-xs font-semibold text-muted">
                    {submissionStatusLabel(submission.status)}
                  </span>
                  {submission.sourceUrl ? (
                    <a
                      className={BUTTON_SECONDARY}
                      href={submission.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      원본 열기
                    </a>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className={REPORT_EMPTY}>아직 제출된 자료가 없습니다.</p>
        )}
      </section>
      <dl className={DETAIL_LIST}>
        <div className={FACT}>
          <dt className={FACT_LABEL}>분석 상태</dt>
          <dd className={FACT_VALUE}>
            {formatProcessingState(invitation.analysisStatus)}
          </dd>
        </div>
        <div className={FACT}>
          <dt className={FACT_LABEL}>연결 평가기준</dt>
          <dd className={FACT_VALUE}>
            {ready ? "면접 전략에 반영됨" : "분석 완료 후 연결"}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function materialLabel(materialType: CompanySubmission["materialType"]) {
  return {
    resume: "이력서",
    cover_letter: "자기소개서",
    career_description: "경력기술서",
    projects: "대표 프로젝트",
    portfolio: "포트폴리오",
  }[materialType];
}

function submissionStatusLabel(status: string) {
  if (status === "ready") return "분석 완료";
  if (status === "partial") return "일부 완료";
  if (status === "failed") return "처리 실패";
  if (status === "analyzing" || status === "validating") return "분석 중";
  return "접수 완료";
}

function InterviewPanel({
  invitation,
  reviewPath,
}: {
  invitation: PositionedInvitation;
  reviewPath: string | null;
}) {
  return (
    <div className={SINGLE_COLUMN}>
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
            <Link className={STATUS_BLOCK_BUTTON} to={reviewPath}>
              면접 기록 열기
              <ChevronRight size={15} aria-hidden="true" />
            </Link>
          ) : null
        }
      />
      <dl className={DETAIL_LIST}>
        <div className={FACT}>
          <dt className={FACT_LABEL}>면접 상태</dt>
          <dd className={FACT_VALUE}>
            {formatInterviewState(invitation.interviewStatus)}
          </dd>
        </div>
        <div className={FACT}>
          <dt className={FACT_LABEL}>세션 연결</dt>
          <dd className={FACT_VALUE}>
            {invitation.interviewSessionId ? "연결됨" : "대기"}
          </dd>
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
    <div className={SINGLE_COLUMN}>
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
            <Link className={`${BUTTON_PRIMARY} mw-620:w-full`} to={reviewPath}>
              전체 분석 리포트 열기
              <ChevronRight size={15} aria-hidden="true" />
            </Link>
          ) : null
        }
      />
      <dl className={DETAIL_LIST}>
        <div className={FACT}>
          <dt className={FACT_LABEL}>리포트 상태</dt>
          <dd className={FACT_VALUE}>
            {formatReportState(invitation.reportStatus)}
          </dd>
        </div>
        <div className={FACT}>
          <dt className={FACT_LABEL}>검토 가능 범위</dt>
          <dd className={FACT_VALUE}>
            {ready ? "영상·응답·기준별 분석" : "생성 대기"}
          </dd>
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
    <header className={CONTENT_HEADER}>
      <span className={SECTION_ICON} aria-hidden="true">
        {icon}
      </span>
      <div>
        <h2 className={SECTION_TITLE}>{title}</h2>
        <p className={SECTION_TEXT}>{description}</p>
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
      className={`${STATUS_BLOCK} ${ready ? STATUS_BLOCK_TONE.ready : STATUS_BLOCK_TONE.waiting}`}
    >
      {ready ? readyIcon : <CircleDashed size={24} aria-hidden="true" />}
      <div>
        <strong className={STATUS_BLOCK_TITLE}>{title}</strong>
        <p className={STATUS_BLOCK_TEXT}>{description}</p>
      </div>
      {trailing ? (
        <span className={STATUS_BLOCK_TRAILING}>{trailing}</span>
      ) : null}
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
