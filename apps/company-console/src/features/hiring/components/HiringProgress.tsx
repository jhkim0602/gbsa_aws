import { Check } from "lucide-react";

import type { HiringStep } from "../types";

export const workflowSteps = [
  { id: "position", label: "포지션 정보" },
  { id: "application", label: "지원자 제출" },
  { id: "evaluation", label: "평가 설계" },
  { id: "interview", label: "면접 운영" },
] as const;

export function HiringProgress({ step }: { step: HiringStep }) {
  const activeStep =
    step === "complete"
      ? workflowSteps.length
      : workflowSteps.findIndex((item) => item.id === step);

  return (
    <nav className="hiring-progress" aria-label="채용 설정 진행 단계">
      <ol aria-label="채용 관리 진행 단계">
        {workflowSteps.map((item, index) => {
          const completed = index < activeStep || step === "complete";
          const current = index === activeStep;
          return (
            <li
              key={item.id}
              className={current ? "is-current" : undefined}
              aria-current={current ? "step" : undefined}
            >
              <span
                className={`${completed ? "is-complete" : ""} ${
                  current ? "is-current" : ""
                }`}
                aria-hidden="true"
              >
                {completed ? <Check size={11} /> : index + 1}
              </span>
              <small>{item.label}</small>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
