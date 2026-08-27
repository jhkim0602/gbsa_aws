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
import { RequirementRadarProfile, TimelineView } from "../review";
import type {
  RequirementAssessment,
  RequirementAssessmentStatus,
  RequirementEvidence,
  ReviewTimelineEntry,
} from "../review/types";
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
  embedded = false,
  initialInvitation,
}: {
  positionId: string;
  invitationId: string;
  api: CompanyOperationsApi;
  embedded?: boolean;
  initialInvitation?: PositionedInvitation;
}) {
  const { invitations, loading, error } = useRecruitingOperations(
    api,
    positionId,
  );
  const invitation =
    invitations.find(
      (item) =>
        item.positionId === positionId && item.invitationId === invitationId,
    ) ??
    (initialInvitation?.positionId === positionId &&
    initialInvitation.invitationId === invitationId
      ? initialInvitation
      : undefined);
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
    enabled: Boolean(invitation && (embedded || !redirectToReview)),
  });

  if (loading && !invitation) {
    return (
      <div className={ASYNC_STATE} role="status">
        지원자 정보를 불러오는 중입니다.
      </div>
    );
  }
  if ((!invitation && error) || !invitation) {
    return (
      <div className={ASYNC_STATE} role="alert">
        지원자 정보를 찾을 수 없습니다.
      </div>
    );
  }
  if (redirectToReview && !embedded) {
    return <Navigate replace to={redirectToReview} />;
  }

  const displayName =
    invitation.applicantDisplayName || invitation.applicantEmail.split("@")[0];
  const status = invitationStatusMeta[invitation.status];
  const requirementAssessments = report?.report.requirementAssessments ?? [];
  const requirementCount = (status: string) =>
    requirementAssessments.filter((assessment) => {
      const effective = assessment.humanOverride?.status ?? assessment.status;
      const normalized = effective === "unknown" ? "not_met" : effective;
      return normalized === status;
    }).length;

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
    <div
      className={embedded ? "grid min-h-full gap-0 bg-[#f6f7fa] pb-6" : ROOT}
    >
      <header className={HEADER}>
        {embedded ? null : (
          <Link to={`/positions/${positionId}`} className={BACK}>
            <ArrowLeft size={14} aria-hidden="true" />{" "}
            {invitation.positionTitle}
          </Link>
        )}
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

      <section className={SCORE_STRIP} aria-label="지원자 자격요건 판정 요약">
        <ScoreMetric
          label="충족"
          value={report ? `${requirementCount("met")}개` : "–"}
          icon={<CheckCircle2 size={16} />}
        />
        <ScoreMetric
          label="부분 충족"
          value={report ? `${requirementCount("partially_met")}개` : "–"}
          icon={<ShieldCheck size={16} />}
        />
        <ScoreMetric
          label="미충족"
          value={report ? `${requirementCount("not_met")}개` : "–"}
          icon={<CircleDashed size={16} />}
        />
        <ScoreMetric
          label="전체 자격요건"
          value={report ? `${requirementAssessments.length}개` : "–"}
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

function InterviewMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="border-r border-border-muted px-3 last:border-r-0 mw-720:border-r-0 mw-720:border-b mw-720:py-2 mw-720:last:border-b-0">
      <dt className="text-[9px] text-muted">{label}</dt>
      <dd className="mt-1 font-mono text-[20px] text-ink">{value}개</dd>
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
  const requirements = report.report.requirementAssessments ?? [];
  const decidedRequirements = requirements.length;
  const questions = report.timeline.entries.filter(
    (entry) => entry.type === "question",
  );
  const mandatoryQuestionAnswers = pairMandatoryQuestionAnswers(
    report.timeline.entries,
  );
  const durationMinutes = Math.max(
    1,
    Math.ceil(
      Math.max(0, ...report.timeline.entries.map((entry) => entry.endMs)) /
        60_000,
    ),
  );
  const companyQuestionCount = questions.filter(
    (entry) => entry.questionRationale?.questionType === "company_required",
  ).length;
  const followUpCount = questions.filter(
    (entry) => entry.questionRationale?.questionType === "follow_up",
  ).length;
  const requirementQuestionCount = questions.filter((entry) =>
    entry.questionRationale?.verificationTargetType.startsWith(
      "job_requirement_",
    ),
  ).length;
  return (
    <div className="grid gap-4">
      <MandatoryQuestionAnswers
        entries={mandatoryQuestionAnswers}
        onOpenEvidence={onOpenEvidence}
      />

      <div className="grid grid-cols-[minmax(0,0.82fr)_minmax(320px,1.18fr)] gap-4 mw-900:grid-cols-[minmax(0,1fr)]">
        <section
          className={`${CARD} bg-[linear-gradient(145deg,#f3f5ff,#ffffff)]`}
        >
          <header className={CARD_HEADER}>
            <div>
              <p className="text-[9px] font-bold text-brand uppercase">
                AI SUMMARY
              </p>
              <h2 className="mt-1 text-[14px] text-ink">자격요건 판정 요약</h2>
            </div>
            <strong className="font-mono text-[24px] text-brand">
              {decidedRequirements}/{requirements.length}
            </strong>
          </header>
          <p className="p-5 text-[12px] leading-[1.75] text-ink-secondary">
            {report.report.summary}
          </p>
          <div className="border-t border-border-muted px-5 py-3 text-[9px] text-muted">
            제출 자료와 면접 답변의 근거를 함께 확인한 상태이며 채용 결정을
            대신하지 않습니다.
          </div>
        </section>
        <section className={CARD}>
          <header className={CARD_HEADER}>
            <div>
              <h2 className="text-[14px] text-ink">면접 진행 요약</h2>
              <p className="mt-1 text-[10px] text-muted">
                최대 30분 안에서 필요한 근거가 모이면 조기 종료합니다.
              </p>
            </div>
            <span className="text-[10px] text-muted">
              실제 {durationMinutes}분
            </span>
          </header>
          <dl className="grid grid-cols-3 p-5 text-center mw-720:grid-cols-1 mw-720:text-left">
            <InterviewMetric
              label="자격요건 질문"
              value={requirementQuestionCount}
            />
            <InterviewMetric
              label="기업 설정 질문"
              value={companyQuestionCount}
            />
            <InterviewMetric label="필요한 꼬리질문" value={followUpCount} />
          </dl>
        </section>
      </div>

      <section className={CARD}>
        <header className={CARD_HEADER}>
          <div>
            <p className="text-[9px] font-bold text-brand uppercase">
              INTERVIEW PROFILE
            </p>
            <h2 className="mt-1 text-[14px] text-ink">자격요건 충족 레이더</h2>
            <p className="mt-1 text-[10px] text-muted">
              기업이 설정한 필수·우대 항목별 충족도를 비교합니다.
            </p>
          </div>
        </header>
        <div className="p-5 mw-720:p-3">
          <RequirementRadarProfile
            assessments={report.report.requirementAssessments ?? []}
          />
        </div>
      </section>

      <section className={CARD}>
        <header className={CARD_HEADER}>
          <div>
            <p className="text-[9px] font-bold text-brand uppercase">
              REQUIREMENT EVIDENCE
            </p>
            <h2 className="mt-1 text-[14px] text-ink">자격요건별 근거 상세</h2>
            <p className="mt-1 text-[10px] text-muted">
              기업이 설정한 필수·우대 자격요건마다 판정 상태와 실제 근거를
              확인합니다.
            </p>
          </div>
        </header>
        {requirements.length ? (
          <div className="grid">
            {requirements.map((assessment, index) => (
              <RequirementEvidenceArticle
                assessment={assessment}
                index={index}
                key={assessment.requirementAssessmentId}
                onOpenEvidence={onOpenEvidence}
              />
            ))}
          </div>
        ) : (
          <p className="p-5 text-[11px] text-muted">
            이 리포트에는 기업 자격요건 판정이 아직 생성되지 않았습니다.
          </p>
        )}
      </section>
    </div>
  );
}

type MandatoryQuestionAnswer = {
  question: ReviewTimelineEntry;
  answer: ReviewTimelineEntry | null;
};

function MandatoryQuestionAnswers({
  entries,
  onOpenEvidence,
}: {
  entries: readonly MandatoryQuestionAnswer[];
  onOpenEvidence(startMs: number): void;
}) {
  return (
    <section className={`${CARD} border-brand/30`}>
      <header className={`${CARD_HEADER} bg-brand-soft/35`}>
        <div>
          <p className="text-[9px] font-bold text-brand uppercase">
            COMPANY REQUIRED QUESTIONS
          </p>
          <h2 className="mt-1 text-[14px] text-ink">
            기업이 반드시 물어본 질문
          </h2>
          <p className="mt-1 text-[10px] text-muted">
            기업 담당자가 직접 설정한 질문과 지원자의 실제 답변입니다.
          </p>
        </div>
        <strong className="rounded-full bg-surface px-3 py-1.5 font-mono text-[10px] text-brand">
          {entries.length}개
        </strong>
      </header>
      {entries.length ? (
        <ol className="grid">
          {entries.map(({ question, answer }, index) => (
            <li
              className="grid gap-3 border-b border-border-muted p-5 last:border-b-0"
              key={question.entryId}
            >
              <div className="flex items-start gap-3">
                <span className="grid size-7 shrink-0 place-items-center rounded-full bg-brand text-[9px] font-bold text-white">
                  Q{index + 1}
                </span>
                <p className="pt-1 text-[12px] font-semibold leading-[1.6] text-ink">
                  {question.text ?? "질문 원문 없음"}
                </p>
              </div>
              {answer?.text ? (
                <button
                  className="ml-10 grid gap-2 rounded-lg border border-border bg-surface-muted px-4 py-3 text-left transition hover:border-brand hover:bg-brand-soft/25"
                  type="button"
                  onClick={() => onOpenEvidence(answer.startMs)}
                >
                  <span className="inline-flex items-center gap-1.5 text-[9px] font-bold text-brand">
                    <PlayCircle size={13} aria-hidden="true" />
                    {formatTime(answer.startMs)} · 지원자 답변
                  </span>
                  <span className="text-[11px] leading-[1.7] text-ink-secondary">
                    {answer.text}
                  </span>
                </button>
              ) : (
                <p className="ml-10 rounded-md bg-warning-soft px-3 py-2.5 text-[10px] text-warning">
                  연결된 답변 기록이 없습니다.
                </p>
              )}
            </li>
          ))}
        </ol>
      ) : (
        <p className="p-5 text-[11px] leading-[1.7] text-muted">
          이 면접에는 기업이 별도로 설정한 필수 질문이 없습니다.
        </p>
      )}
    </section>
  );
}

function RequirementEvidenceArticle({
  assessment,
  index,
  onOpenEvidence,
}: {
  assessment: RequirementAssessment;
  index: number;
  onOpenEvidence(startMs: number): void;
}) {
  const sourceStatus = assessment.humanOverride?.status ?? assessment.status;
  const status = sourceStatus === "unknown" ? "not_met" : sourceStatus;
  return (
    <article className="grid gap-4 border-b border-border-muted p-5 last:border-b-0">
      <div className="flex items-start justify-between gap-4 mw-720:flex-col">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[9px] font-bold text-brand">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="rounded bg-brand-soft px-2 py-1 text-[8px] font-bold text-brand">
              {assessment.requirementType === "required" ? "필수" : "우대"}
            </span>
            <span
              className={`rounded px-2 py-1 text-[8px] font-bold ${requirementStatusTone(status)}`}
            >
              {requirementStatusLabel(status)}
            </span>
          </div>
          <h3 className="mt-2 text-[13px] leading-[1.55] text-ink">
            {assessment.statement}
          </h3>
          <p className="mt-2 text-[10px] leading-[1.65] text-ink-secondary">
            {assessment.rationale}
          </p>
        </div>
      </div>
      {assessment.evidence.length ? (
        <div className="grid gap-2">
          {assessment.evidence.map((evidence) => (
            <RequirementEvidenceItem
              evidence={evidence}
              key={evidence.evidenceId}
              onOpenEvidence={onOpenEvidence}
            />
          ))}
        </div>
      ) : (
        <p className="rounded-md bg-surface-muted px-3 py-2.5 text-[10px] text-muted">
          직접 연결된 제출 자료 또는 면접 답변 근거가 없어 판단을 보류합니다.
        </p>
      )}
    </article>
  );
}

function RequirementEvidenceItem({
  evidence,
  onOpenEvidence,
}: {
  evidence: RequirementEvidence;
  onOpenEvidence(startMs: number): void;
}) {
  const startMs = requirementEvidenceStartMs(evidence);
  const content = (
    <>
      <span className="inline-flex items-center gap-1.5 text-[9px] font-bold text-brand">
        {evidence.sourceKind === "interview" ? (
          <PlayCircle size={13} aria-hidden="true" />
        ) : (
          <FileText size={13} aria-hidden="true" />
        )}
        {startMs != null ? `${formatTime(startMs)} · ` : ""}
        {evidence.sourceKind === "interview" ? "면접 답변" : "제출 자료"}
      </span>
      <span className="text-[11px] leading-[1.65] text-ink-secondary">
        {evidence.excerpt}
      </span>
      <small className="text-[9px] leading-[1.55] text-muted">
        {evidence.explanation}
      </small>
    </>
  );
  return evidence.sourceKind === "interview" && startMs != null ? (
    <button
      className="grid gap-1.5 rounded-lg border border-border bg-surface-muted px-4 py-3 text-left transition hover:border-brand hover:bg-brand-soft/25"
      type="button"
      onClick={() => onOpenEvidence(startMs)}
    >
      {content}
    </button>
  ) : (
    <div className="grid gap-1.5 rounded-lg border border-border bg-surface-muted px-4 py-3">
      {content}
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
                    {entry.type === "question" && entry.questionRationale ? (
                      <span className="mt-1 inline-flex rounded-full bg-brand-soft px-2 py-0.5 text-[8px] font-bold text-brand">
                        {entry.questionRationale.questionType ===
                        "company_required"
                          ? "기업 설정 질문"
                          : entry.questionRationale.questionType === "follow_up"
                            ? "꼬리질문"
                            : entry.questionRationale.verificationTargetType.startsWith(
                                  "job_requirement_",
                                )
                              ? "자격요건 질문"
                              : "AI 질문"}
                      </span>
                    ) : null}
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

function pairMandatoryQuestionAnswers(
  entries: readonly ReviewTimelineEntry[],
): MandatoryQuestionAnswer[] {
  const paired: MandatoryQuestionAnswer[] = [];
  entries.forEach((entry, index) => {
    if (
      entry.type !== "question" ||
      (entry.questionRationale?.questionType !== "company_required" &&
        entry.questionRationale?.verificationTargetType !==
          "company_required_question")
    ) {
      return;
    }
    let answer: ReviewTimelineEntry | null = null;
    for (let cursor = index + 1; cursor < entries.length; cursor += 1) {
      const candidate = entries[cursor];
      if (candidate.type === "question") break;
      if (candidate.type === "answer") {
        answer = candidate;
        break;
      }
    }
    paired.push({ question: entry, answer });
  });
  return paired;
}

function requirementStatusLabel(value: RequirementAssessmentStatus) {
  return {
    met: "충족",
    partially_met: "부분 충족",
    not_met: "미충족",
    unknown: "미충족",
  }[value];
}

function requirementStatusTone(value: RequirementAssessmentStatus) {
  if (value === "met") return "bg-success-soft text-success";
  if (value === "partially_met") return "bg-warning-soft text-warning";
  return "bg-danger-soft text-danger";
}

function requirementEvidenceStartMs(evidence: RequirementEvidence) {
  const value =
    evidence.locator.video_start_ms ??
    evidence.locator.start_ms ??
    evidence.locator.startMs;
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? value
    : null;
}

function formatTime(milliseconds: number) {
  const seconds = Math.floor(milliseconds / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function getInitial(value: string) {
  return value.trim().slice(0, 1).toUpperCase() || "A";
}
