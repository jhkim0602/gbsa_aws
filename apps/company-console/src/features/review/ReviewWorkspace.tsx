import { ClipboardCheck, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { HumanReview } from "./HumanReview";
import { ReportView } from "./ReportView";
import { TimelineView } from "./TimelineView";
import type {
  AssessmentState,
  ReviewApi,
  ReviewDeletion,
  ReviewHistoryEntry,
  ReviewReport,
  ReviewTimeline,
} from "./types";

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

  function overrideAssessment(
    reportItemId: string,
    assessmentState: AssessmentState,
  ) {
    void api.overrideAssessment(
      reportItemId,
      assessmentState,
      "기업 검토자가 평가 상태를 수정함",
    );
  }

  return (
    <div className="review-workspace">
      <header className="page-header review-page-header">
        <div>
          <p className="page-eyebrow">Interview evidence</p>
          <h1>지원자 검토</h1>
          <p>
            AI 분석과 실제 답변 구간을 함께 확인하고 사람의 최종 판단을
            기록합니다.
          </p>
        </div>
        <div className="review-page-meta">
          <span className="status-badge is-success">
            <ClipboardCheck size={13} aria-hidden="true" />
            검토 가능
          </span>
          <span>
            <ShieldCheck size={13} aria-hidden="true" />
            세션 {shortSessionId(sessionId)}
          </span>
        </div>
      </header>

      <div className="page-content review-workspace__layout">
        <div className="review-workspace__timeline">
          <TimelineView
            entries={timeline.entries}
            playbackStatus={timeline.playback.status}
            playbackUrl={timeline.playback.url}
            selectedStartMs={selectedStartMs}
            onSeek={setSelectedStartMs}
          />
        </div>
        <div className="review-workspace__report">
          <ReportView
            report={report}
            onOverride={overrideAssessment}
            onSelectEvidence={setSelectedStartMs}
          />
        </div>
        <div className="review-workspace__decision">
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

function shortSessionId(sessionId: string) {
  return sessionId.replace(/^session-/, "").slice(0, 8) || "unknown";
}
