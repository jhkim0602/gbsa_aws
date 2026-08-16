import { type FormEvent, useState } from "react";

import "./access.css";

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
    <main className="access-screen">
      <header className="access-heading">
        <p className="access-eyebrow">{copy.eyebrow}</p>
        <h1>{copy.title}</h1>
        <p>{copy.description}</p>
      </header>

      {error && (
        <p className="access-alert" role="alert">
          {error}
        </p>
      )}

      {step === "exchange" && (
        <>
          <section className="access-primary-panel">
            <div className="access-invitation-mark" aria-hidden="true">
              IE
            </div>
            <div className="access-invitation-copy">
              <p className="access-panel-label">면접 초대</p>
              <h2>면접 초대가 도착했습니다</h2>
              <p>
                초대 확인 후 제출 자료와 면접 처리 범위를 직접 확인할 수
                있습니다. AI는 질문과 평가 초안을 만들지만 최종 결정은 기업의
                사람이 수행합니다.
              </p>
            </div>
            <button
              className="access-primary-action"
              type="button"
              disabled={pending}
              onClick={() => void exchange()}
            >
              {pending ? "초대 확인 중" : "초대 확인"}
            </button>
          </section>

          <section className="access-process" aria-labelledby="process-title">
            <div className="access-section-heading">
              <p>PROCESS</p>
              <h2 id="process-title">진행 과정</h2>
            </div>
            <ol>
              {PROCESS.map((item, index) => (
                <li key={item.title}>
                  <span aria-hidden="true">{index + 1}</span>
                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.description}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </>
      )}

      {step === "identity" && (
        <section className="access-form-panel">
          <div className="access-section-heading">
            <p>STEP 1 OF 2</p>
            <h2>본인 확인</h2>
          </div>
          <p className="access-form-description">
            초대받은 이름과 기업이 안내한 확인 값을 입력해 주세요.
          </p>
          <form onSubmit={verify}>
            <label>
              <span>이름</span>
              <input
                required
                autoComplete="name"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </label>
            <label>
              <span>확인 값</span>
              <input
                required
                autoComplete="one-time-code"
                value={verificationValue}
                onChange={(event) => setVerificationValue(event.target.value)}
              />
            </label>
            <button
              className="access-primary-action"
              type="submit"
              disabled={pending || !displayName.trim() || !verificationValue}
            >
              {pending ? "확인 중" : "본인 확인 완료"}
            </button>
          </form>
        </section>
      )}

      {step === "consent" && (
        <section className="access-form-panel">
          <div className="access-section-heading">
            <p>STEP 2 OF 2</p>
            <h2>개인정보 및 면접 처리 동의</h2>
          </div>
          {policy && (
            <section className="access-policy" aria-label="동의 정책">
              <p>{policy.aiRole}</p>
              <p>{policy.recordingNotice}</p>
              <dl>
                <div>
                  <dt>보관기간</dt>
                  <dd>{policy.retentionDays}일</dd>
                </div>
                <div>
                  <dt>삭제 방법</dt>
                  <dd>{policy.deletionMethod}</dd>
                </div>
              </dl>
            </section>
          )}
          <form className="access-consent-form" onSubmit={consent}>
            <div className="access-consent-list">
              {(
                policy?.processingPurposes ??
                PURPOSES.map((item) => ({
                  purpose: item.value,
                  title: item.label,
                  description: "",
                }))
              ).map(({ purpose, title, description }) => (
                <label key={purpose}>
                  <input
                    type="checkbox"
                    aria-label={title}
                    checked={accepted.includes(purpose)}
                    onChange={() => togglePurpose(purpose)}
                  />
                  <span>
                    <strong>{title}</strong>
                    {description && <small>{description}</small>}
                  </span>
                </label>
              ))}
            </div>
            <button
              className="access-primary-action"
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
        <section className="access-ready" role="status">
          <span className="access-ready-mark" aria-hidden="true">
            ✓
          </span>
          <p className="access-panel-label">ACCESS VERIFIED</p>
          <h2>면접 준비를 시작할 수 있습니다.</h2>
          <p>다음 단계에서 면접 질문 준비에 사용할 자료를 제출합니다.</p>
          <button
            className="access-primary-action"
            type="button"
            onClick={onContinue}
          >
            자료 제출로 이동
          </button>
        </section>
      )}

      <p className="access-footnote">
        기술 장애와 비언어적 특성은 역량 Evidence로 사용되지 않습니다.
      </p>
    </main>
  );
}
