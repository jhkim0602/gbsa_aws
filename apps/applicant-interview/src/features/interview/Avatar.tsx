import "./interview.css";

export function Avatar({
  textOnly,
  speaking,
  speechMarkIndex,
}: {
  textOnly: boolean;
  speaking: boolean;
  speechMarkIndex: number;
}) {
  if (textOnly) {
    return (
      <div className="avatar-text-only" role="status">
        음성 없이 질문을 표시합니다.
      </div>
    );
  }

  const mouthShapes = ["closed", "open", "wide"] as const;
  const mouthShape = speaking
    ? mouthShapes[speechMarkIndex % mouthShapes.length]
    : "closed";

  return (
    <div
      className={`avatar ${speaking ? "avatar-speaking" : ""}`}
      aria-label={speaking ? "AI 면접관 발화 중" : "AI 면접관 대기 중"}
      data-speech-mark={speechMarkIndex}
      data-mouth-shape={mouthShape}
    >
      <span className="avatar-face" aria-hidden="true">
        AI
      </span>
      <span>
        {speaking ? "질문을 읽고 있습니다" : "다음 응답을 기다립니다"}
      </span>
    </div>
  );
}
