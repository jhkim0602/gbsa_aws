import { FormEvent, useState } from "react";

export type ConsentPurpose =
  "document_analysis" | "recording" | "ai_assessment";

export type ApplicantAccessApi = {
  exchangeToken(token: string): Promise<void>;
  verifyIdentity(displayName: string, verificationValue: string): Promise<void>;
  recordConsent(purposes: ConsentPurpose[]): Promise<void>;
};

type Step = "exchange" | "identity" | "consent" | "ready";

const PURPOSES: Array<{ value: ConsentPurpose; label: string }> = [
  { value: "document_analysis", label: "문서 분석" },
  { value: "recording", label: "면접 녹화" },
  { value: "ai_assessment", label: "AI 평가 보조" },
];

export function ApplicantAccess({
  api,
  initialToken,
}: {
  api: ApplicantAccessApi;
  initialToken: string;
}) {
  const [step, setStep] = useState<Step>("exchange");
  const [displayName, setDisplayName] = useState("");
  const [verificationValue, setVerificationValue] = useState("");
  const [accepted, setAccepted] = useState<ConsentPurpose[]>([]);

  async function exchange() {
    await api.exchangeToken(initialToken);
    setStep("identity");
  }

  async function verify(event: FormEvent) {
    event.preventDefault();
    await api.verifyIdentity(displayName, verificationValue);
    setStep("consent");
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
    if (accepted.length !== PURPOSES.length) {
      return;
    }
    await api.recordConsent(PURPOSES.map(({ value }) => value));
    setStep("ready");
  }

  return (
    <main>
      <header>
        <p>GBSA Interview Evidence</p>
        <h1>지원자 면접</h1>
      </header>

      {step === "exchange" && (
        <button type="button" onClick={exchange}>
          초대 확인
        </button>
      )}

      {step === "identity" && (
        <form onSubmit={verify}>
          <h2>본인 확인</h2>
          <label>
            이름
            <input
              required
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </label>
          <label>
            확인 값
            <input
              required
              value={verificationValue}
              onChange={(event) => setVerificationValue(event.target.value)}
            />
          </label>
          <button type="submit">본인 확인 완료</button>
        </form>
      )}

      {step === "consent" && (
        <form onSubmit={consent}>
          <h2>개인정보 및 면접 처리 동의</h2>
          {PURPOSES.map(({ value, label }) => (
            <label key={value}>
              <input
                type="checkbox"
                checked={accepted.includes(value)}
                onChange={() => togglePurpose(value)}
              />
              {label}
            </label>
          ))}
          <button type="submit" disabled={accepted.length !== PURPOSES.length}>
            동의하고 계속
          </button>
        </form>
      )}

      {step === "ready" && <p role="status">면접 준비를 시작할 수 있습니다.</p>}
    </main>
  );
}
