import { ClipboardCheck, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";

import { buildEvidenceContext } from "./evidenceContext";
import { HumanReview } from "./HumanReview";
import { ReportView } from "./ReportView";
import { TimelineView } from "./TimelineView";
import type {
  AssessmentState,
  InterviewStageSummary,
  ReviewApi,
  ReviewDeletion,
  ReviewHistoryEntry,
  ReviewReport,
  ReviewTimeline,
} from "./types";

// `.page-header` + `.review-page-header`: the latter's `flex-end` wins over `center`. The
// 820px `flex-start` already covers everything below 680px, so the 680px align override is
// redundant. Print: `.review-workspace .page-header` hides it.
const PAGE_HEADER =
  "flex min-h-[65px] items-end justify-between gap-5 px-8 pt-[30px] pb-[14px]" +
  " mw-820:items-start mw-680:px-4 mw-680:py-[14px] print:hidden";

// `.page-eyebrow` loses its color/font-size/margin to `.page-header p` (0,1,1 vs 0,1,0), so
// this renders 14px/muted, NOT 9px/brand. Only the mono family, 600 and uppercase survive.
const PAGE_EYEBROW =
  "mt-0.5 font-mono text-[14px] leading-[1.5] font-semibold uppercase text-muted";

// `.review-page-meta > span` (0,1,1) outranks `.status-badge` (0,1,0) on min-height, padding,
// radius and font-size, and adds a border — so the pill is 26px/6px/9px with a border, not the
// shared 20px/999px/10px badge. Only `.is-success` (0,2,0) keeps its own color and background.
const META_PILL =
  "inline-flex min-h-[26px] items-center gap-1.5 rounded-md border border-border px-[9px]" +
  " font-mono text-[9px]";

// The report column is a fixed-width A4 sheet; the two working panels share the narrower one.
const WORKSPACE_LAYOUT =
  "grid grid-cols-[minmax(280px,0.6fr)_minmax(0,830px)] grid-rows-[auto_auto]" +
  // `items-start` would emit `flex-start`; the source says `start`, so keep it verbatim.
  " [grid-template-areas:'timeline_report'_'decision_report'] [align-items:start] gap-3" +
  " px-8 pt-5 pb-12" +
  " mw-1180:grid-cols-[minmax(280px,0.85fr)_minmax(0,1.15fr)]" +
  " mw-1180:[grid-template-areas:'timeline_report'_'decision_decision']" +
  " mw-820:grid-cols-[minmax(0,1fr)]" +
  " mw-820:[grid-template-areas:'timeline'_'report'_'decision']" +
  " mw-680:p-4 print:block print:p-0";

export function ReviewWorkspace({
  sessionId,
  invitationId,
  report,
  timeline,
  api,
  deletion,
  history = [],
}: {
  sessionId: string;
  invitationId: string;
  report: ReviewReport;
  timeline: ReviewTimeline;
  api: ReviewApi;
  deletion: ReviewDeletion;
  history?: ReviewHistoryEntry[];
}) {
  const [selectedStartMs, setSelectedStartMs] = useState<number | null>(null);
  const evidenceContext = useMemo(
    () => buildEvidenceContext(timeline.entries),
    [timeline.entries],
  );
  const stageSummary = useMemo(
    () => summarizeInterviewStages(timeline.entries),
    [timeline.entries],
  );

  /**
   * Record a reviewer overruling the AI's assessment, with the reason they gave.
   *
   * The reason used to be the fixed string "기업 검토자가 평가 상태를 수정함". The API had always
   * accepted a real one, so every override in the audit trail said the same thing — which is the
   * same as recording nothing. A reviewer disagreeing with a score is exactly the case where the
   * next person needs to know why.
   */
  function overrideAssessment(
    reportItemId: string,
    assessmentState: AssessmentState,
    reason: string,
  ) {
    void api.overrideAssessment(reportItemId, assessmentState, reason);
  }

  return (
    <div className="min-w-0">
      <header className={PAGE_HEADER}>
        <div>
          <p className={PAGE_EYEBROW}>Interview evidence</p>
          <h1 className="text-[28px] font-bold">지원자 검토</h1>
          <p className="mt-0.5 text-[14px] leading-[1.5] text-muted">
            AI 분석과 실제 답변 구간을 함께 확인하고 사람의 최종 판단을
            기록합니다.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 mw-820:justify-start">
          <span
            className={`${META_PILL} bg-success-soft font-medium whitespace-nowrap text-success`}
          >
            <ClipboardCheck size={13} aria-hidden="true" />
            검토 가능
          </span>
          <span className={`${META_PILL} bg-surface text-muted`}>
            <ShieldCheck size={13} aria-hidden="true" />
            세션 {shortSessionId(sessionId)}
          </span>
        </div>
      </header>

      <div className={WORKSPACE_LAYOUT}>
        <div className="min-w-0 [grid-area:timeline] sticky top-3 mw-820:static print:hidden">
          <TimelineView
            entries={timeline.entries}
            playbackStatus={timeline.playback.status}
            playbackUrl={timeline.playback.url}
            selectedStartMs={selectedStartMs}
            onSeek={setSelectedStartMs}
          />
        </div>
        <div className="min-w-0 [grid-area:report]">
          <ReportView
            report={report}
            stageSummary={stageSummary}
            evidenceContext={evidenceContext}
            onOverride={overrideAssessment}
            onSelectEvidence={setSelectedStartMs}
          />
        </div>
        <div className="min-w-0 [grid-area:decision] sticky top-3 mw-1180:static mw-820:static print:hidden">
          <HumanReview
            api={api}
            invitationId={invitationId}
            deletion={deletion}
            history={history}
          />
        </div>
      </div>
    </div>
  );
}

export function summarizeInterviewStages(
  entries: ReviewTimeline["entries"],
): InterviewStageSummary[] {
  const stages: InterviewStageSummary[] = [
    { stage: "technical", label: "기술 면접", questionCount: 0 },
    {
      stage: "project_deep_dive",
      label: "프로젝트 심층",
      questionCount: 0,
    },
    { stage: "behavioral", label: "협업·인성", questionCount: 0 },
  ];
  for (const entry of entries) {
    const stage = entry.questionRationale?.interviewStage;
    if (!stage) continue;
    const summary = stages.find((item) => item.stage === stage);
    if (summary) summary.questionCount += 1;
  }
  return stages;
}

function shortSessionId(sessionId: string) {
  return sessionId.replace(/^session-/, "").slice(0, 8) || "unknown";
}
