import { Link, Outlet, useLocation } from "react-router-dom";

type JourneyStep = Readonly<{
  label: string;
  shortLabel: string;
  path?: string;
}>;

const JOURNEY_STEPS: readonly JourneyStep[] = [
  { label: "초대 확인", shortLabel: "초대" },
  { label: "자료 제출", shortLabel: "제출", path: "/submissions" },
  { label: "환경 점검", shortLabel: "점검", path: "/interview" },
  { label: "AI 면접", shortLabel: "면접" },
  { label: "면접 완료", shortLabel: "완료" },
];

function currentStepIndex(pathname: string) {
  if (pathname.startsWith("/submissions")) return 1;
  if (pathname.startsWith("/interview/complete")) return 4;
  if (pathname.startsWith("/interview/session")) return 3;
  if (pathname.startsWith("/interview")) return 2;
  return 0;
}

export function ApplicantShell() {
  const { pathname } = useLocation();
  const activeStep = currentStepIndex(pathname);

  return (
    <div className="applicant-app">
      <header className="applicant-product-bar" aria-label="제품 탐색">
        <Link
          className="applicant-product-brand"
          to="/"
          aria-label="InterviewEP"
        >
          <span className="applicant-product-mark" aria-hidden="true">
            IE
          </span>
          <span>InterviewEP</span>
        </Link>
        <span className="applicant-product-mode">지원자 포털</span>
        <nav className="applicant-journey" aria-label="면접 진행 단계">
          <ol>
            {JOURNEY_STEPS.map((step, index) => {
              const state =
                index < activeStep
                  ? "complete"
                  : index === activeStep
                    ? "current"
                    : "upcoming";
              const content = (
                <>
                  <span className="applicant-step-index" aria-hidden="true">
                    {index + 1}
                  </span>
                  <span className="applicant-step-label">{step.label}</span>
                  <span className="applicant-step-label-short">
                    {step.shortLabel}
                  </span>
                </>
              );

              return (
                <li key={step.label} data-state={state}>
                  {step.path ? (
                    <Link
                      className="applicant-step"
                      to={step.path}
                      aria-label={step.label}
                      aria-current={state === "current" ? "step" : undefined}
                    >
                      {content}
                    </Link>
                  ) : (
                    <span
                      className="applicant-step"
                      aria-label={step.label}
                      aria-current={state === "current" ? "step" : undefined}
                    >
                      {content}
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        </nav>
        <div className="applicant-progress" aria-hidden="true">
          {JOURNEY_STEPS.map((step, index) => (
            <span
              key={step.label}
              data-state={
                index < activeStep
                  ? "complete"
                  : index === activeStep
                    ? "current"
                    : "upcoming"
              }
            />
          ))}
        </div>
        <span className="applicant-current-step" aria-live="polite">
          {activeStep + 1} / {JOURNEY_STEPS.length}
        </span>
      </header>

      <div className="applicant-content">
        <Outlet />
      </div>
    </div>
  );
}
