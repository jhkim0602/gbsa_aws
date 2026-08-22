import { Check } from "lucide-react";

import type { HiringStep } from "../types";

export const workflowSteps = [
  { id: "position", label: "포지션 정보" },
  { id: "application", label: "지원자 제출" },
  { id: "evaluation", label: "평가 설계" },
  { id: "interview", label: "면접 운영" },
] as const;

// `.hiring-progress` is declared twice, and the second block (hiring.css 2421+) is emitted
// *after* the 880px and 620px media queries that also target it — so at equal specificity it
// wins at every viewport. That makes those overrides dead: the `repeat(2)` columns at 620px
// and the `li:nth-child(2)::after` connector hiding never render. The stepper is always
// 4-across. Only the surviving declarations are ported here.
const STEP =
  "relative grid min-h-0 grid-cols-[minmax(0,1fr)] grid-rows-[24px_auto] justify-items-center" +
  " gap-1.5" +
  // The connector targets a child the markup does not enumerate, but `not-last:after:`
  // compiles to exactly `:not(:last-child)::after`, so it needs no leftover CSS.
  " not-last:after:absolute not-last:after:top-3 not-last:after:left-[calc(50%+18px)]" +
  " not-last:after:block not-last:after:h-px not-last:after:w-[calc(100%-36px)]" +
  " not-last:after:bg-border not-last:after:content-['']";

const MARKER =
  "z-1 row-start-1 grid size-6 place-items-center rounded-[50%] border border-border" +
  " bg-transparent font-mono text-[11px] font-bold text-muted";

// `.hiring-progress li.is-complete` never matched: the markup puts `is-complete` on the span,
// not the li. `li > span.is-complete` (--color-text) is declared after `li > span.is-current`
// (--color-link), so a step that is both would read as complete — it cannot be, since
// `activeStep` is past the last index once the wizard completes, but the order is kept.
export function HiringProgress({ step }: { step: HiringStep }) {
  const activeStep =
    step === "complete"
      ? workflowSteps.length
      : workflowSteps.findIndex((item) => item.id === step);

  return (
    <nav
      className="mx-auto w-[min(100%,520px)]"
      aria-label="채용 설정 진행 단계"
    >
      <ol
        className="grid w-full grid-cols-4 gap-0"
        aria-label="채용 관리 진행 단계"
      >
        {workflowSteps.map((item, index) => {
          const completed = index < activeStep || step === "complete";
          const current = index === activeStep;
          return (
            <li
              key={item.id}
              className={`${STEP} ${current ? "text-ink" : "text-muted"}`}
              aria-current={current ? "step" : undefined}
            >
              <span
                className={`${MARKER} ${
                  completed
                    ? "!border-ink !bg-ink !text-white"
                    : current
                      ? "!border-brand-strong !bg-brand-strong !text-white"
                      : ""
                }`}
                aria-hidden="true"
              >
                {completed ? <Check size={11} /> : index + 1}
              </span>
              <small
                className={`row-start-2 block text-center text-[9px] whitespace-nowrap ${
                  current ? "font-[650]" : "font-medium"
                }`}
              >
                {item.label}
              </small>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
