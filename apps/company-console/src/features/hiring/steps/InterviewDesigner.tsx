import {
  CalendarClock,
  Check,
  ChevronDown,
  Clock3,
  LockKeyhole,
  Mic2,
  Users,
} from "lucide-react";

import { HiringAiFlow } from "../components/HiringAiFlow";
import {
  interviewLevelLabels,
  type HiringDraft,
  type HiringDraftUpdater,
  type InterviewLevel,
} from "../types";

const durationOptions = [10, 20, 30] as const;

// Keep these slots stable when final interviewer portraits and TTS presets arrive.
const interviewerOptions: ReadonlyArray<{
  level: InterviewLevel;
  name: string;
  role: string;
  voice: string;
  image: string;
}> = [
  {
    level: "entry",
    name: "안내형 면접관",
    role: "기초와 성장 가능성 중심",
    voice: "차분하고 친절한 TTS",
    image: "/role-category-selector/role-details/role-detail-common.png",
  },
  {
    level: "junior",
    name: "실무형 면접관",
    role: "본인 기여와 판단 근거 중심",
    voice: "명료하고 균형 잡힌 TTS",
    image: "/role-category-selector/role-details/role-detail-service.png",
  },
  {
    level: "senior",
    name: "심층형 면접관",
    role: "설계·트레이드오프 중심",
    voice: "낮고 신뢰감 있는 TTS",
    image: "/role-category-selector/role-details/role-detail-platform.png",
  },
];

// `.interview-designer` is declared twice; the later `gap: 40px` beats the first `44px`.
const DESIGNER = "grid gap-10 mw-620:gap-8";

// `.interview-schedule`, `.interview-duration` and `.interviewer-picker` share one block; all
// but the schedule also match the rule below it, which adds the top border and padding.
const SECTION = "grid gap-[22px]";
const SECTION_DIVIDED = `${SECTION} border-t border-border pt-9`;

// Two rules target `> header`, so `min-width: 0` merges into the flex row.
const SECTION_HEADER = "flex min-w-0 items-start justify-between gap-6";
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

const DURATION_GRID =
  "grid gap-2 grid-cols-[repeat(3,minmax(0,1fr))_minmax(130px,0.8fr)]" +
  " mw-780:grid-cols-[repeat(3,minmax(0,1fr))] mw-620:grid-cols-[minmax(0,1fr)]";
const DURATION_OPTION =
  "grid min-h-[82px] grid-cols-[24px_minmax(0,1fr)] grid-rows-[auto_auto] content-center" +
  " gap-x-[9px] gap-y-0.5 rounded-[5px] border bg-white px-[14px] py-3 text-left" +
  " [&>svg]:row-[1/3] [&>svg]:self-center";
// `box-shadow` as a utility would need the whole `--tw-shadow` chain; the source declares the
// shorthand, and `text-brand` has to follow the base `text-muted`, which it does here.
const DURATION_OPTION_ACTIVE =
  "border-brand bg-[#5966ce0d] text-brand [box-shadow:inset_0_-3px_var(--color-link)]";
const DURATION_CUSTOM =
  "grid grid-cols-[minmax(0,1fr)_auto] content-center border-b border-border px-[14px] py-3" +
  " mw-780:col-[1/-1] mw-620:col-auto";

const PICKER_GRID =
  "grid grid-cols-[repeat(3,minmax(0,1fr))] gap-2.5 mw-620:grid-cols-[minmax(0,1fr)]";
// `transition` is the arbitrary property, not `transition-[…]` + `duration-[140ms]`: the
// utility pair also injects Tailwind's `cubic-bezier(.4,0,.2,1)`, where the source uses `ease`.
const PICKER_OPTION =
  "grid min-w-0 justify-items-center gap-[5px] rounded-md border bg-white px-3 pt-[14px]" +
  " pb-[13px] text-center text-muted [transition:border-color_.14s,transform_.14s]" +
  " mw-620:grid-cols-[90px_minmax(0,1fr)] mw-620:justify-items-start mw-620:text-left";
// `.is-selected` and `:hover` are both (0,2,1) and the selected rule is declared later, so a
// selected option keeps its own border and lift — hover only applies while unselected.
// `translate-y` is avoided for the same reason as above: it animates `translate`, not
// `transform`, so the source's `transition: transform` would not pick it up.
const PICKER_OPTION_SELECTED =
  "border-brand bg-[#5966ce0a] [box-shadow:inset_0_-3px_var(--color-link)]";
const PICKER_OPTION_IDLE =
  "border-border hover:border-ink-secondary hover:[transform:translateY(-1px)]";
const PICKER_VISUAL =
  "relative mb-[5px] grid size-28 place-items-center overflow-hidden border-b" +
  " border-b-border-muted mw-620:row-[1/6] mw-620:h-[94px] mw-620:w-21";

const POLICY_SUMMARY =
  "grid min-h-[50px] cursor-pointer list-none grid-cols-[minmax(0,1fr)_auto_18px]" +
  " items-center gap-3 [&::-webkit-details-marker]:hidden" +
  " [&>svg:last-child]:[transition:transform_.14s]";

export function InterviewDesigner({
  draft,
  update,
}: {
  draft: HiringDraft;
  update: HiringDraftUpdater;
}) {
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
                max={10000}
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
                max={10000}
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
              동시에 시험을 진행할 수 있는 지원자 수
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

      <section className={SECTION_DIVIDED} aria-labelledby="duration-title">
        <header className={SECTION_HEADER}>
          <span className={SECTION_EYEBROW}>02 · 진행 시간</span>
          <h3 className={SECTION_TITLE} id="duration-title">
            면접 시간
          </h3>
          <p className={SECTION_TEXT}>
            평가기준 수와 질문 깊이에 맞는 시간을 선택합니다.
          </p>
        </header>
        <fieldset className={DURATION_GRID}>
          <legend className="sr-only">면접 시간 선택</legend>
          {durationOptions.map((duration) => (
            <button
              className={`${DURATION_OPTION} ${
                draft.interviewDurationMinutes === duration
                  ? DURATION_OPTION_ACTIVE
                  : "border-border"
              }`}
              key={duration}
              type="button"
              onClick={() => update("interviewDurationMinutes", duration)}
            >
              <Clock3 aria-hidden="true" size={17} />
              <strong className="text-[13px] text-ink">{duration}분</strong>
              <small className="text-[9px]">
                {duration === 10
                  ? "핵심 확인"
                  : duration === 20
                    ? "표준 면접"
                    : "심층 검증"}
              </small>
            </button>
          ))}
          <label className={DURATION_CUSTOM}>
            <span className="col-[1/-1] text-[9px] text-muted">직접 입력</span>
            <input
              aria-label="면접 시간(분)"
              className="h-[34px] w-full min-w-0 border-0 bg-transparent p-0 text-[13px] text-ink"
              max={120}
              min={10}
              type="number"
              value={draft.interviewDurationMinutes}
              onChange={(event) =>
                update("interviewDurationMinutes", Number(event.target.value))
              }
            />
            <small className="self-center text-[9px] text-muted">분</small>
          </label>
        </fieldset>
      </section>

      <section className={SECTION_DIVIDED} aria-labelledby="interviewer-title">
        <header className={SECTION_HEADER}>
          <span className={SECTION_EYEBROW}>03 · 면접관</span>
          <h3 className={SECTION_TITLE} id="interviewer-title">
            면접관과 난이도
          </h3>
          <p className={SECTION_TEXT}>
            난이도에 따라 질문 깊이와 꼬리질문 횟수가 달라집니다. 음성 프리셋은
            TTS 연결을 위해 예약됩니다.
          </p>
        </header>
        <select
          aria-label="면접 난이도"
          className="sr-only"
          value={draft.interviewLevel}
          onChange={(event) =>
            update("interviewLevel", event.target.value as InterviewLevel)
          }
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
                onClick={() => update("interviewLevel", option.level)}
              >
                <span className={PICKER_VISUAL}>
                  <img
                    alt=""
                    className="size-23 object-contain mw-620:size-19"
                    src={option.image}
                  />
                  {selected ? (
                    <i className="absolute right-1 bottom-[7px] grid size-[22px] place-items-center rounded-[50%] bg-brand text-white">
                      <Check aria-hidden="true" size={13} />
                    </i>
                  ) : null}
                </span>
                <span className="font-mono text-[9px] font-bold text-brand">
                  {interviewLevelLabels[option.level].name}
                </span>
                <strong className="text-[13px] text-ink">{option.name}</strong>
                <small className="min-h-7 text-[9px] leading-[1.45]">
                  {option.role}
                </small>
                <span className="mt-1.5 flex items-center gap-[5px] border-t border-t-border-muted pt-2 text-[8px] text-muted mw-620:w-full">
                  <Mic2 aria-hidden="true" size={12} />
                  {option.voice}
                </span>
              </button>
            );
          })}
        </div>
        <p className="-mt-2.5 text-center text-[9px] leading-[1.5] text-muted">
          {interviewLevelLabels[draft.interviewLevel].hint}
        </p>
      </section>

      {/* Two rules give `.interview-policy` a top border with `padding-top` and a bottom one. */}
      <details className="border-y border-border pt-9 open:[&>summary_svg:last-child]:[transform:rotate(180deg)]">
        <summary className={POLICY_SUMMARY}>
          <span className="flex items-center gap-[7px] text-[10px] font-[650] text-ink-secondary">
            <LockKeyhole aria-hidden="true" size={14} />
            내부 면접 정책
          </span>
          <small className="text-[8px] text-subtle">
            지원자에게 노출되지 않음
          </small>
          <ChevronDown aria-hidden="true" size={15} />
        </summary>
        <div className="grid gap-2 pb-4 pl-[22px]">
          <label className="grid gap-[5px]">
            <span className="text-[9px] text-muted">금지 주제</span>
            <input
              aria-label="금지 주제"
              className="min-h-9 border-0 border-b border-b-border bg-transparent p-0 text-[11px] text-ink"
              required
              value={draft.prohibitedTopics}
              onChange={(event) =>
                update("prohibitedTopics", event.target.value)
              }
            />
          </label>
          <p className="text-[8px] leading-[1.5] text-subtle">
            질문 생성과 실시간 꼬리질문 필터에만 사용하며 지원자 화면과
            리포트에는 표시하지 않습니다.
          </p>
        </div>
      </details>

      <HiringAiFlow
        title="게시 후 면접 실행 흐름"
        description="예약 정보와 선택한 면접관 프리셋을 기준으로 질문 정책을 고정하고, 모든 지원자에게 동일한 평가 버전을 적용합니다."
        stages={["실행 환경 예약", "AI 질문·TTS", "근거 리포트"]}
      />
    </div>
  );
}
