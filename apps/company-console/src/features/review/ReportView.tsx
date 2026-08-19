import { Bot, FileSearch, LockKeyhole, PlayCircle, Quote } from "lucide-react";
import { type KeyboardEvent, useState } from "react";

import { formatLocator, sourceTypeLabel } from "./questionSources";
import type {
  AssessmentState,
  AxisAssessment,
  EvidenceRange,
  EvidenceSufficiency,
  ReviewEvidenceContext,
  ReviewQuestionSource,
  ReviewReport,
  ReviewReportItem,
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
  " px-[14px] py-3 max-[520px]:items-start print:hidden";

const PANEL_EYEBROW =
  "font-mono text-[8px] font-semibold uppercase text-muted";

const TAB_BUTTON =
  "relative flex-[0_0_auto] px-0.5 text-[10px] font-[650] text-muted" +
  " aria-selected:text-brand" +
  // `::after` is the 2px underline; transparent until the tab is selected.
  " after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-transparent" +
  " after:content-[''] aria-selected:after:bg-brand";

// A4 is 210mm wide. The aspect ratio sets the minimum height so a short report still looks
// like one page. Below A4 width the sheet stops being a page and becomes a plain column.
const REPORT_PAGE =
  "grid w-full max-w-[210mm] min-h-[calc(210mm*297/210)]" +
  " grid-rows-[auto_minmax(0,1fr)_auto] border border-border bg-surface shadow-soft" +
  " outline-none max-[1180px]:min-h-0 max-[1180px]:border-0 max-[1180px]:shadow-none" +
  " print:block print:max-w-none print:min-h-0 print:border-0 print:shadow-none";

const REPORT_SECTION = "grid gap-[9px]";

const REPORT_SECTION_HEADING =
  "flex items-center border-b border-border-muted pb-[5px] text-[11px] font-bold";

const REPORT_EMPTY = "text-[9px] leading-[1.6] text-muted";

const AXIS_ROW =
  "grid grid-cols-[62px_62px_minmax(80px,1fr)] items-center gap-y-1 gap-x-2.5 py-[7px]" +
  " [&+&]:border-t [&+&]:border-border-muted break-inside-avoid" +
  " max-[520px]:grid-cols-[minmax(0,1fr)_auto]";

// `.report-axis-list.is-detailed .report-axis` narrows the bar column.
const AXIS_ROW_DETAILED = AXIS_ROW.replace(
  "grid-cols-[62px_62px_minmax(80px,1fr)]",
  "grid-cols-[62px_62px_minmax(60px,0.7fr)]",
);

const AXIS_LABEL =
  "min-w-0 overflow-hidden text-ellipsis whitespace-nowrap text-[10px] font-[650]" +
  " text-ink-secondary";

const AXIS_META =
  "col-[2/-1] text-[8px] text-subtle max-[520px]:col-span-full";

const AXIS_RATIONALE =
  "col-[2/-1] text-[9px] leading-[1.65] text-muted max-[520px]:col-span-full";

// `.report-axis__bar > i` is the track and `> i > b` the fill, so the tone lands on the b.
const AXIS_BAR_TRACK =
  "block h-[5px] overflow-hidden rounded-[3px] bg-surface-strong";

// Structure only: each variant supplies its own border/background/text, because
// `.axis-citation.is-missing` (0,2,0, declared later) beats `.axis-citation:hover` and so
// the unresolved chip has no hover state at all.
// Dropped when printed: only the seek controls go, not the quoted answers behind them.
const CITATION_CHIP =
  "inline-flex min-h-[22px] items-center gap-1 rounded-[11px] border px-[7px] py-0.5" +
  " text-[8px] font-[650] print:hidden";

const reportTabs = [
  { id: "overview", label: "종합평가" },
  { id: "criteria", label: "기준별 평가" },
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
  sourcesByCriterionId: {},
};

export function ReportView({
  report,
  evidenceContext = EMPTY_CONTEXT,
  onSelectEvidence,
  onOverride,
}: {
  report: ReviewReport;
  /** Resolves a citation to the answer it quoted. Absent leaves the spans unresolved. */
  evidenceContext?: ReviewEvidenceContext;
  onSelectEvidence(startMs: number): void;
  onOverride?(reportItemId: string, assessmentState: AssessmentState): void;
}) {
  const [activeTab, setActiveTab] = useState<ReportTab>("overview");
  const activeIndex = reportTabs.findIndex((tab) => tab.id === activeTab);

  function selectTab(index: number) {
    const tab = reportTabs[(index + reportTabs.length) % reportTabs.length];
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
      selectTab(reportTabs.length - 1);
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
          className={`${BADGE_BASE} bg-surface-muted text-muted max-[520px]:max-w-[108px] max-[520px]:whitespace-normal`}
        >
          <LockKeyhole size={13} aria-hidden="true" />
          AI 원본 · 변경 불가
        </span>
      </header>

      <div
        className="flex min-h-[42px] gap-[22px] overflow-x-auto border-b border-border bg-surface px-[14px] print:hidden"
        role="tablist"
        aria-label="리포트 항목"
      >
        {reportTabs.map((tab) => (
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

      {/* The canvas the sheet sits on, so the page reads as paper rather than as a panel.
          The column is sized explicitly: `justify-content: center` makes a grid column hug
          its content, so the sheet's `width: 100%` would otherwise resolve against whatever
          that tab happens to contain and every tab would be a different width. */}
      <div className="grid grid-cols-[minmax(0,210mm)] justify-center bg-surface-strong p-[14px] max-[1180px]:bg-surface max-[1180px]:p-0 print:block print:bg-transparent print:p-0">
        <article
          id={`report-panel-${activeTab}`}
          className={REPORT_PAGE}
          role="tabpanel"
          aria-labelledby={`report-tab-${activeTab}`}
          tabIndex={0}
        >
          <header className="flex items-start justify-between gap-3 border-b border-ink px-[18mm] pt-[20mm] pb-[8mm] max-[1180px]:px-4 max-[1180px]:pt-4 max-[1180px]:pb-3">
            <span>
              <p className="font-mono text-[9px] font-semibold tracking-[0.06em] uppercase text-muted">
                AI 면접 분석 리포트
              </p>
              <h3 className="mt-1 text-[20px] font-bold">
                {reportTabs[activeIndex]?.label}
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

          <div className="grid content-start gap-4 px-[18mm] py-[10mm] max-[1180px]:px-4 max-[1180px]:py-3.5">
            {activeTab === "overview" ? <OverviewPage report={report} /> : null}
            {activeTab === "criteria" ? (
              <CriteriaPage
                report={report}
                evidenceContext={evidenceContext}
                onSelectEvidence={onSelectEvidence}
                onOverride={onOverride}
              />
            ) : null}
            {activeTab === "followups" ? (
              <FollowUpPage report={report} />
            ) : null}
          </div>

          <footer className="flex items-center justify-between gap-2.5 border-t border-border-muted px-[18mm] pt-[8mm] pb-[14mm] font-mono text-[8px] text-subtle max-[1180px]:px-4 max-[1180px]:py-3">
            <span>AI 원본 · 최종 결정은 담당자가 기록합니다</span>
            {/* Labelled as a section, not "2 / 3": a section can run past one sheet, and a
                bare fraction in a document footer reads as a page number that is wrong. */}
            <span>
              섹션 {activeIndex + 1} / {reportTabs.length}
            </span>
          </footer>
        </article>
      </div>
    </section>
  );
}

function OverviewPage({ report }: { report: ReviewReport }) {
  const axes = summarizeAxes(report.items);
  const states = countStates(report.items);

  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-[132px_minmax(0,1fr)] items-center gap-4 max-[520px]:grid-cols-[minmax(0,1fr)]">
        <div className="grid justify-items-center gap-0.5 rounded-lg border border-border-muted bg-surface-muted px-2.5 py-[14px] text-center">
          <span className="text-[9px] font-[650] text-muted">종합 점수</span>
          <strong
            className={`text-[34px] font-bold leading-[1.1] ${toneText[toneOf(report.overallScore)]}`}
          >
            {report.overallScore ?? "—"}
          </strong>
          <small className="text-[8px] leading-[1.4] text-subtle">
            {report.overallScore === null
              ? "점수화된 기준 없음"
              : `100점 기준 · 기준 ${report.items.length - report.unscoredCriteriaCount}개 평균`}
          </small>
        </div>
        <p className="text-[11px] leading-[1.75] text-ink-secondary">
          {report.summary}
        </p>
      </div>

      {/* Sits under the score because the number is the thing most easily misread as a
          hiring verdict, which the constitution reserves for a person. */}
      <p className="rounded-e-[5px] border-l-2 border-brand bg-brand-soft px-3 py-2.5 text-[9px] leading-[1.65] text-ink-secondary">
        합격 여부를 판단한 점수가 아닙니다. AI가 지원자의 실제 답변만 읽고 매긴
        판단 근거이며, {PASSING_BAND}점 이상은 해당 축을 답변에서 보여줬다는
        뜻입니다. 최종 결정은 담당자가 근거를 직접 확인한 뒤 기록합니다.
        {report.unscoredCriteriaCount > 0
          ? ` 기준 ${report.unscoredCriteriaCount}개는 인용할 답변이 없어 이 점수에 포함되지 않았습니다.`
          : ""}
      </p>

      <section className={REPORT_SECTION} aria-label="축별 평균 점수">
        <h4 className={REPORT_SECTION_HEADING}>축별 평균</h4>
        {axes.length > 0 ? (
          <div className="grid gap-1">
            {axes.map((axis) => (
              <div className={AXIS_ROW} key={axis.axis}>
                <span className={AXIS_LABEL}>{axis.label}</span>
                <ScoreValue score={axis.score} />
                <ScoreBar score={axis.score} />
                <small className={AXIS_META}>
                  {axis.scoredCount > 0
                    ? `기준 ${axis.scoredCount}개에서 판단`
                    : "인용할 답변 없음"}
                </small>
              </div>
            ))}
          </div>
        ) : (
          <p className={REPORT_EMPTY}>
            이 리포트에는 축별 점수가 없습니다. 점수화 이전에 생성된
            리포트이거나 인용할 답변이 기록되지 않았습니다.
          </p>
        )}
      </section>

      <section className={REPORT_SECTION} aria-label="기준 상태 요약">
        <h4 className={REPORT_SECTION_HEADING}>기준 상태</h4>
        <dl className="flex flex-wrap gap-y-2 gap-x-4">
          {states.map(([state, count]) => (
            <div key={state} className="flex items-center gap-1.5">
              <dt>
                <span className={`${BADGE_BASE} ${assessmentTone[state]}`}>
                  {assessmentLabels[state]}
                </span>
              </dt>
              <dd className="font-mono text-[10px] font-[650] text-ink-secondary">
                {count}개
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className={REPORT_SECTION} aria-label="기준별 점수">
        <h4 className={REPORT_SECTION_HEADING}>기준별 점수</h4>
        {report.items.length > 0 ? (
          <table className="w-full border-collapse text-[10px] [&_td]:border-b [&_td]:border-border-muted [&_td]:px-2 [&_td]:py-[7px] [&_td]:text-left [&_td]:align-middle [&_th]:border-b [&_th]:border-border-muted [&_th]:px-2 [&_th]:py-[7px] [&_th]:text-left [&_th]:align-middle [&_thead_th]:text-[8px] [&_thead_th]:font-[650] [&_thead_th]:tracking-[0.04em] [&_thead_th]:uppercase [&_thead_th]:text-muted [&_tbody_th]:text-[10px] [&_tbody_th]:font-[650] [&_td:last-child]:font-mono [&_td:last-child]:text-[9px] [&_td:last-child]:whitespace-nowrap [&_td:last-child]:text-subtle">
            <thead>
              <tr>
                <th>평가 기준</th>
                <th>점수</th>
                <th>근거 상태</th>
                <th>인용</th>
              </tr>
            </thead>
            <tbody>
              {report.items.map((item) => (
                <tr key={item.reportItemId}>
                  <th scope="row">{item.criterionName}</th>
                  <td>
                    <ScoreValue score={item.averageScore} />
                  </td>
                  <td>
                    <span
                      className={`${BADGE_BASE} ${assessmentTone[item.assessmentState]}`}
                    >
                      {assessmentLabels[item.assessmentState]}
                    </span>
                  </td>
                  <td>{item.evidence.length}건</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className={REPORT_EMPTY}>평가된 기준이 없습니다.</p>
        )}
      </section>
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
  onOverride?(reportItemId: string, assessmentState: AssessmentState): void;
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
      {report.items.map((item) => {
        const evidenceById = new Map(
          item.evidence.map((evidence) => [evidence.evidenceId, evidence]),
        );
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
                <ScoreValue score={item.averageScore} />
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

            {item.axisAssessments.length > 0 ? (
              <div className="grid gap-1">
                {item.axisAssessments.map((axis) => (
                  <div className={AXIS_ROW_DETAILED} key={axis.axis}>
                    <span className={AXIS_LABEL}>{axis.label}</span>
                    <ScoreValue score={axis.score} />
                    <ScoreBar score={axis.score} />
                    <p className={AXIS_RATIONALE}>{axis.rationale}</p>
                    <AxisCitations
                      axis={axis}
                      evidenceById={evidenceById}
                      followedEvidenceId={followedEvidenceId}
                      onFollow={followEvidence}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className={REPORT_EMPTY}>
                이 기준에는 축별 점수가 없습니다. 아래 Evidence를 직접 확인해
                주세요.
              </p>
            )}

            {onOverride && (
              // `.report-item .compact-field` is hidden when printed: an editable control
              // is not part of the document.
              <label className="grid gap-1.5 print:hidden">
                <span className="text-[9px] font-semibold text-ink-secondary">
                  사람 평가
                </span>
                <select
                  className="min-h-[34px] w-full rounded-md border border-border bg-surface px-[9px] py-[7px] text-[10px] text-ink focus:border-brand focus:outline-2 focus:outline-offset-0 focus:outline-[#5966ce1f]"
                  defaultValue={item.assessmentState}
                  onChange={(event) =>
                    onOverride(
                      item.reportItemId,
                      event.target.value as AssessmentState,
                    )
                  }
                >
                  <option value="confirmed">확인됨</option>
                  <option value="partially_confirmed">부분 확인</option>
                  <option value="insufficient_evidence">근거 부족</option>
                  <option value="needs_follow_up">추가 확인 필요</option>
                </select>
              </label>
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

/**
 * The clickable half of a traced score.
 *
 * The backend only stores a score whose citations resolved, so an id here that is missing
 * from the criterion's Evidence means the report and the Evidence rows disagree. That is
 * said out loud rather than dropped: a reviewer who cannot reach the quoted answer needs
 * to know the number is unverifiable, not see one fewer chip than there are citations.
 */
function AxisCitations({
  axis,
  evidenceById,
  followedEvidenceId,
  onFollow,
}: {
  axis: AxisAssessment;
  evidenceById: Map<string, EvidenceRange>;
  followedEvidenceId: string | null;
  onFollow(evidence: EvidenceRange): void;
}) {
  if (axis.quotedEvidenceIds.length === 0) {
    return (
      <small className={AXIS_META}>
        {axis.score === null ? "인용할 답변 없음" : "인용 확인 실패"}
      </small>
    );
  }

  return (
    // One chip per citation the axis rests on, so the number and the answer behind it are
    // one click apart rather than a count the reviewer has to take on trust.
    <div className="col-[2/-1] flex flex-wrap items-center gap-[5px] max-[520px]:col-span-full">
      <small className="text-[8px] text-subtle">
        인용한 답변 {axis.quotedEvidenceIds.length}건
      </small>
      {axis.quotedEvidenceIds.map((evidenceId, index) => {
        const evidence = evidenceById.get(evidenceId);
        if (!evidence) {
          // A citation the report kept but the Evidence rows no longer carry. Said out loud
          // in the reviewer's colour for "look at this", not hidden.
          return (
            <span
              className={`${CITATION_CHIP} border-border bg-surface-strong text-muted`}
              key={evidenceId}
            >
              근거 {index + 1} · 확인 불가
            </span>
          );
        }
        const isFollowed = followedEvidenceId === evidence.evidenceId;
        return (
          // `.axis-citation.is-followed` is declared after `.axis-citation:hover` at equal
          // specificity, so a followed chip keeps its 18% fill on hover. A `hover:` utility
          // would outrank the plain one, so the hover state is only emitted when not
          // followed.
          <button
            className={`${CITATION_CHIP} text-brand-strong ${
              isFollowed
                ? "border-brand bg-[#5966ce2e]"
                : "border-[#5966ce47] bg-[#5966ce0f] hover:border-brand hover:bg-[#5966ce1f]"
            }`}
            key={evidenceId}
            type="button"
            aria-label={`${axis.label} 근거 ${index + 1} 답변 보기`}
            onClick={() => onFollow(evidence)}
          >
            <Quote size={11} aria-hidden="true" />
            근거 {index + 1}
            <small className="font-mono text-[7px] font-semibold text-muted">
              {formatTime(evidence.startMs)}
            </small>
          </button>
        );
      })}
    </div>
  );
}

/** One quoted answer: what the AI read into it, and the applicant's own words. */
function EvidenceCard({
  evidence,
  answer,
  isFollowed,
  onFollow,
}: {
  evidence: EvidenceRange;
  answer?: { text: string; startMs: number; endMs: number };
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
        <span
          className={`rounded-sm px-1.5 py-0.5 text-[8px] font-[650] ${sufficiencyTone[evidence.sufficiency]}`}
          title="AI가 이 답변을 기준의 근거로 얼마나 직접적으로 봤는지"
        >
          {sufficiencyLabels[evidence.sufficiency]}
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
      <p
        className={`${REPORT_EMPTY} border-t border-border-muted pt-2`}
      >
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
    <span
      className="max-[520px]:col-span-full"
      aria-hidden="true"
    >
      <i className={AXIS_BAR_TRACK}>
        <b
          className={`block h-full rounded-[3px] ${toneBar[toneOf(score)]}`}
          style={{ width: `${score ?? 0}%` }}
        />
      </i>
    </span>
  );
}

type AxisSummary = {
  axis: string;
  label: string;
  score: number | null;
  scoredCount: number;
};

/**
 * Average each axis across the criteria that could be judged on it.
 *
 * Criteria with a null score on an axis are left out of that axis's mean instead of
 * counting as zero, the same way the backend averages: a criterion the interview never
 * reached must not drag an axis toward a failure.
 */
function summarizeAxes(items: ReviewReportItem[]): AxisSummary[] {
  const order: string[] = [];
  const groups = new Map<string, { label: string; scores: number[] }>();
  for (const item of items) {
    for (const axis of item.axisAssessments) {
      let group = groups.get(axis.axis);
      if (!group) {
        group = { label: axis.label, scores: [] };
        groups.set(axis.axis, group);
        order.push(axis.axis);
      }
      if (axis.score !== null) group.scores.push(axis.score);
    }
  }
  return order.map((axis) => {
    const group = groups.get(axis);
    const scores = group?.scores ?? [];
    return {
      axis,
      label: group?.label ?? axis,
      score:
        scores.length > 0
          ? Math.round(
              scores.reduce((total, score) => total + score, 0) / scores.length,
            )
          : null,
      scoredCount: scores.length,
    };
  });
}

function countStates(items: ReviewReportItem[]) {
  return (Object.keys(assessmentLabels) as AssessmentState[])
    .map(
      (state) =>
        [
          state,
          items.filter((item) => item.assessmentState === state).length,
        ] as const,
    )
    .filter(([, count]) => count > 0);
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
