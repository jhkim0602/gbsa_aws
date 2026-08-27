import type { ReviewTimelineEntry } from "./types";

/**
 * Projects the transcript the review page already holds into a WebVTT track.
 *
 * The track is built in the browser rather than served from an endpoint because
 * `<track src>` is fetched by the media element without our `Authorization`
 * header, so a server route would have to carry the tenant token in the URL —
 * exactly what the platform security rule prohibits. The timeline response is
 * already tenant-scoped, so projecting it here needs no second trip.
 */

const speakerLabels: Record<"question" | "answer", string> = {
  question: "AI 면접관",
  answer: "지원자",
};

/** A cue with no duration is dropped by the parser, so give it a readable floor. */
const MINIMUM_CUE_MS = 700;

/** Keep native video captions compact; the full transcript remains available in the timeline. */
const MAX_CAPTION_CHARACTERS = 56;

export function buildCaptionTrack(entries: ReviewTimelineEntry[]): string {
  const cues = entries
    .filter(
      (entry): entry is ReviewTimelineEntry & { text: string } =>
        (entry.type === "question" || entry.type === "answer") &&
        typeof entry.text === "string" &&
        entry.text.trim().length > 0,
    )
    .sort((left, right) => left.startMs - right.startMs)
    .map((entry, index) => {
      const start = Math.max(0, entry.startMs);
      const end = Math.max(entry.endMs, start + MINIMUM_CUE_MS);
      const speaker = speakerLabels[entry.type as "question" | "answer"];
      return [
        String(index + 1),
        `${formatTimestamp(start)} --> ${formatTimestamp(end)}`,
        `<v ${speaker}>${escapeCueText(compactCaptionText(entry.text))}`,
      ].join("\n");
    });

  return ["WEBVTT", "", ...cues.flatMap((cue) => [cue, ""])].join("\n").trim();
}

function compactCaptionText(text: string): string {
  const compact = text.replace(/\s+/g, " ").trim();
  if (compact.length <= MAX_CAPTION_CHARACTERS) return compact;
  return `${compact.slice(0, MAX_CAPTION_CHARACTERS - 1).trimEnd()}…`;
}

export function formatTimestamp(milliseconds: number): string {
  const totalSeconds = Math.floor(milliseconds / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const remainder = Math.floor(milliseconds % 1000);
  return (
    `${pad(hours, 2)}:${pad(minutes, 2)}:${pad(seconds, 2)}` +
    `.${pad(remainder, 3)}`
  );
}

/**
 * Escaping `<` and `>` also neutralizes a literal `-->` inside answer text,
 * which would otherwise be read as the start of a new cue timing line.
 */
function escapeCueText(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\s*\n\s*\n\s*/g, "\n")
    .trim();
}

function pad(value: number, width: number): string {
  return String(value).padStart(width, "0");
}
