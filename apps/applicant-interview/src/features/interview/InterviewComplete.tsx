// `.applicant-content > .interview-complete` set a 560px max, but it lost to
// `.applicant-content > .interview-shell:not(.interview-room)` on specificity (0,2,0 vs
// 0,3,0), so the panel has always rendered at 920px. Kept as it renders.
const SHELL =
  "mx-auto w-[min(calc(100%-48px),920px)] bg-canvas py-[56px] pb-[88px] text-ink" +
  " mw-680:w-[min(calc(100%-32px),920px)] mw-680:py-[38px] mw-680:pb-[64px]";

const EYEBROW =
  "mb-2 font-[ui-monospace,SFMono-Regular,Consolas,monospace] text-[11px]" +
  " font-semibold text-muted";

const STEP_INDEX =
  "grid size-[21px] place-items-center rounded-full border border-border bg-surface" +
  " font-[ui-monospace,SFMono-Regular,Consolas,monospace] text-[10px] text-muted";

export function InterviewComplete() {
  return (
    <main className={SHELL}>
      <section
        className="rounded-panel border border-border bg-surface px-[30px] py-9 text-center shadow-soft mw-680:px-5 mw-680:py-7"
        role="status"
      >
        <span
          className="mx-auto mb-[18px] grid size-[50px] place-items-center rounded-full bg-success-soft text-[23px] font-bold text-success"
          aria-hidden="true"
        >
          ✓
        </span>
        <p className={EYEBROW}>INTERVIEW SUBMITTED</p>
        <h1 className="text-[25px] tracking-normal mw-680:text-[22px]">
          면접을 완료하셨습니다
        </h1>
        <p className="mx-auto mt-2.5 mb-[26px] text-[14px] leading-[1.65] text-muted">
          제출된 답변과 녹화 자료는 기업의 사람 검토자가 확인합니다. AI가 만든
          평가 초안은 최종 채용 결정으로 사용되지 않습니다.
        </p>
        <div className="rounded-panel border border-border bg-surface p-[18px] text-left">
          <p className={EYEBROW}>WHAT HAPPENS NEXT</p>
          <ol className="grid gap-[14px]">
            <li className="grid grid-cols-[22px_1fr] gap-[11px]">
              <span className={STEP_INDEX} aria-hidden="true">
                1
              </span>
              <div>
                <strong className="text-[13px]">면접 자료 확인</strong>
                <p className="mt-[3px] text-[12px] leading-[1.5] text-muted">
                  답변, 자막과 재생 구간이 검토 가능한 상태로 준비됩니다.
                </p>
              </div>
            </li>
            <li className="grid grid-cols-[22px_1fr] gap-[11px]">
              <span className={STEP_INDEX} aria-hidden="true">
                2
              </span>
              <div>
                <strong className="text-[13px]">기업의 사람 검토</strong>
                <p className="mt-[3px] text-[12px] leading-[1.5] text-muted">
                  채용 담당자가 Evidence를 확인하고 최종 판단합니다.
                </p>
              </div>
            </li>
          </ol>
        </div>
        <p className="mt-[18px] text-[12px] text-muted">
          이제 이 창을 닫아도 면접 제출 상태는 유지됩니다.
        </p>
      </section>
    </main>
  );
}
