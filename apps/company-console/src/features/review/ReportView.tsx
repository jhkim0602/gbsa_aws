import { Bot, LockKeyhole, PlayCircle } from "lucide-react";

import type { AssessmentState, ReviewReport } from "./types";

const assessmentLabels: Record<AssessmentState, string> = {
  confirmed: "확인됨",
  partially_confirmed: "부분 확인",
  insufficient_evidence: "근거 부족",
  needs_follow_up: "추가 확인",
};

export function ReportView({
  report,
  onSelectEvidence,
  onOverride,
}: {
  report: ReviewReport;
  onSelectEvidence(startMs: number): void;
  onOverride?(reportItemId: string, assessmentState: AssessmentState): void;
}) {
  return (
    <section
      className="review-panel report-panel"
      aria-labelledby="report-title"
      aria-label="AI 리포트"
    >
      <header className="review-panel__header">
        <div className="review-panel__title">
          <span className="review-panel__icon" aria-hidden="true">
            <Bot size={18} />
          </span>
          <span>
            <p>AI 분석</p>
            <h2 id="report-title">면접 리포트</h2>
          </span>
        </div>
        <span className="immutable-badge">
          <LockKeyhole size={13} aria-hidden="true" />
          AI 원본 · 변경 불가
        </span>
      </header>

      <div className="report-summary">
        <span
          className={`report-status report-status--${report.status}`}
          role="status"
        >
          {report.status === "ready" ? "분석 완료" : report.status}
        </span>
        <p>{report.summary}</p>
      </div>

      <div className="report-items">
        {report.items.map((item) => (
          <article className="report-item" key={item.reportItemId}>
            <header>
              <h3>{item.criterionName}</h3>
              <span
                className={`assessment-badge assessment-badge--${item.assessmentState}`}
              >
                {assessmentLabels[item.assessmentState]}
              </span>
            </header>
            <p className="report-item__observation">{item.observation}</p>
            {onOverride && (
              <label className="compact-field">
                <span>사람 평가</span>
                <select
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
            <div className="evidence-list">
              {item.evidence.map((evidence) => (
                <button
                  key={evidence.evidenceId}
                  type="button"
                  aria-label="Evidence 재생"
                  onClick={() => onSelectEvidence(evidence.startMs)}
                >
                  <PlayCircle size={16} aria-hidden="true" />
                  <span>
                    <strong>Evidence 재생</strong>
                    <small>
                      {formatTime(evidence.startMs)} –{" "}
                      {formatTime(evidence.endMs)}
                    </small>
                  </span>
                </button>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function formatTime(milliseconds: number) {
  const seconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(
    2,
    "0",
  )}`;
}
