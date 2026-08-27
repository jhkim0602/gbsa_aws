import {
  ArrowLeft,
  BarChart3,
  BriefcaseBusiness,
  CheckCircle2,
  CircleDashed,
  ExternalLink,
  FileCheck2,
  FileText,
  FolderOpen,
  Mail,
  MessageSquareQuote,
  PlayCircle,
  ShieldCheck,
  Sparkles,
  UserRound,
  Video,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, Navigate } from "react-router-dom";

import { applicantWorkspacePath } from "../../app/applicantWorkspacePath";
import {
  ASYNC_STATE,
  BUTTON_SECONDARY,
  INVITATION_STATUS,
  invitationTone,
} from "../../app/styles/primitives";
import { invitationStatusMeta } from "../hiring/PositionInvitations";
import { InterviewAxisRadarProfile, TimelineView } from "../review";
import { ApplicantCapabilityBars } from "./CompetencyInsights";
import type {
  CompanyApplicantReport,
  CompanyInvitation,
  CompanyOperationsApi,
  CompanySubmission,
} from "./types";
import { useRecruitingOperations } from "./useRecruitingOperations";
import { useApplicantReviewDossier } from "./useApplicantReviewDossier";

type PositionedInvitation = CompanyInvitation & { positionTitle: string };
type ApplicantReportTab = "analysis" | "interview" | "materials" | "profile";

const reportTabs: ReadonlyArray<{
  id: ApplicantReportTab;
  label: string;
  icon: typeof BarChart3;
}> = [
  { id: "analysis", label: "분석 리포트", icon: BarChart3 },
  { id: "interview", label: "면접 기록", icon: Video },
  { id: "materials", label: "제출 자료", icon: FolderOpen },
  { id: "profile", label: "지원 정보", icon: UserRound },
];

const ROOT = "grid min-h-full gap-0 bg-[#f6f7fa] pb-12";
const HEADER =
  "border-b border-border bg-surface px-8 pt-6 pb-7 mw-720:px-4 mw-720:pt-4";
const BACK =
  "mb-5 inline-flex items-center gap-1.5 text-[11px] text-muted hover:text-brand";
const IDENTITY =
  "grid grid-cols-[54px_minmax(0,1fr)_auto] items-center gap-4 mw-720:grid-cols-[46px_minmax(0,1fr)]";
const AVATAR =
  "grid size-[54px] place-items-center rounded-xl bg-brand-soft text-[18px] font-bold text-brand mw-720:size-[46px]";
const META = "mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted";
const META_ITEM = "inline-flex items-center gap-1.5";
const STATUS = "mw-720:col-[2] mw-720:justify-self-start";
const SCORE_STRIP =
  "mx-8 mt-4 grid grid-cols-4 overflow-hidden rounded-xl border border-border bg-surface mw-900:grid-cols-2 mw-720:mx-4";
const SCORE_CELL =
  "grid min-h-[88px] grid-cols-[32px_minmax(0,1fr)] items-center gap-3 border-r border-border-muted px-5 last:border-r-0 mw-900:nth-2:border-r-0 mw-900:nth-[-n+2]:border-b mw-900:nth-[-n+2]:border-border-muted mw-720:px-4";
const SCORE_ICON =
  "grid size-8 place-items-center rounded-lg bg-brand-soft text-brand";
const SCORE_LABEL = "block text-[9px] text-muted";
const SCORE_VALUE = "mt-1 block font-mono text-[20px] text-ink";
const WORKSPACE =
  "mx-8 mt-4 overflow-hidden rounded-xl border border-border bg-surface mw-720:mx-4";
const TABS = "flex min-h-14 gap-7 overflow-x-auto border-b border-border px-5";
const TAB =
  "relative inline-flex flex-none items-center gap-1.5 px-0.5 text-[12px] font-semibold text-muted after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 aria-selected:text-brand aria-selected:after:bg-brand";
const PANEL = "min-h-[480px] p-5 outline-none mw-720:p-4";
const CARD = "overflow-hidden rounded-lg border border-border-muted bg-surface";
const CARD_HEADER =
  "flex min-h-16 items-center justify-between gap-4 border-b border-border-muted px-5 py-3";

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
  const invitation = invitations.find(
    (item) =>
      item.positionId === positionId && item.invitationId === invitationId,
  );
  const [selectedTab, setSelectedTab] =
    useState<ApplicantReportTab>("analysis");
  const [selectedStartMs, setSelectedStartMs] = useState<number | null>(null);
  const reviewPath = invitation ? applicantWorkspacePath(invitation) : null;
  const redirectToReview = reviewPath?.startsWith("/review/")
    ? reviewPath
    : null;
  const {
    submissions,
    report,
    loading: detailLoading,
  } = useApplicantReviewDossier({
    api,
    invitation,
    enabled: Boolean(invitation && !redirectToReview),
  });

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
  if (redirectToReview) {
    return <Navigate replace to={redirectToReview} />;
  }

  const displayName =
    invitation.applicantDisplayName || invitation.applicantEmail.split("@")[0];
  const status = invitationStatusMeta[invitation.status];
  const evidenceCount = report?.report.items.reduce(
    (sum, item) => sum + item.evidence.length,
    0,
  );

  function openEvidence(startMs: number) {
    setSelectedStartMs(startMs);
    setSelectedTab("interview");
    window.requestAnimationFrame(() => {
      document.getElementById("applicant-report-panel-interview")?.focus();
    });
  }

  function moveTab(direction: -1 | 1) {
    const current = reportTabs.findIndex((tab) => tab.id === selectedTab);
    const next =
      reportTabs[(current + direction + reportTabs.length) % reportTabs.length];
    setSelectedTab(next.id);
    window.requestAnimationFrame(() => {
      document.getElementById(`applicant-report-tab-${next.id}`)?.focus();
    });
  }

  return (
    <div className={ROOT}>
      <header className={HEADER}>
        <Link to={`/positions/${positionId}`} className={BACK}>
          <ArrowLeft size={14} aria-hidden="true" /> {invitation.positionTitle}
        </Link>
        <div className={IDENTITY}>
          <span className={AVATAR} aria-hidden="true">
            {getInitial(displayName)}
          </span>
          <div className="min-w-0">
            <p className="mb-1 text-[10px] font-bold tracking-[0.05em] text-brand uppercase">
              APPLICANT EVIDENCE
            </p>
            <h1 className="text-[25px] leading-[1.2] text-ink mw-720:text-[21px]">
              {displayName}
            </h1>
            <div className={META}>
              <span className={META_ITEM}>
                <Mail size={13} />
                {invitation.applicantEmail}
              </span>
              <span className={META_ITEM}>
                <BriefcaseBusiness size={13} />
                {invitation.positionTitle}
              </span>
            </div>
          </div>
          <span
            className={`${INVITATION_STATUS} ${invitationTone(status.tone)} ${STATUS}`}
          >
            {status.label}
          </span>
        </div>
      </header>

      <section className={SCORE_STRIP} aria-label="지원자 역량 요약">
        <ScoreMetric
          label="총점"
          value={
            report?.insight.overallScore == null
              ? "–"
              : String(report.insight.overallScore)
          }
          icon={<Sparkles size={16} />}
        />
        <ScoreMetric
          label="답변 근거 충족"
          value={report ? `${report.insight.evidenceCoverage}%` : "–"}
          icon={<ShieldCheck size={16} />}
        />
        <ScoreMetric
          label="평가 기준"
          value={report ? `${report.insight.criteria.length}개` : "–"}
          icon={<BarChart3 size={16} />}
        />
        <ScoreMetric
          label="인용 근거"
          value={evidenceCount == null ? "–" : `${evidenceCount}개`}
          icon={<MessageSquareQuote size={16} />}
        />
      </section>

      <div className={WORKSPACE}>
        <div className={TABS} role="tablist" aria-label="지원자 리포트 메뉴">
          {reportTabs.map((tab) => {
            const Icon = tab.icon;
            return (
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
                <Icon size={15} aria-hidden="true" /> {tab.label}
              </button>
            );
          })}
        </div>
        <section
          id={`applicant-report-panel-${selectedTab}`}
          className={PANEL}
          role="tabpanel"
          aria-labelledby={`applicant-report-tab-${selectedTab}`}
          tabIndex={0}
        >
          {detailLoading ? (
            <div className={ASYNC_STATE} role="status">
              리포트와 제출 자료를 불러오는 중입니다.
            </div>
          ) : selectedTab === "analysis" ? (
            <AnalysisPanel report={report} onOpenEvidence={openEvidence} />
          ) : selectedTab === "interview" ? (
            <InterviewPanel
              report={report}
              selectedStartMs={selectedStartMs}
              onSeek={setSelectedStartMs}
            />
          ) : selectedTab === "materials" ? (
            <MaterialsPanel submissions={submissions} />
          ) : (
            <ProfilePanel invitation={invitation} report={report} />
          )}
        </section>
      </div>
    </div>
  );
}

function AnalysisPanel({
  report,
  onOpenEvidence,
}: {
  report: CompanyApplicantReport | null;
  onOpenEvidence(startMs: number): void;
}) {
  if (!report)
    return (
      <ReportPending icon={<BarChart3 size={22} />} title="분석 리포트 대기" />
    );
  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-[minmax(0,0.82fr)_minmax(320px,1.18fr)] gap-4 mw-900:grid-cols-[minmax(0,1fr)]">
        <section
          className={`${CARD} bg-[linear-gradient(145deg,#f3f5ff,#ffffff)]`}
        >
          <header className={CARD_HEADER}>
            <div>
              <p className="text-[9px] font-bold text-brand uppercase">
                AI SUMMARY
              </p>
              <h2 className="mt-1 text-[14px] text-ink">종합 분석</h2>
            </div>
            <strong className="font-mono text-[30px] text-brand">
              {report.insight.overallScore}
            </strong>
          </header>
          <p className="p-5 text-[12px] leading-[1.75] text-ink-secondary">
            {report.report.summary}
          </p>
          <div className="border-t border-border-muted px-5 py-3 text-[9px] text-muted">
            게시된 가중치를 적용한 참고 점수이며 채용 결정을 대신하지 않습니다.
          </div>
        </section>
        <section className={CARD}>
          <header className={CARD_HEADER}>
            <div>
              <h2 className="text-[14px] text-ink">기준별 역량</h2>
              <p className="mt-1 text-[10px] text-muted">
                실제 답변 근거가 있는 기준별 점수입니다.
              </p>
            </div>
            <span className="text-[10px] text-muted">100점 기준</span>
          </header>
          <div className="p-5">
            <ApplicantCapabilityBars insight={report.insight} />
          </div>
        </section>
      </div>

      <section className={CARD}>
        <header className={CARD_HEADER}>
          <div>
            <p className="text-[9px] font-bold text-brand uppercase">
              INTERVIEW PROFILE
            </p>
            <h2 className="mt-1 text-[14px] text-ink">5축 역량 레이더</h2>
            <p className="mt-1 text-[10px] text-muted">
              정확성·깊이·CS 기본기·본인 기여·설명력을 답변 근거로 비교합니다.
            </p>
          </div>
        </header>
        <div className="p-5 mw-720:p-3">
          <InterviewAxisRadarProfile items={report.report.items} />
        </div>
      </section>

      <section className={CARD}>
        <header className={CARD_HEADER}>
          <div>
            <h2 className="text-[14px] text-ink">평가 기준과 답변 근거</h2>
            <p className="mt-1 text-[10px] text-muted">
              타임스탬프를 누르면 해당 답변 영상으로 이동합니다.
            </p>
          </div>
        </header>
        <div className="grid">
          {report.report.items.map((item) => (
            <article
              className="grid gap-4 border-b border-border-muted p-5 last:border-b-0"
              key={item.reportItemId}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <span
                    className={`inline-flex rounded px-2 py-1 text-[9px] font-bold ${assessmentTone(item.assessmentState)}`}
                  >
                    {assessmentLabel(item.assessmentState)}
                  </span>
                  <h3 className="mt-2 text-[14px] text-ink">
                    {item.criterionName}
                  </h3>
                  <p className="mt-2 text-[11px] leading-[1.65] text-ink-secondary">
                    {item.observation}
                  </p>
                </div>
                <strong className="flex-none font-mono text-[24px] text-ink">
                  {item.averageScore ?? "–"}
                </strong>
              </div>
              <div className="flex flex-wrap gap-2">
                {item.evidence.map((evidence) => (
                  <button
                    className="inline-flex min-h-9 items-center gap-2 rounded-md border border-border bg-surface-muted px-3 text-left text-[10px] text-ink-secondary hover:border-brand hover:text-brand"
                    key={evidence.evidenceId}
                    type="button"
                    onClick={() => onOpenEvidence(evidence.startMs)}
                  >
                    <PlayCircle size={14} aria-hidden="true" />
                    <span>
                      <b className="font-mono">
                        {formatTime(evidence.startMs)}
                      </b>{" "}
                      · {evidence.observation}
                    </span>
                  </button>
                ))}
              </div>
              {item.followUpQuestion ? (
                <p className="rounded-md bg-warning-soft px-3 py-2.5 text-[10px] leading-[1.55] text-warning">
                  추가 확인 · {item.followUpQuestion}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function InterviewPanel({
  report,
  selectedStartMs,
  onSeek,
}: {
  report: CompanyApplicantReport | null;
  selectedStartMs: number | null;
  onSeek(startMs: number): void;
}) {
  if (!report)
    return <ReportPending icon={<Video size={22} />} title="면접 기록 대기" />;
  return (
    <div className="grid grid-cols-[minmax(300px,0.72fr)_minmax(0,1.28fr)] items-start gap-4 mw-900:grid-cols-[minmax(0,1fr)]">
      <div className="min-w-0">
        <TimelineView
          entries={report.timeline.entries}
          playbackStatus={report.timeline.playback.status}
          playbackUrl={report.timeline.playback.url}
          selectedStartMs={selectedStartMs}
          onSeek={onSeek}
          showTimeline={false}
        />
      </div>
      <section className={CARD}>
        <header className={CARD_HEADER}>
          <div>
            <h2 className="text-[14px] text-ink">시간별 대화 기록</h2>
            <p className="mt-1 text-[10px] text-muted">
              왼쪽은 면접 영상입니다. 대화 행을 누르면 영상이 해당 시점으로
              이동합니다.
            </p>
          </div>
        </header>
        <ol className="grid max-h-[620px] overflow-auto [content-visibility:auto]">
          {report.timeline.entries
            .filter((entry) => entry.text)
            .map((entry) => (
              <li
                className="border-b border-border-muted last:border-b-0"
                key={entry.entryId}
              >
                <button
                  className="grid w-full grid-cols-[58px_minmax(0,1fr)] gap-3 px-5 py-4 text-left hover:bg-surface-muted"
                  type="button"
                  onClick={() => onSeek(entry.startMs)}
                >
                  <span className="font-mono text-[10px] text-brand">
                    {formatTime(entry.startMs)}
                  </span>
                  <span>
                    <strong className="block text-[10px] text-ink">
                      {entry.type === "question"
                        ? "AI 면접관"
                        : entry.type === "answer"
                          ? "지원자"
                          : "기록"}
                    </strong>
                    <small className="mt-1 block text-[11px] leading-[1.65] text-ink-secondary">
                      {entry.text}
                    </small>
                  </span>
                </button>
              </li>
            ))}
        </ol>
      </section>
    </div>
  );
}

function MaterialsPanel({
  submissions,
}: {
  submissions: readonly CompanySubmission[];
}) {
  return (
    <div className="grid gap-4">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-[15px] text-ink">제출 자료 원본</h2>
          <p className="mt-1 text-[11px] text-muted">
            분석 요약과 지원자가 제출한 원본을 함께 확인합니다.
          </p>
        </div>
        <span className="rounded-full bg-brand-soft px-3 py-1.5 text-[10px] font-bold text-brand">
          {submissions.length}건
        </span>
      </header>
      {submissions.length ? (
        <div className="grid grid-cols-3 gap-3 mw-1050:grid-cols-2 mw-720:grid-cols-[minmax(0,1fr)]">
          {submissions.map((submission) => (
            <article
              className="group grid min-h-[210px] content-between rounded-lg border border-border bg-surface p-5 hover:border-[#aeb7ef] hover:shadow-sm"
              key={submission.submissionId}
            >
              <div>
                <span className="grid size-10 place-items-center rounded-lg bg-brand-soft text-brand">
                  <FileText size={19} />
                </span>
                <span className="mt-5 inline-flex items-center gap-1 text-[9px] font-semibold text-success">
                  <FileCheck2 size={12} />
                  {submissionStatusLabel(submission.status)}
                </span>
                <h3 className="mt-2 text-[14px] text-ink">
                  {materialLabel(submission.materialType)}
                </h3>
                <p className="mt-1 truncate text-[10px] text-muted">
                  {submission.originalFilename ??
                    submission.sourceUrl ??
                    "제출 자료"}
                </p>
                {submission.impactSummary ? (
                  <p className="mt-3 text-[10px] leading-[1.55] text-ink-secondary">
                    {submission.impactSummary}
                  </p>
                ) : null}
              </div>
              {submission.sourceUrl ? (
                <a
                  className={`${BUTTON_SECONDARY} mt-4 w-full`}
                  href={submission.sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  원본 열기 <ExternalLink size={13} />
                </a>
              ) : (
                <span className="mt-4 text-[9px] text-subtle">
                  보안 원본 링크 준비 중
                </span>
              )}
            </article>
          ))}
        </div>
      ) : (
        <ReportPending
          icon={<FolderOpen size={22} />}
          title="제출된 자료가 없습니다"
        />
      )}
    </div>
  );
}

function ProfilePanel({
  invitation,
  report,
}: {
  invitation: PositionedInvitation;
  report: CompanyApplicantReport | null;
}) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(280px,0.55fr)] gap-4 mw-900:grid-cols-[minmax(0,1fr)]">
      <section className={CARD}>
        <header className={CARD_HEADER}>
          <h2 className="text-[14px] text-ink">지원 정보</h2>
        </header>
        <dl className="grid grid-cols-2 mw-720:grid-cols-[minmax(0,1fr)]">
          <Fact
            label="지원 포지션"
            value={invitation.positionTitle}
            icon={<BriefcaseBusiness size={15} />}
          />
          <Fact
            label="지원자 이메일"
            value={invitation.applicantEmail}
            icon={<Mail size={15} />}
          />
          <Fact
            label="면접 일정"
            value="포지션 설정 일정 적용"
            icon={<Video size={15} />}
          />
          <Fact
            label="면접 세션"
            value={invitation.interviewSessionId ? "연결됨" : "대기"}
            icon={<Video size={15} />}
          />
        </dl>
      </section>
      <section className={`${CARD} bg-surface-muted`}>
        <header className={CARD_HEADER}>
          <h2 className="text-[14px] text-ink">검토 준비 상태</h2>
        </header>
        <div className="grid gap-3 p-5">
          <Readiness
            label="제출 자료 분석"
            ready={invitation.analysisStatus === "ready"}
          />
          <Readiness
            label="면접 기록"
            ready={invitation.interviewStatus === "completed"}
          />
          <Readiness label="분석 리포트" ready={Boolean(report)} />
        </div>
      </section>
    </div>
  );
}

function ScoreMetric({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: ReactNode;
}) {
  return (
    <article className={SCORE_CELL}>
      <span className={SCORE_ICON}>{icon}</span>
      <span>
        <small className={SCORE_LABEL}>{label}</small>
        <strong className={SCORE_VALUE}>{value}</strong>
      </span>
    </article>
  );
}

function ReportPending({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="grid min-h-[340px] place-items-center">
      <div className="grid justify-items-center gap-3 text-center">
        <span className="grid size-11 place-items-center rounded-full bg-surface-strong text-muted">
          {icon}
        </span>
        <div>
          <strong className="text-[13px] text-ink-secondary">{title}</strong>
          <p className="mt-1 text-[10px] text-muted">
            면접과 후처리가 완료되면 이곳에 자동으로 연결됩니다.
          </p>
        </div>
      </div>
    </div>
  );
}

function Fact({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: ReactNode;
}) {
  return (
    <div className="grid min-h-24 grid-cols-[28px_minmax(0,1fr)] content-center gap-2 border-r border-b border-border-muted p-5 even:border-r-0 mw-720:border-r-0">
      <span className="text-brand">{icon}</span>
      <span>
        <dt className="text-[9px] text-muted">{label}</dt>
        <dd className="mt-1 text-[11px] font-semibold text-ink">{value}</dd>
      </span>
    </div>
  );
}

function Readiness({ label, ready }: { label: string; ready: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-surface px-3 py-2.5">
      <span className="text-[10px] text-ink-secondary">{label}</span>
      <span
        className={`inline-flex items-center gap-1 text-[9px] font-semibold ${ready ? "text-success" : "text-muted"}`}
      >
        {ready ? <CheckCircle2 size={13} /> : <CircleDashed size={13} />}
        {ready ? "준비 완료" : "대기"}
      </span>
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

function assessmentLabel(
  value: CompanyApplicantReport["report"]["items"][number]["assessmentState"],
) {
  return {
    confirmed: "근거 충분",
    partially_confirmed: "부분 확인",
    insufficient_evidence: "근거 부족",
    needs_follow_up: "추가 확인",
  }[value];
}

function assessmentTone(
  value: CompanyApplicantReport["report"]["items"][number]["assessmentState"],
) {
  if (value === "confirmed") return "bg-success-soft text-success";
  if (value === "partially_confirmed") return "bg-brand-soft text-brand";
  return "bg-warning-soft text-warning";
}

function formatTime(milliseconds: number) {
  const seconds = Math.floor(milliseconds / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function getInitial(value: string) {
  return value.trim().slice(0, 1).toUpperCase() || "A";
}
