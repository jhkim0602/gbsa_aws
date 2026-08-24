import { useEffect, useId, useState } from "react";

export type InterviewerLevel = "entry" | "junior" | "senior";

type EyeState = "open" | "closed";
type MouthState = "closed" | "mid" | "open";

const MOUTH_SEQUENCE: readonly MouthState[] = [
  "mid",
  "mid",
  "closed",
  "mid",
  "mid",
  "open",
  "mid",
  "closed",
];
const MOUTH_FRAME_DURATION_MS = 180;
const MOUTH_CROSSFADE_MS = 110;
const MID_MOUTH_OPACITY = 0.88;
const OPEN_MOUTH_OPACITY = 0.72;
const BLINK_DURATION_MS = 140;
const BLINK_DELAYS_MS = [3200, 4700, 3800] as const;
const AVATAR_WIDTH = 1536;
const AVATAR_HEIGHT = 1024;

type MaskArea = {
  centerX: number;
  centerY: number;
  radiusX: number;
  radiusY: number;
};

type MaskGroup = {
  areas: readonly MaskArea[];
  blur: number;
};

const FACE_MASKS: Readonly<
  Record<InterviewerLevel, { eyes: MaskGroup; mouth: MaskGroup }>
> = {
  entry: {
    eyes: {
      areas: [
        { centerX: 704, centerY: 312, radiusX: 60, radiusY: 30 },
        { centerX: 832, centerY: 312, radiusX: 60, radiusY: 30 },
      ],
      blur: 8,
    },
    mouth: {
      areas: [{ centerX: 768, centerY: 462, radiusX: 82, radiusY: 34 }],
      blur: 5,
    },
  },
  junior: {
    eyes: {
      areas: [
        { centerX: 704, centerY: 306, radiusX: 61, radiusY: 31 },
        { centerX: 832, centerY: 306, radiusX: 61, radiusY: 31 },
      ],
      blur: 8,
    },
    mouth: {
      areas: [{ centerX: 768, centerY: 468, radiusX: 86, radiusY: 35 }],
      blur: 5,
    },
  },
  senior: {
    eyes: {
      areas: [
        { centerX: 704, centerY: 326, radiusX: 62, radiusY: 32 },
        { centerX: 832, centerY: 326, radiusX: 62, radiusY: 32 },
      ],
      blur: 9,
    },
    mouth: {
      areas: [{ centerX: 768, centerY: 490, radiusX: 84, radiusY: 35 }],
      blur: 5,
    },
  },
};

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
  const avatarId = useId().replaceAll(":", "");

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
    for (const imageSource of avatarImageSources(level)) {
      const image = new Image();
      image.src = imageSource;
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
  const maskAreas = FACE_MASKS[level];
  const eyeMaskId = `${avatarId}-eye-mask`;
  const eyeBlurId = `${avatarId}-eye-blur`;
  const mouthMaskId = `${avatarId}-mouth-mask`;
  const mouthBlurId = `${avatarId}-mouth-blur`;
  const baseImageSource = avatarImageSource(level, "open", "closed");
  const closedEyesImageSource = avatarImageSource(level, "closed", "closed");
  const midMouthImageSource = avatarImageSource(level, "open", "mid");
  const openMouthImageSource = avatarImageSource(level, "open", "open");

  return (
    <figure
      className={`relative m-0 h-full min-h-0 overflow-hidden bg-slate-200 ${className}`}
      aria-label={speaking ? "AI 면접관 발화 중" : "AI 면접관 대기 중"}
      data-speech-mark={speechMarkIndex}
      data-level={level}
      data-eyes={eyes}
      data-mouth={mouth}
    >
      <svg
        className="h-full w-full"
        viewBox={`0 0 ${AVATAR_WIDTH} ${AVATAR_HEIGHT}`}
        preserveAspectRatio="xMidYMid slice"
        role="img"
        aria-label={`${levelInfo.label} AI 면접관`}
        focusable="false"
      >
        <defs>
          <filter
            id={eyeBlurId}
            x="0"
            y="0"
            width={AVATAR_WIDTH}
            height={AVATAR_HEIGHT}
            filterUnits="userSpaceOnUse"
          >
            <feGaussianBlur stdDeviation={maskAreas.eyes.blur} />
          </filter>
          <filter
            id={mouthBlurId}
            x="0"
            y="0"
            width={AVATAR_WIDTH}
            height={AVATAR_HEIGHT}
            filterUnits="userSpaceOnUse"
          >
            <feGaussianBlur stdDeviation={maskAreas.mouth.blur} />
          </filter>
          <mask
            id={eyeMaskId}
            x="0"
            y="0"
            width={AVATAR_WIDTH}
            height={AVATAR_HEIGHT}
            maskUnits="userSpaceOnUse"
          >
            <rect width={AVATAR_WIDTH} height={AVATAR_HEIGHT} fill="black" />
            {maskAreas.eyes.areas.map((area, index) => (
              <ellipse
                key={index}
                cx={area.centerX}
                cy={area.centerY}
                rx={area.radiusX}
                ry={area.radiusY}
                fill="white"
                filter={`url(#${eyeBlurId})`}
              />
            ))}
          </mask>
          <mask
            id={mouthMaskId}
            x="0"
            y="0"
            width={AVATAR_WIDTH}
            height={AVATAR_HEIGHT}
            maskUnits="userSpaceOnUse"
          >
            <rect width={AVATAR_WIDTH} height={AVATAR_HEIGHT} fill="black" />
            {maskAreas.mouth.areas.map((area, index) => (
              <ellipse
                key={index}
                cx={area.centerX}
                cy={area.centerY}
                rx={area.radiusX}
                ry={area.radiusY}
                fill="white"
                filter={`url(#${mouthBlurId})`}
              />
            ))}
          </mask>
        </defs>
        <image
          data-avatar-layer="base"
          href={baseImageSource}
          width={AVATAR_WIDTH}
          height={AVATAR_HEIGHT}
        />
        <image
          data-avatar-layer="eyes-closed"
          href={closedEyesImageSource}
          width={AVATAR_WIDTH}
          height={AVATAR_HEIGHT}
          mask={`url(#${eyeMaskId})`}
          opacity={eyes === "closed" ? 1 : 0}
        />
        <image
          data-avatar-layer="mouth-mid"
          href={midMouthImageSource}
          width={AVATAR_WIDTH}
          height={AVATAR_HEIGHT}
          mask={`url(#${mouthMaskId})`}
          opacity={mouth === "mid" ? MID_MOUTH_OPACITY : 0}
          style={{ transition: `opacity ${MOUTH_CROSSFADE_MS}ms ease-out` }}
        />
        <image
          data-avatar-layer="mouth-open"
          href={openMouthImageSource}
          width={AVATAR_WIDTH}
          height={AVATAR_HEIGHT}
          mask={`url(#${mouthMaskId})`}
          opacity={mouth === "open" ? OPEN_MOUTH_OPACITY : 0}
          style={{ transition: `opacity ${MOUTH_CROSSFADE_MS}ms ease-out` }}
        />
      </svg>
      <figcaption className="sr-only">
        {speaking ? "질문을 읽고 있습니다" : "다음 응답을 기다립니다"}
      </figcaption>
    </figure>
  );
}

function avatarImageSource(
  level: InterviewerLevel,
  eyeState: EyeState,
  mouthState: MouthState,
) {
  return `/interviewers/${level}_eyes_${eyeState}_mouth_${mouthState}.webp`;
}

function avatarImageSources(level: InterviewerLevel) {
  return [
    avatarImageSource(level, "open", "closed"),
    avatarImageSource(level, "closed", "closed"),
    avatarImageSource(level, "open", "mid"),
    avatarImageSource(level, "open", "open"),
  ];
}
