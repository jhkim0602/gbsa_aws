import { useEffect, useState } from "react";

export type InterviewerLevel = "entry" | "junior" | "senior";

type EyeState = "open" | "closed";
type MouthState = "closed" | "mid" | "open";

const MOUTH_SEQUENCE: readonly MouthState[] = [
  "mid",
  "open",
  "mid",
  "closed",
  "mid",
  "open",
];
const MOUTH_FRAME_DURATION_MS = 140;
const BLINK_DURATION_MS = 140;
const BLINK_DELAYS_MS = [3200, 4700, 3800] as const;

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
  const [eyes, setEyes] = useState<EyeState>("open");
  const [mouth, setMouth] = useState<MouthState>("closed");

  useEffect(() => {
    if (textOnly) {
      setEyes("open");
      return undefined;
    }

    let blinkDelayIndex = 0;
    let blinkTimer: number | undefined;
    let reopenTimer: number | undefined;

    const scheduleBlink = () => {
      blinkTimer = window.setTimeout(() => {
        setEyes("closed");
        reopenTimer = window.setTimeout(() => {
          setEyes("open");
          blinkDelayIndex = (blinkDelayIndex + 1) % BLINK_DELAYS_MS.length;
          scheduleBlink();
        }, BLINK_DURATION_MS);
      }, BLINK_DELAYS_MS[blinkDelayIndex]);
    };

    scheduleBlink();
    return () => {
      if (blinkTimer !== undefined) window.clearTimeout(blinkTimer);
      if (reopenTimer !== undefined) window.clearTimeout(reopenTimer);
    };
  }, [textOnly]);

  useEffect(() => {
    if (textOnly || !speaking) {
      setMouth("closed");
      return undefined;
    }

    let sequenceIndex =
      ((speechMarkIndex % MOUTH_SEQUENCE.length) + MOUTH_SEQUENCE.length) %
      MOUTH_SEQUENCE.length;
    setMouth(MOUTH_SEQUENCE[sequenceIndex]);

    const mouthTimer = window.setInterval(() => {
      sequenceIndex = (sequenceIndex + 1) % MOUTH_SEQUENCE.length;
      setMouth(MOUTH_SEQUENCE[sequenceIndex]);
    }, MOUTH_FRAME_DURATION_MS);

    return () => window.clearInterval(mouthTimer);
  }, [speaking, speechMarkIndex, textOnly]);

  useEffect(() => {
    if (typeof Image === "undefined") return;
    for (const eyeState of ["open", "closed"] as const) {
      for (const mouthState of ["closed", "mid", "open"] as const) {
        const image = new Image();
        image.src = `/interviewers/${level}_eyes_${eyeState}_mouth_${mouthState}.webp`;
      }
    }
  }, [level]);

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
  const imageSource = `/interviewers/${level}_eyes_${eyes}_mouth_${mouth}.webp`;

  return (
    <figure
      className={`relative m-0 h-full min-h-0 overflow-hidden bg-slate-200 ${className}`}
      aria-label={speaking ? "AI 면접관 발화 중" : "AI 면접관 대기 중"}
      data-speech-mark={speechMarkIndex}
      data-level={level}
      data-eyes={eyes}
      data-mouth={mouth}
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
