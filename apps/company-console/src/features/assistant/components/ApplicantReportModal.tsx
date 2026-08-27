import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ExternalLink,
  FileText,
  FolderOpen,
  MessageSquareQuote,
  PlayCircle,
  ShieldCheck,
  Sparkles,
  Video,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { applicantWorkspacePath } from "../../../app/applicantWorkspacePath";
import { ASYNC_STATE } from "../../../app/styles/primitives";
import {
  displayApplicant,
  invitationProjection,
} from "../../company/recruitingState";
import type {
  CompanyApplicantInsight,
  CompanyApplicantReport,
  CompanyOperationsApi,
  CompanyRecruitingStage,
  CompanySubmission,
} from "../../company/types";
import { useApplicantReviewDossier } from "../../company/useApplicantReviewDossier";
import { RequirementRadarProfile, TimelineView } from "../../review";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../../hiring/tech-stack-combobox/dialog";
import type { ApplicantReportPreview } from "../types";

const DOSSIER_PAGES = [
  { id: "overview", label: "한눈에 보기" },
  { id: "criteria", label: "기준별 평가" },
  { id: "evidence", label: "답변 근거" },
  { id: "interview", label: "면접 기록" },
  { id: "submissions", label: "제출 서류" },
  { id: "review", label: "최종 검토" },
] as const;

type DossierPageId = (typeof DOSSIER_PAGES)[number]["id"];

export function ApplicantReportModal({
  preview,
  open,
  api,
  stages = [],
  moving = false,
  onChangeStage,
  onOpenChange,
}: {
  preview: ApplicantReportPreview | undefined;
  open: boolean;
  api: CompanyOperationsApi;
  stages?: readonly CompanyRecruitingStage[];
  moving?: boolean;
  onChangeStage?(stageId: string): Promise<boolean>;
  onOpenChange(open: boolean): void;
}) {
  const invitation = preview?.invitation;
  const { submissions, report, loading, error } = useApplicantReviewDossier({
    api,
    invitation,
    enabled: open,
  });
  const [pageIndex, setPageIndex] = useState(0);
  const [selectedStartMs, setSelectedStartMs] = useState<number | null>(null);
  const [selectedSubmissionId, setSelectedSubmissionId] = useState("");
  const [selectedStageId, setSelectedStageId] = useState("");

  useEffect(() => {
    setPageIndex(0);
    setSelectedStartMs(null);
    setSelectedSubmissionId("");
    setSelectedStageId(invitation?.recruitingStageId ?? "");
  }, [invitation?.invitationId, invitation?.recruitingStageId]);

  useEffect(() => {
    if (
      submissions.length > 0 &&
      !submissions.some(
        (submission) => submission.submissionId === selectedSubmissionId,
      )
    ) {
      setSelectedSubmissionId(submissions[0]?.submissionId ?? "");
    }
  }, [selectedSubmissionId, submissions]);

  if (!preview || !invitation) return null;

  const applicantName = displayApplicant(invitation);
  const status = invitationProjection(invitation.status);
  const activePage = DOSSIER_PAGES[pageIndex] ?? DOSSIER_PAGES[0];
  const insight = report?.insight ?? preview.insight;

  function goToPage(pageId: DossierPageId) {
    const nextIndex = DOSSIER_PAGES.findIndex((page) => page.id === pageId);
    if (nextIndex >= 0) setPageIndex(nextIndex);
  }

  function openEvidence(startMs: number) {
    setSelectedStartMs(startMs);
    goToPage("interview");
  }

  async function changeStage() {
    if (!selectedStageId || !onChangeStage) return;
    const changed = await onChangeStage(selectedStageId);
    if (changed) onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="grid max-h-[92vh] w-[min(1040px,96vw)] max-w-none grid-rows-[auto_auto_minmax(0,1fr)_auto] gap-0 overflow-hidden rounded-xl border-border bg-white p-0">
        <DialogHeader className="sr-only">
          <DialogTitle>지원자 평가 요약서</DialogTitle>
          <DialogDescription>
            {applicantName} 지원자의 평가·근거·제출 서류 오버뷰
          </DialogDescription>
        </DialogHeader>

        <header className="flex min-h-16 items-center justify-between gap-4 border-b border-border bg-white px-6 pr-14 mw-620:px-4 mw-620:pr-12">
          <div className="min-w-0">
            <strong className="block truncate text-[13px] text-ink">
              {applicantName}
            </strong>
            <span className="block truncate text-[9px] text-muted">
              {preview.positionTitle} · 채용 단계{" "}
              {preview.recruitingStageName ?? "미지정"} · 시스템 {status.label}
            </span>
          </div>
          <Link
            className="inline-flex min-h-9 flex-none items-center gap-1.5 rounded-lg bg-brand px-3 text-[10px] font-semibold text-white hover:opacity-90"
            to={applicantWorkspacePath(invitation)}
          >
            지원자 상세보기 <ExternalLink size={13} aria-hidden="true" />
          </Link>
        </header>

        <DossierNavigation activePageId={activePage.id} onSelect={goToPage} />

        <div className="min-h-0 overflow-y-auto bg-[#f2f2ef] p-5 mw-620:p-2">
          <article className="mx-auto min-h-full w-full max-w-[920px] border border-[#d7d7d1] bg-white px-8 py-7 shadow-[0_2px_12px_rgb(0_0_0_/_6%)] mw-720:px-4 mw-720:py-5">
            <PageHeading
              number={pageIndex + 1}
              title={activePage.label}
              description={pageDescription(activePage.id)}
            />

            {error ? (
              <p
                className="mb-5 rounded-lg bg-warning-soft px-4 py-3 text-[10px] text-warning"
                role="alert"
              >
                일부 자료를 불러오지 못했습니다. 현재 확인 가능한 정보만
                표시합니다.
              </p>
            ) : null}

            {loading && !insight && activePage.id !== "submissions" ? (
              <div className={ASYNC_STATE} role="status">
                지원자 평가 자료를 불러오는 중입니다.
              </div>
            ) : activePage.id === "overview" ? (
              <OverviewPage
                applicantName={applicantName}
                positionTitle={preview.positionTitle}
                stageName={preview.recruitingStageName ?? "미지정"}
                systemStatus={status.label}
                email={invitation.applicantEmail}
                insight={insight}
                report={report}
              />
            ) : activePage.id === "criteria" ? (
              <CriteriaPage insight={insight} report={report} />
            ) : activePage.id === "evidence" ? (
              <EvidencePage report={report} onOpenEvidence={openEvidence} />
            ) : activePage.id === "interview" ? (
              <InterviewPage
                report={report}
                selectedStartMs={selectedStartMs}
                onSeek={setSelectedStartMs}
              />
            ) : activePage.id === "submissions" ? (
              <SubmissionsPage
                loading={loading}
                submissions={submissions}
                selectedSubmissionId={selectedSubmissionId}
                onSelect={setSelectedSubmissionId}
              />
            ) : (
              <FinalReviewPage
                insight={insight}
                report={report}
                submissions={submissions}
                stages={stages}
                selectedStageId={selectedStageId}
                moving={moving}
                canChangeStage={Boolean(onChangeStage)}
                onStageChange={setSelectedStageId}
                onConfirm={() => void changeStage()}
              />
            )}
          </article>
        </div>

        <DossierFooter
          pageIndex={pageIndex}
          onPrevious={() => setPageIndex((current) => Math.max(0, current - 1))}
          onNext={() =>
            setPageIndex((current) =>
              Math.min(DOSSIER_PAGES.length - 1, current + 1),
            )
          }
        />
      </DialogContent>
    </Dialog>
  );
}

function DossierNavigation({
  activePageId,
  onSelect,
}: {
  activePageId: DossierPageId;
  onSelect(pageId: DossierPageId): void;
}) {
  return (
    <nav
      className="overflow-x-auto border-b border-border bg-[#fafaf8] px-5 py-3"
      aria-label="지원자 평가 요약서 페이지"
    >
      <ol className="mx-auto flex min-w-[760px] max-w-[920px] items-center">
        {DOSSIER_PAGES.map((page, index) => {
          const active = page.id === activePageId;
          return (
            <li className="flex min-w-0 flex-1 items-center" key={page.id}>
              <button
                className={`group flex min-w-0 items-center gap-2 text-left text-[9px] font-semibold ${
                  active ? "text-brand" : "text-muted hover:text-ink"
                }`}
                type="button"
                aria-current={active ? "page" : undefined}
                onClick={() => onSelect(page.id)}
              >
                <span
                  className={`grid size-6 flex-none place-items-center rounded-full border font-mono text-[8px] ${
                    active
                      ? "border-brand bg-brand text-white"
                      : "border-border bg-white text-muted group-hover:border-ink"
                  }`}
                >
                  {index + 1}
                </span>
                <span className="truncate">{page.label}</span>
              </button>
              {index < DOSSIER_PAGES.length - 1 ? (
                <span
                  className="mx-2 h-px flex-1 bg-border"
                  aria-hidden="true"
                />
              ) : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function DossierFooter({
  pageIndex,
  onPrevious,
  onNext,
}: {
  pageIndex: number;
  onPrevious(): void;
  onNext(): void;
}) {
  return (
    <footer className="grid grid-cols-[1fr_auto_1fr] items-center border-t border-border bg-white px-5 py-3">
      <button
        className="inline-flex min-h-9 w-fit items-center gap-1.5 rounded-lg border border-border px-3 text-[10px] font-semibold text-ink-secondary disabled:opacity-35"
        type="button"
        disabled={pageIndex === 0}
        onClick={onPrevious}
      >
        <ArrowLeft size={13} /> 이전
      </button>
      <span className="font-mono text-[9px] text-muted">
        {pageIndex + 1} / {DOSSIER_PAGES.length}
      </span>
      <button
        className="ml-auto inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-ink px-3 text-[10px] font-semibold text-white disabled:opacity-35"
        type="button"
        disabled={pageIndex === DOSSIER_PAGES.length - 1}
        onClick={onNext}
      >
        다음 <ArrowRight size={13} />
      </button>
    </footer>
  );
}

function PageHeading({
  number,
  title,
  description,
}: {
  number: number;
  title: string;
  description: string;
}) {
  return (
    <header className="mb-6 flex items-start gap-3 border-b-2 border-ink pb-5">
      <span className="grid size-7 flex-none place-items-center bg-ink font-mono text-[9px] text-white">
        {number}
      </span>
      <div>
        <h2 className="text-[19px] font-bold tracking-[-0.02em] text-ink">
          {title}
        </h2>
        <p className="mt-1 text-[10px] text-muted">{description}</p>
      </div>
    </header>
  );
}

function OverviewPage({
  applicantName,
  positionTitle,
  stageName,
  systemStatus,
  email,
  insight,
  report,
}: {
  applicantName: string;
  positionTitle: string;
  stageName: string;
  systemStatus: string;
  email: string;
  insight: CompanyApplicantInsight | undefined;
  report: CompanyApplicantReport | null;
}) {
  return (
    <div className="grid gap-5">
      <dl className="grid grid-cols-2 overflow-hidden rounded-lg border border-border-muted mw-620:grid-cols-1">
        <Fact label="지원자" value={applicantName} />
        <Fact label="지원 포지션" value={positionTitle} />
        <Fact label="이메일" value={email} />
        <Fact label="현재 상태" value={`${stageName} · ${systemStatus}`} />
      </dl>

      <section className="grid grid-cols-4 gap-2 mw-720:grid-cols-2">
        <SummaryMetric
          icon={<Sparkles size={16} />}
          label="종합 점수"
          value={
            insight?.overallScore == null ? "–" : `${insight.overallScore}점`
          }
        />
        <SummaryMetric
          icon={<ShieldCheck size={16} />}
          label="근거 충족"
          value={insight ? `${insight.evidenceCoverage}%` : "–"}
        />
        <SummaryMetric
          icon={<BarChart3 size={16} />}
          label="평가 기준"
          value={insight ? `${insight.criteria.length}개` : "–"}
        />
        <SummaryMetric
          icon={<MessageSquareQuote size={16} />}
          label="판단 보류"
          value={insight ? `${insight.unscoredCriteriaCount}개` : "–"}
        />
      </section>

      <section className="rounded-lg border border-border-muted bg-[linear-gradient(145deg,#f4f5ff,#fff)] p-5">
        <p className="text-[9px] font-bold tracking-[0.12em] text-brand">
          AI SUMMARY
        </p>
        <p className="mt-3 text-[12px] leading-7 text-ink-secondary">
          {insight?.summary ??
            "AI 평가 리포트가 아직 생성되지 않았습니다. 분석이 완료되면 이곳에 핵심 요약이 표시됩니다."}
        </p>
      </section>

      <section className="rounded-lg border border-border-muted p-4">
        <h3 className="mb-3 text-[12px] font-bold text-ink">
          자격요건 충족 프로필
        </h3>
        {report ? (
          <RequirementRadarProfile
            assessments={report.report.requirementAssessments ?? []}
          />
        ) : (
          <EmptyPage
            icon={<BarChart3 size={22} />}
            title="자격요건 평가 데이터 대기"
            description="면접 리포트가 준비되면 등록한 자격요건 개수에 맞는 레이더로 충족도를 비교합니다."
          />
        )}
      </section>
    </div>
  );
}

function CriteriaPage({
  insight,
  report,
}: {
  insight: CompanyApplicantInsight | undefined;
  report: CompanyApplicantReport | null;
}) {
  if (report) {
    return (
      <div className="grid gap-3">
        {report.report.items.map((item, index) => (
          <article
            className="grid grid-cols-[34px_minmax(0,1fr)_70px] gap-4 rounded-lg border border-border-muted p-4 mw-620:grid-cols-[30px_minmax(0,1fr)]"
            key={item.reportItemId}
          >
            <span className="grid size-8 place-items-center rounded-md bg-surface-muted font-mono text-[9px] text-muted">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-[12px] font-bold text-ink">
                  {item.criterionName}
                </h3>
                <span
                  className={`rounded-full px-2 py-1 text-[8px] font-semibold ${assessmentTone(item.assessmentState)}`}
                >
                  {assessmentLabel(item.assessmentState)}
                </span>
                <span className="text-[9px] text-muted">
                  가중치 {item.criterionWeight}% · 근거 {item.evidence.length}건
                </span>
              </div>
              <p className="mt-2 text-[11px] leading-6 text-ink-secondary">
                {item.observation}
              </p>
              {item.followUpQuestion ? (
                <p className="mt-2 rounded-md bg-warning-soft px-3 py-2 text-[9px] leading-5 text-warning">
                  추가 확인: {item.followUpQuestion}
                </p>
              ) : null}
            </div>
            <strong className="text-right font-mono text-[24px] text-ink mw-620:col-start-2 mw-620:text-left">
              {item.averageScore ?? "–"}
            </strong>
          </article>
        ))}
      </div>
    );
  }

  if (insight?.criteria.length) {
    return (
      <div className="grid gap-3">
        {insight.criteria.map((criterion, index) => (
          <article
            className="flex items-center gap-4 rounded-lg border border-border-muted p-4"
            key={criterion.criterionId}
          >
            <span className="font-mono text-[9px] text-muted">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div className="min-w-0 flex-1">
              <h3 className="truncate text-[12px] font-bold text-ink">
                {criterion.criterionName}
              </h3>
              <p className="mt-1 text-[9px] text-muted">
                {assessmentLabel(criterion.assessmentState)} · 근거{" "}
                {criterion.evidenceCount}건
              </p>
            </div>
            <strong className="font-mono text-[20px] text-ink">
              {criterion.score ?? "–"}
            </strong>
          </article>
        ))}
      </div>
    );
  }

  return (
    <EmptyPage
      icon={<BarChart3 size={22} />}
      title="기준별 평가 대기"
      description="평가 리포트가 생성되면 기준별 점수와 관찰 내용을 확인할 수 있습니다."
    />
  );
}

function EvidencePage({
  report,
  onOpenEvidence,
}: {
  report: CompanyApplicantReport | null;
  onOpenEvidence(startMs: number): void;
}) {
  const evidence = useMemo(
    () =>
      report?.report.items.flatMap((item) =>
        item.evidence.map((entry) => ({
          ...entry,
          criterionName: item.criterionName,
        })),
      ) ?? [],
    [report],
  );

  if (!evidence.length) {
    return (
      <EmptyPage
        icon={<MessageSquareQuote size={22} />}
        title="연결된 답변 근거 없음"
        description="AI가 인용한 답변 구간이 생기면 기준과 함께 표시됩니다."
      />
    );
  }

  return (
    <div className="grid gap-3">
      {evidence.map((entry) => (
        <article
          className="rounded-lg border border-border-muted p-4"
          key={entry.evidenceId}
        >
          <div className="flex items-center justify-between gap-3">
            <span className="rounded-full bg-brand-soft px-2 py-1 text-[8px] font-semibold text-brand">
              {entry.criterionName}
            </span>
            <button
              className="inline-flex min-h-8 items-center gap-1.5 rounded-md border border-border px-2.5 font-mono text-[9px] text-brand hover:bg-brand-soft"
              type="button"
              onClick={() => onOpenEvidence(entry.startMs)}
            >
              <PlayCircle size={13} /> {formatTime(entry.startMs)} 재생
            </button>
          </div>
          <blockquote className="mt-3 border-l-2 border-brand pl-3 text-[11px] leading-6 text-ink">
            “{entry.observation}”
          </blockquote>
          <p className="mt-2 text-[10px] leading-5 text-muted">
            {entry.rationale}
          </p>
        </article>
      ))}
    </div>
  );
}

function InterviewPage({
  report,
  selectedStartMs,
  onSeek,
}: {
  report: CompanyApplicantReport | null;
  selectedStartMs: number | null;
  onSeek(startMs: number): void;
}) {
  if (!report) {
    return (
      <EmptyPage
        icon={<Video size={22} />}
        title="면접 기록 대기"
        description="면접 영상과 자막이 준비되면 인용 근거와 함께 확인할 수 있습니다."
      />
    );
  }
  return (
    <TimelineView
      entries={report.timeline.entries}
      playbackStatus={report.timeline.playback.status}
      playbackUrl={report.timeline.playback.url}
      selectedStartMs={selectedStartMs}
      onSeek={onSeek}
    />
  );
}

function SubmissionsPage({
  loading,
  submissions,
  selectedSubmissionId,
  onSelect,
}: {
  loading: boolean;
  submissions: readonly CompanySubmission[];
  selectedSubmissionId: string;
  onSelect(submissionId: string): void;
}) {
  const selected =
    submissions.find(
      (submission) => submission.submissionId === selectedSubmissionId,
    ) ?? submissions[0];

  if (loading && !submissions.length) {
    return (
      <div className={ASYNC_STATE} role="status">
        제출 서류를 불러오는 중입니다.
      </div>
    );
  }
  if (!selected) {
    return (
      <EmptyPage
        icon={<FolderOpen size={22} />}
        title="제출 서류 없음"
        description="지원자가 제출한 자료가 아직 없거나 분석 대기 중입니다."
      />
    );
  }

  return (
    <div className="grid grid-cols-[220px_minmax(0,1fr)] overflow-hidden rounded-lg border border-border-muted mw-720:grid-cols-1">
      <aside className="border-r border-border-muted bg-[#fafaf8] p-3 mw-720:border-r-0 mw-720:border-b">
        <p className="mb-2 px-2 text-[8px] font-bold tracking-[0.12em] text-muted">
          SUBMITTED FILES
        </p>
        <div className="grid gap-1">
          {submissions.map((submission) => (
            <button
              className={`grid min-h-12 grid-cols-[28px_minmax(0,1fr)] items-center gap-2 rounded-md px-2 text-left ${submission.submissionId === selected.submissionId ? "bg-white text-brand shadow-sm" : "text-ink-secondary hover:bg-white"}`}
              key={submission.submissionId}
              type="button"
              onClick={() => onSelect(submission.submissionId)}
            >
              <span className="grid size-7 place-items-center rounded bg-surface-muted">
                <FileText size={14} />
              </span>
              <span className="min-w-0">
                <strong className="block truncate text-[10px]">
                  {materialLabel(submission.materialType)}
                </strong>
                <span className="block truncate text-[8px] text-muted">
                  {submission.originalFilename ?? submission.sourceType}
                </span>
              </span>
            </button>
          ))}
        </div>
      </aside>
      <section className="min-w-0 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-[13px] font-bold text-ink">
              {selected.originalFilename ??
                materialLabel(selected.materialType)}
            </h3>
            <p className="mt-1 text-[9px] text-muted">
              {materialLabel(selected.materialType)} ·{" "}
              {submissionStatusLabel(selected.status)}
            </p>
          </div>
          {selected.sourceUrl ? (
            <a
              className="inline-flex min-h-8 flex-none items-center gap-1 rounded-md border border-border px-2.5 text-[9px] font-semibold text-ink-secondary hover:text-brand"
              href={selected.sourceUrl}
              target="_blank"
              rel="noreferrer"
            >
              원본 열기 <ExternalLink size={12} />
            </a>
          ) : null}
        </div>
        {selected.impactSummary ? (
          <p className="mt-3 rounded-md bg-brand-soft px-3 py-2 text-[10px] leading-5 text-brand">
            AI 자료 분석: {selected.impactSummary}
          </p>
        ) : null}
        <SubmissionPreview submission={selected} />
      </section>
    </div>
  );
}

function SubmissionPreview({ submission }: { submission: CompanySubmission }) {
  const sourceUrl = submission.sourceUrl;
  const isText = Boolean(sourceUrl && /\.txt(?:$|\?)/i.test(sourceUrl));
  const isPdf = Boolean(sourceUrl && /\.pdf(?:$|\?)/i.test(sourceUrl));
  const [documentText, setDocumentText] = useState<string>();
  const [previewFailed, setPreviewFailed] = useState(false);

  useEffect(() => {
    setDocumentText(undefined);
    setPreviewFailed(false);
    if (!sourceUrl || !isText) return;
    const controller = new AbortController();
    void fetch(sourceUrl, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("submission preview failed");
        return response.text();
      })
      .then(setDocumentText)
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setPreviewFailed(true);
        }
      });
    return () => controller.abort();
  }, [isText, sourceUrl]);

  return (
    <div className="mt-4 min-h-[360px] overflow-hidden rounded-md border border-border-muted bg-surface-muted">
      {isText && documentText ? (
        <pre className="min-h-[420px] whitespace-pre-wrap bg-white p-7 font-sans text-[11px] leading-7 text-ink-secondary">
          {documentText}
        </pre>
      ) : isText && !previewFailed ? (
        <div className={ASYNC_STATE} role="status">
          문서 본문을 불러오는 중입니다.
        </div>
      ) : isPdf && sourceUrl ? (
        <iframe
          className="h-[420px] w-full bg-white"
          loading="lazy"
          referrerPolicy="no-referrer"
          sandbox=""
          src={sourceUrl}
          title={`${submission.originalFilename ?? materialLabel(submission.materialType)} 미리보기`}
        />
      ) : (
        <div className={ASYNC_STATE}>
          <div>
            <FolderOpen className="mx-auto mb-3" size={24} />
            <p>
              {sourceUrl
                ? "이 자료는 원본 링크에서 확인할 수 있습니다."
                : "미리보기 주소가 제공되지 않았습니다."}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function FinalReviewPage({
  insight,
  report,
  submissions,
  stages,
  selectedStageId,
  moving,
  canChangeStage,
  onStageChange,
  onConfirm,
}: {
  insight: CompanyApplicantInsight | undefined;
  report: CompanyApplicantReport | null;
  submissions: readonly CompanySubmission[];
  stages: readonly CompanyRecruitingStage[];
  selectedStageId: string;
  moving: boolean;
  canChangeStage: boolean;
  onStageChange(stageId: string): void;
  onConfirm(): void;
}) {
  const evidenceCount =
    report?.report.items.reduce((sum, item) => sum + item.evidence.length, 0) ??
    0;
  return (
    <div className="grid gap-5">
      <section className="grid grid-cols-4 gap-2 mw-720:grid-cols-2">
        <ReviewCheck
          label="평가 리포트"
          ready={Boolean(report)}
          value={report ? "확인 가능" : "대기"}
        />
        <ReviewCheck
          label="제출 서류"
          ready={submissions.length > 0}
          value={`${submissions.length}건`}
        />
        <ReviewCheck
          label="답변 근거"
          ready={evidenceCount > 0}
          value={`${evidenceCount}건`}
        />
        <ReviewCheck
          label="판단 보류"
          ready={insight?.unscoredCriteriaCount === 0}
          value={insight ? `${insight.unscoredCriteriaCount}건` : "–"}
        />
      </section>

      <section className="rounded-lg border border-border-muted p-5">
        <div className="flex items-start justify-between gap-5">
          <div>
            <p className="text-[9px] font-bold tracking-[0.12em] text-brand">
              FINAL REVIEW
            </p>
            <h3 className="mt-1 text-[14px] font-bold text-ink">
              담당자 최종 확인
            </h3>
          </div>
          <strong className="font-mono text-[30px] text-brand">
            {insight?.overallScore ?? "–"}
          </strong>
        </div>
        <p className="mt-4 text-[11px] leading-6 text-ink-secondary">
          {insight?.summary ??
            "최종 검토에 사용할 평가 요약이 아직 준비되지 않았습니다."}
        </p>
        <p className="mt-3 text-[9px] leading-5 text-muted">
          AI 결과는 검토를 돕는 참고 자료이며 채용 결정을 대신하지 않습니다.
        </p>
      </section>

      {canChangeStage ? (
        <section className="rounded-lg border border-brand/25 bg-brand-soft p-5">
          <div className="flex items-center gap-2 text-brand">
            <CheckCircle2 size={17} />
            <h3 className="text-[12px] font-bold">채용 단계 변경</h3>
          </div>
          <p className="mt-2 text-[10px] text-ink-secondary">
            검토가 끝났다면 현재 지원자의 채용 단계만 변경할 수 있습니다.
          </p>
          <div className="mt-4 flex gap-2 mw-620:flex-col">
            <select
              className="h-10 min-w-0 flex-1 rounded-lg border border-border bg-white px-3 text-[11px] text-ink"
              aria-label="최종 검토 채용 단계"
              value={selectedStageId}
              onChange={(event) => onStageChange(event.target.value)}
            >
              <option value="">단계를 선택하세요</option>
              {stages.map((stage) => (
                <option
                  key={stage.recruitingStageId}
                  value={stage.recruitingStageId}
                >
                  {stage.name}
                </option>
              ))}
            </select>
            <button
              className="min-h-10 rounded-lg bg-brand px-4 text-[10px] font-semibold text-white disabled:opacity-40"
              type="button"
              disabled={!selectedStageId || moving}
              onClick={onConfirm}
            >
              {moving ? "변경 중..." : "선택한 단계로 변경"}
            </button>
          </div>
        </section>
      ) : (
        <section className="rounded-lg bg-surface-muted p-4 text-[10px] leading-5 text-muted">
          현재 화면은 조회 전용입니다. 채용 단계 변경은 지원자 관리의
          칸반보드에서 할 수 있습니다.
        </section>
      )}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-r border-b border-border-muted p-4 even:border-r-0 mw-620:border-r-0">
      <dt className="text-[9px] text-muted">{label}</dt>
      <dd className="mt-1 text-[11px] font-semibold text-ink">{value}</dd>
    </div>
  );
}

function SummaryMetric({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-border-muted p-4">
      <span className="text-brand">{icon}</span>
      <span className="mt-4 block text-[9px] text-muted">{label}</span>
      <strong className="mt-1 block font-mono text-[18px] text-ink">
        {value}
      </strong>
    </div>
  );
}

function ReviewCheck({
  label,
  ready,
  value,
}: {
  label: string;
  ready: boolean;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-border-muted p-3">
      <span
        className={`inline-flex items-center gap-1 text-[8px] font-semibold ${ready ? "text-success" : "text-muted"}`}
      >
        <CheckCircle2 size={12} />
        {ready ? "확인" : "대기"}
      </span>
      <p className="mt-3 text-[9px] text-muted">{label}</p>
      <strong className="mt-1 block text-[12px] text-ink">{value}</strong>
    </div>
  );
}

function EmptyPage({
  icon,
  title,
  description,
}: {
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="grid min-h-[300px] place-items-center rounded-lg border border-dashed border-border bg-[#fafaf8] p-8 text-center">
      <div>
        <span className="mx-auto grid size-11 place-items-center rounded-full bg-surface-strong text-muted">
          {icon}
        </span>
        <h3 className="mt-3 text-[12px] font-bold text-ink">{title}</h3>
        <p className="mt-2 text-[10px] text-muted">{description}</p>
      </div>
    </div>
  );
}

function pageDescription(pageId: DossierPageId) {
  return {
    overview: "핵심 상태와 평가 지표를 먼저 확인합니다.",
    criteria: "채용 기준별 점수, 판정, 관찰 내용을 검토합니다.",
    evidence: "AI 평가에 인용된 실제 답변 구간을 확인합니다.",
    interview: "면접 영상과 자막을 시간 순서로 검토합니다.",
    submissions: "지원자가 제출한 서류와 분석 결과를 함께 확인합니다.",
    review: "검토 준비 상태를 확인하고 채용 단계를 결정합니다.",
  }[pageId];
}

function assessmentLabel(value: string) {
  if (value === "confirmed") return "근거 충분";
  if (value === "partially_confirmed") return "부분 확인";
  if (value === "insufficient_evidence") return "근거 부족";
  return "추가 확인";
}

function assessmentTone(value: string) {
  if (value === "confirmed") return "bg-success-soft text-success";
  if (value === "partially_confirmed") return "bg-brand-soft text-brand";
  return "bg-warning-soft text-warning";
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

function formatTime(milliseconds: number) {
  const seconds = Math.floor(milliseconds / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
