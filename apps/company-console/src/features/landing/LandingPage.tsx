import {
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Database,
  FileSearch,
  Play,
  Quote,
  ServerCog,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { AnimatedWhyYouLogo } from "./AnimatedWhyYouLogo";
import {
  ProductTourGallery,
  type ProductTourSlide,
} from "./ProductTourGallery";

type FlowStep = Readonly<{
  number: string;
  title: string;
  description: string;
  image: string;
  imageAlt: string;
}>;

type ArchitectureLane = Readonly<{
  eyebrow: string;
  title: string;
  description: string;
  detail: string;
  icon: LucideIcon;
}>;

type Showcase = Readonly<{
  number: string;
  title: string;
  description: string;
  points: readonly string[];
  src: string;
  alt: string;
  slides?: readonly ProductTourSlide[];
  inset?: boolean;
  galleryLabel?: string;
}>;

const CONTAINER_CLASS =
  "mx-auto w-[min(1180px,calc(100%-48px))] max-md:w-[calc(100%-32px)]";
const EYEBROW_CLASS =
  "flex items-center gap-2 text-[11px] font-extrabold tracking-[0.15em] text-[#315dff]";
const SECTION_TITLE_CLASS =
  "mt-[15px] mb-4 text-[clamp(32px,4vw,48px)] leading-[1.18] font-bold tracking-[-0.05em] text-[#030b24]";
const BODY_COPY_CLASS = "text-[15px] leading-[1.8] text-[#6c748c]";
const LIST_ITEM_CLASS =
  "flex items-start gap-2 text-[13px] leading-[1.55] text-[#4f586f] [&>svg]:mt-px [&>svg]:shrink-0 [&>svg]:text-[#315dff]";
const DARK_BUTTON_CLASS =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-[11px] bg-[#030b24] px-4 text-[13px] font-bold text-white shadow-[0_7px_18px_rgb(3_11_36/14%)] transition hover:-translate-y-0.5 hover:bg-[#111a38]";
const LIGHT_BUTTON_CLASS =
  "inline-flex min-h-12 items-center justify-center gap-2 rounded-[11px] bg-[#030b24] px-5 text-[13px] font-bold text-white shadow-[0_14px_40px_rgb(3_11_36/18%)] transition hover:-translate-y-0.5 hover:bg-[#111a38] hover:shadow-[0_18px_50px_rgb(3_11_36/22%)]";
const GHOST_BUTTON_CLASS =
  "inline-flex min-h-12 items-center justify-center gap-2 rounded-[11px] border border-[#dce2f2] bg-white/75 px-5 text-[13px] font-bold text-[#17203a] transition hover:-translate-y-0.5 hover:border-[#b7c4ff] hover:bg-white";

const FLOW_STEPS: readonly FlowStep[] = [
  {
    number: "01",
    title: "포지션·평가 기준 설계",
    description: "직무 요건과 핵심 역량, 기준별 가중치를 먼저 정의합니다.",
    image: "/landing/flow-01-criteria.png",
    imageAlt: "포지션 평가 기준을 설계하는 일러스트",
  },
  {
    number: "02",
    title: "지원자 초대·자료 제출",
    description:
      "맞춤 초대 메일로 이력서, 경력기술서, 포트폴리오를 수집합니다.",
    image: "/landing/flow-02-invite.png",
    imageAlt: "지원자를 초대하고 자료를 받는 일러스트",
  },
  {
    number: "03",
    title: "근거 기반 질문 생성",
    description:
      "지원 자료의 실제 경험과 평가 기준을 연결해 질문을 준비합니다.",
    image: "/landing/flow-03-question.png",
    imageAlt: "지원 자료를 분석해 질문을 만드는 일러스트",
  },
  {
    number: "04",
    title: "맥락을 잇는 AI 면접",
    description:
      "답변 내용에 따라 후속 질문을 이어가며 구체적인 근거를 확인합니다.",
    image: "/landing/flow-04-interview.png",
    imageAlt: "답변 맥락을 이어가는 AI 면접 일러스트",
  },
  {
    number: "05",
    title: "리포트·담당자 판단",
    description:
      "답변 구간과 분석 근거를 검토한 뒤 사람이 최종 판단을 기록합니다.",
    image: "/landing/flow-05-report.png",
    imageAlt: "리포트를 검토하고 최종 판단하는 일러스트",
  },
];

const ARCHITECTURE_LANES: readonly ArchitectureLane[] = [
  {
    eyebrow: "INTERVIEW RAG",
    title: "지원자별 면접 검색",
    description:
      "제출 자료와 Git 분석 결과를 지원자·초대·평가 기준 범위로 검색해 질문과 후속 질문에 연결합니다.",
    detail: "retrieval_documents · applicant scoped",
    icon: FileSearch,
  },
  {
    eyebrow: "RECRUITER RAG",
    title: "최종 리포트 전용 검색",
    description:
      "완료된 리포트를 별도 검색 문서로 투영하고, 기업·포지션 범위 안에서 벡터와 키워드를 함께 검색합니다.",
    detail: "assistant_retrieval_documents · tenant scoped",
    icon: Database,
  },
  {
    eyebrow: "AWS RUNTIME",
    title: "실시간과 비동기 처리 분리",
    description:
      "원본은 S3에 보관하고 ECS API·Worker와 SQS가 분석을 나눕니다. 실시간 면접 컨텍스트는 TTL이 있는 DynamoDB로 분리합니다.",
    detail: "S3 · ECS Fargate · SQS · DynamoDB",
    icon: ServerCog,
  },
];

const HIRING_SETUP_SCREENS: readonly ProductTourSlide[] = [
  {
    label: "포지션 정보",
    src: "/landing/hiring-step-01-position.webp",
    alt: "포지션명과 채용 일정을 설정하는 실제 기업 콘솔 화면",
  },
  {
    label: "지원자 제출",
    src: "/landing/hiring-step-02-submission.webp",
    alt: "지원자에게 받을 제출 자료를 선택하는 실제 기업 콘솔 화면",
  },
  {
    label: "평가 설계",
    src: "/landing/hiring-step-03-criteria.webp",
    alt: "자격요건과 평가 가중치를 설계하는 실제 기업 콘솔 화면",
  },
  {
    label: "면접 운영",
    src: "/landing/hiring-step-04-interview.webp",
    alt: "면접 일정과 면접관을 설정하는 실제 기업 콘솔 화면",
  },
] as const;

const ASSISTANT_SCREENS: readonly ProductTourSlide[] = [
  {
    label: "근거 기반 답변",
    src: "/landing/ai-assistant.png",
    alt: "최종 리포트 근거를 검색해 답하는 AI 채용 어시스턴트 화면",
  },
  {
    label: "지원자 평가 근거",
    src: "/landing/ai-assistant-evidence.webp",
    alt: "AI 채용 어시스턴트에서 검색 근거를 클릭해 연 지원자 평가 요약서",
  },
] as const;

const SHOWCASES: readonly Showcase[] = [
  {
    number: "01 / OPERATIONS",
    title: "채용 전체를 한 화면에서",
    description:
      "포지션별 지원자 수, 진행 중인 면접, 검토 대기 상태와 채용 일정을 실시간으로 파악합니다.",
    points: ["포지션 핵심 지표", "채용 일정 캘린더", "지원자 실시간 로그"],
    src: "/landing/console-dashboard.png",
    alt: "채용 운영 대시보드 실제 화면",
  },
  {
    number: "02 / DESIGN",
    title: "평가 기준이 먼저인 면접 설계",
    description:
      "포지션 정보, 제출 자료, 평가 기준, 면접 운영을 단계별로 구성해 모든 질문의 출발점을 명확히 합니다.",
    points: ["4단계 채용 설정", "역량·가중치 정의", "면접관 페르소나 선택"],
    src: HIRING_SETUP_SCREENS[0].src,
    alt: HIRING_SETUP_SCREENS[0].alt,
    slides: HIRING_SETUP_SCREENS,
  },
  {
    number: "03 / INSIGHT",
    title: "비교 가능한 지원자 인사이트",
    description:
      "포지션의 평가 기준별 평균과 답변 근거 충족도를 함께 보며 검토가 필요한 지점을 빠르게 찾습니다.",
    points: ["평가 기준별 분석", "지원자 비교", "면접·검토 상태 추적"],
    src: "/landing/position-operations.png",
    alt: "포지션 인사이트 실제 화면",
  },
  {
    number: "04 / ASSISTANT",
    title: "근거를 찾아 답하는 AI 어시스턴트",
    description:
      "지원자와 포지션 데이터를 탐색하고, 연결된 최종 리포트의 근거를 바탕으로 채용 질문에 답합니다.",
    points: ["포지션 범위 검색", "리포트 근거 연결", "후보자 비교·요약"],
    src: ASSISTANT_SCREENS[0].src,
    alt: ASSISTANT_SCREENS[0].alt,
    slides: ASSISTANT_SCREENS,
    inset: true,
    galleryLabel: "AI 어시스턴트 근거 화면 갤러리",
  },
] as const;

const PROBLEMS = [
  {
    title: "자료만으로는 보이지 않는 역량",
    description:
      "이력서의 한 문장을 실제 경험과 판단 과정까지 이어서 확인해야 합니다.",
    image: "/landing/flow-03-question.png",
    imageAlt: "지원 자료에서 면접 근거를 찾는 일러스트",
  },
  {
    title: "반복되는 사전 면접 리소스",
    description:
      "같은 질문을 되풀이하는 대신 모든 지원자에게 일관된 검증 기회를 제공합니다.",
    image: "/landing/flow-04-interview.png",
    imageAlt: "일관된 AI 면접을 진행하는 일러스트",
  },
  {
    title: "결과만 남고 사라지는 근거",
    description:
      "점수와 요약을 원본 답변 구간에 연결해 언제든 판단 근거를 다시 확인합니다.",
    image: "/landing/flow-05-report.png",
    imageAlt: "답변 근거가 연결된 면접 리포트 일러스트",
  },
] as const;

const HERO_SCREENS = [
  {
    label: "운영 대시보드",
    eyebrow: "LIVE OPERATIONS",
    src: "/landing/console-dashboard.png",
    alt: "WhyYou 기업 콘솔 채용 운영 대시보드",
  },
  {
    label: "면접 설계",
    eyebrow: "INTERVIEW DESIGN",
    src: HIRING_SETUP_SCREENS[0].src,
    alt: "WhyYou 포지션과 평가 기준 설계 화면",
  },
  {
    label: "지원자 인사이트",
    eyebrow: "EVIDENCE INSIGHT",
    src: "/landing/position-operations.png",
    alt: "WhyYou 지원자 인사이트 화면",
  },
  {
    label: "AI 어시스턴트",
    eyebrow: "RECRUITING COPILOT",
    src: "/landing/ai-assistant.png",
    alt: "WhyYou AI 채용 어시스턴트 대화 화면",
  },
] as const;

const INTERVIEWERS = [
  {
    level: "신입",
    name: "안내형 면접관",
    role: "기초와 성장 가능성 중심",
    detail: "친절하게 경험의 배경부터 질문합니다.",
    image: "/interviewers/entry_eyes_open_mouth_closed.webp",
    evidence: "팀 프로젝트에서 처음 맡은 역할과 가장 크게 배운 점",
    question:
      "처음 맡아본 업무에서 어려웠던 점은 무엇이었고, 어떻게 해결해 나갔나요?",
  },
  {
    level: "주니어",
    name: "실무형 면접관",
    role: "본인 기여와 판단 근거 중심",
    detail: "실제 실행과 선택의 이유를 균형 있게 묻습니다.",
    image: "/interviewers/junior_eyes_open_mouth_closed.webp",
    evidence: "ECS 운영 중 트래픽 급증으로 발생한 장애 대응",
    question:
      "당시 본인이 직접 내린 판단은 무엇이었고, 결과를 어떤 지표로 확인했나요?",
  },
  {
    level: "시니어",
    name: "심층형 면접관",
    role: "설계·트레이드오프 중심",
    detail: "대안과 장기적 영향을 깊이 확인합니다.",
    image: "/interviewers/senior_eyes_open_mouth_closed.webp",
    evidence: "고가용성 구조 전환과 비용 효율 사이의 설계 결정",
    question:
      "선택하지 않은 대안과 비교했을 때, 이 설계의 가장 큰 트레이드오프는 무엇이었나요?",
  },
] as const;

function SectionHeading({
  eyebrow,
  title,
  children,
  dark = false,
  align = "center",
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  dark?: boolean;
  align?: "center" | "left";
}) {
  return (
    <div
      className={`mb-14 max-w-[780px] ${align === "center" ? "mx-auto text-center" : "text-left"}`}
    >
      <p
        className={`${EYEBROW_CLASS} ${align === "center" ? "justify-center" : ""}`}
      >
        {eyebrow}
      </p>
      <h2 className={`${SECTION_TITLE_CLASS} ${dark ? "!text-white" : ""}`}>
        {title}
      </h2>
      <p className={`${BODY_COPY_CLASS} ${dark ? "!text-[#aab2ca]" : ""}`}>
        {children}
      </p>
    </div>
  );
}

function ProductFrame({
  src,
  alt,
  slides,
  inset = false,
  galleryLabel,
}: {
  src: string;
  alt: string;
  slides?: readonly ProductTourSlide[];
  inset?: boolean;
  galleryLabel?: string;
}) {
  return (
    <div className="overflow-hidden rounded-[18px] border border-[#d8dce6] bg-white shadow-[0_30px_80px_rgb(3_11_36/14%)] transition duration-500 group-hover:-translate-y-1 group-hover:shadow-[0_36px_90px_rgb(3_11_36/18%)]">
      <div className="flex h-[34px] items-center gap-[5px] border-b border-[#e7e9ef] bg-[#fbfbfc] px-3">
        <span className="flex gap-[5px]" aria-hidden="true">
          {Array.from({ length: 3 }, (_, index) => (
            <i key={index} className="size-1.5 rounded-full bg-[#d6d9e1]" />
          ))}
        </span>
        <span className="mx-auto flex-1 rounded-[5px] bg-[#f1f2f5] px-3 py-1 text-center text-[7px] text-[#a0a6b5]">
          app.whyyou.ai
        </span>
      </div>
      {slides ? (
        <ProductTourGallery
          slides={slides}
          inset={inset}
          ariaLabel={galleryLabel}
        />
      ) : (
        <div className="relative aspect-[1.6/1] overflow-hidden bg-[#f4f6fb]">
          <img
            className="h-full w-full object-contain object-center"
            src={src}
            alt={alt}
            width="1440"
            height="900"
            loading="lazy"
            decoding="async"
          />
        </div>
      )}
    </div>
  );
}

function EvidenceList({ points }: { points: readonly string[] }) {
  return (
    <ul className="mt-7 grid list-none gap-3 p-0">
      {points.map((point) => (
        <li className={LIST_ITEM_CLASS} key={point}>
          <Check size={15} aria-hidden="true" />
          {point}
        </li>
      ))}
    </ul>
  );
}

function HeroProductCarousel() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const activeScreen = HERO_SCREENS[activeIndex];

  useEffect(() => {
    if (paused) return;
    const timer = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % HERO_SCREENS.length);
    }, 5200);
    return () => window.clearInterval(timer);
  }, [paused]);

  function move(step: number) {
    setActiveIndex(
      (current) => (current + step + HERO_SCREENS.length) % HERO_SCREENS.length,
    );
  }

  return (
    <div
      className="relative w-full"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget))
          setPaused(false);
      }}
    >
      <div className="overflow-hidden rounded-[22px] border border-[#dce2f1] bg-white shadow-[0_32px_80px_rgb(36_55_112/16%)]">
        <div className="flex min-h-11 items-center gap-2 border-b border-[#e7eaf2] bg-[#fbfcff] px-4 text-[9px] font-extrabold tracking-[0.08em] text-[#6d7690]">
          <span className="flex gap-1.5" aria-hidden="true">
            <i className="size-2 rounded-full bg-[#ff9ea7]" />
            <i className="size-2 rounded-full bg-[#ffd16d]" />
            <i className="size-2 rounded-full bg-[#6ed6ae]" />
          </span>
          <span className="ml-2 inline-flex items-center gap-1.5">
            <i className="size-1.5 animate-pulse rounded-full bg-[#26bd7f] shadow-[0_0_0_4px_rgb(38_189_127/12%)] motion-reduce:animate-none" />
            {activeScreen.eyebrow}
          </span>
          <span className="ml-auto rounded-full bg-[#eef2ff] px-2.5 py-1 text-[#315dff]">
            {String(activeIndex + 1).padStart(2, "0")} / 04
          </span>
        </div>
        <div className="relative aspect-[1.6/1] overflow-hidden bg-[#f4f6fb] max-sm:aspect-[1.35/1]">
          {activeScreen.label === "면접 설계" ? (
            <ProductTourGallery
              slides={HIRING_SETUP_SCREENS}
              interval={3000}
              ariaLabel="히어로 면접 설계 화면 갤러리"
            />
          ) : (
            <img
              className="h-full w-full object-cover object-top [animation:landing-screen-in_.48s_cubic-bezier(.22,.8,.2,1)] motion-reduce:animate-none"
              key={activeScreen.src}
              src={activeScreen.src}
              alt={activeScreen.alt}
              width="1440"
              height="900"
              decoding="async"
            />
          )}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-white/90 to-transparent" />
        </div>
        <div className="flex items-center gap-2 border-t border-[#edf0f6] bg-white px-4 py-3 max-sm:flex-wrap">
          <div className="flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto [scrollbar-width:none]">
            {HERO_SCREENS.map((screen, index) => (
              <button
                className={`shrink-0 rounded-full px-3 py-2 text-[10px] font-bold transition ${
                  index === activeIndex
                    ? "bg-[#315dff] text-white shadow-[0_7px_18px_rgb(49_93_255/23%)]"
                    : "bg-[#f2f4f9] text-[#69728a] hover:bg-[#e9edff] hover:text-[#315dff]"
                }`}
                key={screen.label}
                type="button"
                aria-pressed={index === activeIndex}
                onClick={() => setActiveIndex(index)}
              >
                {screen.label}
              </button>
            ))}
          </div>
          <div className="flex shrink-0 gap-1.5">
            <button
              className="grid size-8 place-items-center rounded-full border border-[#dfe4f1] text-[#536078] transition hover:border-[#315dff] hover:text-[#315dff]"
              type="button"
              aria-label="이전 핵심 화면"
              onClick={() => move(-1)}
            >
              <ChevronLeft size={15} aria-hidden="true" />
            </button>
            <button
              className="grid size-8 place-items-center rounded-full border border-[#dfe4f1] text-[#536078] transition hover:border-[#315dff] hover:text-[#315dff]"
              type="button"
              aria-label="다음 핵심 화면"
              onClick={() => move(1)}
            >
              <ChevronRight size={15} aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function FlowCard({
  step,
  preview = false,
}: {
  step: FlowStep;
  preview?: boolean;
}) {
  return (
    <li
      className={`group grid h-[270px] w-[calc((100vw-60px)/5)] min-w-[150px] max-w-[270px] shrink-0 grid-rows-[auto_auto_150px] overflow-hidden rounded-[20px] border border-[#dfe4ee] bg-white px-4 pt-4 shadow-[0_18px_45px_rgb(28_45_92/7%)] transition duration-300 hover:-translate-y-1 hover:border-[#c7d2ff] hover:shadow-[0_24px_60px_rgb(49_93_255/11%)] max-sm:h-[340px] max-sm:w-[72vw] max-sm:min-w-[72vw] max-sm:grid-rows-[auto_auto_190px] ${
        preview ? "opacity-55" : ""
      }`}
      aria-hidden={preview || undefined}
    >
      <h3 className="mb-2 flex min-h-[40px] items-start gap-1.5 text-[clamp(14px,1.35vw,17px)] leading-[1.4] font-bold tracking-[-0.04em] text-[#111936]">
        <span className="mt-[2px] shrink-0 text-[10px] font-extrabold tracking-[0.08em] text-[#315dff]">
          {step.number}
        </span>
        <span>{step.title}</span>
      </h3>
      <p className="min-h-[50px] text-[11px] leading-[1.65] text-[#727b90]">
        {step.description}
      </p>
      <div className="-mx-2 mt-0 h-full overflow-hidden rounded-[18px] bg-[radial-gradient(circle_at_50%_50%,rgb(99_111_246/12%),transparent_61%)]">
        <img
          className="h-full w-full object-contain object-center transition duration-500 group-hover:scale-[1.03]"
          src={step.image}
          alt={preview ? "" : step.imageAlt}
          width="540"
          height="440"
          loading="lazy"
        />
      </div>
    </li>
  );
}

function FlowCarousel() {
  const [startIndex, setStartIndex] = useState(0);
  const [direction, setDirection] = useState<"next" | "previous">("next");
  const visibleSteps = Array.from({ length: 6 }, (_, slot) => {
    const index =
      (startIndex + slot - 1 + FLOW_STEPS.length) % FLOW_STEPS.length;
    return FLOW_STEPS[index];
  });

  function move(step: number) {
    setDirection(step > 0 ? "next" : "previous");
    setStartIndex(
      (current) => (current + step + FLOW_STEPS.length) % FLOW_STEPS.length,
    );
  }

  function moveTo(index: number) {
    if (index === startIndex) return;

    const forwardDistance =
      (index - startIndex + FLOW_STEPS.length) % FLOW_STEPS.length;
    const backwardDistance =
      (startIndex - index + FLOW_STEPS.length) % FLOW_STEPS.length;
    setDirection(forwardDistance <= backwardDistance ? "next" : "previous");
    setStartIndex(index);
  }

  return (
    <div className="relative left-1/2 w-screen -translate-x-1/2 overflow-hidden py-1">
      <ol
        className={`flex list-none justify-center gap-3 p-0 motion-reduce:animate-none ${
          direction === "next"
            ? "[animation:landing-flow-next_.9s_cubic-bezier(.22,.75,.2,1)]"
            : "[animation:landing-flow-previous_.9s_cubic-bezier(.22,.75,.2,1)]"
        }`}
        key={`${direction}-${startIndex}`}
      >
        {visibleSteps.map((step, slot) => (
          <FlowCard
            key={`${startIndex}-${slot}-${step.number}`}
            step={step}
            preview={slot === 0 || slot === visibleSteps.length - 1}
          />
        ))}
      </ol>
      <button
        className="absolute top-1/2 left-4 z-[3] grid size-11 -translate-y-1/2 place-items-center rounded-full border border-[#d9e0ee] bg-white/95 text-[#315dff] shadow-[0_12px_30px_rgb(28_45_92/18%)] backdrop-blur transition hover:-translate-x-1 hover:border-[#315dff] max-sm:left-2"
        type="button"
        aria-label="이전 채용 단계 보기"
        onClick={() => move(-1)}
      >
        <ChevronLeft size={20} aria-hidden="true" />
      </button>
      <button
        className="absolute top-1/2 right-4 z-[3] grid size-11 -translate-y-1/2 place-items-center rounded-full border border-[#d9e0ee] bg-white/95 text-[#315dff] shadow-[0_12px_30px_rgb(28_45_92/18%)] backdrop-blur transition hover:translate-x-1 hover:border-[#315dff] max-sm:right-2"
        type="button"
        aria-label="다음 채용 단계 보기"
        onClick={() => move(1)}
      >
        <ChevronRight size={20} aria-hidden="true" />
      </button>
      <div
        className="mt-3 flex justify-center gap-1.5"
        aria-label="채용 단계 캐러셀 위치"
      >
        {FLOW_STEPS.map((step, index) => (
          <button
            className={`h-1.5 rounded-full transition-all ${
              index === startIndex ? "w-7 bg-[#315dff]" : "w-1.5 bg-[#c9cfdd]"
            }`}
            key={step.number}
            type="button"
            aria-label={`${Number(step.number)}번 단계부터 보기`}
            aria-pressed={index === startIndex}
            onClick={() => moveTo(index)}
          />
        ))}
      </div>
    </div>
  );
}

function InterviewerSlider() {
  const [activeIndex, setActiveIndex] = useState(1);
  const interviewer = INTERVIEWERS[activeIndex];

  function move(step: number) {
    setActiveIndex(
      (current) => (current + step + INTERVIEWERS.length) % INTERVIEWERS.length,
    );
  }

  return (
    <div className="relative min-h-[570px] overflow-hidden rounded-[28px] border border-[#dfe4f1] bg-[radial-gradient(circle_at_50%_18%,rgb(96_124_255/16%),transparent_34%),linear-gradient(155deg,#fbfcff,#f1f5ff)] p-[24px_28px_28px] shadow-[0_32px_80px_rgb(5_13_42/12%)] before:absolute before:inset-0 before:bg-[radial-gradient(#9daaf5_0.75px,transparent_0.75px)] before:bg-[size:16px_16px] before:opacity-15 max-sm:min-h-0 max-sm:p-5">
      <div className="relative z-[1] flex items-center justify-between text-[9px] font-extrabold tracking-[0.09em] text-[#646d85]">
        <span className="flex items-center gap-2">
          <i className="size-1.5 animate-pulse rounded-full bg-[#26bd7f] shadow-[0_0_0_4px_rgb(38_189_127/12%)] motion-reduce:animate-none" />
          AI INTERVIEW · LIVE
        </span>
        <span>07:42</span>
      </div>

      <div
        className="relative z-[1] mt-6 flex justify-center gap-2"
        aria-label="AI 면접관 유형"
      >
        {INTERVIEWERS.map((item, index) => (
          <button
            className={`rounded-full px-4 py-2 text-[10px] font-bold transition ${
              index === activeIndex
                ? "bg-[#315dff] text-white shadow-[0_8px_20px_rgb(49_93_255/24%)]"
                : "border border-[#dce2f0] bg-white/75 text-[#68718a] hover:border-[#315dff] hover:text-[#315dff]"
            }`}
            key={item.level}
            type="button"
            aria-pressed={index === activeIndex}
            onClick={() => setActiveIndex(index)}
          >
            {item.level}
          </button>
        ))}
      </div>

      <div
        className="relative z-[1] [animation:landing-interviewer-slide_.44s_cubic-bezier(.22,.8,.2,1)] motion-reduce:animate-none"
        key={interviewer.level}
        aria-live="polite"
      >
        <div className="mx-auto my-[28px_22px] grid w-full max-w-[470px] grid-cols-[112px_1fr] items-center gap-[22px] max-sm:grid-cols-[82px_1fr] max-sm:gap-4">
          <div className="size-28 rounded-full border border-[#cdd5f5] bg-white p-[5px] shadow-[0_14px_35px_rgb(49_93_255/14%)] max-sm:size-[82px]">
            <img
              className="size-full rounded-full object-cover"
              src={interviewer.image}
              alt={`${interviewer.level} ${interviewer.name}`}
              width="180"
              height="180"
              loading="lazy"
            />
          </div>
          <div className="grid gap-1">
            <small className="text-[9px] font-extrabold tracking-[0.09em] text-[#315dff]">
              {interviewer.level.toUpperCase()} · AI INTERVIEWER
            </small>
            <strong className="text-lg text-[#111936]">
              {interviewer.name}
            </strong>
            <span className="text-[11px] font-semibold text-[#5f6880]">
              {interviewer.role}
            </span>
            <span className="text-[10px] text-[#8990a3]">
              {interviewer.detail}
            </span>
          </div>
        </div>
        <div className="relative z-[1] mx-auto mb-3 w-full max-w-[520px] rounded-[13px] border border-[#e1e5f0] bg-white/90 p-[17px_19px] shadow-[0_8px_24px_rgb(4_12_38/6%)]">
          <span className="text-[9px] font-extrabold tracking-[0.09em] text-[#315dff]">
            지원 자료 근거
          </span>
          <p className="mt-[7px] text-xs leading-[1.65] text-[#485169]">
            “{interviewer.evidence}”
          </p>
        </div>
        <div className="relative z-[1] mx-auto mb-3 grid w-full max-w-[520px] grid-cols-[22px_1fr] items-start rounded-[13px] border border-[#cbd5ff] bg-[#eef2ff] p-[17px_19px] shadow-[0_8px_24px_rgb(4_12_38/6%)]">
          <Quote
            className="mt-[3px] text-[#315dff]"
            size={18}
            aria-hidden="true"
          />
          <p className="text-xs leading-[1.65] font-semibold text-[#1d2c62]">
            {interviewer.question}
          </p>
        </div>
      </div>

      <div className="relative z-[2] mt-5 flex items-center justify-center gap-3">
        <button
          className="grid size-9 place-items-center rounded-full border border-[#d6ddef] bg-white text-[#5d6680] shadow-sm transition hover:-translate-x-0.5 hover:border-[#315dff] hover:text-[#315dff]"
          type="button"
          aria-label="이전 AI 면접관"
          onClick={() => move(-1)}
        >
          <ChevronLeft size={17} aria-hidden="true" />
        </button>
        <div className="flex gap-1.5" aria-hidden="true">
          {INTERVIEWERS.map((item, index) => (
            <i
              className={`h-1.5 rounded-full transition-all ${index === activeIndex ? "w-7 bg-[#315dff]" : "w-1.5 bg-[#c9cfdd]"}`}
              key={item.level}
            />
          ))}
        </div>
        <button
          className="grid size-9 place-items-center rounded-full border border-[#d6ddef] bg-white text-[#5d6680] shadow-sm transition hover:translate-x-0.5 hover:border-[#315dff] hover:text-[#315dff]"
          type="button"
          aria-label="다음 AI 면접관"
          onClick={() => move(1)}
        >
          <ChevronRight size={17} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

export function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-clip bg-white text-[#111936]">
      <a
        className="fixed top-2 left-2 z-[300] -translate-y-[160%] rounded-lg bg-[#315dff] px-3 py-2 text-white focus-visible:translate-y-0"
        href="#landing-content"
      >
        본문으로 이동
      </a>

      <header className="sticky top-0 z-[100] min-h-[72px] border-b border-[#e1e4ee]/80 bg-white/90 backdrop-blur-[18px]">
        <div className="mx-auto grid min-h-[72px] w-[min(1240px,calc(100%-48px))] grid-cols-[154px_1fr_auto] items-center max-md:w-[calc(100%-32px)] max-md:grid-cols-[1fr_auto]">
          <Link
            className="inline-flex w-[126px] leading-none"
            to="/"
            aria-label="WhyYou 홈"
          >
            <img
              className="h-auto w-full"
              src="/brand-motion/logo.svg"
              alt="WhyYou"
              width="1364"
              height="533"
            />
          </Link>
          <nav
            className="flex justify-center gap-[34px] text-[13px] font-semibold text-[#4f5770] max-lg:hidden [&>a]:transition [&>a:hover]:text-[#315dff]"
            aria-label="랜딩페이지 탐색"
          >
            <a href="#service">서비스</a>
            <a href="#flow">면접 플로우</a>
            <a href="#console">기업 콘솔</a>
            <a href="#architecture">기술 구성</a>
          </nav>
          <div className="flex items-center gap-[18px] max-sm:gap-3">
            <Link
              className="text-[13px] font-bold transition hover:text-[#315dff]"
              to="/auth/login"
            >
              로그인
            </Link>
            <Link
              className={`${DARK_BUTTON_CLASS} max-sm:hidden`}
              to="/auth/signup"
            >
              기업 계정 만들기
              <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </header>

      <main id="landing-content">
        <section
          className="relative isolate scroll-mt-[86px] overflow-hidden bg-[radial-gradient(circle_at_82%_22%,rgb(106_129_255/24%),transparent_28%),radial-gradient(circle_at_12%_82%,rgb(119_225_221/18%),transparent_26%),linear-gradient(145deg,#ffffff_0%,#f5f8ff_58%,#edf2ff_100%)] py-[100px] max-lg:py-20 max-md:py-16"
          aria-labelledby="landing-hero-title"
        >
          <div
            className="absolute inset-0 -z-10 bg-[linear-gradient(rgb(49_93_255/4%)_1px,transparent_1px),linear-gradient(90deg,rgb(49_93_255/4%)_1px,transparent_1px)] bg-[size:52px_52px] [mask-image:linear-gradient(to_bottom,black,transparent_90%)]"
            aria-hidden="true"
          />
          <div className="absolute -top-44 right-[4%] -z-10 size-[520px] rounded-full bg-[#9fb0ff]/20 blur-[45px]" />
          <div className="pointer-events-none absolute top-[130px] right-[1%] z-0 w-[min(50vw,680px)] opacity-35 drop-shadow-[0_24px_50px_rgb(49_93_255/14%)] max-lg:top-[150px] max-lg:right-[4%] max-lg:w-[430px] max-lg:opacity-35 max-sm:top-[370px] max-sm:right-[-105px] max-sm:w-[430px] max-sm:opacity-[0.14]">
            <AnimatedWhyYouLogo />
          </div>
          <div className={`${CONTAINER_CLASS} relative z-[1] grid gap-14`}>
            <div className="max-w-[620px]">
              <p className={EYEBROW_CLASS}>
                <Sparkles size={15} aria-hidden="true" />
                EVIDENCE-BASED AI INTERVIEW
              </p>
              <h1
                className="my-[22px] max-w-[620px] text-[clamp(46px,5.1vw,72px)] leading-[1.07] font-bold tracking-[-0.058em] text-[#030b24] max-sm:text-[42px]"
                id="landing-hero-title"
              >
                면접의 이유를,
                <br />
                <span className="bg-[linear-gradient(105deg,#315dff,#7472f4)] bg-clip-text text-transparent">
                  근거로 확인하세요.
                </span>
              </h1>
              <p className="max-w-[550px] text-base leading-[1.85] text-[#5f6981]">
                WhyYou는 지원 자료와 실제 답변을 연결해 직무 맞춤 질문을 만들고,
                AI 면접의 모든 대화를 검토 가능한 근거로 정리합니다.
              </p>
              <div className="mt-[34px] flex gap-2.5 max-sm:flex-col">
                <Link className={LIGHT_BUTTON_CLASS} to="/auth/login">
                  기업 콘솔 로그인
                  <ArrowRight size={17} aria-hidden="true" />
                </Link>
                <a className={GHOST_BUTTON_CLASS} href="#flow">
                  <Play size={15} fill="currentColor" aria-hidden="true" />
                  서비스 흐름 보기
                </a>
              </div>
              <ul
                className="mt-7 flex list-none flex-wrap gap-[17px] p-0 text-[11px] text-[#69738a] [&>li]:inline-flex [&>li]:items-center [&>li]:gap-[5px] [&_svg]:text-[#315dff]"
                aria-label="WhyYou 핵심 원칙"
              >
                <li>
                  <Check size={14} aria-hidden="true" />
                  근거 기반 질문
                </li>
                <li>
                  <Check size={14} aria-hidden="true" />
                  실시간 AI 면접
                </li>
                <li>
                  <Check size={14} aria-hidden="true" />
                  사람의 최종 결정
                </li>
              </ul>
            </div>

            <HeroProductCarousel />
          </div>
        </section>

        <section
          className="scroll-mt-[86px] bg-white py-[120px] max-md:py-20"
          id="service"
          aria-labelledby="problem-title"
        >
          <div className={CONTAINER_CLASS}>
            <SectionHeading
              eyebrow="THE RECRUITING GAP"
              title="채용 담당자의 시간은, 판단에 쓰여야 하니까"
            >
              반복되는 확인 업무는 줄이고 지원자의 역량을 검증하는 일에
              집중하세요.
            </SectionHeading>
            <div className="grid grid-cols-3 gap-5 max-lg:gap-3 max-md:grid-cols-1 max-md:gap-5">
              {PROBLEMS.map(({ title, description, image, imageAlt }) => (
                <article
                  className="group grid min-h-[390px] grid-rows-[auto_auto_minmax(0,1fr)] overflow-hidden rounded-[22px] border border-[#dfe4ef] bg-[linear-gradient(150deg,#ffffff,#f8faff)] px-7 pt-7 shadow-[0_20px_55px_rgb(24_39_88/7%)] transition duration-300 hover:-translate-y-1 hover:border-[#c7d1ff] hover:shadow-[0_26px_70px_rgb(49_93_255/12%)] max-md:min-h-[360px]"
                  key={title}
                >
                  <h3 className="mb-3 text-[20px] font-bold tracking-[-0.04em] text-[#111936]">
                    {title}
                  </h3>
                  <p className="text-[13px] leading-[1.75] text-[#6c758b]">
                    {description}
                  </p>
                  <div className="-mx-4 mt-1 min-h-0 overflow-hidden rounded-t-[22px] bg-[radial-gradient(circle_at_50%_64%,rgb(102_112_245/13%),transparent_58%)]">
                    <img
                      className="h-full w-full origin-bottom scale-[1.16] object-contain object-bottom transition duration-500 group-hover:scale-[1.21]"
                      src={image}
                      alt={imageAlt}
                      width="600"
                      height="430"
                      loading="lazy"
                    />
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section
          className="scroll-mt-[86px] overflow-hidden bg-[linear-gradient(180deg,#f5f8ff_0%,#ffffff_100%)] py-[124px] max-md:py-20"
          id="flow"
          aria-labelledby="flow-title"
        >
          <div className={CONTAINER_CLASS}>
            <SectionHeading
              eyebrow="ONE CONNECTED FLOW"
              title="채용 기준에서 최종 검토까지, 하나의 흐름으로"
            >
              면접이 시작되기 전의 설계부터 면접 이후의 사람 판단까지 자연스럽게
              연결됩니다.
            </SectionHeading>
            <FlowCarousel />
            <div className="mt-5 flex justify-center gap-8 text-[11px] font-semibold text-[#687189] max-sm:grid max-sm:grid-cols-2 max-sm:gap-4">
              <span className="inline-flex items-center gap-2">
                <Check
                  className="text-[#315dff]"
                  size={14}
                  aria-hidden="true"
                />
                공정하고 일관된 평가
              </span>
              <span className="inline-flex items-center gap-2">
                <Check
                  className="text-[#315dff]"
                  size={14}
                  aria-hidden="true"
                />
                채용 시간 효율화
              </span>
              <span className="inline-flex items-center gap-2">
                <Check
                  className="text-[#315dff]"
                  size={14}
                  aria-hidden="true"
                />
                데이터 기반 의사결정
              </span>
              <span className="inline-flex items-center gap-2">
                <Check
                  className="text-[#315dff]"
                  size={14}
                  aria-hidden="true"
                />
                사람의 최종 판단 보장
              </span>
            </div>
          </div>
        </section>

        <section
          className="bg-white py-32 max-md:py-20"
          aria-labelledby="interview-title"
        >
          <div
            className={`${CONTAINER_CLASS} grid grid-cols-[0.8fr_1.2fr] items-center gap-[94px] max-lg:grid-cols-1 max-lg:gap-14`}
          >
            <div>
              <p className={EYEBROW_CLASS}>CONTEXT-AWARE INTERVIEW</p>
              <h2 className={SECTION_TITLE_CLASS} id="interview-title">
                지원자의 자료에서 출발하고,
                <br />
                답변의 맥락에 따라 깊어집니다.
              </h2>
              <p className={BODY_COPY_CLASS}>
                미리 정한 평가 기준을 유지하면서도 지원자의 답변에 등장한 경험과
                선택을 따라 후속 질문을 이어갑니다.
              </p>
              <EvidenceList
                points={[
                  "지원 자료와 직무 요건을 함께 반영",
                  "답변 맥락에 따른 후속 질문",
                  "질문·답변·영상 시점 자동 연결",
                ]}
              />
            </div>
            <InterviewerSlider />
          </div>
        </section>

        <section
          className="scroll-mt-[86px] bg-[#f5f6f9] py-32 max-md:py-20"
          id="console"
          aria-labelledby="console-title"
        >
          <div className={CONTAINER_CLASS}>
            <SectionHeading
              eyebrow="REAL PRODUCT, REAL WORKFLOW"
              title="채용 운영을 위해 필요한 화면을, 실제 제품 안에"
            >
              WhyYou 기업 콘솔의 실제 화면으로 포지션 설계부터 분석까지 확인해
              보세요.
            </SectionHeading>
            <div className="grid gap-28 max-md:gap-20">
              {SHOWCASES.map((showcase, index) => (
                <article
                  className="group grid grid-cols-[0.72fr_1.28fr] items-center gap-16 max-lg:grid-cols-1 max-lg:gap-9"
                  key={showcase.number}
                >
                  <div
                    className={
                      index % 2 === 1 ? "order-2 max-lg:order-none" : ""
                    }
                  >
                    <span className="text-[10px] font-extrabold tracking-[0.12em] text-[#315dff]">
                      {showcase.number}
                    </span>
                    <h3 className="mt-[13px] mb-3.5 text-[clamp(26px,3vw,37px)] font-bold tracking-[-0.05em] text-[#030b24]">
                      {showcase.title}
                    </h3>
                    <p className="text-sm leading-[1.8] text-[#6c7489]">
                      {showcase.description}
                    </p>
                    <EvidenceList points={showcase.points} />
                  </div>
                  <ProductFrame
                    src={showcase.src}
                    alt={showcase.alt}
                    slides={showcase.slides}
                    inset={showcase.inset}
                    galleryLabel={showcase.galleryLabel}
                  />
                </article>
              ))}
            </div>
          </div>
        </section>

        <section
          className="scroll-mt-[86px] overflow-hidden bg-[#f3f6ff] py-28 max-md:py-20"
          id="architecture"
          aria-labelledby="architecture-title"
        >
          <div className={CONTAINER_CLASS}>
            <div className="mx-auto mb-14 max-w-[820px] text-center">
              <p className={`${EYEBROW_CLASS} justify-center`}>
                TECHNICAL FOUNDATION
              </p>
              <h2 className={SECTION_TITLE_CLASS} id="architecture-title">
                두 RAG 저장소를, 쓰임에 맞게 분리했습니다.
              </h2>
              <p className={BODY_COPY_CLASS}>
                지원자 면접과 채용 담당자 챗봇은 같은 Aurora PostgreSQL을
                사용하지만, 서로 다른 벡터 테이블과 검색 스코프로 데이터 경계를
                유지합니다.
              </p>
            </div>

            <div className="grid grid-cols-3 gap-4 max-md:grid-cols-1">
              {ARCHITECTURE_LANES.map((lane) => {
                const Icon = lane.icon;
                return (
                  <article
                    className="rounded-[20px] border border-[#dce3f5] bg-white p-7 shadow-[0_18px_50px_rgb(38_55_107/8%)]"
                    key={lane.title}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <span className="text-[10px] font-extrabold tracking-[0.13em] text-[#315dff]">
                        {lane.eyebrow}
                      </span>
                      <span className="grid size-10 shrink-0 place-items-center rounded-[11px] bg-[#edf1ff] text-[#315dff]">
                        <Icon size={20} strokeWidth={1.8} aria-hidden="true" />
                      </span>
                    </div>
                    <h3 className="mt-6 mb-3 text-[20px] font-bold tracking-[-0.04em] text-[#08112e]">
                      {lane.title}
                    </h3>
                    <p className="text-[13px] leading-[1.75] text-[#667087]">
                      {lane.description}
                    </p>
                    <code className="mt-6 block overflow-hidden text-ellipsis whitespace-nowrap rounded-[9px] bg-[#f4f6fb] px-3 py-2.5 text-[10px] text-[#4e5c7d]">
                      {lane.detail}
                    </code>
                  </article>
                );
              })}
            </div>

            <div className="mt-5 rounded-[18px] border border-[#dce3f5] bg-white px-6 py-5">
              <p className="mb-4 text-[11px] font-extrabold tracking-[0.12em] text-[#111936]">
                DEPLOYED DATA FLOW
              </p>
              <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold text-[#59657d]">
                {[
                  "Cognito",
                  "CloudFront + S3",
                  "ECS Fargate API / Worker",
                  "SQS",
                  "Aurora Serverless v2 + pgvector",
                  "DynamoDB TTL",
                  "Bedrock + Titan Embeddings",
                ].map((technology, index, technologies) => (
                  <div className="contents" key={technology}>
                    <span className="rounded-full bg-[#f1f4ff] px-3 py-2">
                      {technology}
                    </span>
                    {index < technologies.length - 1 ? (
                      <ArrowRight
                        className="text-[#9ba7c3] max-sm:hidden"
                        size={13}
                        aria-hidden="true"
                      />
                    ) : null}
                  </div>
                ))}
              </div>
              <p className="mt-4 text-[11px] leading-[1.65] text-[#7a8499]">
                원본 파일과 생성 결과는 분리 보관하며, 모든 검색은 기업·지원자
                범위와 소스 버전을 함께 검사합니다.
              </p>
            </div>
          </div>
        </section>

        <section
          className="relative isolate overflow-hidden bg-[#030b24] py-[110px] text-white max-md:py-20"
          aria-labelledby="final-cta-title"
        >
          <div className="absolute top-1/2 left-1/2 -z-10 h-[260px] w-[760px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#315dff]/30 blur-[70px]" />
          <div className={`${CONTAINER_CLASS} text-center`}>
            <p className="text-[11px] font-extrabold tracking-[0.16em] text-[#9eafff]">
              WHY YOU, WHY NOW
            </p>
            <h2
              className="mt-4 mb-4 text-[clamp(34px,4.6vw,56px)] font-bold tracking-[-0.05em]"
              id="final-cta-title"
            >
              지원자의 가능성에 더 확실한 이유를.
            </h2>
            <span className="text-[15px] text-[#b9c1db]">
              직무 기준부터 답변 근거까지 연결된 AI 면접을 시작해 보세요.
            </span>
            <div className="mt-8 flex justify-center gap-2.5 max-sm:flex-col">
              <Link className={LIGHT_BUTTON_CLASS} to="/auth/login">
                기업 콘솔 로그인
                <ArrowRight size={17} aria-hidden="true" />
              </Link>
              <Link className={GHOST_BUTTON_CLASS} to="/auth/signup">
                기업 계정 만들기
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-white py-12">
        <div
          className={`${CONTAINER_CLASS} grid grid-cols-[auto_1fr_auto] items-center gap-x-10 gap-y-5 max-md:grid-cols-1 max-md:justify-items-center max-md:text-center`}
        >
          <Link
            className="inline-flex w-[126px] leading-none"
            to="/"
            aria-label="WhyYou 홈"
          >
            <img
              className="h-auto w-full"
              src="/brand-motion/logo.svg"
              alt="WhyYou"
              width="1364"
              height="533"
            />
          </Link>
          <p className="text-xs text-[#767d90]">
            근거로 연결되는 AI 인터뷰 플랫폼
          </p>
          <nav
            className="flex gap-5 text-xs font-semibold text-[#535b70] [&>a]:transition [&>a:hover]:text-[#315dff]"
            aria-label="푸터 메뉴"
          >
            <a href="#service">서비스</a>
            <a href="#flow">면접 플로우</a>
            <Link to="/auth/login">기업 로그인</Link>
          </nav>
          <small className="col-span-3 text-[10px] text-[#a0a5b3] max-md:col-span-1">
            © 2026 WhyYou. Interview evidence, made reviewable.
          </small>
        </div>
      </footer>
    </div>
  );
}
