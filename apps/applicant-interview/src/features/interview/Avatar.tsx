export type InterviewerLevel = "entry" | "junior" | "senior";

export const INTERVIEWER_LEVELS: Readonly<
  Record<
    InterviewerLevel,
    {
      label: string;
      shortLabel: string;
      description: string;
    }
  >
> = {
  entry: {
    label: "신입",
    shortLabel: "Entry",
    description: "기초 역량과 성장 가능성을 중심으로 질문합니다.",
  },
  junior: {
    label: "주니어",
    shortLabel: "Junior",
    description: "실무 경험과 문제 해결 과정을 중심으로 질문합니다.",
  },
  senior: {
    label: "시니어",
    shortLabel: "Senior",
    description: "기술 리더십과 복잡한 의사결정을 중심으로 질문합니다.",
  },
};

export function Avatar({
  textOnly,
  speaking,
  speechMarkIndex,
  level = "entry",
  className = "",
}: {
  textOnly: boolean;
  speaking: boolean;
  speechMarkIndex: number;
  level?: InterviewerLevel;
  className?: string;
}) {
  if (textOnly) {
    return (
      <div
        className={`grid h-full min-h-56 place-items-center bg-slate-100 px-6 text-center text-sm text-slate-500 ${className}`}
        role="status"
      >
        음성 없이 질문을 표시합니다.
      </div>
    );
  }

  const levelInfo = INTERVIEWER_LEVELS[level];

  /*
   * TODO: TTS가 phoneme/viseme 타임라인을 제공하면 아래 6개 프레임을
   * speechMarkIndex에 매핑한다.
   * eyes_open/closed x mouth_closed/mid/open = 총 6단계.
   * 현재는 안정적인 기본 표정(open + closed) 한 장만 표시한다.
   */
  const imageSource = `/interviewers/${level}_eyes_open_mouth_closed.webp`;

  return (
    <figure
      className={`relative m-0 h-full min-h-0 overflow-hidden bg-slate-200 ${className}`}
      aria-label={speaking ? "AI 면접관 발화 중" : "AI 면접관 대기 중"}
      data-speech-mark={speechMarkIndex}
      data-level={level}
    >
      <img
        className="h-full w-full object-cover object-center"
        src={imageSource}
        alt={`${levelInfo.label} AI 면접관`}
        decoding="async"
      />
      <figcaption className="sr-only">
        {speaking ? "질문을 읽고 있습니다" : "다음 응답을 기다립니다"}
      </figcaption>
    </figure>
  );
}
