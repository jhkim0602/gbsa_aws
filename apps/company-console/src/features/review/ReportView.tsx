import { Bot, FileSearch, LockKeyhole, PlayCircle } from "lucide-react";
import { type KeyboardEvent, useState } from "react";

import { BUTTON_SECONDARY } from "../../app/styles/primitives";
import { formatLocator, sourceTypeLabel } from "./questionSources";
import { reviewErrorMessage } from "./reviewErrors";
import { TimelineView } from "./TimelineView";
import type {
  AssessmentState,
  EvidenceRange,
  EvidenceSufficiency,
  InterviewStage,
  InterviewStageSummary,
  ReviewEvidenceContext,
  ReviewQuestionSource,
  ReviewReport,
  ReviewReportItem,
  ReviewTimeline,
  RequirementAssessment,
  RequirementAssessmentStatus,
  ScoreBreakdown,
} from "./types";

const assessmentLabels: Record<AssessmentState, string> = {
  confirmed: "확인됨",
  partially_confirmed: "부분 확인",
  insufficient_evidence: "근거 부족",
  needs_follow_up: "추가 확인",
};

// `.immutable-badge, .report-status, .assessment-badge` share one base rule; each variant
// then replaces only the color pair.
const BADGE_BASE =
  "inline-flex min-h-[22px] items-center gap-[5px] rounded-full px-[7px]" +
  " text-[8px] font-[650] whitespace-nowrap";

/** `.assessment-badge--*`. `partially_confirmed` and `needs_follow_up` share a rule. */
const assessmentTone: Record<AssessmentState, string> = {
  confirmed: "bg-success-soft text-success",
  partially_confirmed: "bg-warning-soft text-warning",
  needs_follow_up: "bg-warning-soft text-warning",
  insufficient_evidence: "bg-surface-strong text-muted",
};

/** `.report-score.is-*` and `.report-axis__score.is-*` colour the number by band. */
const toneText: Record<string, string> = {
  strong: "text-success",
  watch: "text-warning",
  weak: "text-danger",
  unscored: "text-subtle",
};

/** `.report-axis__bar.is-*` colours the fill; an unscored axis keeps the neutral bar. */
const toneBar: Record<string, string> = {
  strong: "bg-success",
  watch: "bg-warning",
  weak: "bg-danger",
  unscored: "bg-subtle",
};

const PANEL_HEADER =
  "flex min-h-[58px] items-center justify-between gap-3 border-b border-border-muted" +
  " px-[14px] py-3 mw-520:items-start print:hidden";

const PANEL_EYEBROW = "font-mono text-[8px] font-semibold uppercase text-muted";

const TAB_BUTTON =
  "relative min-w-0 justify-self-stretch px-0.5 text-[10px] font-[650] whitespace-nowrap text-muted" +
  " aria-selected:text-brand" +
  // `::after` is the 2px underline; transparent until the tab is selected.
  " after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-transparent" +
  " after:content-[''] aria-selected:after:bg-brand";

// A4 is 210mm wide. The aspect ratio sets the minimum height so a short report still looks
// like one page. Below A4 width the sheet stops being a page and becomes a plain column.
const REPORT_PAGE =
  "grid w-full max-w-[210mm] min-h-[calc(210mm*297/210)]" +
  " grid-rows-[auto_minmax(0,1fr)_auto] border border-border bg-surface shadow-soft" +
  " outline-none mw-1180:min-h-0 mw-1180:border-0 mw-1180:shadow-none" +
  " print:block print:max-w-none print:min-h-0 print:border-0 print:shadow-none";

const REPORT_SECTION = "grid gap-[9px]";

const REPORT_SECTION_HEADING =
  "flex items-center border-b border-border-muted pb-[5px] text-[11px] font-bold";

const REPORT_EMPTY = "text-[9px] leading-[1.6] text-muted";

// `.report-axis__bar > i` is the track and `> i > b` the fill, so the tone lands on the b.
const AXIS_BAR_TRACK =
  "block h-[5px] overflow-hidden rounded-[3px] bg-surface-strong";

const reportTabs = [
  { id: "overview", label: "종합평가" },
  { id: "criteria", label: "면접 답변 근거" },
  { id: "timeline", label: "면접 타임라인" },
  { id: "requirements", label: "자격요건 평가" },
  { id: "followups", label: "추가 확인" },
] as const;

type ReportTab = (typeof reportTabs)[number]["id"];

/** The score at or above which the AI was told an axis counts as demonstrated. */
const PASSING_BAND = 60;

/** What a null score reads as. Never "0점" — the interview simply never asked. */
const UNSCORED_TEXT = "판단 근거 없음";

const sufficiencyLabels: Record<EvidenceSufficiency, string> = {
  direct: "직접 근거",
  supporting: "보조 근거",
  weak: "약한 근거",
};

/** `.evidence-sufficiency.is-*`; `weak` has no modifier, so it keeps the base tone. */
const sufficiencyTone: Record<EvidenceSufficiency, string> = {
  direct: "bg-success-soft text-success",
  supporting: "bg-warning-soft text-warning",
  weak: "bg-surface-strong text-muted",
};

const EMPTY_CONTEXT: ReviewEvidenceContext = {
  answersBySegmentId: {},
  stageBySegmentId: {},
  sourcesByCriterionId: {},
};

export function ReportView({
  report,
  evidenceContext = EMPTY_CONTEXT,
  stageSummary = [],
  timeline,
  selectedStartMs,
  onSelectEvidence,
  onOverride,
  onOverrideRequirement,
}: {
  report: ReviewReport;
  /** Resolves a citation to the answer it quoted. Absent leaves the spans unresolved. */
  evidenceContext?: ReviewEvidenceContext;
  stageSummary?: InterviewStageSummary[];
  timeline?: ReviewTimeline;
  selectedStartMs?: number | null;
  onSelectEvidence(startMs: number): void;
  onOverride?(
    reportItemId: string,
    assessmentState: AssessmentState,
    reason: string,
  ): Promise<void>;
  onOverrideRequirement?(
    requirementAssessmentId: string,
    requirementStatus: RequirementAssessmentStatus,
    reason: string,
  ): Promise<void>;
}) {
  const [activeTab, setActiveTab] = useState<ReportTab>("overview");
  const requirementAssessments = report.requirementAssessments ?? [];
  const availableTabs = timeline
    ? reportTabs
    : reportTabs.filter((tab) => tab.id !== "timeline");
  const activeIndex = availableTabs.findIndex((tab) => tab.id === activeTab);

  function selectTab(index: number) {
    const tab =
      availableTabs[(index + availableTabs.length) % availableTabs.length];
    if (!tab) return;
    setActiveTab(tab.id);
    window.requestAnimationFrame(() => {
      document.getElementById(`report-tab-${tab.id}`)?.focus();
    });
  }

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      selectTab(activeIndex + 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      selectTab(activeIndex - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      selectTab(0);
    } else if (event.key === "End") {
      event.preventDefault();
      selectTab(availableTabs.length - 1);
    }
  }

  return (
    // `overflow: hidden` clips instead of paginating when printed, so a report longer than
    // one sheet would lose everything past the first page break.
    <section
      className="overflow-hidden rounded-md border border-border bg-surface print:overflow-visible print:border-0"
      aria-labelledby="report-title"
      aria-label="AI 리포트"
    >
      <header className={PANEL_HEADER}>
        <div className="flex min-w-0 items-center gap-[9px]">
          <span
            className="grid size-[30px] flex-[0_0_30px] place-items-center rounded-md border border-border-muted bg-surface-muted text-brand-strong"
            aria-hidden="true"
          >
            <Bot size={18} />
          </span>
          <span className="grid min-w-0 gap-px">
            <p className={PANEL_EYEBROW}>AI 분석</p>
            <h2 id="report-title" className="text-[12px] font-[650]">
              면접 리포트
            </h2>
          </span>
        </div>
        <span
          className={`${BADGE_BASE} bg-surface-muted text-muted mw-520:max-w-[108px] mw-520:whitespace-normal`}
        >
          <LockKeyhole size={13} aria-hidden="true" />
          AI 원본 · 변경 불가
        </span>
      </header>

      <div
        className="grid min-h-[42px] grid-flow-col auto-cols-fr overflow-hidden border-b border-border bg-surface px-[14px] print:hidden"
        role="tablist"
        aria-label="리포트 항목"
      >
        {availableTabs.map((tab) => (
          <button
            key={tab.id}
            id={`report-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls={`report-panel-${tab.id}`}
            tabIndex={activeTab === tab.id ? 0 : -1}
            onClick={() => setActiveTab(tab.id)}
            onKeyDown={handleTabKeyDown}
            className={TAB_BUTTON}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "timeline" && timeline ? (
        <div
          id="report-panel-timeline"
          className="bg-surface p-[14px] outline-none mw-680:p-3 print:hidden"
          role="tabpanel"
          aria-labelledby="report-tab-timeline"
          tabIndex={0}
        >
          <TimelineView
            entries={timeline.entries}
            playbackStatus={timeline.playback.status}
            playbackUrl={timeline.playback.url}
            selectedStartMs={selectedStartMs}
            onSeek={onSelectEvidence}
            expanded
            idPrefix="report-timeline"
          />
        </div>
      ) : (
        <>
          {/* The canvas the sheet sits on, so the page reads as paper rather than as a panel.
          The column is sized explicitly: `justify-content: center` makes a grid column hug
          its content, so the sheet's `width: 100%` would otherwise resolve against whatever
          that tab happens to contain and every tab would be a different width. */}
          <div className="grid grid-cols-[minmax(0,210mm)] justify-center bg-surface-strong p-[14px] mw-1180:bg-surface mw-1180:p-0 print:block print:bg-transparent print:p-0">
            <article
              id={`report-panel-${activeTab}`}
              className={REPORT_PAGE}
              role="tabpanel"
              aria-labelledby={`report-tab-${activeTab}`}
              tabIndex={0}
            >
              <header className="flex items-start justify-between gap-3 border-b border-ink px-[18mm] pt-[20mm] pb-[8mm] mw-1180:px-4 mw-1180:pt-4 mw-1180:pb-3">
                <span>
                  <p className="font-mono text-[9px] font-semibold tracking-[0.06em] uppercase text-muted">
                    AI 면접 분석 리포트
                  </p>
                  <h3 className="mt-1 text-[20px] font-bold">
                    {availableTabs[activeIndex]?.label}
                  </h3>
                </span>
                {/* `.report-status--${status}` matched no rule in any stylesheet, so the badge
                has always rendered in the base success tone. */}
                <span
                  className={`${BADGE_BASE} bg-success-soft text-success`}
                  role="status"
                >
                  {report.status === "ready" ? "분석 완료" : report.status}
                </span>
              </header>

              <div className="grid content-start gap-4 px-[18mm] py-[10mm] mw-1180:px-4 mw-1180:py-3.5">
                {activeTab === "overview" ? (
                  <OverviewPage report={report} stageSummary={stageSummary} />
                ) : null}
                {activeTab === "criteria" ? (
                  <CriteriaPage
                    report={report}
                    evidenceContext={evidenceContext}
                    onSelectEvidence={onSelectEvidence}
                    onOverride={onOverride}
                  />
                ) : null}
                {activeTab === "requirements" ? (
                  <RequirementsPage
                    assessments={requirementAssessments}
                    onOverride={onOverrideRequirement}
                  />
                ) : null}
                {activeTab === "followups" ? (
                  <FollowUpPage report={report} />
                ) : null}
              </div>

              <footer className="flex items-center justify-between gap-2.5 border-t border-border-muted px-[18mm] pt-[8mm] pb-[14mm] font-mono text-[8px] text-subtle mw-1180:px-4 mw-1180:py-3">
                <span>AI 원본 · 최종 결정은 담당자가 기록합니다</span>
                {/* Labelled as a section, not "2 / 3": a section can run past one sheet, and a
                bare fraction in a document footer reads as a page number that is wrong. */}
                <span>
                  섹션 {activeIndex + 1} / {availableTabs.length}
                </span>
              </footer>
            </article>
          </div>
        </>
      )}
    </section>
  );
}

const requirementStatusLabels: Record<RequirementAssessmentStatus, string> = {
  met: "충족",
  partially_met: "부분 충족",
  not_met: "미충족",
  unknown: "판단 불가",
};

const requirementStatusTone: Record<RequirementAssessmentStatus, string> = {
  met: "bg-success-soft text-success",
  partially_met: "bg-warning-soft text-warning",
  not_met: "bg-danger-soft text-danger",
  unknown: "bg-surface-strong text-muted",
};

const requirementStatusTextColor: Record<RequirementAssessmentStatus, string> =
  {
    met: "var(--color-success)",
    partially_met: "var(--color-warning)",
    not_met: "var(--color-danger)",
    unknown: "var(--color-subtle)",
  };

const requirementStatusOrder: RequirementAssessmentStatus[] = [
  "met",
  "partially_met",
  "not_met",
  "unknown",
];

function requirementPlotValue(
  status: RequirementAssessmentStatus,
): number | null {
  if (status === "met") return 100;
  if (status === "partially_met") return 50;
  if (status === "not_met") return 0;
  return null;
}

function RequirementsPage({
  assessments,
  onOverride,
}: {
  assessments: RequirementAssessment[];
  onOverride?(
    requirementAssessmentId: string,
    requirementStatus: RequirementAssessmentStatus,
    reason: string,
  ): Promise<void>;
}) {
  if (assessments.length === 0) {
    return (
      <div className="grid gap-3">
        <p className={REPORT_EMPTY}>
          이 리포트에는 자격요건 충족도 판정이 없습니다. 기존 리포트는 그대로
          유지되며 새로 생성되는 리포트부터 별도 판정이 추가됩니다.
        </p>
      </div>
    );
  }
  const required = assessments.filter(
    (item) => item.requirementType === "required",
  );
  const preferred = assessments.filter(
    (item) => item.requirementType === "preferred",
  );

  return (
    <div className="grid gap-4">
      <p className="rounded-e-[5px] border-l-2 border-brand bg-brand-soft px-3 py-2.5 text-[9px] leading-[1.65] text-ink-secondary">
        제출 자료와 면접 답변을 함께 확인해 각 자격요건을 충족, 부분 충족,
        미충족, 판단 불가 중 하나의 상태로 표시합니다.
      </p>
      <RequirementGroup
        assessments={required}
        label="필수 자격"
        onOverride={onOverride}
      />
      <RequirementGroup
        assessments={preferred}
        label="우대 사항"
        onOverride={onOverride}
      />
    </div>
  );
}

function RequirementGroup({
  label,
  assessments,
  onOverride,
}: {
  label: string;
  assessments: RequirementAssessment[];
  onOverride?(
    requirementAssessmentId: string,
    requirementStatus: RequirementAssessmentStatus,
    reason: string,
  ): Promise<void>;
}) {
  return (
    <section className={REPORT_SECTION} aria-label={label}>
      <h4 className={REPORT_SECTION_HEADING}>{label}</h4>
      {assessments.length ? (
        <div className="grid gap-2.5">
          {assessments.map((assessment, index) => (
            <RequirementCard
              assessment={assessment}
              index={index}
              key={assessment.requirementAssessmentId}
              onOverride={onOverride}
            />
          ))}
        </div>
      ) : (
        <p className={REPORT_EMPTY}>등록된 항목이 없습니다.</p>
      )}
    </section>
  );
}

function RequirementCard({
  assessment,
  index,
  onOverride,
}: {
  assessment: RequirementAssessment;
  index: number;
  onOverride?(
    requirementAssessmentId: string,
    requirementStatus: RequirementAssessmentStatus,
    reason: string,
  ): Promise<void>;
}) {
  const initialStatus = assessment.humanOverride?.status ?? assessment.status;
  const [status, setStatus] =
    useState<RequirementAssessmentStatus>(initialStatus);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const changed = status !== initialStatus;

  async function save() {
    if (!onOverride || saving || !changed || !reason.trim()) return;
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      await onOverride(
        assessment.requirementAssessmentId,
        status,
        reason.trim(),
      );
      setSaved(true);
    } catch (cause) {
      console.error("requirement override failed", cause);
      setError(
        reviewErrorMessage(cause, "자격요건 판단을 기록하지 못했습니다."),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="grid gap-2 rounded-md border border-border-muted bg-surface-muted/50 p-3 break-inside-avoid">
      <header className="flex items-start justify-between gap-3">
        <strong className="text-[11px] leading-[1.55] text-ink">
          {assessment.statement}
        </strong>
        <span className="inline-flex shrink-0 items-center gap-1.5">
          <span
            className={`${BADGE_BASE} ${requirementStatusTone[initialStatus]}`}
          >
            {assessment.humanOverride ? "사람 판단 · " : ""}
            {requirementStatusLabels[initialStatus]}
          </span>
        </span>
      </header>
      <p className="text-[9px] leading-[1.65] text-muted">
        {assessment.rationale}
      </p>
      <span className="font-mono text-[8px] text-subtle">
        근거 {assessment.evidence.length}건
        {assessment.status === "unknown"
          ? " · 신뢰도 계산 안 함"
          : ` · 판정 신뢰도 ${Math.round(assessment.confidence * 100)}%`}
      </span>
      {assessment.evidence.length ? (
        <div className="grid gap-1.5">
          {assessment.evidence.map((evidence) => (
            <div
              className="rounded-md border border-border-muted bg-surface px-2.5 py-2"
              key={`${assessment.requirementAssessmentId}-${evidence.evidenceId}`}
            >
              <div className="flex flex-wrap items-center gap-1.5 text-[8px] text-subtle">
                <b className="text-brand">
                  {evidence.sourceKind === "interview"
                    ? "면접 답변"
                    : "제출 자료"}
                </b>
                <span>{sourceTypeLabel(evidence.sourceType)}</span>
                <span>{formatLocator(evidence.locator)}</span>
              </div>
              <p className="mt-1 text-[9px] leading-[1.55] text-ink-secondary">
                {evidence.excerpt}
              </p>
              <p className="mt-1 text-[8px] leading-[1.5] text-muted">
                {evidence.explanation}
              </p>
            </div>
          ))}
        </div>
      ) : null}
      {onOverride ? (
        <div className="grid gap-1.5 border-t border-border-muted pt-2 print:hidden">
          <label className="grid gap-1">
            <span className="text-[8px] font-semibold text-ink-secondary">
              사람 판단
            </span>
            <select
              aria-label={`자격요건 사람 판단 ${index + 1}`}
              className="min-h-[32px] rounded-md border border-border bg-surface px-2 text-[9px]"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as RequirementAssessmentStatus);
                setSaved(false);
              }}
            >
              <option value="met">충족</option>
              <option value="partially_met">부분 충족</option>
              <option value="not_met">미충족</option>
              <option value="unknown">판단 불가</option>
            </select>
          </label>
          {changed ? (
            <>
              <textarea
                aria-label={`자격요건 수정 사유 ${index + 1}`}
                className="min-h-[52px] resize-y rounded-md border border-border bg-surface px-2 py-1.5 text-[9px] leading-[1.5]"
                placeholder="자료와 답변을 확인한 판단 근거를 적어 주세요."
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
              <button
                className={`${BUTTON_SECONDARY} justify-self-start`}
                disabled={!reason.trim() || saving}
                type="button"
                onClick={() => void save()}
              >
                {saving ? "저장 중…" : "사람 판단 저장"}
              </button>
            </>
          ) : null}
          {saved ? (
            <p className="text-[8px] text-success" role="status">
              사람 판단을 별도로 기록했습니다.
            </p>
          ) : null}
          {error ? (
            <p className="text-[8px] text-danger" role="alert">
              {error}
            </p>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function OverviewPage({
  report,
  stageSummary,
}: {
  report: ReviewReport;
  stageSummary: InterviewStageSummary[];
}) {
  const assessments = report.requirementAssessments ?? [];
  const scoredCount = assessments.filter(
    (assessment) => assessment.status !== "unknown",
  ).length;
  const statusCounts = requirementStatusOrder.map(
    (status) =>
      [
        status,
        assessments.filter((assessment) => assessment.status === status).length,
      ] as const,
  );

  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-[132px_132px_minmax(0,1fr)] items-center gap-3 mw-680:grid-cols-[repeat(2,minmax(0,1fr))] mw-520:grid-cols-[minmax(0,1fr)]">
        <div className="grid justify-items-center gap-0.5 rounded-lg border border-border-muted bg-surface-muted px-2.5 py-[14px] text-center">
          <span className="text-[9px] font-[650] text-muted">
            자격요건 평가
          </span>
          <strong className="text-[17px] font-bold leading-[1.3] text-brand-strong">
            상태별 판정
          </strong>
          <small className="text-[8px] leading-[1.4] text-subtle">
            점수로 환산하지 않음
          </small>
        </div>
        <div className="grid justify-items-center gap-0.5 rounded-lg border border-border-muted bg-brand-soft px-2.5 py-[14px] text-center">
          <span className="text-[9px] font-[650] text-muted">판단 완료</span>
          <strong className="text-[34px] font-bold leading-[1.1] text-brand-strong">
            {scoredCount}
          </strong>
          <small className="text-[8px] leading-[1.4] text-subtle">
            전체 {assessments.length}개 자격요건
          </small>
        </div>
        <p className="text-[11px] leading-[1.75] text-ink-secondary mw-680:col-span-2 mw-520:col-span-1">
          {report.summary}
        </p>
      </div>

      <p className="rounded-e-[5px] border-l-2 border-brand bg-brand-soft px-3 py-2.5 text-[9px] leading-[1.65] text-ink-secondary">
        기업이 작성한 필수·우대 자격요건만 평가합니다. 각 항목은 충족, 부분
        충족, 미충족, 판단 불가 상태로만 표시하며 최종 채용 결정은 담당자가
        기록합니다.
      </p>

      {stageSummary.length > 0 ? (
        <section className={REPORT_SECTION} aria-label="적응형 면접 구성 요약">
          <h4 className={REPORT_SECTION_HEADING}>지원자별 적응형 면접</h4>
          <p className="mb-2 text-[8px] leading-[1.6] text-muted">
            고정된 기술·프로젝트·인성 단계 대신 기업의 자격요건과 필수 질문을
            지원자 자료에 연결하고, 답변 근거가 부족할 때만 꼬리질문을
            이어갑니다. 총 질문 {stageSummary.reduce((sum, item) => sum + item.questionCount, 0)}개 ·
            확인된 근거 {stageSummary.reduce((sum, item) => sum + item.evidenceCount, 0)}개
          </p>
          <ol className="grid grid-cols-3 gap-2 mw-520:grid-cols-[minmax(0,1fr)]">
            {[
              ["기업 자격요건 확인", "필수·우대 항목과 제출 자료의 관련 근거를 연결"],
              ["반드시 물어볼 질문", "기업이 지정한 질문을 자연스러운 흐름으로 확인"],
              ["필요한 꼬리질문", "본인 역할·판단 근거·결과가 부족한 경우에만 추가 확인"],
            ].map(([label, description], index) => (
              <li
                className="rounded-md border border-border-muted bg-surface-muted px-3 py-2.5"
                key={label}
              >
                <small className="font-mono text-[8px] text-brand">
                  {String(index + 1).padStart(2, "0")}
                </small>
                <strong className="mt-0.5 block text-[10px]">{label}</strong>
                <span className="mt-1 block text-[8px] text-muted">
                  {description}
                </span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <section className={REPORT_SECTION} aria-label="자격요건 충족 프로필">
        <h4 className={REPORT_SECTION_HEADING}>자격요건 충족 프로필</h4>
        {assessments.length > 0 ? (
          <RequirementRadarProfile assessments={assessments} />
        ) : (
          <p className={REPORT_EMPTY}>
            이 리포트에는 평가할 자격요건이 없습니다.
          </p>
        )}
      </section>

      <section className={REPORT_SECTION} aria-label="자격요건 상태 요약">
        <h4 className={REPORT_SECTION_HEADING}>자격요건 상태</h4>
        <dl className="flex flex-wrap gap-y-2 gap-x-4">
          {statusCounts.map(([status, count]) => (
            <div key={status} className="flex items-center gap-1.5">
              <dt>
                <span
                  className={`${BADGE_BASE} ${requirementStatusTone[status]}`}
                >
                  {requirementStatusLabels[status]}
                </span>
              </dt>
              <dd className="font-mono text-[10px] font-[650] text-ink-secondary">
                {count}개
              </dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}

/**
 * A reviewer overruling the AI's assessment of one criterion, with the reason they give.
 *
 * The reason is required, and the control will not submit without one. Before this, the state
 * was sent the moment the select changed and the reason was a fixed string, so every override in
 * the audit trail read identically — which records the fact and loses the only part a later
 * reader needs. Disagreement with a score is exactly where "why" matters.
 *
 * Human judgement stays separate from the AI original: this writes a `HumanReview`, and the
 * report itself remains immutable (`ai_original_immutable`).
 */
function AssessmentOverride({
  item,
  index,
  onOverride,
}: {
  item: ReviewReportItem;
  index: number;
  onOverride(
    reportItemId: string,
    assessmentState: AssessmentState,
    reason: string,
  ): Promise<void>;
}) {
  const [state, setState] = useState<AssessmentState>(item.assessmentState);
  const [reason, setReason] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const changed = state !== item.assessmentState;
  const ready = changed && reason.trim().length > 0 && !saving;

  async function save() {
    // The guard is on the handler, not only on `disabled`: the attribute reflects the last
    // render, so a second click landing before React re-renders would submit twice.
    if (saving) return;
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      await onOverride(item.reportItemId, state, reason.trim());
      setSaved(true);
    } catch (cause) {
      // The only record of the failure other than this message: nothing in the console logs
      // review writes, so a silent rejection left no trace at all.
      console.error("assessment override failed", cause);
      setError(reviewErrorMessage(cause, "사람 평가를 기록하지 못했습니다."));
    } finally {
      setSaving(false);
    }
  }

  return (
    // `.report-item .compact-field` is hidden when printed: an editable control is not part of
    // the document.
    <div className="grid gap-1.5 print:hidden">
      <label className="grid gap-1.5">
        <span className="text-[9px] font-semibold text-ink-secondary">
          사람 평가
        </span>
        <select
          aria-label={`사람 평가 ${index + 1}`}
          className="min-h-[34px] w-full rounded-md border border-border bg-surface px-[9px] py-[7px] text-[10px] text-ink focus:border-brand focus:outline-2 focus:outline-offset-0 focus:outline-[#5966ce1f]"
          value={state}
          onChange={(event) => {
            setState(event.target.value as AssessmentState);
            setSaved(false);
          }}
        >
          <option value="confirmed">확인됨</option>
          <option value="partially_confirmed">부분 확인</option>
          <option value="insufficient_evidence">근거 부족</option>
          <option value="needs_follow_up">추가 확인 필요</option>
        </select>
      </label>

      {changed ? (
        <>
          <label className="grid gap-1.5">
            <span className="text-[9px] font-semibold text-ink-secondary">
              수정 사유
            </span>
            <textarea
              aria-label={`수정 사유 ${index + 1}`}
              className="min-h-[56px] w-full resize-y rounded-md border border-border bg-surface px-[9px] py-[7px] text-[10px] leading-[1.6] text-ink placeholder:text-subtle focus:border-brand focus:outline-2 focus:outline-offset-0 focus:outline-[#5966ce1f]"
              placeholder="Evidence를 확인한 결과 AI 판단과 다르게 본 이유를 적어 주세요."
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <button
            className={`${BUTTON_SECONDARY} justify-self-start`}
            disabled={!ready}
            type="button"
            onClick={() => void save()}
          >
            {saving ? "저장 중…" : "사람 평가 저장"}
          </button>
        </>
      ) : null}

      {saved ? (
        <p className="text-[9px] text-success" role="status">
          사람 평가를 기록했습니다. AI 원본 리포트는 그대로 유지됩니다.
        </p>
      ) : null}

      {error ? (
        <p className="text-[9px] text-danger" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function CriteriaPage({
  report,
  evidenceContext,
  onSelectEvidence,
  onOverride,
}: {
  report: ReviewReport;
  evidenceContext: ReviewEvidenceContext;
  onSelectEvidence(startMs: number): void;
  onOverride?(
    reportItemId: string,
    assessmentState: AssessmentState,
    reason: string,
  ): Promise<void>;
}) {
  // Which citation the reviewer is following, so the axis they clicked and the answer it
  // rests on are highlighted together instead of the reviewer having to match ids by eye.
  const [followedEvidenceId, setFollowedEvidenceId] = useState<string | null>(
    null,
  );

  if (report.items.length === 0) {
    return <p className={REPORT_EMPTY}>평가된 기준이 없습니다.</p>;
  }

  function followEvidence(evidence: EvidenceRange) {
    setFollowedEvidenceId(evidence.evidenceId);
    onSelectEvidence(evidence.startMs);
  }

  return (
    <div className="grid gap-3.5">
      {report.items.map((item, index) => {
        const sources = evidenceContext.sourcesByCriterionId[item.criterionId];

        return (
          // A criterion reads as one unit, so it breaks between rather than through.
          <article
            className="grid gap-2.5 break-inside-avoid [&+&]:border-t [&+&]:border-border-muted [&+&]:pt-3.5"
            key={item.reportItemId}
          >
            <header className="flex items-center justify-between gap-2.5">
              <h3 className="min-w-0 text-[12px] font-bold">
                {item.criterionName}
              </h3>
              <span className="inline-flex flex-[0_0_auto] items-center gap-[7px]">
                <span
                  className={`${BADGE_BASE} ${assessmentTone[item.assessmentState]}`}
                >
                  {assessmentLabels[item.assessmentState]}
                </span>
              </span>
            </header>
            <p className="text-[10px] leading-[1.6] text-muted">
              {item.observation}
            </p>

            {onOverride && (
              <AssessmentOverride
                item={item}
                index={index}
                onOverride={onOverride}
              />
            )}

            <div className="grid gap-2">
              {item.evidence.map((evidence) => (
                <EvidenceCard
                  key={evidence.evidenceId}
                  evidence={evidence}
                  answer={
                    evidenceContext.answersBySegmentId[
                      evidence.transcriptSegmentId
                    ]
                  }
                  interviewStage={
                    evidenceContext.stageBySegmentId?.[
                      evidence.transcriptSegmentId
                    ]
                  }
                  isFollowed={followedEvidenceId === evidence.evidenceId}
                  onFollow={followEvidence}
                />
              ))}
            </div>

            {sources && sources.length > 0 ? (
              <QuestionSources sources={sources} />
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

/** One quoted answer: what the AI read into it, and the applicant's own words. */
function EvidenceCard({
  evidence,
  answer,
  interviewStage,
  isFollowed,
  onFollow,
}: {
  evidence: EvidenceRange;
  answer?: { text: string; startMs: number; endMs: number };
  interviewStage?: InterviewStage;
  isFollowed: boolean;
  onFollow(evidence: EvidenceRange): void;
}) {
  return (
    <article
      // `is-followed` marks the answer the reviewer arrived at from an axis chip.
      className={`grid gap-1.5 break-inside-avoid rounded-md border border-l-[3px] px-2.5 py-[9px] ${
        isFollowed
          ? "border-[#5966ce4c] border-l-brand bg-[#5966ce0f]"
          : "border-border-muted border-l-border bg-surface-muted"
      }`}
      aria-current={isFollowed ? "true" : undefined}
    >
      <header className="flex items-center justify-between gap-2">
        <span className="flex flex-wrap items-center gap-1.5">
          <span
            className={`rounded-sm px-1.5 py-0.5 text-[8px] font-[650] ${sufficiencyTone[evidence.sufficiency]}`}
            title="AI가 이 답변을 기준의 근거로 얼마나 직접적으로 봤는지"
          >
            {sufficiencyLabels[evidence.sufficiency]}
          </span>
          {interviewStage ? (
            <span className="rounded-sm bg-brand-soft px-1.5 py-0.5 text-[8px] font-[650] text-brand-strong">
              {interviewStageLabels[interviewStage]}
            </span>
          ) : null}
        </span>
        <button
          type="button"
          aria-label="Evidence 재생"
          onClick={() => onFollow(evidence)}
          className="inline-flex flex-[0_0_auto] min-h-[30px] items-center gap-1.5 rounded-md border border-[#5966ce47] bg-surface px-2 py-1 text-brand-strong hover:border-brand hover:bg-[#5966ce1a] print:hidden"
        >
          <PlayCircle size={15} aria-hidden="true" />
          <span className="grid gap-px text-left">
            <strong className="text-[9px]">Evidence 재생</strong>
            <small className="font-mono text-[8px] text-muted">
              {formatTime(evidence.startMs)} – {formatTime(evidence.endMs)}
            </small>
          </span>
        </button>
      </header>
      <p className="text-[9px] font-semibold leading-[1.55] text-ink-secondary">
        {evidence.observation}
      </p>
      <p className="text-[9px] leading-[1.6] text-muted">
        {evidence.rationale}
      </p>
      {answer ? (
        // The applicant's own words, set apart from the AI's prose above it: a reviewer must
        // be able to tell what was said from what was concluded.
        <blockquote className="grid gap-[3px] rounded-[5px] bg-surface px-[9px] py-[7px]">
          <small className="font-mono text-[7px] text-subtle">
            지원자 답변 · {formatTime(answer.startMs)}
          </small>
          <p className="text-[9px] leading-[1.65] text-ink">{answer.text}</p>
        </blockquote>
      ) : (
        <p className={REPORT_EMPTY}>
          이 구간의 답변 전문이 타임라인에 없습니다. 영상에서 직접 확인해
          주세요.
        </p>
      )}
    </article>
  );
}

const interviewStageLabels: Record<InterviewStage, string> = {
  adaptive: "기업 기준",
  technical: "기술",
  project_deep_dive: "프로젝트",
  behavioral: "협업·인성",
};

/**
 * The submitted material the interview drew this criterion's questions from.
 *
 * Kept visibly separate from Evidence: a resume line the applicant wrote is not an answer
 * they gave, and a reviewer who reads it as one would be crediting the wrong thing.
 */
function QuestionSources({ sources }: { sources: ReviewQuestionSource[] }) {
  return (
    <details className="rounded-[5px] border border-border-muted bg-surface-muted [&>p]:px-[9px] [&>p]:pb-[9px] [&>ul]:px-[9px] [&>ul]:pb-[9px]">
      <summary className="flex min-h-[30px] cursor-pointer list-none items-center gap-1.5 px-[9px] py-1.5 text-[9px] font-[650] text-ink-secondary [&::-webkit-details-marker]:hidden">
        <FileSearch size={13} aria-hidden="true" />
        질문 근거 자료
        <span className="ml-auto font-mono text-[8px] text-subtle">
          {sources.length}개
        </span>
      </summary>
      <p className={`${REPORT_EMPTY} border-t border-border-muted pt-2`}>
        지원자 답변이 아니라 AI가 질문을 만들 때 참고한 제출 자료입니다.
      </p>
      <ul className="grid gap-1.5">
        {sources.map((source) => (
          <li
            key={source.sourceId}
            className="grid gap-[5px] rounded-sm border border-border-muted bg-surface p-2 [&+&]:border-t [&+&]:border-border-muted"
          >
            <span className="flex items-center gap-[7px] text-[8px] font-[650] text-ink-secondary">
              {sourceTypeLabel(source.sourceType)}
              <small className="font-mono text-[7px] text-subtle">
                {formatLocator(source.locator)}
              </small>
            </span>
            <p className="text-[8px] leading-[1.55] text-muted">
              {source.excerpt}
            </p>
          </li>
        ))}
      </ul>
    </details>
  );
}

function FollowUpPage({ report }: { report: ReviewReport }) {
  const followUps = report.items.filter((item) => item.followUpQuestion);
  const unscored = report.items.filter((item) => item.averageScore === null);

  return (
    <div className="grid gap-4">
      <section className={REPORT_SECTION} aria-label="사람이 물어볼 질문">
        <h4 className={REPORT_SECTION_HEADING}>사람 면접에서 확인할 질문</h4>
        {followUps.length > 0 ? (
          <ol className="grid gap-[9px]">
            {followUps.map((item) => (
              <li
                key={item.reportItemId}
                className="grid gap-[3px] border-l-2 border-warning pl-[9px]"
              >
                <span className="text-[9px] font-[650] text-ink-secondary">
                  {item.criterionName}
                </span>
                <p className="text-[10px] leading-[1.65] text-muted">
                  {item.followUpQuestion}
                </p>
              </li>
            ))}
          </ol>
        ) : (
          <p className={REPORT_EMPTY}>
            AI가 추가로 물어볼 질문을 남기지 않았습니다.
          </p>
        )}
      </section>

      <section className={REPORT_SECTION} aria-label="점수 없는 기준">
        <h4 className={REPORT_SECTION_HEADING}>점수가 없는 기준</h4>
        {unscored.length > 0 ? (
          <ul className="grid gap-[9px]">
            {unscored.map((item) => (
              <li
                key={item.reportItemId}
                className="grid gap-[3px] rounded-[5px] border border-border-muted bg-surface-muted px-2.5 py-[9px]"
              >
                <strong className="text-[10px]">{item.criterionName}</strong>
                <small className="text-[8px] text-subtle">
                  {assessmentLabels[item.assessmentState]}
                </small>
                <p className="text-[10px] leading-[1.65] text-muted">
                  {item.evidence.length > 0
                    ? "인용된 답변은 있으나 축별 점수가 남지 않았습니다. Evidence를 직접 확인해 주세요."
                    : "면접에서 이 기준을 확인할 답변이 기록되지 않았습니다."}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className={REPORT_EMPTY}>모든 기준에 점수가 있습니다.</p>
        )}
      </section>
    </div>
  );
}

function ScoreValue({ score }: { score: number | null }) {
  const tone = toneOf(score);
  return (
    // An unjudged axis is greyed and set smaller: it must never read as a zero.
    <span
      className={`font-mono whitespace-nowrap ${toneText[tone]} ${
        tone === "unscored"
          ? "text-[9px] font-semibold"
          : "text-[11px] font-bold"
      }`}
    >
      {score === null ? UNSCORED_TEXT : `${score}점`}
    </span>
  );
}

function ScoreBar({ score }: { score: number | null }) {
  return (
    <span className="mw-520:col-span-full" aria-hidden="true">
      <i className={AXIS_BAR_TRACK}>
        <b
          className={`block h-full rounded-[3px] ${toneBar[toneOf(score)]}`}
          style={{ width: `${score ?? 0}%` }}
        />
      </i>
    </span>
  );
}

/**
 * What the score covers, in the terms the score was actually computed in.
 *
 * "기준 3개 평균" counts criteria; the score is a weighted mean, so a criterion worth 40% and one
 * worth 5% are not two of anything. The divisor is the honest unit, and it is the one the
 * calculator below expands.
 */
function coverageLabel(report: ReviewReport) {
  const denominator = report.scoringBreakdown?.denominator;
  if (denominator === undefined || denominator <= 0) {
    return `100점 기준 · 기준 ${report.items.length - report.unscoredCriteriaCount}개 평균`;
  }
  const covered = Math.round(denominator * 100);
  return covered >= 100
    ? "100점 기준 · 전체 기준 반영"
    : `100점 기준 · 가중치 ${covered}%만 반영`;
}

const CALC_ROW =
  "grid grid-cols-[minmax(0,1fr)_58px_44px_62px] items-center gap-2 py-[5px]" +
  " mw-520:grid-cols-[minmax(0,1fr)_auto]";
const CALC_NAME = "truncate text-[10px] text-ink-secondary";
const CALC_NUMBER = "text-right font-mono text-[10px] text-ink-secondary";
const CALC_TOTAL =
  "mt-1 grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-2 border-t border-border" +
  " pt-2 text-[10px]";

/**
 * The arithmetic behind the report score, laid out so a reviewer can redo it.
 *
 * The divisor is the reason this exists rather than a bare number. `55.7 ÷ 0.75 = 74` says a
 * quarter of the interview is not in the score; `74` alone cannot. Excluded criteria are listed
 * with their reason for the same reason — otherwise the divisor appears from nowhere.
 */
function ScoreCalculator({
  breakdown,
  score,
}: {
  breakdown: ScoreBreakdown | null;
  score: number | null;
}) {
  // Null on reports generated before the arithmetic was recorded. Rendering an empty calculator
  // would imply a finding; saying nothing is accurate.
  if (!breakdown || breakdown.contributions.length === 0) return null;

  return (
    <section className={REPORT_SECTION} aria-label="종합 점수 계산 근거">
      <h4 className={REPORT_SECTION_HEADING}>이 점수가 나온 계산</h4>
      <div>
        {breakdown.contributions.map((contribution) => (
          <div className={CALC_ROW} key={contribution.key}>
            <span className={CALC_NAME}>
              {contribution.criterionName ?? contribution.key}
            </span>
            <span className={CALC_NUMBER}>{contribution.score}점</span>
            <span className={CALC_NUMBER}>
              {Math.round(contribution.normalizedWeight * 100)}%
            </span>
            <span className={`${CALC_NUMBER} text-ink`}>
              {contribution.contribution.toFixed(1)}
            </span>
          </div>
        ))}
        <p className={CALC_TOTAL}>
          <span className="text-muted">
            합 {breakdown.numerator.toFixed(1)} ÷{" "}
            {breakdown.denominator.toFixed(2)}
          </span>
          <strong className="font-mono text-[13px] font-bold text-ink">
            {score ?? UNSCORED_TEXT}
          </strong>
        </p>
      </div>

      {breakdown.exclusions.length > 0 ? (
        <div className="grid gap-1 rounded-[5px] bg-surface-muted px-2.5 py-2">
          <span className="text-[8px] font-[650] text-muted">
            점수에서 제외된 기준
          </span>
          {breakdown.exclusions.map((exclusion) => (
            <p
              className="text-[9px] leading-[1.55] text-ink-secondary"
              key={exclusion.key}
            >
              <span className="font-mono">
                {Math.round(exclusion.normalizedWeight * 100)}%
              </span>{" "}
              {exclusion.criterionName ?? exclusion.key}
              {exclusion.reason ? ` — ${exclusion.reason}` : ""}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  );
}

const RADAR_WIDTH = 360;
const RADAR_HEIGHT = 270;
const RADAR_CENTER_X = RADAR_WIDTH / 2;
const RADAR_CENTER_Y = 130;
const RADAR_RADIUS = 82;

export function RequirementRadarProfile({
  assessments,
}: {
  assessments: RequirementAssessment[];
}) {
  let requiredIndex = 0;
  let preferredIndex = 0;
  const plottedRequirements = assessments.map((assessment) => {
    const index =
      assessment.requirementType === "required"
        ? (requiredIndex += 1)
        : (preferredIndex += 1);
    return {
      ...assessment,
      shortLabel: `${assessment.requirementType === "required" ? "필수" : "우대"} ${index}`,
      plotValue: requirementPlotValue(assessment.status),
    };
  });
  const gridLevels = [25, 50, 75, 100];
  const dataPoints = plottedRequirements.map((requirement, index) =>
    radarPoint(index, requirement.plotValue ?? 0, plottedRequirements.length),
  );
  const hasUnknownStatus = plottedRequirements.some(
    (requirement) => requirement.plotValue === null,
  );

  if (plottedRequirements.length === 0) {
    return <p className={REPORT_EMPTY}>평가할 자격요건이 없습니다.</p>;
  }

  return (
    <div className="grid grid-cols-[minmax(280px,0.95fr)_minmax(220px,1.05fr)] items-center gap-5 rounded-lg bg-surface-muted px-4 py-3 mw-680:grid-cols-[minmax(0,1fr)] mw-680:gap-2 mw-520:px-2.5">
      <svg
        aria-label={`기업이 설정한 자격요건 ${plottedRequirements.length}개의 상태 프로필`}
        className="mx-auto h-auto w-full max-w-[360px] overflow-visible"
        role="img"
        viewBox={`0 0 ${RADAR_WIDTH} ${RADAR_HEIGHT}`}
      >
        <title>자격요건 충족 프로필</title>
        <desc>
          기업이 설정한 필수·우대 자격요건을 충족, 부분 충족, 미충족, 판단 불가
          상태로 비교합니다.
        </desc>
        {gridLevels.map((level) =>
          radarGrid(level, plottedRequirements.length),
        )}
        {plottedRequirements.map((requirement, index) => {
          const outer = radarPoint(index, 100, plottedRequirements.length);
          return (
            <line
              key={requirement.jobRequirementId}
              stroke="var(--color-border-strong)"
              strokeWidth="0.8"
              x1={RADAR_CENTER_X}
              x2={outer.x}
              y1={RADAR_CENTER_Y}
              y2={outer.y}
            />
          );
        })}
        {radarDataShape(dataPoints, hasUnknownStatus)}
        {dataPoints.map((point, index) => {
          const requirement = plottedRequirements[index];
          return (
            <circle
              aria-hidden="true"
              cx={point.x}
              cy={point.y}
              fill={
                requirement.plotValue === null
                  ? "var(--color-surface)"
                  : "var(--color-brand)"
              }
              key={requirement.jobRequirementId}
              r={requirement.plotValue === null ? 3.5 : 4}
              stroke="var(--color-brand)"
              strokeWidth="1.5"
            />
          );
        })}
        {plottedRequirements.map((requirement, index) => {
          const labelPoint = radarPoint(index, 128, plottedRequirements.length);
          return (
            <g key={requirement.jobRequirementId}>
              <text
                fill="var(--color-ink-secondary)"
                fontSize="10"
                fontWeight="650"
                textAnchor="middle"
                x={labelPoint.x}
                y={labelPoint.y - 2}
              >
                {requirement.shortLabel}
              </text>
              <text
                fill={requirementStatusTextColor[requirement.status]}
                fontSize="9"
                fontWeight="700"
                textAnchor="middle"
                x={labelPoint.x}
                y={labelPoint.y + 11}
              >
                {requirementStatusLabels[requirement.status]}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="grid gap-2.5">
        <div>
          <strong className="text-[11px] text-ink">
            기업이 설정한 자격요건
          </strong>
          <p className="mt-1 text-[8px] leading-[1.6] text-muted">
            등록된 자격요건 개수만큼 축이 만들어집니다. 바깥쪽에 가까울수록 제출
            자료와 면접 답변에서 충족 근거가 명확하게 확인됐습니다.
          </p>
        </div>
        <dl className="grid gap-y-2">
          {plottedRequirements.map((requirement) => (
            <div
              className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-2 border-b border-border-muted pb-1.5"
              key={requirement.jobRequirementId}
            >
              <dt className="min-w-0 text-[9px] font-[650] leading-[1.45] text-ink-secondary">
                <small className="mr-1 text-[7px] font-semibold text-brand">
                  {requirement.shortLabel}
                </small>
                {requirement.statement}
              </dt>
              <dd className="text-right">
                <span
                  className={`${BADGE_BASE} ${requirementStatusTone[requirement.status]}`}
                >
                  {requirementStatusLabels[requirement.status]}
                </span>
              </dd>
            </div>
          ))}
        </dl>
        {hasUnknownStatus ? (
          <p className="text-[8px] leading-[1.5] text-subtle">
            판단 불가는 해당 자격요건을 확인할 근거가 부족하다는 뜻입니다.
          </p>
        ) : null}
      </div>
    </div>
  );
}

function radarPoint(index: number, score: number, axisCount: number) {
  const angle = -Math.PI / 2 + (index * Math.PI * 2) / Math.max(axisCount, 1);
  const radius = RADAR_RADIUS * (score / 100);
  return {
    x: Number((RADAR_CENTER_X + Math.cos(angle) * radius).toFixed(2)),
    y: Number((RADAR_CENTER_Y + Math.sin(angle) * radius).toFixed(2)),
  };
}

function radarGrid(level: number, axisCount: number) {
  const common = {
    fill: "none",
    stroke: "var(--color-border-strong)",
    strokeWidth: level === 100 ? 1.2 : 0.8,
  };
  if (axisCount === 1) {
    return (
      <circle
        {...common}
        cx={RADAR_CENTER_X}
        cy={RADAR_CENTER_Y}
        key={level}
        r={(RADAR_RADIUS * level) / 100}
      />
    );
  }
  if (axisCount === 2) {
    const first = radarPoint(0, level, axisCount);
    const second = radarPoint(1, level, axisCount);
    return (
      <line
        {...common}
        key={level}
        x1={first.x}
        x2={second.x}
        y1={first.y}
        y2={second.y}
      />
    );
  }
  return (
    <polygon
      {...common}
      key={level}
      points={Array.from({ length: axisCount }, (_, index) =>
        pointPair(radarPoint(index, level, axisCount)),
      ).join(" ")}
    />
  );
}

function radarDataShape(
  points: Array<{ x: number; y: number }>,
  dashed: boolean,
) {
  const common = {
    fill: "var(--color-brand)",
    fillOpacity: 0.16,
    stroke: "var(--color-brand)",
    strokeDasharray: dashed ? "4 3" : undefined,
    strokeWidth: 2,
  };
  if (points.length === 1) {
    return (
      <line
        {...common}
        x1={RADAR_CENTER_X}
        x2={points[0].x}
        y1={RADAR_CENTER_Y}
        y2={points[0].y}
      />
    );
  }
  if (points.length === 2) {
    return (
      <line
        {...common}
        x1={points[0].x}
        x2={points[1].x}
        y1={points[0].y}
        y2={points[1].y}
      />
    );
  }
  return (
    <polygon
      {...common}
      points={points.map(pointPair).join(" ")}
      strokeLinejoin="round"
    />
  );
}

function pointPair(point: { x: number; y: number }) {
  return `${point.x},${point.y}`;
}

function toneOf(score: number | null) {
  if (score === null) return "unscored";
  if (score >= PASSING_BAND) return "strong";
  if (score >= 40) return "watch";
  return "weak";
}

function formatTime(milliseconds: number) {
  const seconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(
    2,
    "0",
  )}`;
}
