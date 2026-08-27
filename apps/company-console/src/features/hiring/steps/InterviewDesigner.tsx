import { useEffect, useRef, useState } from "react";

import {
  CalendarClock,
  Check,
  Coins,
  MessageSquareText,
  Mic2,
  Plus,
  ServerCog,
  Sparkles,
  Trash2,
  Users,
} from "lucide-react";

import { HiringAiFlow } from "../components/HiringAiFlow";
import {
  estimateInterviewCapacity,
  formatEstimatedKrw,
  INTERVIEW_CAPACITY_POLICY,
  MAX_GUARANTEED_INTERVIEW_CONCURRENCY,
} from "../interviewCapacityEstimate";
import {
  interviewLevelLabels,
  interviewerSystemPrompts,
  type HiringDraft,
  type HiringDraftUpdater,
  type InterviewLevel,
  type InterviewerTone,
} from "../types";

const MAX_MANDATORY_QUESTIONS = 3;

const mandatoryQuestionExamples = [
  "협업 과정에서 의견이 달랐을 때 어떻게 조율했나요?",
  "업무 스트레스가 높을 때 본인만의 관리·회복 방법은 무엇인가요?",
  "새로운 환경이나 업무를 빠르게 익혀야 했을 때 어떻게 접근했나요?",
] as const;

const adaptiveInterviewFlow = [
  {
    label: "기업 기준으로 구성",
    description:
      "필수·우대 자격요건과 반드시 물어볼 질문을 확인 순서에 넣습니다.",
  },
  {
    label: "지원자 자료와 연결",
    description:
      "이력서·포트폴리오·GitHub에서 관련 근거를 찾아 질문에 엮습니다.",
  },
  {
    label: "필요한 만큼만 꼬리질문",
    description: "답변의 본인 역할·판단 근거·결과가 부족할 때만 더 확인합니다.",
  },
] as const;

const interviewerOptions: ReadonlyArray<{
  level: InterviewLevel;
  name: string;
  role: string;
  voice: string;
  voiceId: string;
  tone: InterviewerTone;
  image: string;
  systemPrompt: string;
}> = [
  {
    level: "entry",
    name: "안내형 면접관",
    role: "기초와 성장 가능성 중심",
    voice: "한국어 남성 음성",
    voiceId: "Seoyeon",
    tone: "friendly",
    image: "/interviewers/entry_eyes_open_mouth_closed.webp",
    systemPrompt: interviewerSystemPrompts.entry,
  },
  {
    level: "junior",
    name: "실무형 면접관",
    role: "본인 기여와 판단 근거 중심",
    voice: "한국어 남성 음성",
    voiceId: "Seoyeon",
    tone: "analytical",
    image: "/interviewers/junior_eyes_open_mouth_closed.webp",
    systemPrompt: interviewerSystemPrompts.junior,
  },
  {
    level: "senior",
    name: "심층형 면접관",
    role: "설계·트레이드오프 중심",
    voice: "한국어 남성 음성",
    voiceId: "Seoyeon",
    tone: "concise",
    image: "/interviewers/senior_eyes_open_mouth_closed.webp",
    systemPrompt: interviewerSystemPrompts.senior,
  },
];

// `.interview-designer` is declared twice; the later `gap: 40px` beats the first `44px`.
const DESIGNER = "grid gap-10 mw-620:gap-8";

// `.interview-schedule`, `.interview-duration` and `.interviewer-picker` share one block; all
// but the schedule also match the rule below it, which adds the top border and padding.
const SECTION = "grid gap-[22px]";
const SECTION_DIVIDED = `${SECTION} border-t border-border pt-9`;

const SECTION_HEADER = "grid min-w-0 justify-items-start gap-0";
const SECTION_EYEBROW = "font-mono text-[12px] font-[650] text-brand";
const SECTION_TITLE = "mt-1 text-[26px] font-bold mw-620:text-[23px]";
const SECTION_TEXT =
  "mt-[5px] text-[14px] leading-[1.55] text-muted mw-620:text-[13px]";

const SCHEDULE_FIELDS =
  "grid gap-7 border-y border-border py-[18px]" +
  " grid-cols-[minmax(150px,0.7fr)_minmax(150px,0.7fr)_minmax(280px,1.35fr)]" +
  " mw-620:grid-cols-[minmax(0,1fr)]";
const SCHEDULE_LABEL_TEXT =
  "flex items-center gap-1.5 text-[10px] font-[650] text-ink-secondary";
// `.interview-schedule__fields input` puts the bottom border on the input, but inside this
// number+unit wrapper the border sits on the wrapper and `> div input` zeroes the input's.
const SCHEDULE_UNIT_BOX =
  "grid grid-cols-[minmax(0,1fr)_28px] items-center border-b border-border";
const SCHEDULE_INPUT =
  "min-h-[46px] w-full rounded-none border-0 bg-transparent p-0 text-[15px] text-ink";
const SCHEDULE_INPUT_BORDERED = `${SCHEDULE_INPUT} border-b border-b-border`;
// One rule styles both the `small` unit and the `p` note.
const SCHEDULE_NOTE = "text-[9px] leading-[1.45] text-subtle";
const CAPACITY_ESTIMATE =
  "col-[1/-1] grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3" +
  " rounded-lg border border-[color-mix(in_srgb,var(--color-link)_18%,var(--color-border))]" +
  " bg-[color-mix(in_srgb,var(--color-link)_4%,white)] px-4 py-3" +
  " mw-620:col-[1] mw-620:grid-cols-[auto_minmax(0,1fr)]";

const REQUIRED_QUESTION_PANEL =
  "overflow-hidden rounded-lg border border-brand/20 bg-brand-soft/25";
const QUESTION_EXAMPLE_BUTTON =
  "inline-flex min-h-7 items-center gap-1 rounded-md border border-brand/20 bg-white px-2" +
  " text-[8px] font-semibold text-brand hover:bg-brand-soft";
const PICKER_GRID =
  "grid grid-cols-[repeat(3,minmax(0,1fr))] gap-2.5 mw-620:grid-cols-[minmax(0,1fr)]";
const PICKER_SHELL =
  "relative min-h-[286px] min-w-0 [perspective:1200px] mw-620:min-h-[250px]";
const PICKER_CARD =
  "relative size-full min-h-[286px] [transform-style:preserve-3d]" +
  " [transition:transform_.55s_cubic-bezier(.2,.75,.25,1)] mw-620:min-h-[250px]";
const PICKER_OPTION =
  "group absolute inset-0 isolate min-h-[286px] min-w-0 overflow-hidden rounded-lg border" +
  " text-left text-white shadow-[0_8px_24px_#17203a14] outline-none" +
  " [backface-visibility:hidden]" +
  " [transition:border-color_.18s,transform_.18s,box-shadow_.18s]" +
  " focus-visible:[box-shadow:0_0_0_3px_#5966ce47] mw-620:min-h-[250px]";
const PICKER_OPTION_SELECTED =
  "border-brand [box-shadow:0_0_0_2px_var(--color-link),0_14px_30px_#17203a2b]" +
  " [transform:translateY(-3px)]";
const PICKER_OPTION_IDLE =
  "border-[#ffffff73] hover:border-[#ffffffcc] hover:[transform:translateY(-2px)]";
const PICKER_IMAGE =
  "absolute inset-0 z-0 h-full w-full object-cover object-center" +
  " [transition:transform_.35s_ease] group-hover:[transform:scale(1.025)]";
const PICKER_SHADE =
  "absolute inset-0 z-10 bg-[linear-gradient(180deg,rgba(12,18,31,0.04)_24%,rgba(12,18,31,0.24)_52%,rgba(12,18,31,0.94)_100%)]";
const PICKER_LEVEL =
  "absolute top-3 left-3 z-20 rounded-full border border-white/30 bg-black/25 px-2.5" +
  " py-1 font-mono text-[9px] font-bold text-white backdrop-blur-sm";
const PICKER_SELECTED =
  "absolute top-3 right-3 z-20 inline-flex items-center gap-1 rounded-full bg-brand px-2.5" +
  " py-1 text-[9px] font-semibold text-white shadow-md";
const PICKER_CONTENT =
  "absolute inset-x-0 bottom-0 z-20 grid gap-1 px-4 pb-4 pt-12";
const PICKER_BACK =
  "absolute inset-0 z-30 flex min-h-[286px] flex-col overflow-hidden rounded-lg border" +
  " border-brand/35 bg-white p-4 text-ink shadow-[0_14px_34px_#17203a20]" +
  " [backface-visibility:hidden] [transform:rotateY(180deg)] mw-620:min-h-[250px]";

export function InterviewDesigner({
  draft,
  update,
}: {
  draft: HiringDraft;
  update: HiringDraftUpdater;
}) {
  const [flippedLevel, setFlippedLevel] = useState<InterviewLevel | null>(null);
  const [promptEditorValue, setPromptEditorValue] = useState("");
  const [questionExamplesAnimating, setQuestionExamplesAnimating] =
    useState(false);
  const questionAnimationTimerRef = useRef<number | null>(null);
  const capacityEstimate = estimateInterviewCapacity(draft.interviewCapacity);
  const hasAdditionalCapacity =
    capacityEstimate.additionalApiTasks > 0 ||
    capacityEstimate.additionalWorkerTasks > 0;

  useEffect(
    () => () => {
      if (questionAnimationTimerRef.current !== null) {
        window.clearTimeout(questionAnimationTimerRef.current);
      }
    },
    [],
  );

  function applyInterviewer(
    option: (typeof interviewerOptions)[number],
    systemPrompt = option.systemPrompt,
  ) {
    update("interviewLevel", option.level);
    update("interviewerName", option.name);
    update("interviewerTone", option.tone);
    update("interviewerVoiceId", option.voiceId);
    update("interviewerSystemPrompt", systemPrompt.trim());
  }

  function openInterviewerPrompt(option: (typeof interviewerOptions)[number]) {
    setPromptEditorValue(
      draft.interviewLevel === option.level
        ? draft.interviewerSystemPrompt || option.systemPrompt
        : option.systemPrompt,
    );
    setFlippedLevel(option.level);
  }

  function updateMandatoryQuestion(index: number, value: string) {
    update(
      "mandatoryQuestions",
      draft.mandatoryQuestions.map((question, questionIndex) =>
        questionIndex === index ? value : question,
      ),
    );
  }

  function addMandatoryQuestion() {
    if (draft.mandatoryQuestions.length >= MAX_MANDATORY_QUESTIONS) return;
    update("mandatoryQuestions", [...draft.mandatoryQuestions, ""]);
  }

  function removeMandatoryQuestion(index: number) {
    update(
      "mandatoryQuestions",
      draft.mandatoryQuestions.filter(
        (_, questionIndex) => questionIndex !== index,
      ),
    );
  }

  function applyMandatoryQuestionExamples() {
    setQuestionExamplesAnimating(true);
    update("mandatoryQuestions", [...mandatoryQuestionExamples]);
    if (questionAnimationTimerRef.current !== null) {
      window.clearTimeout(questionAnimationTimerRef.current);
    }
    questionAnimationTimerRef.current = window.setTimeout(() => {
      setQuestionExamplesAnimating(false);
      questionAnimationTimerRef.current = null;
    }, 650);
  }

  return (
    <div className={DESIGNER}>
      <section className={SECTION} aria-labelledby="schedule-title">
        <header className={SECTION_HEADER}>
          <span className={SECTION_EYEBROW}>01 · 일정과 정원</span>
          <h3 className={SECTION_TITLE} id="schedule-title">
            채용과 면접 운영
          </h3>
          <p className={SECTION_TEXT}>
            최종 채용 목표와 동시에 진행할 면접 정원, 시작 시각을 지정합니다.
            면접은 최대 30분이며 자격요건과 필수 질문의 판단 근거를 모두
            확보하면 더 일찍 종료될 수 있습니다.
          </p>
        </header>
        <div className={SCHEDULE_FIELDS}>
          <label className="grid gap-2">
            <span className={SCHEDULE_LABEL_TEXT}>
              <Users aria-hidden="true" size={15} />
              채용 인원
            </span>
            <div className={SCHEDULE_UNIT_BOX}>
              <input
                aria-label="채용 인원"
                className={SCHEDULE_INPUT}
                max={MAX_GUARANTEED_INTERVIEW_CONCURRENCY}
                min={1}
                type="number"
                value={draft.headcount}
                onChange={(event) =>
                  update("headcount", Number(event.target.value))
                }
              />
              <small className={SCHEDULE_NOTE}>명</small>
            </div>
            <p className={SCHEDULE_NOTE}>
              이번 공고에서 최종 합격시킬 목표 인원
            </p>
          </label>
          <label className="grid gap-2">
            <span className={SCHEDULE_LABEL_TEXT}>
              <Users aria-hidden="true" size={15} />
              면접 정원
            </span>
            <div className={SCHEDULE_UNIT_BOX}>
              <input
                aria-label="면접 정원"
                className={SCHEDULE_INPUT}
                max={MAX_GUARANTEED_INTERVIEW_CONCURRENCY}
                min={1}
                type="number"
                value={draft.interviewCapacity}
                onChange={(event) =>
                  update("interviewCapacity", Number(event.target.value))
                }
              />
              <small className={SCHEDULE_NOTE}>명</small>
            </div>
            <p className={SCHEDULE_NOTE}>
              동시에 진행할 지원자 수 · 현재 예약 보장 한도 400명
            </p>
          </label>
          <label className="grid gap-2">
            <span className={SCHEDULE_LABEL_TEXT}>
              <CalendarClock aria-hidden="true" size={15} />
              면접 시각
            </span>
            <input
              aria-label="면접 시각"
              className={SCHEDULE_INPUT_BORDERED}
              required
              type="datetime-local"
              value={draft.interviewAt}
              onChange={(event) => update("interviewAt", event.target.value)}
            />
            <p className={SCHEDULE_NOTE}>
              예약된 시각을 기준으로 면접 실행 환경을 준비합니다.
            </p>
          </label>
          <aside
            aria-label="예약 오토스케일링 예상 비용"
            className={CAPACITY_ESTIMATE}
          >
            <span className="grid size-9 place-items-center rounded-full bg-brand-soft text-brand">
              <ServerCog aria-hidden="true" size={18} />
            </span>
            <div className="min-w-0">
              <strong className="text-[11px] text-ink">
                필요 최소 용량 · API {capacityEstimate.apiTasks}개 · Worker{" "}
                {capacityEstimate.workerTasks}개
              </strong>
              <p className="mt-0.5 text-[9px] leading-[1.5] text-muted">
                면접 정원 × 25% 여유 ÷ 태스크당{" "}
                {INTERVIEW_CAPACITY_POLICY.safeSessionsPerTask}명 · 기본 용량
                API {INTERVIEW_CAPACITY_POLICY.apiBaselineTasks}개, Worker{" "}
                {INTERVIEW_CAPACITY_POLICY.workerBaselineTasks}개 포함
              </p>
            </div>
            <span className="inline-flex items-center gap-1 whitespace-nowrap text-[10px] font-semibold text-brand mw-620:col-[1/-1] mw-620:ml-12">
              <Coins aria-hidden="true" size={14} />
              {hasAdditionalCapacity ? (
                <>
                  예약 증설 약{" "}
                  {formatEstimatedKrw(
                    capacityEstimate.estimatedIncrementalCostKrw,
                  )}
                  원/회
                </>
              ) : (
                <>추가 증설 없음 · 0원</>
              )}
            </span>
            <p className="col-[2/-1] text-[8px] leading-[1.5] text-subtle mw-620:col-[1/-1] mw-620:ml-12">
              {hasAdditionalCapacity
                ? `추가 증설 API +${capacityEstimate.additionalApiTasks}개 · Worker +${capacityEstimate.additionalWorkerTasks}개 · `
                : "기본 상시 용량으로 처리 · "}
              API는 시작 15분 전부터 종료 10분 후까지(
              {capacityEstimate.apiCapacityWindowMinutes}분), Worker는 종료 5분
              전부터 45분 후까지(
              {capacityEstimate.workerCapacityWindowMinutes}분) 확보합니다. 서울
              리전 1 vCPU·2GB, 1달러=1,400원 기준 추정치입니다.
            </p>
          </aside>
        </div>
      </section>

      <section
        className={SECTION_DIVIDED}
        aria-labelledby="required-question-title"
      >
        <header className={SECTION_HEADER}>
          <span className={SECTION_EYEBROW}>02 · 필수 질문</span>
          <h3 className={SECTION_TITLE} id="required-question-title">
            반드시 물어볼 질문
          </h3>
          <p className={SECTION_TEXT}>
            회사가 꼭 확인해야 하는 질문을 입력하면 AI 면접관이 모든 지원자에게
            직접 물어봅니다. 직무뿐 아니라 협업·업무 방식처럼 자유롭게 정할 수
            있습니다.
          </p>
        </header>
        <aside className={REQUIRED_QUESTION_PANEL}>
          <div className="flex items-start gap-3 border-b border-brand/15 px-4 py-3.5">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand text-white">
              <MessageSquareText aria-hidden="true" size={17} />
            </span>
            <p className="text-[10px] leading-[1.65] text-ink-secondary">
              앞에서 작성한 필수·우대 자격요건은 AI가 확인할 면접 주제가 되고,
              지원자의 제출 자료와 연결해 질문을 구성합니다.
              <br />
              아래 질문은 모든 지원자에게 반드시 묻고, 이후 답변에 필요한
              꼬리질문은 지원자마다 다르게 이어집니다.
            </p>
          </div>
          <div className="grid gap-2 bg-white px-4 py-4">
            <header className="flex items-center justify-between gap-3 pb-1">
              <span className="text-[8px] leading-[1.45] text-muted">
                협업, 업무 스트레스 관리, 학습 방식 등 회사가 궁금한 내용을
                자유롭게 입력하세요.
              </span>
              <button
                aria-label="필수 질문 예시 채우기"
                className={QUESTION_EXAMPLE_BUTTON}
                type="button"
                onClick={applyMandatoryQuestionExamples}
              >
                <Sparkles aria-hidden="true" size={11} />
                예시 채우기
              </button>
            </header>
            {draft.mandatoryQuestions.length ? (
              draft.mandatoryQuestions.map((question, index) => (
                <label
                  className={`grid grid-cols-[28px_minmax(0,1fr)_34px] items-center gap-2 rounded-md border border-border-muted bg-surface-muted px-2 py-1.5 ${
                    questionExamplesAnimating
                      ? "[animation:requirement-row-in_.42s_cubic-bezier(.2,.8,.2,1)_both] motion-reduce:animate-none"
                      : ""
                  }`}
                  key={`mandatory-question-${index}`}
                  style={
                    questionExamplesAnimating
                      ? { animationDelay: `${index * 90}ms` }
                      : undefined
                  }
                >
                  <span className="font-mono text-[9px] font-semibold text-brand">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <input
                    aria-label={`필수 질문 ${index + 1}`}
                    className="min-h-9 w-full bg-transparent text-[11px] text-ink outline-none placeholder:text-subtle"
                    maxLength={240}
                    placeholder="예: 이 역할에서 가장 먼저 개선하고 싶은 부분은 무엇인가요?"
                    value={question}
                    onChange={(event) =>
                      updateMandatoryQuestion(index, event.target.value)
                    }
                  />
                  <button
                    aria-label={`필수 질문 ${index + 1} 삭제`}
                    className="grid size-8 place-items-center rounded-md text-subtle hover:bg-danger-soft hover:text-danger"
                    type="button"
                    onClick={() => removeMandatoryQuestion(index)}
                  >
                    <Trash2 aria-hidden="true" size={14} />
                  </button>
                </label>
              ))
            ) : (
              <section
                className="grid gap-2 rounded-md border border-dashed border-brand/25 bg-brand-soft/20 p-3"
                aria-label="지원자별 적응형 면접 구성"
              >
                <header className="grid gap-0.5 text-center">
                  <strong className="text-[10px] text-ink">
                    정해진 3단계 대신 기업 기준과 지원자 근거로 진행합니다
                  </strong>
                  <span className="text-[8px] leading-[1.45] text-muted">
                    필수 질문이 없어도 자격요건을 중심으로 묻고, 답변에 따라
                    질문의 깊이와 꼬리질문을 유동적으로 조정합니다.
                  </span>
                </header>
                <ol className="grid grid-cols-3 gap-1.5 mw-620:grid-cols-1">
                  {adaptiveInterviewFlow.map((step, index) => (
                    <li
                      className="grid gap-1 rounded-md border border-border-muted bg-white px-2.5 py-2.5"
                      key={step.label}
                    >
                      <span className="font-mono text-[8px] font-semibold text-brand">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <strong className="text-[9px] text-ink">
                        {step.label}
                      </strong>
                      <small className="text-[8px] leading-[1.45] text-muted">
                        {step.description}
                      </small>
                    </li>
                  ))}
                </ol>
              </section>
            )}
            {draft.mandatoryQuestions.length < MAX_MANDATORY_QUESTIONS ? (
              <button
                className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-md border border-border bg-white text-[10px] font-semibold text-brand hover:bg-brand-soft"
                type="button"
                onClick={addMandatoryQuestion}
              >
                <Plus aria-hidden="true" size={13} />
                필수 질문 추가
              </button>
            ) : (
              <small className="text-right text-[8px] text-muted">
                필수 질문은 최대 {MAX_MANDATORY_QUESTIONS}개까지 설정할 수
                있습니다.
              </small>
            )}
          </div>
        </aside>
      </section>

      <section className={SECTION_DIVIDED} aria-labelledby="interviewer-title">
        <header className={SECTION_HEADER}>
          <span className={SECTION_EYEBROW}>03 · 면접관</span>
          <h3 className={SECTION_TITLE} id="interviewer-title">
            면접관의 질문 방식
          </h3>
          <p className={SECTION_TEXT}>
            카드를 눌러 실제 시스템 프롬프트를 확인하고 직접 수정할 수 있습니다.
            적용한 내용은 지원자 자료를 엮는 질문 방식과 꼬리질문에 반영됩니다.
          </p>
        </header>
        <select
          aria-label="면접 난이도"
          className="sr-only"
          value={draft.interviewLevel}
          onChange={(event) => {
            const option = interviewerOptions.find(
              (candidate) => candidate.level === event.target.value,
            );
            if (option) applyInterviewer(option);
          }}
        >
          {interviewerOptions.map((option) => (
            <option key={option.level} value={option.level}>
              {interviewLevelLabels[option.level].name}
            </option>
          ))}
        </select>
        <div className={PICKER_GRID}>
          {interviewerOptions.map((option) => {
            const selected = draft.interviewLevel === option.level;
            const flipped = flippedLevel === option.level;
            return (
              <article className={PICKER_SHELL} key={option.level}>
                <div
                  className={`${PICKER_CARD} ${flipped ? "[transform:rotateY(180deg)]" : ""}`}
                >
                  <button
                    aria-label={`${interviewLevelLabels[option.level].name} ${selected ? "선택됨 " : ""}${option.name} 시스템 프롬프트 보기`}
                    aria-pressed={selected}
                    className={`${PICKER_OPTION} ${
                      selected ? PICKER_OPTION_SELECTED : PICKER_OPTION_IDLE
                    }`}
                    type="button"
                    onClick={() => openInterviewerPrompt(option)}
                  >
                    <img
                      alt={`${interviewLevelLabels[option.level].name} AI 면접관`}
                      className={PICKER_IMAGE}
                      decoding="async"
                      src={option.image}
                    />
                    <span aria-hidden="true" className={PICKER_SHADE} />
                    <span className={PICKER_LEVEL}>
                      {interviewLevelLabels[option.level].name}
                    </span>
                    {selected ? (
                      <span className={PICKER_SELECTED}>
                        <Check aria-hidden="true" size={11} />
                        선택됨
                      </span>
                    ) : null}
                    <span className={PICKER_CONTENT}>
                      <strong className="text-[15px] text-white">
                        {option.name}
                      </strong>
                      <small className="text-[9px] leading-[1.45] text-white/75">
                        {option.role}
                      </small>
                      <span className="mt-2 flex items-center gap-1.5 border-t border-white/20 pt-2.5 text-[8px] text-white/65">
                        <Mic2 aria-hidden="true" size={12} />
                        {option.voice}
                      </span>
                    </span>
                  </button>
                  <section
                    aria-label={`${option.name} 시스템 프롬프트 편집`}
                    aria-hidden={!flipped}
                    className={PICKER_BACK}
                  >
                    <span className="font-mono text-[8px] font-semibold text-brand">
                      실제 질문 생성에 적용
                    </span>
                    <strong className="mt-1 text-[13px]">{option.name}</strong>
                    <label className="mt-3 grid min-h-0 flex-1 gap-1.5">
                      <span className="text-[9px] font-semibold text-ink-secondary">
                        면접관 시스템 프롬프트
                      </span>
                      <textarea
                        aria-label={`${option.name} 시스템 프롬프트`}
                        className="min-h-[116px] w-full resize-none rounded-md border border-border bg-surface-muted p-2.5 text-[9px] leading-[1.55] outline-none focus:border-brand"
                        maxLength={1000}
                        tabIndex={flipped ? 0 : -1}
                        value={
                          flipped ? promptEditorValue : option.systemPrompt
                        }
                        onChange={(event) =>
                          setPromptEditorValue(event.target.value)
                        }
                      />
                    </label>
                    <div className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-2">
                      <button
                        className="min-h-9 rounded-md border border-border px-3 text-[9px] font-semibold text-muted hover:bg-surface-muted"
                        tabIndex={flipped ? 0 : -1}
                        type="button"
                        onClick={() => setFlippedLevel(null)}
                      >
                        취소
                      </button>
                      <button
                        className="min-h-9 rounded-md bg-brand px-3 text-[9px] font-semibold text-white disabled:opacity-45"
                        disabled={!promptEditorValue.trim()}
                        tabIndex={flipped ? 0 : -1}
                        type="button"
                        onClick={() => {
                          applyInterviewer(option, promptEditorValue);
                          setFlippedLevel(null);
                        }}
                      >
                        이 면접관으로 적용
                      </button>
                    </div>
                  </section>
                </div>
              </article>
            );
          })}
        </div>
        <p className="-mt-2.5 text-center text-[9px] leading-[1.5] text-muted">
          {interviewLevelLabels[draft.interviewLevel].hint}
        </p>
      </section>

      <HiringAiFlow
        title="게시 후 지원자별 면접 흐름"
        description="자격요건·필수 질문·면접관 프롬프트를 한 평가 버전으로 고정한 뒤, 각 지원자의 제출 자료와 답변에 맞춰 질문과 꼬리질문을 구성합니다. 최대 30분 안에서 판단 근거가 충분해지면 면접을 자연스럽게 마칩니다."
        stages={[
          "기업 설정 버전 고정",
          "자료 기반 질문·꼬리질문",
          "자격요건 근거 리포트",
        ]}
      />
    </div>
  );
}
