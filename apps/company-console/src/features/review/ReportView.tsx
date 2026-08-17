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
    <section
      className="review-panel report-panel report-document"
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

      <div
        className="report-document__tabs"
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
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="report-document__sheet-area">
        <article
          id={`report-panel-${activeTab}`}
          className="report-page"
          role="tabpanel"
          aria-labelledby={`report-tab-${activeTab}`}
          tabIndex={0}
        >
          <header className="report-page__letterhead">
            <span>
              <p>AI 면접 분석 리포트</p>
              <h3>{reportTabs[activeIndex]?.label}</h3>
            </span>
            <span
              className={`report-status report-status--${report.status}`}
              role="status"
            >
              {report.status === "ready" ? "분석 완료" : report.status}
            </span>
          </header>

          <div className="report-page__body">
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

          <footer className="report-page__footer">
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
    <div className="report-overview">
      <div className="report-overview__headline">
        <div className={`report-score is-${toneOf(report.overallScore)}`}>
          <span>종합 점수</span>
          <strong>{report.overallScore ?? "—"}</strong>
          <small>
            {report.overallScore === null
              ? "점수화된 기준 없음"
              : `100점 기준 · 기준 ${report.items.length - report.unscoredCriteriaCount}개 평균`}
          </small>
        </div>
        <p className="report-overview__summary">{report.summary}</p>
      </div>

      <p className="report-notice">
        합격 여부를 판단한 점수가 아닙니다. AI가 지원자의 실제 답변만 읽고 매긴
        판단 근거이며, {PASSING_BAND}점 이상은 해당 축을 답변에서 보여줬다는
        뜻입니다. 최종 결정은 담당자가 근거를 직접 확인한 뒤 기록합니다.
        {report.unscoredCriteriaCount > 0
          ? ` 기준 ${report.unscoredCriteriaCount}개는 인용할 답변이 없어 이 점수에 포함되지 않았습니다.`
          : ""}
      </p>

      <section className="report-section" aria-label="축별 평균 점수">
        <h4>축별 평균</h4>
        {axes.length > 0 ? (
          <div className="report-axis-list">
            {axes.map((axis) => (
              <div className="report-axis" key={axis.axis}>
                <span className="report-axis__label">{axis.label}</span>
                <ScoreValue score={axis.score} />
                <ScoreBar score={axis.score} />
                <small className="report-axis__meta">
                  {axis.scoredCount > 0
                    ? `기준 ${axis.scoredCount}개에서 판단`
                    : "인용할 답변 없음"}
                </small>
              </div>
            ))}
          </div>
        ) : (
          <p className="report-empty">
            이 리포트에는 축별 점수가 없습니다. 점수화 이전에 생성된
            리포트이거나 인용할 답변이 기록되지 않았습니다.
          </p>
        )}
      </section>

      <section className="report-section" aria-label="기준 상태 요약">
        <h4>기준 상태</h4>
        <dl className="report-state-list">
          {states.map(([state, count]) => (
            <div key={state}>
              <dt>
                <span className={`assessment-badge assessment-badge--${state}`}>
                  {assessmentLabels[state]}
                </span>
              </dt>
              <dd>{count}개</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="report-section" aria-label="기준별 점수">
        <h4>기준별 점수</h4>
        {report.items.length > 0 ? (
          <table className="report-criteria-table">
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
                      className={`assessment-badge assessment-badge--${item.assessmentState}`}
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
          <p className="report-empty">평가된 기준이 없습니다.</p>
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
    return <p className="report-empty">평가된 기준이 없습니다.</p>;
  }

  function followEvidence(evidence: EvidenceRange) {
    setFollowedEvidenceId(evidence.evidenceId);
    onSelectEvidence(evidence.startMs);
  }

  return (
    <div className="report-items">
      {report.items.map((item) => {
        const evidenceById = new Map(
          item.evidence.map((evidence) => [evidence.evidenceId, evidence]),
        );
        const sources = evidenceContext.sourcesByCriterionId[item.criterionId];

        return (
          <article className="report-item" key={item.reportItemId}>
            <header>
              <h3>{item.criterionName}</h3>
              <span className="report-item__verdict">
                <ScoreValue score={item.averageScore} />
                <span
                  className={`assessment-badge assessment-badge--${item.assessmentState}`}
                >
                  {assessmentLabels[item.assessmentState]}
                </span>
              </span>
            </header>
            <p className="report-item__observation">{item.observation}</p>

            {item.axisAssessments.length > 0 ? (
              <div className="report-axis-list is-detailed">
                {item.axisAssessments.map((axis) => (
                  <div className="report-axis" key={axis.axis}>
                    <span className="report-axis__label">{axis.label}</span>
                    <ScoreValue score={axis.score} />
                    <ScoreBar score={axis.score} />
                    <p className="report-axis__rationale">{axis.rationale}</p>
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
              <p className="report-empty">
                이 기준에는 축별 점수가 없습니다. 아래 Evidence를 직접 확인해
                주세요.
              </p>
            )}

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
      <small className="report-axis__meta">
        {axis.score === null ? "인용할 답변 없음" : "인용 확인 실패"}
      </small>
    );
  }

  return (
    <div className="axis-citations">
      <small>인용한 답변 {axis.quotedEvidenceIds.length}건</small>
      {axis.quotedEvidenceIds.map((evidenceId, index) => {
        const evidence = evidenceById.get(evidenceId);
        if (!evidence) {
          return (
            <span className="axis-citation is-missing" key={evidenceId}>
              근거 {index + 1} · 확인 불가
            </span>
          );
        }
        return (
          <button
            className={`axis-citation${
              followedEvidenceId === evidence.evidenceId ? " is-followed" : ""
            }`}
            key={evidenceId}
            type="button"
            aria-label={`${axis.label} 근거 ${index + 1} 답변 보기`}
            onClick={() => onFollow(evidence)}
          >
            <Quote size={11} aria-hidden="true" />
            근거 {index + 1}
            <small>{formatTime(evidence.startMs)}</small>
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
      className={`evidence-card${isFollowed ? " is-followed" : ""}`}
      aria-current={isFollowed ? "true" : undefined}
    >
      <header>
        <span
          className={`evidence-sufficiency is-${evidence.sufficiency}`}
          title="AI가 이 답변을 기준의 근거로 얼마나 직접적으로 봤는지"
        >
          {sufficiencyLabels[evidence.sufficiency]}
        </span>
        <button
          type="button"
          aria-label="Evidence 재생"
          onClick={() => onFollow(evidence)}
        >
          <PlayCircle size={15} aria-hidden="true" />
          <span>
            <strong>Evidence 재생</strong>
            <small>
              {formatTime(evidence.startMs)} – {formatTime(evidence.endMs)}
            </small>
          </span>
        </button>
      </header>
      <p className="evidence-card__observation">{evidence.observation}</p>
      <p className="evidence-card__rationale">{evidence.rationale}</p>
      {answer ? (
        <blockquote className="evidence-card__answer">
          <small>지원자 답변 · {formatTime(answer.startMs)}</small>
          <p>{answer.text}</p>
        </blockquote>
      ) : (
        <p className="report-empty">
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
    <details className="report-item__sources">
      <summary>
        <FileSearch size={13} aria-hidden="true" />
        질문 근거 자료
        <span>{sources.length}개</span>
      </summary>
      <p className="report-empty">
        지원자 답변이 아니라 AI가 질문을 만들 때 참고한 제출 자료입니다.
      </p>
      <ul className="question-source-list">
        {sources.map((source) => (
          <li key={source.sourceId}>
            <span>
              {sourceTypeLabel(source.sourceType)}
              <small>{formatLocator(source.locator)}</small>
            </span>
            <p>{source.excerpt}</p>
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
    <div className="report-followups">
      <section className="report-section" aria-label="사람이 물어볼 질문">
        <h4>사람 면접에서 확인할 질문</h4>
        {followUps.length > 0 ? (
          <ol className="report-followup-list">
            {followUps.map((item) => (
              <li key={item.reportItemId}>
                <span>{item.criterionName}</span>
                <p>{item.followUpQuestion}</p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="report-empty">
            AI가 추가로 물어볼 질문을 남기지 않았습니다.
          </p>
        )}
      </section>

      <section className="report-section" aria-label="점수 없는 기준">
        <h4>점수가 없는 기준</h4>
        {unscored.length > 0 ? (
          <ul className="report-unscored-list">
            {unscored.map((item) => (
              <li key={item.reportItemId}>
                <strong>{item.criterionName}</strong>
                <small>{assessmentLabels[item.assessmentState]}</small>
                <p>
                  {item.evidence.length > 0
                    ? "인용된 답변은 있으나 축별 점수가 남지 않았습니다. Evidence를 직접 확인해 주세요."
                    : "면접에서 이 기준을 확인할 답변이 기록되지 않았습니다."}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="report-empty">모든 기준에 점수가 있습니다.</p>
        )}
      </section>
    </div>
  );
}

function ScoreValue({ score }: { score: number | null }) {
  return (
    <span className={`report-axis__score is-${toneOf(score)}`}>
      {score === null ? UNSCORED_TEXT : `${score}점`}
    </span>
  );
}

function ScoreBar({ score }: { score: number | null }) {
  return (
    <span className={`report-axis__bar is-${toneOf(score)}`} aria-hidden="true">
      <i>
        <b style={{ width: `${score ?? 0}%` }} />
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
