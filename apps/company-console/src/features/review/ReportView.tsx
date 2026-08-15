type Evidence = {
  evidenceId: string;
  startMs: number;
  endMs: number;
};

type ReportItem = {
  reportItemId: string;
  criterionName: string;
  assessmentState:
    | "confirmed"
    | "partially_confirmed"
    | "insufficient_evidence"
    | "needs_follow_up";
  observation: string;
  evidence: Evidence[];
};

export function ReportView({
  report,
  onSelectEvidence,
  onOverride,
}: {
  report: { summary: string; status: string; items: ReportItem[] };
  onSelectEvidence(startMs: number): void;
  onOverride?(
    reportItemId: string,
    assessmentState: ReportItem["assessmentState"],
  ): void;
}) {
  return (
    <section aria-labelledby="report-title">
      <header>
        <h2 id="report-title">면접 리포트</h2>
        <p>AI 원본 · 변경 불가</p>
        <span role="status">{report.status}</span>
      </header>
      <p>{report.summary}</p>
      {report.items.map((item) => (
        <article key={item.reportItemId}>
          <h3>{item.criterionName}</h3>
          <p>{item.assessmentState}</p>
          <p>{item.observation}</p>
          {onOverride && (
            <label>
              사람 평가
              <select
                defaultValue={item.assessmentState}
                onChange={(event) =>
                  onOverride(
                    item.reportItemId,
                    event.target.value as ReportItem["assessmentState"],
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
          {item.evidence.map((evidence) => (
            <button
              key={evidence.evidenceId}
              type="button"
              onClick={() => onSelectEvidence(evidence.startMs)}
            >
              Evidence 재생
            </button>
          ))}
        </article>
      ))}
    </section>
  );
}
