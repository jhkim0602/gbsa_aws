import { BriefcaseBusiness, Check, Settings2 } from "lucide-react";

import type { HiringStep } from "../types";

export const workflowSteps = [
  { id: "position", label: "직무 설정", icon: BriefcaseBusiness },
  { id: "criteria", label: "면접 기준", icon: Settings2 },
] as const;

export function HiringProgress({ step }: { step: HiringStep }) {
  const activeStep =
    step === "complete"
      ? workflowSteps.length
      : workflowSteps.findIndex((item) => item.id === step);

  return (
    <aside className="hiring-progress">
      <header>
        <span>설정 진행률</span>
        <strong>{Math.min(activeStep + 1, 2)} / 2</strong>
      </header>
      <div className="progress-track" aria-hidden="true">
        <span
          style={{
            width: `${Math.min(((activeStep + 1) / 2) * 100, 100)}%`,
          }}
        />
      </div>
      <ol aria-label="채용 관리 진행 단계">
        {workflowSteps.map((item, index) => {
          const Icon = item.icon;
          const completed = index < activeStep || step === "complete";
          const current = index === activeStep;
          return (
            <li
              key={item.id}
              className={`${completed ? "is-complete" : ""} ${
                current ? "is-current" : ""
              }`}
              aria-current={current ? "step" : undefined}
            >
              <span aria-hidden="true">
                {completed ? <Check size={12} /> : <Icon size={13} />}
              </span>
              <strong>{item.label}</strong>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
