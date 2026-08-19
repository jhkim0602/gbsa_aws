import { type FormEvent, useState } from "react";

export type ConsentPurpose =
  "document_analysis" | "recording" | "ai_assessment";

export type ConsentPolicy = Readonly<{
  policyVersion: string;
  aiRole: string;
  recordingNotice: string;
  processingPurposes: ReadonlyArray<{
    purpose: ConsentPurpose;
    title: string;
    description: string;
  }>;
  retentionDays: number;
  deletionMethod: string;
  requiredPurposes: ConsentPurpose[];
  contentDigest: string;
}>;

export type ApplicantAccessApi = {
  exchangeToken(token: string): Promise<void>;
  verifyIdentity(displayName: string, verificationValue: string): Promise<void>;
  getConsentPolicy(): Promise<ConsentPolicy>;
  recordConsent(
    policy: ConsentPolicy,
    purposes: ConsentPurpose[],
  ): Promise<void>;
};

type Step = "exchange" | "identity" | "consent" | "ready";

// `.applicant-content > .access-screen` set a 560px max, but it lost to
// `.applicant-content > main:not(.interview-room)` in shell.css on specificity (0,2,0 vs
// 0,2,1), so this screen has always rendered at `--applicant-content-width` (960px) with
// shell.css's 72px/104px block padding. Kept as it renders.
const SHELL =
  "mx-auto w-[min(calc(100%-48px),var(--applicant-content-width))] pt-[72px] pb-[104px]" +
  " max-[600px]:w-[min(calc(100%-32px),var(--applicant-content-width))]" +
  " max-[600px]:pt-12 max-[600px]:pb-[72px]";

// `.access-primary-panel`, `.access-process`, `.access-form-panel`, `.access-ready`
const PANEL = "rounded-panel border border-border bg-surface shadow-soft";

// `.access-eyebrow` and `.access-section-heading > p` — no sibling rule outranks them.
const EYEBROW =
  "mb-2 font-[ui-monospace,SFMono-Regular,Consolas,monospace] text-[11px]" +
  " tracking-normal text-muted";

// `.access-panel-label` (0,1,0) loses `font-size`/`line-height`/`color` to the later
// `.access-primary-panel p` (0,1,1), so this label renders at 14px/1.65, not 11px. Only its
// margin, mono family and letter-spacing survive. Kept as it renders.
const PANEL_LABEL =
  "mb-2 font-[ui-monospace,SFMono-Regular,Consolas,monospace] text-[14px]" +
  " leading-[1.65] tracking-normal text-muted";

// The same label inside `.access-ready` additionally loses its `margin: 0 0 8px` to
// `.access-ready > p` (0,1,1), which lands 10px/22px on it. Kept as it renders.
const READY_LABEL =
  "mt-2.5 mb-[22px] font-[ui-monospace,SFMono-Regular,Consolas,monospace] text-[14px]" +
  " leading-[1.65] tracking-normal text-muted";

// `.access-heading > p:last-child, .access-form-description, .access-primary-panel p,
//  .access-process li p, .access-ready > p`
const BODY_COPY = "text-[14px] leading-[1.65] text-muted";

const PRIMARY_ACTION =
  "inline-flex min-h-10 items-center justify-center rounded-panel border border-brand" +
  " bg-brand px-[18px] font-[650] text-white shadow-[0_1px_0_rgb(27_31_36_/_5%)]" +
  " disabled:border-border disabled:bg-surface-strong disabled:text-subtle" +
  " disabled:shadow-none";

// `.access-form-panel input:not([type="checkbox"])` — only the identity fields match, the
// consent checkboxes are excluded by the `:not()`.
const FORM_INPUT =
  "w-full min-h-11 rounded-panel border border-border bg-surface px-3 py-[7px] text-ink";

// `.access-process li > span`
const PROCESS_INDEX =
  "grid size-[22px] place-items-center rounded-full border border-border bg-surface" +
  " font-[ui-monospace,SFMono-Regular,Consolas,monospace] text-[10px] text-muted";

// `.access-consent-list label + label` — every child of the list is a `label`, so
// `not-first:` is exact.
const CONSENT_ROW =
  "grid cursor-pointer grid-cols-[18px_1fr] items-start gap-3 px-4 py-[14px]" +
  " not-first:border-t not-first:border-t-border";

const PURPOSES: Array<{ value: ConsentPurpose; label: string }> = [
  { value: "document_analysis", label: "문서 분석" },
  { value: "recording", label: "면접 녹화" },
  { value: "ai_assessment", label: "AI 평가 보조" },
];

const PROCESS = [
  {
    title: "자료 제출",
    description: "이력서와 공개 코드 저장소를 면접 질문 준비에 사용합니다.",
  },
  {
    title: "환경 점검",
    description: "카메라, 마이크와 네트워크 상태를 확인합니다.",
  },
  {
    title: "AI 면접",
    description: "제출 자료와 고정된 평가 기준을 바탕으로 질문합니다.",
  },
  {
    title: "제출 완료",
    description: "면접 결과는 기업의 사람 검토자에게 전달됩니다.",
  },
] as const;

const STEP_COPY: Record<
  Step,
  Readonly<{ eyebrow: string; title: string; description: string }>
> = {
  exchange: {
    eyebrow: "INVITATION",
    title: "지원자 면접",
    description:
      "초대 링크를 확인한 뒤 본인 확인과 개인정보 처리 동의를 진행합니다.",
  },
  identity: {
    eyebrow: "IDENTITY",
    title: "지원자 면접",
    description: "초대를 받은 지원자가 맞는지 간단히 확인합니다.",
  },
  consent: {
    eyebrow: "CONSENT",
    title: "지원자 면접",
    description: "서버가 제공한 정책을 확인하고 필요한 목적에 직접 동의합니다.",
  },
  ready: {
    eyebrow: "READY",
    title: "지원자 면접",
    description: "초대 확인과 필수 동의가 모두 완료되었습니다.",
  },
};

export function ApplicantAccess({
  api,
  initialToken,
  onContinue,
}: {
  api: ApplicantAccessApi;
  initialToken: string;
  onContinue?: () => void;
}) {
  const [step, setStep] = useState<Step>("exchange");
  const [displayName, setDisplayName] = useState("");
  const [verificationValue, setVerificationValue] = useState("");
  const [accepted, setAccepted] = useState<ConsentPurpose[]>([]);
  const [policy, setPolicy] = useState<ConsentPolicy | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const copy = STEP_COPY[step];

  async function run(action: () => Promise<void>) {
    setPending(true);
    setError("");
    try {
      await action();
    } catch {
      setError("요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setPending(false);
    }
  }

  async function exchange() {
    await run(async () => {
      await api.exchangeToken(initialToken);
      setStep("identity");
    });
  }

  async function verify(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await api.verifyIdentity(displayName, verificationValue);
      setPolicy(await api.getConsentPolicy());
      setStep("consent");
    });
  }

  function togglePurpose(purpose: ConsentPurpose) {
    setAccepted((current) =>
      current.includes(purpose)
        ? current.filter((item) => item !== purpose)
        : [...current, purpose],
    );
  }

  async function consent(event: FormEvent) {
    event.preventDefault();
    if (!policy || accepted.length !== policy.requiredPurposes.length) {
      return;
    }
    await run(async () => {
      await api.recordConsent(policy, [...policy.requiredPurposes]);
      setStep("ready");
    });
  }

  return (
    <main className={SHELL}>
      <header className="mb-7">
        <p className={EYEBROW}>{copy.eyebrow}</p>
        <h1 className="text-[26px] leading-[1.3] tracking-normal max-[600px]:text-[23px]">
          {copy.title}
        </h1>
        <p className={`mt-2 ${BODY_COPY}`}>{copy.description}</p>
      </header>

      {error && (
        <p
          className="mb-4 rounded-panel border border-[#f1b5b5] bg-[#fdecec] px-[14px] py-3 text-[13px] text-danger"
          role="alert"
        >
          {error}
        </p>
      )}

      {step === "exchange" && (
        <>
          <section
            className={`grid grid-cols-[44px_1fr] gap-[18px] p-7 max-[600px]:grid-cols-[38px_1fr] max-[600px]:gap-[14px] max-[600px]:px-5 max-[600px]:py-[22px] ${PANEL}`}
          >
            <div
              className="grid size-11 place-items-center rounded-panel border border-border bg-surface font-[ui-monospace,SFMono-Regular,Consolas,monospace] text-[15px] font-bold text-brand max-[600px]:size-[38px]"
              aria-hidden="true"
            >
              IE
            </div>
            <div>
              <p className={PANEL_LABEL}>면접 초대</p>
              <h2 className="text-[20px] tracking-normal">
                면접 초대가 도착했습니다
              </h2>
              <p className={`mt-2.5 ${BODY_COPY}`}>
                초대 확인 후 제출 자료와 면접 처리 범위를 직접 확인할 수
                있습니다. AI는 질문과 평가 초안을 만들지만 최종 결정은 기업의
                사람이 수행합니다.
              </p>
            </div>
            <button
              className={`col-span-full mt-1.5 w-full ${PRIMARY_ACTION}`}
              type="button"
              disabled={pending}
              onClick={() => void exchange()}
            >
              {pending ? "초대 확인 중" : "초대 확인"}
            </button>
          </section>

          <section
            className={`mt-4 px-6 py-[22px] max-[600px]:p-5 ${PANEL}`}
            aria-labelledby="process-title"
          >
            <div>
              <p className={EYEBROW}>PROCESS</p>
              <h2 id="process-title" className="text-[16px] tracking-normal">
                진행 과정
              </h2>
            </div>
            <ol className="mt-[18px] grid gap-[14px]">
              {PROCESS.map((item, index) => (
                <li
                  key={item.title}
                  className="grid grid-cols-[24px_1fr] items-start gap-3"
                >
                  <span className={PROCESS_INDEX} aria-hidden="true">
                    {index + 1}
                  </span>
                  <div>
                    <strong className="block text-[14px] font-semibold">
                      {item.title}
                    </strong>
                    <p className="mt-[3px] text-[12px] leading-[1.65] text-muted">
                      {item.description}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </>
      )}

      {step === "identity" && (
        <section className={`p-7 max-[600px]:p-5 ${PANEL}`}>
          <div>
            <p className={EYEBROW}>STEP 1 OF 2</p>
            <h2 className="text-[16px] tracking-normal">본인 확인</h2>
          </div>
          <p className={`mt-2.5 mb-6 ${BODY_COPY}`}>
            초대받은 이름과 기업이 안내한 확인 값을 입력해 주세요.
          </p>
          <form className="grid gap-4" onSubmit={verify}>
            <label className="grid gap-[7px] text-[13px] font-semibold">
              <span>이름</span>
              <input
                className={FORM_INPUT}
                required
                autoComplete="name"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </label>
            <label className="grid gap-[7px] text-[13px] font-semibold">
              <span>확인 값</span>
              <input
                className={FORM_INPUT}
                required
                autoComplete="one-time-code"
                value={verificationValue}
                onChange={(event) => setVerificationValue(event.target.value)}
              />
            </label>
            <button
              className={PRIMARY_ACTION}
              type="submit"
              disabled={pending || !displayName.trim() || !verificationValue}
            >
              {pending ? "확인 중" : "본인 확인 완료"}
            </button>
          </form>
        </section>
      )}

      {step === "consent" && (
        <section className={`p-7 max-[600px]:p-5 ${PANEL}`}>
          <div>
            <p className={EYEBROW}>STEP 2 OF 2</p>
            <h2 className="text-[16px] tracking-normal">
              개인정보 및 면접 처리 동의
            </h2>
          </div>
          {policy && (
            <section
              className="my-5 rounded-panel border border-[#dfe2ff] bg-brand-soft p-4"
              aria-label="동의 정책"
            >
              <p className="mb-2 text-[13px] leading-[1.55]">{policy.aiRole}</p>
              <p className="mb-2 text-[13px] leading-[1.55]">
                {policy.recordingNotice}
              </p>
              <dl className="mt-[14px] grid gap-2">
                <div className="grid grid-cols-[76px_1fr] gap-3 max-[600px]:grid-cols-[1fr] max-[600px]:gap-[3px]">
                  <dt className="text-[12px] text-muted">보관기간</dt>
                  <dd className="text-[12px] leading-[1.5]">
                    {policy.retentionDays}일
                  </dd>
                </div>
                <div className="grid grid-cols-[76px_1fr] gap-3 max-[600px]:grid-cols-[1fr] max-[600px]:gap-[3px]">
                  <dt className="text-[12px] text-muted">삭제 방법</dt>
                  <dd className="text-[12px] leading-[1.5]">
                    {policy.deletionMethod}
                  </dd>
                </div>
              </dl>
            </section>
          )}
          <form className="grid gap-4" onSubmit={consent}>
            <div className="grid overflow-hidden rounded-panel border border-border">
              {(
                policy?.processingPurposes ??
                PURPOSES.map((item) => ({
                  purpose: item.value,
                  title: item.label,
                  description: "",
                }))
              ).map(({ purpose, title, description }) => (
                <label key={purpose} className={CONSENT_ROW}>
                  <input
                    className="mt-0.5 size-4 accent-brand"
                    type="checkbox"
                    aria-label={title}
                    checked={accepted.includes(purpose)}
                    onChange={() => togglePurpose(purpose)}
                  />
                  <span>
                    <strong className="block text-[14px]">{title}</strong>
                    {description && (
                      <small className="mt-[3px] block text-[12px] leading-[1.5] font-normal text-muted">
                        {description}
                      </small>
                    )}
                  </span>
                </label>
              ))}
            </div>
            <button
              className={PRIMARY_ACTION}
              type="submit"
              disabled={
                pending ||
                !policy ||
                accepted.length !== policy.requiredPurposes.length
              }
            >
              {pending ? "동의 기록 중" : "동의하고 계속"}
            </button>
          </form>
        </section>
      )}

      {step === "ready" && (
        <section
          className={`px-7 py-9 text-center max-[600px]:p-5 ${PANEL}`}
          role="status"
        >
          <span
            className="mx-auto mb-4 grid size-[42px] place-items-center rounded-full bg-success-soft text-[20px] font-bold text-success"
            aria-hidden="true"
          >
            ✓
          </span>
          <p className={READY_LABEL}>ACCESS VERIFIED</p>
          <h2 className="text-[20px] tracking-normal">
            면접 준비를 시작할 수 있습니다.
          </h2>
          <p className={`mt-2.5 mb-[22px] ${BODY_COPY}`}>
            다음 단계에서 면접 질문 준비에 사용할 자료를 제출합니다.
          </p>
          <button
            className={`w-full ${PRIMARY_ACTION}`}
            type="button"
            onClick={onContinue}
          >
            자료 제출로 이동
          </button>
        </section>
      )}

      <p className="mt-[18px] text-center text-[12px] leading-[1.6] text-muted">
        기술 장애와 비언어적 특성은 역량 Evidence로 사용되지 않습니다.
      </p>
    </main>
  );
}
