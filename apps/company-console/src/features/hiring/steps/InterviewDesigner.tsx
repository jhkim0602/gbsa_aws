import {
  CalendarClock,
  Check,
  ChevronDown,
  Clock3,
  Coins,
  Info,
  Mic2,
  ServerCog,
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
  type HiringDraft,
  type HiringDraftUpdater,
  type InterviewLevel,
  type InterviewerTone,
} from "../types";

const interviewStages = [
  {
    name: "기술 면접",
    duration: 9,
    weight: 3,
    questionLimit: 6,
    description: "기술 선택과 문제 해결 과정",
  },
  {
    name: "프로젝트 심층",
    duration: 12,
    weight: 4,
    questionLimit: 8,
    description: "본인 역할과 설계·구현 근거",
  },
  {
    name: "협업·인성",
    duration: 9,
    weight: 3,
    questionLimit: 6,
    description: "협업 방식과 의사소통 경험",
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
}> = [
  {
    level: "entry",
    name: "안내형 면접관",
    role: "기초와 성장 가능성 중심",
    voice: "차분하고 친절한 TTS",
    voiceId: "Seoyeon",
    tone: "friendly",
    image: "/interviewers/entry_eyes_open_mouth_closed.webp",
  },
  {
    level: "junior",
    name: "실무형 면접관",
    role: "본인 기여와 판단 근거 중심",
    voice: "명료하고 균형 잡힌 TTS",
    voiceId: "Seoyeon",
    tone: "analytical",
    image: "/interviewers/junior_eyes_open_mouth_closed.webp",
  },
  {
    level: "senior",
    name: "심층형 면접관",
    role: "설계·트레이드오프 중심",
    voice: "낮고 신뢰감 있는 TTS",
    voiceId: "Seoyeon",
    tone: "concise",
    image: "/interviewers/senior_eyes_open_mouth_closed.webp",
  },
];

// `.interview-designer` is declared twice; the later `gap: 40px` beats the first `44px`.
const DESIGNER = "grid gap-10 mw-620:gap-8";

// `.interview-schedule`, `.interview-duration` and `.interviewer-picker` share one block; all
// but the schedule also match the rule below it, which adds the top border and padding.
const SECTION = "grid gap-[22px]";
const SECTION_DIVIDED = `${SECTION} border-t border-border pt-9`;

const SECTION_HEADER = "grid min-w-0 justify-items-start gap-0";
const SECTION_EYEBROW = "font-mono text-[9px] font-[650] text-brand";
const SECTION_TITLE = "mt-1 text-[17px] font-bold";
const SECTION_TEXT = "mt-[5px] text-[10px] leading-[1.5] text-muted";

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

const DURATION_NOTICE =
  "overflow-hidden rounded-lg border border-[color-mix(in_srgb,var(--color-brand)_20%,var(--color-border))]" +
  " bg-[color-mix(in_srgb,var(--color-brand)_3%,white)]";
const DURATION_TIMELINE =
  "grid grid-cols-[9fr_12fr_9fr] border-t border-[color-mix(in_srgb,var(--color-brand)_14%,var(--color-border))]" +
  " mw-620:grid-cols-[minmax(0,1fr)]";
const DURATION_STAGE =
  "relative grid min-h-[92px] content-center gap-1 px-4 py-3" +
  " not-last:border-r not-last:border-[color-mix(in_srgb,var(--color-brand)_14%,var(--color-border))]" +
  " mw-620:min-h-0 mw-620:grid-cols-[36px_minmax(0,1fr)_auto] mw-620:items-center" +
  " mw-620:not-last:border-r-0 mw-620:not-last:border-b";
const DURATION_EXPLANATION =
  "group border-t border-[color-mix(in_srgb,var(--color-brand)_14%,var(--color-border))] bg-white";
const DURATION_EXPLANATION_SUMMARY =
  "flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3" +
  " text-[10px] font-semibold text-ink-secondary outline-none" +
  " hover:bg-brand-soft/40 focus-visible:bg-brand-soft/55" +
  " [&::-webkit-details-marker]:hidden";
const PICKER_GRID =
  "grid grid-cols-[repeat(3,minmax(0,1fr))] gap-2.5 mw-620:grid-cols-[minmax(0,1fr)]";
const PICKER_OPTION =
  "group relative isolate min-h-[286px] min-w-0 overflow-hidden rounded-lg border" +
  " text-left text-white shadow-[0_8px_24px_#17203a14] outline-none" +
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

export function InterviewDesigner({
  draft,
  update,
}: {
  draft: HiringDraft;
  update: HiringDraftUpdater;
}) {
  const capacityEstimate = estimateInterviewCapacity(draft.interviewCapacity);
  const hasAdditionalCapacity =
    capacityEstimate.additionalApiTasks > 0 ||
    capacityEstimate.additionalWorkerTasks > 0;

  function selectInterviewer(option: (typeof interviewerOptions)[number]) {
    update("interviewLevel", option.level);
    update("interviewerName", option.name);
    update("interviewerTone", option.tone);
    update("interviewerVoiceId", option.voiceId);
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

      <section className={SECTION_DIVIDED} aria-labelledby="duration-title">
        <header className={SECTION_HEADER}>
          <span className={SECTION_EYEBROW}>02 · 진행 시간</span>
          <h3 className={SECTION_TITLE} id="duration-title">
            면접 시간 안내
          </h3>
          <p className={SECTION_TEXT}>
            총 진행 시간과 단계별 시간 배분을 확인하세요.
          </p>
        </header>
        <aside className={DURATION_NOTICE} aria-label="30분 고정 면접 안내">
          <div className="flex items-start gap-3 px-4 py-4 mw-620:flex-wrap">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand text-white">
              <Clock3 aria-hidden="true" size={18} />
            </span>
            <div className="min-w-0 flex-1">
              <strong className="text-[13px] text-ink">
                모든 면접은 30분을 기준으로 진행됩니다
              </strong>
              <p className="mt-1 text-[9px] leading-[1.55] text-muted">
                지원자별로 시간을 따로 설정하지 않으며, 아래 3단계에 동일한 시간
                배분 기준을 적용합니다.
              </p>
            </div>
            <span className="rounded-full border border-brand/20 bg-brand-soft px-2.5 py-1 text-[9px] font-semibold text-brand">
              기본 30분
            </span>
          </div>
          <div className="flex items-center justify-between border-t border-[color-mix(in_srgb,var(--color-brand)_14%,var(--color-border))] bg-white/70 px-4 py-2">
            <strong className="text-[9px] text-ink-secondary">
              단계별 시간 배분
            </strong>
            <span className="font-mono text-[9px] font-semibold text-brand">
              9분 · 12분 · 9분 = 총 30분
            </span>
          </div>
          <ol className={DURATION_TIMELINE} aria-label="면접 단계별 시간">
            {interviewStages.map((stage, index) => (
              <li className={DURATION_STAGE} key={stage.name}>
                <span className="font-mono text-[9px] font-semibold text-brand">
                  0{index + 1}
                </span>
                <strong className="text-[12px] text-ink">
                  {index + 1}. {stage.name} · {stage.duration}분
                </strong>
                <small className="text-[8px] leading-[1.45] text-muted mw-620:col-[2]">
                  {stage.description}
                </small>
                <span
                  aria-hidden="true"
                  className="absolute inset-x-0 bottom-0 h-0.5 bg-brand/75"
                />
              </li>
            ))}
          </ol>
          <details className={DURATION_EXPLANATION}>
            <summary className={DURATION_EXPLANATION_SUMMARY}>
              <span className="inline-flex items-center gap-2">
                <Info aria-hidden="true" size={14} className="text-brand" />
                시간 배분은 어떻게 동작하나요?
              </span>
              <ChevronDown
                aria-hidden="true"
                className="shrink-0 text-muted transition-transform group-open:rotate-180"
                size={15}
              />
            </summary>
            <div className="grid gap-3 border-t border-border-muted bg-[color-mix(in_srgb,var(--color-brand)_2%,white)] px-4 py-4">
              <p className="text-[9px] leading-[1.6] text-ink-secondary">
                전체 30분을 <strong className="text-ink">3:4:3</strong>으로
                나눕니다. 질문 하나당 약 90초를 기준으로 단계별 질문 수를 제한해
                한 영역에 면접 시간이 몰리지 않도록 합니다.
              </p>
              <dl className="grid grid-cols-3 gap-2 mw-620:grid-cols-1">
                {interviewStages.map((stage) => (
                  <div
                    className="grid gap-1 rounded-md border border-border-muted bg-white px-3 py-2.5"
                    key={stage.name}
                  >
                    <dt className="text-[9px] font-semibold text-ink">
                      {stage.name}
                    </dt>
                    <dd className="font-mono text-[9px] text-brand">
                      가중치 {stage.weight}/10 → {stage.duration}분
                    </dd>
                    <dd className="text-[8px] text-muted">
                      질문 최대 {stage.questionLimit}개
                    </dd>
                  </div>
                ))}
              </dl>
              <p className="flex items-start gap-2 rounded-md bg-warning-soft px-3 py-2.5 text-[8px] leading-[1.55] text-warning">
                <span aria-hidden="true">※</span>
                <span>
                  단계 시간은 답변을 강제로 끊는 시간이 아니라 진행 기준입니다.
                  답변 중 기준 시간이 지나면 답변을 마친 뒤 다음 단계로
                  이동하므로 실제 종료 시각은 조금 달라질 수 있습니다.
                </span>
              </p>
            </div>
          </details>
        </aside>
      </section>

      <section className={SECTION_DIVIDED} aria-labelledby="interviewer-title">
        <header className={SECTION_HEADER}>
          <span className={SECTION_EYEBROW}>03 · 면접관</span>
          <h3 className={SECTION_TITLE} id="interviewer-title">
            면접관과 난이도
          </h3>
          <p className={SECTION_TEXT}>
            난이도에 따라 질문 깊이와 꼬리질문 횟수가 달라집니다. 선택한 음성
            프리셋도 면접 설정에 함께 저장됩니다.
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
            if (option) selectInterviewer(option);
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
            return (
              <button
                aria-pressed={selected}
                className={`${PICKER_OPTION} ${
                  selected ? PICKER_OPTION_SELECTED : PICKER_OPTION_IDLE
                }`}
                key={option.level}
                type="button"
                onClick={() => selectInterviewer(option)}
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
                    {option.voice} · {option.voiceId}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
        <p className="-mt-2.5 text-center text-[9px] leading-[1.5] text-muted">
          {interviewLevelLabels[draft.interviewLevel].hint}
        </p>
      </section>

      <HiringAiFlow
        title="게시 후 면접 실행 흐름"
        description="예약 정보와 선택한 면접관 프리셋을 기준으로 질문 정책을 고정하고, 모든 지원자에게 동일한 평가 버전을 적용합니다."
        stages={["실행 환경 예약", "AI 질문·TTS", "근거 리포트"]}
      />
    </div>
  );
}
