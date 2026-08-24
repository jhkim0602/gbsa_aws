import {
  ArrowRight,
  Check,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";

type CompanyAuthMode = "login" | "signup";

const AUTH_COPY = {
  login: {
    eyebrow: "WELCOME BACK",
    title: "기업 로그인",
    description:
      "기업 계정으로 로그인하고 채용 포지션과 지원자 검토를 이어가세요.",
    primary: "기업 계정으로 로그인",
    alternateLead: "처음 이용하시나요?",
    alternateLabel: "기업 계정 만들기",
    alternateTo: "/auth/signup",
  },
  signup: {
    eyebrow: "START WITH WHY",
    title: "기업 계정 만들기",
    description:
      "WhyYou 워크스페이스를 만들고 근거 기반 채용 운영을 시작하세요.",
    primary: "기업 계정 만들기",
    alternateLead: "이미 계정이 있나요?",
    alternateLabel: "로그인",
    alternateTo: "/auth/login",
  },
} as const;

export function CompanyAuthView({
  mode,
  cognitoEnabled,
  error,
  onPrimary,
  onDemo,
}: {
  mode: CompanyAuthMode;
  cognitoEnabled: boolean;
  error: boolean;
  onPrimary(): void;
  onDemo(): void;
}) {
  const copy = AUTH_COPY[mode];

  return (
    <main className="relative isolate min-h-screen overflow-hidden bg-[radial-gradient(circle_at_16%_20%,rgb(98_128_255/19%),transparent_30%),radial-gradient(circle_at_88%_82%,rgb(108_226_213/14%),transparent_27%),linear-gradient(145deg,#fdfefe_0%,#f3f6ff_55%,#edf2ff_100%)] text-[#111936]">
      <div
        className="absolute inset-0 -z-10 bg-[linear-gradient(rgb(49_93_255/4%)_1px,transparent_1px),linear-gradient(90deg,rgb(49_93_255/4%)_1px,transparent_1px)] bg-[size:52px_52px] [mask-image:linear-gradient(to_bottom,black,transparent_92%)]"
        aria-hidden="true"
      />

      <header className="mx-auto flex min-h-[82px] w-[min(1180px,calc(100%-48px))] items-center justify-between max-sm:w-[calc(100%-32px)]">
        <Link className="w-[142px]" to="/" aria-label="WhyYou 홈">
          <img
            className="h-auto w-full"
            src="/brand-motion/logo.svg"
            alt="WhyYou"
            width="1364"
            height="533"
          />
        </Link>
        <Link
          className="text-[12px] font-bold text-[#5d6680] transition hover:text-[#315dff]"
          to="/"
        >
          서비스 소개로 돌아가기
        </Link>
      </header>

      <div className="mx-auto grid min-h-[calc(100vh-82px)] w-[min(1180px,calc(100%-48px))] grid-cols-[minmax(0,1fr)_440px] items-center gap-14 py-8 max-[900px]:grid-cols-1 max-[900px]:gap-12 max-[900px]:py-14 max-sm:w-[calc(100%-32px)]">
        <section className="max-w-[590px] max-[900px]:mx-auto max-[900px]:text-center">
          <p className="flex items-center gap-2 text-[11px] font-extrabold tracking-[0.16em] text-[#315dff] max-[900px]:justify-center">
            <Sparkles size={15} aria-hidden="true" />
            EVIDENCE-BASED HIRING
          </p>
          <h2 className="mt-6 text-[clamp(38px,4.5vw,64px)] leading-[1.08] font-bold tracking-[-0.06em] text-[#030b24]">
            좋은 질문에서 시작해,
            <br />
            <span className="bg-[linear-gradient(105deg,#315dff,#7472f4)] bg-clip-text text-transparent">
              근거 있는 판단까지.
            </span>
          </h2>
          <p className="mt-7 max-w-[540px] text-[15px] leading-[1.85] text-[#667087] max-[900px]:mx-auto">
            지원 자료, AI 면접, 답변 근거와 최종 검토를 하나의 기업 콘솔에서
            연결합니다.
          </p>
          <ul className="mt-9 grid list-none gap-3 p-0 max-[900px]:mx-auto max-[900px]:w-fit max-[900px]:text-left">
            {[
              "직무별 평가 기준 설계",
              "맥락을 잇는 AI 면접",
              "원문과 연결된 근거 리포트",
            ].map((point) => (
              <li
                className="flex items-center gap-3 text-[13px] font-semibold text-[#4e5871]"
                key={point}
              >
                <span className="grid size-6 place-items-center rounded-full bg-[#e8edff] text-[#315dff]">
                  <Check size={14} strokeWidth={2.4} aria-hidden="true" />
                </span>
                {point}
              </li>
            ))}
          </ul>
        </section>

        <section
          className="w-full rounded-[28px] border border-white/90 bg-white/88 p-8 shadow-[0_32px_90px_rgb(31_48_102/16%)] backdrop-blur-xl max-sm:p-6"
          aria-labelledby="company-auth-title"
        >
          <span className="inline-flex items-center gap-2 rounded-full bg-[#eef2ff] px-3 py-2 text-[9px] font-extrabold tracking-[0.12em] text-[#315dff]">
            <LockKeyhole size={13} aria-hidden="true" />
            {copy.eyebrow}
          </span>
          <h1
            className="mt-5 text-[32px] font-bold tracking-[-0.05em] text-[#030b24]"
            id="company-auth-title"
          >
            {copy.title}
          </h1>
          <p className="mt-3 text-[13px] leading-[1.75] text-[#6b748b]">
            {copy.description}
          </p>

          <button
            className="mt-7 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-[12px] bg-[#030b24] px-5 text-[13px] font-bold text-white shadow-[0_15px_35px_rgb(3_11_36/18%)] transition hover:-translate-y-0.5 hover:bg-[#111a38] disabled:cursor-not-allowed disabled:opacity-45"
            type="button"
            disabled={mode === "signup" && !cognitoEnabled}
            onClick={onPrimary}
          >
            {copy.primary}
            <ArrowRight size={16} aria-hidden="true" />
          </button>

          {!cognitoEnabled ? (
            <p
              className="mt-2 text-center text-[10px] text-[#8991a5]"
              role="status"
            >
              {mode === "login"
                ? "로컬 개발 인증으로 연결됩니다."
                : "회원가입은 Cognito가 연결된 배포 환경에서 사용할 수 있습니다."}
            </p>
          ) : null}

          <div
            className="my-6 flex items-center gap-3 text-[9px] font-bold tracking-[0.1em] text-[#a0a7b7]"
            aria-hidden="true"
          >
            <span className="h-px flex-1 bg-[#e6e9f1]" />
            DEMO ACCESS
            <span className="h-px flex-1 bg-[#e6e9f1]" />
          </div>

          <div className="rounded-[18px] border border-[#cfd8ff] bg-[linear-gradient(145deg,#f5f7ff,#edf2ff)] p-5">
            <div className="flex items-start gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-[12px] bg-white text-[#315dff] shadow-[0_8px_20px_rgb(49_93_255/12%)]">
                <ShieldCheck size={21} aria-hidden="true" />
              </span>
              <div>
                <strong className="block text-[14px] text-[#17234e]">
                  심사위원이신가요?
                </strong>
                <p className="mt-1 text-[11px] leading-[1.65] text-[#68728c]">
                  준비된 공용 데모 계정으로 기업 콘솔의 전체 흐름을 확인하세요.
                </p>
              </div>
            </div>
            <button
              className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-[11px] bg-[#315dff] px-4 text-[12px] font-bold text-white shadow-[0_12px_28px_rgb(49_93_255/24%)] transition hover:-translate-y-0.5 hover:bg-[#244fe4]"
              type="button"
              onClick={onDemo}
            >
              데모 아이디로 들어가기
              <ArrowRight size={15} aria-hidden="true" />
            </button>
          </div>

          <p className="mt-6 text-center text-[12px] text-[#788197]">
            {copy.alternateLead}{" "}
            <Link
              className="font-bold text-[#315dff] hover:underline"
              to={copy.alternateTo}
            >
              {copy.alternateLabel}
            </Link>
          </p>

          {error ? (
            <p
              className="mt-4 rounded-[10px] bg-red-50 px-3 py-2 text-center text-[11px] font-semibold text-red-600"
              role="alert"
            >
              인증을 시작할 수 없습니다. 잠시 후 다시 시도해 주세요.
            </p>
          ) : null}
        </section>
      </div>
    </main>
  );
}

export function CompanyAuthStatusView({ error }: { error: boolean }) {
  return (
    <main className="grid min-h-screen place-items-center bg-[linear-gradient(145deg,#ffffff,#eef3ff)] p-6">
      <section className="grid w-[min(100%,440px)] justify-items-center gap-5 rounded-[24px] border border-white bg-white/90 p-9 text-center shadow-[0_28px_75px_rgb(31_48_102/15%)]">
        <Link className="w-[142px]" to="/" aria-label="WhyYou 홈">
          <img
            className="h-auto w-full"
            src="/brand-motion/logo.svg"
            alt="WhyYou"
            width="1364"
            height="533"
          />
        </Link>
        <h1 className="text-[24px] font-bold tracking-[-0.04em] text-[#030b24]">
          기업 로그인 확인
        </h1>
        <p
          className={`text-[13px] leading-[1.7] ${error ? "text-red-600" : "text-[#6b748b]"}`}
          role={error ? "alert" : "status"}
        >
          {error
            ? "로그인 응답을 확인할 수 없습니다."
            : "기업 계정 로그인을 안전하게 확인하고 있습니다."}
        </p>
      </section>
    </main>
  );
}
