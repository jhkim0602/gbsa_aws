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

export function InterviewDesigner({
  draft,
  update,
}: {
  draft: HiringDraft;
  update: HiringDraftUpdater;
}) {
  return (
    <div className="interview-designer">
      <section className="interview-schedule" aria-labelledby="schedule-title">
        <header>
          <span>01 · 일정과 정원</span>
          <h3 id="schedule-title">채용과 면접 운영</h3>
          <p>
            최종 채용 목표와 동시에 진행할 면접 정원, 시작 시각을 지정합니다.
          </p>
        </header>
        <div className="interview-schedule__fields">
          <label>
            <span>
              <Users aria-hidden="true" size={15} />
              채용 인원
            </span>
            <div>
              <input
                aria-label="채용 인원"
                max={10000}
                min={1}
                type="number"
                value={draft.headcount}
                onChange={(event) =>
                  update("headcount", Number(event.target.value))
                }
              />
              <small>명</small>
            </div>
            <p>이번 공고에서 최종 합격시킬 목표 인원</p>
          </label>
          <label>
            <span>
              <Users aria-hidden="true" size={15} />
              면접 정원
            </span>
            <div>
              <input
                aria-label="면접 정원"
                max={10000}
                min={1}
                type="number"
                value={draft.interviewCapacity}
                onChange={(event) =>
                  update("interviewCapacity", Number(event.target.value))
                }
              />
              <small>명</small>
            </div>
            <p>동시에 시험을 진행할 수 있는 지원자 수</p>
          </label>
          <label>
            <span>
              <CalendarClock aria-hidden="true" size={15} />
              면접 시각
            </span>
            <input
              aria-label="면접 시각"
              required
              type="datetime-local"
              value={draft.interviewAt}
              onChange={(event) => update("interviewAt", event.target.value)}
            />
            <p>예약된 시각을 기준으로 면접 실행 환경을 준비합니다.</p>
          </label>
        </div>
      </section>

      <section className="interview-duration" aria-labelledby="duration-title">
        <header>
          <span>02 · 진행 시간</span>
          <h3 id="duration-title">면접 시간</h3>
          <p>평가기준 수와 질문 깊이에 맞는 시간을 선택합니다.</p>
        </header>
        <fieldset>
          <legend className="sr-only">면접 시간 선택</legend>
          {durationOptions.map((duration) => (
            <button
              className={
                draft.interviewDurationMinutes === duration ? "is-active" : ""
              }
              key={duration}
              type="button"
              onClick={() => update("interviewDurationMinutes", duration)}
            >
              <Clock3 aria-hidden="true" size={17} />
              <strong>{duration}분</strong>
              <small>
                {duration === 10
                  ? "핵심 확인"
                  : duration === 20
                    ? "표준 면접"
                    : "심층 검증"}
              </small>
            </button>
          ))}
          <label className="interview-duration__custom">
            <span>직접 입력</span>
            <input
              aria-label="면접 시간(분)"
              max={120}
              min={10}
              type="number"
              value={draft.interviewDurationMinutes}
              onChange={(event) =>
                update("interviewDurationMinutes", Number(event.target.value))
              }
            />
            <small>분</small>
          </label>
        </fieldset>
      </section>

      <section
        className="interviewer-picker"
        aria-labelledby="interviewer-title"
      >
        <header>
          <span>03 · 면접관</span>
          <h3 id="interviewer-title">면접관과 난이도</h3>
          <p>
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
        <div className="interviewer-picker__grid">
          {interviewerOptions.map((option) => {
            const selected = draft.interviewLevel === option.level;
            return (
              <button
                aria-pressed={selected}
                className={selected ? "is-selected" : ""}
                key={option.level}
                type="button"
                onClick={() => update("interviewLevel", option.level)}
              >
                <span className="interviewer-picker__visual">
                  <img alt="" src={option.image} />
                  {selected ? (
                    <i>
                      <Check aria-hidden="true" size={13} />
                    </i>
                  ) : null}
                </span>
                <span className="interviewer-picker__level">
                  {interviewLevelLabels[option.level].name}
                </span>
                <strong>{option.name}</strong>
                <small>{option.role}</small>
                <span className="interviewer-picker__voice">
                  <Mic2 aria-hidden="true" size={12} />
                  {option.voice}
                </span>
              </button>
            );
          })}
        </div>
        <p className="interviewer-picker__hint">
          {interviewLevelLabels[draft.interviewLevel].hint}
        </p>
      </section>

      <details className="interview-policy">
        <summary>
          <span>
            <LockKeyhole aria-hidden="true" size={14} />
            내부 면접 정책
          </span>
          <small>지원자에게 노출되지 않음</small>
          <ChevronDown aria-hidden="true" size={15} />
        </summary>
        <div>
          <label>
            <span>금지 주제</span>
            <input
              aria-label="금지 주제"
              required
              value={draft.prohibitedTopics}
              onChange={(event) =>
                update("prohibitedTopics", event.target.value)
              }
            />
          </label>
          <p>
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
