import { CalendarClock, Check, Mic2, Users } from "lucide-react";

import { HiringAiFlow } from "../components/HiringAiFlow";
import { MAX_GUARANTEED_INTERVIEW_CONCURRENCY } from "../interviewCapacityEstimate";
import {
  interviewLevelLabels,
  type HiringDraft,
  type HiringDraftUpdater,
  type InterviewLevel,
  type InterviewerTone,
} from "../types";

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
    name: "신입 면접관",
    role: "기초와 성장 가능성 중심",
    voice: "한국어 남성 음성",
    voiceId: "Seoyeon",
    tone: "friendly",
    image: "/interviewers/entry_eyes_open_mouth_closed.webp",
  },
  {
    level: "junior",
    name: "주니어 면접관",
    role: "본인 기여와 판단 근거 중심",
    voice: "한국어 남성 음성",
    voiceId: "Seoyeon",
    tone: "analytical",
    image: "/interviewers/junior_eyes_open_mouth_closed.webp",
  },
  {
    level: "senior",
    name: "시니어 면접관",
    role: "설계·트레이드오프 중심",
    voice: "한국어 남성 음성",
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
        </div>
      </section>

      <section className={SECTION_DIVIDED} aria-labelledby="interviewer-title">
        <header className={SECTION_HEADER}>
          <span className={SECTION_EYEBROW}>02 · 면접관</span>
          <h3 className={SECTION_TITLE} id="interviewer-title">
            면접관과 난이도
          </h3>
          <p className={SECTION_TEXT}>
            난이도에 따라 질문 깊이와 확인 관점만 달라집니다. 꼬리질문은
            난이도와 무관하게 답변 근거가 부족할 때 진행됩니다.
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
                    {option.voice}
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
