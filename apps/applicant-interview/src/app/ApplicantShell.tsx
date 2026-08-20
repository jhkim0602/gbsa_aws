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

// `group` carries `.applicant-app:has(.interview-room) > .applicant-product-bar`, which hid
// the bar inside the interview room. `.interview-room` still sits on InterviewRoom's <main>.
const APP = "group min-h-screen bg-canvas";

const PRODUCT_BAR =
  "sticky top-0 z-20 flex min-h-16 items-center gap-6 overflow-hidden border-b" +
  " border-border bg-[rgb(255_255_255_/_94%)] px-7 text-ink backdrop-blur-[16px]" +
  " group-has-[.interview-room]:hidden mw-600:min-h-[58px] mw-600:gap-3" +
  " mw-600:px-4";

const PRODUCT_MARK =
  "inline-grid size-7 place-items-center rounded-lg border border-ink bg-surface" +
  " text-[10px] font-bold";

const PRODUCT_MODE =
  "flex-none border-l border-border pl-4 text-[14px] text-muted mw-600:hidden";

const JOURNEY =
  "ml-auto min-w-0 overflow-x-auto [scrollbar-width:none]" +
  " [&::-webkit-scrollbar]:hidden mw-860:hidden";

// `.applicant-journey li + li::before`
const STEP_SEPARATOR = "before:mx-0.5 before:text-subtle before:content-['›']";

const STEP =
  "inline-flex min-h-9 items-center gap-[7px] rounded-lg border px-2.5 text-[13px]" +
  " whitespace-nowrap";

const STEP_INDEX =
  "inline-grid size-[19px] place-items-center rounded-full border text-[10px]";

const PROGRESS_DOT =
  "h-0.5 w-4 rounded-full bg-surface-strong data-[state=complete]:bg-brand" +
  " data-[state=current]:bg-brand mw-600:w-[18px]";

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
    <div className={APP}>
      <header className={PRODUCT_BAR} aria-label="제품 탐색">
        <Link
          className="inline-flex flex-none items-center gap-[9px] text-[15px] font-bold"
          to="/"
          aria-label="InterviewEP"
        >
          <span className={PRODUCT_MARK} aria-hidden="true">
            IE
          </span>
          <span>InterviewEP</span>
        </Link>
        <span className={PRODUCT_MODE}>지원자 포털</span>
        <nav className={JOURNEY} aria-label="면접 진행 단계">
          <ol className="flex w-max items-center gap-1">
            {JOURNEY_STEPS.map((step, index) => {
              const state =
                index < activeStep
                  ? "complete"
                  : index === activeStep
                    ? "current"
                    : "upcoming";
              const stepClassName = `${STEP} ${
                state === "current"
                  ? "border-border bg-surface-strong font-semibold text-ink"
                  : "border-transparent text-muted"
              }`;
              const content = (
                <>
                  <span
                    className={`${STEP_INDEX} ${
                      state === "complete"
                        ? "border-brand text-brand"
                        : "border-current"
                    }`}
                    aria-hidden="true"
                  >
                    {index + 1}
                  </span>
                  <span>{step.label}</span>
                  <span className="hidden">{step.shortLabel}</span>
                </>
              );

              return (
                <li
                  key={step.label}
                  className={`flex items-center${index > 0 ? ` ${STEP_SEPARATOR}` : ""}`}
                  data-state={state}
                >
                  {step.path ? (
                    <Link
                      className={stepClassName}
                      to={step.path}
                      aria-label={step.label}
                      aria-current={state === "current" ? "step" : undefined}
                    >
                      {content}
                    </Link>
                  ) : (
                    <span
                      className={stepClassName}
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
        <div
          className="flex items-center gap-[5px] mw-600:ml-auto"
          aria-hidden="true"
        >
          {JOURNEY_STEPS.map((step, index) => (
            <span
              key={step.label}
              className={PROGRESS_DOT}
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
        <span
          className="min-w-8 text-right text-[12px] text-muted"
          aria-live="polite"
        >
          {activeStep + 1} / {JOURNEY_STEPS.length}
        </span>
      </header>

      <div className="min-w-0">
        <Outlet />
      </div>
    </div>
  );
}
