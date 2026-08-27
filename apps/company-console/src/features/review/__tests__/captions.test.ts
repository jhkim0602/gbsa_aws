import { describe, expect, it } from "vitest";

import { buildCaptionTrack, formatTimestamp } from "../captions";
import type { ReviewTimelineEntry } from "../types";

function entry(
  overrides: Partial<ReviewTimelineEntry> & Pick<ReviewTimelineEntry, "type">,
): ReviewTimelineEntry {
  return {
    entryId: "entry-1",
    startMs: 0,
    endMs: 1_000,
    text: "본문",
    ...overrides,
  };
}

describe("buildCaptionTrack", () => {
  it("writes one speaker-labelled cue per transcript segment", () => {
    const track = buildCaptionTrack([
      entry({
        entryId: "q1",
        type: "question",
        startMs: 200,
        endMs: 1_000,
        text: "ECS 장애의 원인을 어떻게 좁혔나요?",
      }),
      entry({
        entryId: "a1",
        type: "answer",
        startMs: 1_200,
        endMs: 3_200,
        text: "캐시와 큐를 비교했습니다.",
      }),
    ]);

    expect(track).toBe(
      [
        "WEBVTT",
        "",
        "1",
        "00:00:00.200 --> 00:00:01.000",
        "<v AI 면접관>ECS 장애의 원인을 어떻게 좁혔나요?",
        "",
        "2",
        "00:00:01.200 --> 00:00:03.200",
        "<v 지원자>캐시와 큐를 비교했습니다.",
      ].join("\n"),
    );
  });

  it("orders cues by start time regardless of entry order", () => {
    const track = buildCaptionTrack([
      entry({ entryId: "late", type: "answer", startMs: 5_000, endMs: 6_000 }),
      entry({
        entryId: "early",
        type: "question",
        startMs: 1_000,
        endMs: 2_000,
      }),
    ]);

    expect(track.indexOf("00:00:01.000")).toBeLessThan(
      track.indexOf("00:00:05.000"),
    );
  });

  it("omits technical events and blank transcript text", () => {
    const track = buildCaptionTrack([
      entry({ entryId: "event", type: "event", text: null }),
      entry({ entryId: "blank", type: "answer", text: "   " }),
    ]);

    expect(track).toBe("WEBVTT");
  });

  it("escapes markup so answer text cannot forge a cue boundary", () => {
    const track = buildCaptionTrack([
      entry({
        type: "answer",
        startMs: 0,
        endMs: 1_000,
        text: "a --> b, <script>, x & y",
      }),
    ]);

    expect(track).toContain("a --&gt; b, &lt;script&gt;, x &amp; y");
    // Only the real timing line may contain an unescaped arrow.
    expect(track.match(/-->/g)).toHaveLength(1);
  });

  it("gives a zero-length segment a visible duration", () => {
    const track = buildCaptionTrack([
      entry({ type: "answer", startMs: 4_000, endMs: 4_000 }),
    ]);

    expect(track).toContain("00:00:04.000 --> 00:00:04.700");
  });
});

describe("formatTimestamp", () => {
  it("uses the WebVTT hour:minute:second.millisecond form", () => {
    expect(formatTimestamp(0)).toBe("00:00:00.000");
    expect(formatTimestamp(59_999)).toBe("00:00:59.999");
    expect(formatTimestamp(3_723_456)).toBe("01:02:03.456");
  });
});
