export type WhyYouAssistantAvatarState =
  "idle" | "searching" | "thinking" | "complete";

export function WhyYouAssistantAvatar({
  state = "idle",
}: {
  state?: WhyYouAssistantAvatarState;
}) {
  return (
    <span
      className="why-you-bot grid size-8 shrink-0 place-items-center text-brand"
      data-assistant-avatar-state={state}
      aria-hidden="true"
    >
      <svg
        className="size-6 overflow-visible"
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <g className="why-you-bot__figure">
          <path
            d="M5.8 8.5 10.4 23 16 13.2 21.6 23 26.2 8.5"
            stroke="currentColor"
            strokeWidth="4.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>
        <circle
          className="why-you-bot__orbit"
          cx="16"
          cy="1.8"
          r="1.7"
          fill="currentColor"
        />
      </svg>
    </span>
  );
}
