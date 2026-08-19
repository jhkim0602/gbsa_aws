export function InterviewComplete() {
  return (
    <main className="interview-shell interview-complete">
      <section className="completion-panel" role="status">
        <span className="completion-mark" aria-hidden="true">
          ✓
        </span>
        <p className="interview-brand">INTERVIEW SUBMITTED</p>
        <h1>면접을 완료하셨습니다</h1>
        <p>
          제출된 답변과 녹화 자료는 기업의 사람 검토자가 확인합니다. AI가 만든
          평가 초안은 최종 채용 결정으로 사용되지 않습니다.
        </p>
        <div className="completion-next">
          <p>WHAT HAPPENS NEXT</p>
          <ol>
            <li>
              <span aria-hidden="true">1</span>
              <div>
                <strong>면접 자료 확인</strong>
                <p>답변, 자막과 재생 구간이 검토 가능한 상태로 준비됩니다.</p>
              </div>
            </li>
            <li>
              <span aria-hidden="true">2</span>
              <div>
                <strong>기업의 사람 검토</strong>
                <p>채용 담당자가 Evidence를 확인하고 최종 판단합니다.</p>
              </div>
            </li>
          </ol>
        </div>
        <p className="completion-footnote">
          이제 이 창을 닫아도 면접 제출 상태는 유지됩니다.
        </p>
      </section>
    </main>
  );
}
