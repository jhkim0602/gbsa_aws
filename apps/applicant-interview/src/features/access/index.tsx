import {
  BriefcaseBusiness,
  CalendarClock,
  Clock3,
  FileCheck2,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";

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
  getInvitationPreview(token: string): Promise<ApplicantInvitationPreview>;
  exchangeToken(token: string): Promise<void>;
  verifyIdentity(displayName: string): Promise<void>;
  getConsentPolicy(): Promise<ConsentPolicy>;
  recordConsent(
    policy: ConsentPolicy,
    purposes: ConsentPurpose[],
  ): Promise<void>;
};

export type ApplicantInvitationPreview = Readonly<{
  companyName: string;
  positionTitle: string;
  positionDescription: string;
  roleType?: string | null;
  interviewAt?: string | null;
  interviewDurationMinutes: number;
  interviewLevel: "entry" | "junior" | "senior";
  interviewerName?: string | null;
  submissionRequirements: readonly {
    materialType: string;
    required: boolean;
    enabled: boolean;
    instructions?: string | null;
  }[];
}>;

type Step = "exchange" | "identity" | "consent" | "ready";

// `.applicant-content > .access-screen` set a 560px max, but it lost to
// `.applicant-content > main:not(.interview-room)` in shell.css on specificity (0,2,0 vs
// 0,2,1), so this screen has always rendered at `--applicant-content-width` (960px) with
// shell.css's 72px/104px block padding. Kept as it renders.
const SHELL =
  "mx-auto w-[min(calc(100%-48px),1080px)] pt-10 pb-20" +
  " mw-600:mx-4 mw-600:w-auto mw-600:pt-8 mw-600:pb-14";

// `.access-primary-panel`, `.access-process`, `.access-form-panel`, `.access-ready`
const PANEL = "rounded-panel border border-border bg-surface shadow-soft";

// `.access-eyebrow` and `.access-section-heading > p` — no sibling rule outranks them.
const EYEBROW =
  "mb-2 font-[ui-monospace,SFMono-Regular,Consolas,monospace] text-[11px]" +
  " tracking-normal text-muted";

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

const ONBOARDING_GRID =
  "grid grid-cols-[minmax(0,1.55fr)_minmax(280px,0.75fr)] items-start gap-4" +
  " mw-860:grid-cols-1";

const DETAIL_ICON =
  "grid size-8 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand";

const INTERVIEW_DATE_FORMATTER = new Intl.DateTimeFormat(
  "en-US-u-ca-gregory-nu-latn",
  {
    timeZone: "Asia/Seoul",
    month: "numeric",
    day: "numeric",
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    hourCycle: "h23",
  },
);

const WEEKDAY_LABELS: Record<string, string> = {
  Sun: "일",
  Mon: "월",
  Tue: "화",
  Wed: "수",
  Thu: "목",
  Fri: "금",
  Sat: "토",
};

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

const MATERIAL_LABELS: Record<string, string> = {
  resume: "이력서",
  cover_letter: "자기소개서",
  career_description: "경력기술서",
  projects: "대표 프로젝트",
  portfolio: "포트폴리오",
};

const INTERVIEW_LEVEL_LABELS: Record<
  ApplicantInvitationPreview["interviewLevel"],
  string
> = {
  entry: "안내형 면접관",
  junior: "실무형 면접관",
  senior: "심층형 면접관",
};

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
  const [accepted, setAccepted] = useState<ConsentPurpose[]>([]);
  const [policy, setPolicy] = useState<ConsentPolicy | null>(null);
  const [preview, setPreview] = useState<ApplicantInvitationPreview | null>(
    null,
  );
  const [previewState, setPreviewState] = useState<
    "loading" | "ready" | "unavailable"
  >("loading");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const copy = STEP_COPY[step];

  useEffect(() => {
    let active = true;
    if (initialToken.length < 32) {
      setPreviewState("unavailable");
      return () => {
        active = false;
      };
    }
    setPreviewState("loading");
    api
      .getInvitationPreview(initialToken)
      .then((result) => {
        if (!active) return;
        setPreview(result);
        setPreviewState("ready");
      })
      .catch(() => {
        if (active) setPreviewState("unavailable");
      });
    return () => {
      active = false;
    };
  }, [api, initialToken]);

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
      await api.verifyIdentity(displayName);
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
        <h1 className="text-[26px] leading-[1.3] tracking-normal mw-600:text-[23px]">
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

      <div className={ONBOARDING_GRID}>
        <div className="min-w-0">
          {step === "exchange" ? (
            <InvitationBrief
              preview={preview}
              state={previewState}
              pending={pending}
              onConfirm={() => void exchange()}
            />
          ) : null}

          {step === "identity" ? (
            <section className={`p-7 mw-600:p-5 ${PANEL}`}>
              <div>
                <p className={EYEBROW}>STEP 1 OF 2</p>
                <h2 className="text-[16px] tracking-normal">본인 확인</h2>
              </div>
              <p className={`mt-2.5 mb-6 ${BODY_COPY}`}>
                초대받은 지원자 이름을 입력해 주세요.
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
                <button
                  className={PRIMARY_ACTION}
                  type="submit"
                  disabled={pending || !displayName.trim()}
                >
                  {pending ? "확인 중" : "본인 확인 완료"}
                </button>
              </form>
            </section>
          ) : null}

          {step === "consent" ? (
            <section className={`p-7 mw-600:p-5 ${PANEL}`}>
              <div>
                <p className={EYEBROW}>STEP 2 OF 2</p>
                <h2 className="text-[16px] tracking-normal">
                  개인정보 및 면접 처리 동의
                </h2>
              </div>
              {policy ? (
                <section
                  className="my-5 rounded-panel border border-[#dfe2ff] bg-brand-soft p-4"
                  aria-label="동의 정책"
                >
                  <p className="mb-2 text-[13px] leading-[1.55]">
                    {policy.aiRole}
                  </p>
                  <p className="mb-2 text-[13px] leading-[1.55]">
                    {policy.recordingNotice}
                  </p>
                  <dl className="mt-[14px] grid gap-2">
                    <div className="grid grid-cols-[76px_1fr] gap-3 mw-600:grid-cols-[1fr] mw-600:gap-[3px]">
                      <dt className="text-[12px] text-muted">보관기간</dt>
                      <dd className="text-[12px] leading-[1.5]">
                        {policy.retentionDays}일
                      </dd>
                    </div>
                    <div className="grid grid-cols-[76px_1fr] gap-3 mw-600:grid-cols-[1fr] mw-600:gap-[3px]">
                      <dt className="text-[12px] text-muted">삭제 방법</dt>
                      <dd className="text-[12px] leading-[1.5]">
                        {policy.deletionMethod}
                      </dd>
                    </div>
                  </dl>
                </section>
              ) : null}
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
                        {description ? (
                          <small className="mt-[3px] block text-[12px] leading-[1.5] font-normal text-muted">
                            {description}
                          </small>
                        ) : null}
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
          ) : null}

          {step === "ready" ? (
            <section
              className={`px-7 py-9 text-center mw-600:p-5 ${PANEL}`}
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
          ) : null}
        </div>

        {step === "exchange" ? (
          <ProcessPanel />
        ) : (
          <InvitationSummary preview={preview} state={previewState} />
        )}
      </div>

      <p className="mt-[18px] text-center text-[12px] leading-[1.6] text-muted">
        기술 장애와 비언어적 특성은 역량 Evidence로 사용되지 않습니다.
      </p>
    </main>
  );
}

function InvitationBrief({
  preview,
  state,
  pending,
  onConfirm,
}: {
  preview: ApplicantInvitationPreview | null;
  state: "loading" | "ready" | "unavailable";
  pending: boolean;
  onConfirm(): void;
}) {
  const enabledMaterials = preview?.submissionRequirements.filter(
    (requirement) => requirement.enabled,
  );
  return (
    <section
      className={`overflow-hidden ${PANEL}`}
      aria-labelledby="brief-title"
    >
      <div className="border-b border-border bg-[linear-gradient(135deg,#f8f9ff_0%,#ffffff_72%)] px-7 py-6 mw-600:p-5">
        <div className="flex items-start gap-4">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl border border-[#dfe2ff] bg-surface text-brand">
            <BriefcaseBusiness size={21} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="mb-1 text-[11px] font-semibold text-brand">
              {preview
                ? `${preview.companyName}${preview.roleType ? ` · ${preview.roleType}` : ""}`
                : "면접 초대"}
            </p>
            <h2
              id="brief-title"
              className="text-[22px] leading-[1.35] tracking-normal text-ink"
            >
              {preview?.positionTitle ?? "면접 정보를 확인하고 있습니다"}
            </h2>
            <p className="mt-2 line-clamp-3 text-[13px] leading-[1.65] text-muted">
              {preview?.positionDescription ??
                (state === "loading"
                  ? "채용담당자가 설정한 포지션과 면접 정보를 불러오는 중입니다."
                  : "초대 링크에서 포지션 정보를 확인할 수 없습니다. 링크를 다시 확인해 주세요.")}
            </p>
          </div>
        </div>
      </div>

      <dl className="grid grid-cols-3 border-b border-border mw-600:grid-cols-1">
        <BriefFact
          icon={<CalendarClock size={16} aria-hidden="true" />}
          label="면접 예정"
          value={formatInterviewAt(preview?.interviewAt)}
        />
        <BriefFact
          icon={<Clock3 size={16} aria-hidden="true" />}
          label="예상 소요 시간"
          value={preview ? `${preview.interviewDurationMinutes}분` : "확인 중"}
        />
        <BriefFact
          icon={<UserRound size={16} aria-hidden="true" />}
          label="면접 방식"
          value={interviewerLabel(preview)}
        />
      </dl>

      <div className="px-7 py-5 mw-600:p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className={EYEBROW}>REQUIRED MATERIALS</p>
            <h3 className="text-[14px] font-semibold text-ink">제출 자료</h3>
          </div>
          {preview ? (
            <span className="text-[11px] text-muted">
              필수{" "}
              {enabledMaterials?.filter((item) => item.required).length ?? 0}개
            </span>
          ) : null}
        </div>
        <div className="mt-3 flex min-h-8 flex-wrap gap-2" aria-live="polite">
          {enabledMaterials?.length ? (
            enabledMaterials.map((requirement) => (
              <span
                key={requirement.materialType}
                className="inline-flex min-h-8 max-w-full min-w-0 items-center gap-1.5 overflow-hidden rounded-lg border border-border bg-surface-muted px-2.5 text-[12px] text-ink-secondary mw-600:w-full"
                title={requirement.instructions ?? undefined}
              >
                <FileCheck2 className="shrink-0" size={13} aria-hidden="true" />
                <span className="truncate">
                  {materialLabel(requirement.materialType)}
                </span>
                <small
                  className={`shrink-0 ${requirement.required ? "text-brand" : "text-muted"}`}
                >
                  {requirement.required ? "필수" : "선택"}
                </small>
              </span>
            ))
          ) : (
            <span className="text-[12px] text-muted">
              {state === "loading"
                ? "제출 항목을 확인하는 중입니다."
                : "제출 항목을 표시할 수 없습니다."}
            </span>
          )}
        </div>
        <div className="mt-5 flex items-start gap-2 rounded-lg bg-surface-muted px-3 py-2.5 text-[11px] leading-[1.55] text-muted">
          <ShieldCheck
            className="mt-0.5 shrink-0 text-success"
            size={15}
            aria-hidden="true"
          />
          <p>
            표시된 일정과 제출 자료는 채용담당자가 이 포지션에 설정한 값입니다.
            내부 평가 기준과 가중치는 지원자에게 공개되지 않습니다.
          </p>
        </div>
        <button
          className={`mt-5 w-full ${PRIMARY_ACTION}`}
          type="button"
          disabled={pending || state === "loading"}
          onClick={onConfirm}
        >
          {pending ? "초대 확인 중" : "내용을 확인하고 계속"}
        </button>
      </div>
    </section>
  );
}

function BriefFact({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3 border-r border-border px-5 py-4 last:border-r-0 mw-600:border-r-0 mw-600:not-last:border-b">
      <span className={DETAIL_ICON}>{icon}</span>
      <div className="min-w-0">
        <dt className="text-[10px] text-muted">{label}</dt>
        <dd className="mt-0.5 truncate text-[12px] font-semibold text-ink">
          {value}
        </dd>
      </div>
    </div>
  );
}

function ProcessPanel() {
  return (
    <aside
      className={`px-5 py-5 mw-600:p-5 ${PANEL}`}
      aria-labelledby="process-title"
    >
      <p className={EYEBROW}>PROCESS</p>
      <h2 id="process-title" className="text-[16px] tracking-normal">
        진행 과정
      </h2>
      <ol className="mt-5 grid gap-4">
        {PROCESS.map((item, index) => (
          <li
            key={item.title}
            className="grid grid-cols-[24px_1fr] items-start gap-3"
          >
            <span className={PROCESS_INDEX} aria-hidden="true">
              {index + 1}
            </span>
            <div>
              <strong className="block text-[13px] font-semibold">
                {item.title}
              </strong>
              <p className="mt-1 text-[11px] leading-[1.55] text-muted">
                {item.description}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </aside>
  );
}

function InvitationSummary({
  preview,
  state,
}: {
  preview: ApplicantInvitationPreview | null;
  state: "loading" | "ready" | "unavailable";
}) {
  return (
    <aside className={`overflow-hidden ${PANEL}`} aria-label="현재 면접 정보">
      <header className="border-b border-border bg-surface-muted px-5 py-4">
        <p className={EYEBROW}>INTERVIEW BRIEF</p>
        <h2 className="text-[15px] font-semibold text-ink">
          {preview?.positionTitle ?? "면접 정보"}
        </h2>
        <p className="mt-1 text-[11px] text-muted">
          {preview?.companyName ??
            (state === "loading" ? "설정값 확인 중" : "초대 정보 없음")}
        </p>
      </header>
      <dl className="grid px-5 py-2">
        <SummaryFact
          label="면접 예정"
          value={formatInterviewAt(preview?.interviewAt)}
        />
        <SummaryFact
          label="소요 시간"
          value={preview ? `${preview.interviewDurationMinutes}분` : "확인 중"}
        />
        <SummaryFact label="면접 방식" value={interviewerLabel(preview)} />
        <SummaryFact label="제출 자료" value={materialSummary(preview)} />
      </dl>
    </aside>
  );
}

function SummaryFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[72px_1fr] gap-3 border-b border-border-muted py-3 last:border-b-0">
      <dt className="text-[11px] text-muted">{label}</dt>
      <dd className="text-right text-[11px] font-semibold leading-[1.5] text-ink">
        {value}
      </dd>
    </div>
  );
}

function formatInterviewAt(value?: string | null) {
  if (!value) return "추후 안내";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "추후 안내";
  const parts = Object.fromEntries(
    INTERVIEW_DATE_FORMATTER.formatToParts(date).map((part) => [
      part.type,
      part.value,
    ]),
  );
  const hour = Number(parts.hour);
  const weekday = WEEKDAY_LABELS[parts.weekday];
  if (!Number.isInteger(hour) || !weekday) return "추후 안내";
  const dayPeriod = hour < 12 ? "오전" : "오후";
  const displayHour = String(hour % 12 || 12).padStart(2, "0");
  return `${parts.month}월 ${parts.day}일 (${weekday}) ${dayPeriod} ${displayHour}:${parts.minute}`;
}

function interviewerLabel(preview: ApplicantInvitationPreview | null) {
  if (!preview) return "확인 중";
  return (
    preview.interviewerName ?? INTERVIEW_LEVEL_LABELS[preview.interviewLevel]
  );
}

function materialLabel(materialType: string) {
  return MATERIAL_LABELS[materialType] ?? materialType.replaceAll("_", " ");
}

function materialSummary(preview: ApplicantInvitationPreview | null) {
  if (!preview) return "확인 중";
  const enabled = preview.submissionRequirements.filter((item) => item.enabled);
  if (!enabled.length) return "없음";
  const required = enabled.filter((item) => item.required).length;
  return `${enabled.length}개 · 필수 ${required}개`;
}
