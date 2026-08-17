/**
 * The review video must expose the transcript as a real caption track.
 *
 * `TimelineView` previously rendered `<track kind="captions" />` with no `src`,
 * so the player offered a caption menu that could never display anything.
 */
import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TimelineView } from "../TimelineView";
import type { ReviewTimelineEntry } from "../types";

const ENTRIES: ReviewTimelineEntry[] = [
  {
    entryId: "q1",
    type: "question",
    startMs: 200,
    endMs: 1_000,
    text: "ECS 장애의 원인을 어떻게 좁혔나요?",
  },
  {
    entryId: "a1",
    type: "answer",
    startMs: 1_200,
    endMs: 3_200,
    text: "캐시와 큐를 비교했습니다.",
  },
];

// jsdom implements neither half of the object-URL API.
const blobs = new Map<string, Blob>();
const revoked: string[] = [];

beforeEach(() => {
  blobs.clear();
  revoked.length = 0;
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: vi.fn((blob: Blob) => {
      const url = `blob:captions/${blobs.size + 1}`;
      blobs.set(url, blob);
      return url;
    }),
    revokeObjectURL: vi.fn((url: string) => revoked.push(url)),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** jsdom's Blob has no `.text()`, so go through FileReader. */
function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

function renderTimeline(entries: ReviewTimelineEntry[]) {
  return render(
    <TimelineView
      entries={entries}
      playbackStatus="ready"
      playbackUrl="https://media.example.test/interview.m3u8"
      onSeek={vi.fn()}
    />,
  );
}

describe("review caption track", () => {
  it("serves the transcript as a default Korean caption track", async () => {
    renderTimeline(ENTRIES);

    const track = document.querySelector("track");
    expect(track).not.toBeNull();
    expect(track?.getAttribute("kind")).toBe("captions");
    expect(track?.getAttribute("srclang")).toBe("ko");
    expect(track?.hasAttribute("default")).toBe(true);

    const src = track?.getAttribute("src") ?? "";
    const blob = blobs.get(src);
    expect(blob?.type).toBe("text/vtt");
    const vtt = await readBlob(blob!);
    expect(vtt).toContain("WEBVTT");
    expect(vtt).toContain("00:00:01.200 --> 00:00:03.200");
    expect(vtt).toContain("<v 지원자>캐시와 큐를 비교했습니다.");
  });

  it("renders no track when the transcript has no speech", () => {
    renderTimeline([
      { entryId: "e1", type: "event", startMs: 0, endMs: 500, text: null },
    ]);

    expect(document.querySelector("track")).toBeNull();
  });

  it("releases the previous blob when the transcript changes", () => {
    const { rerender } = renderTimeline(ENTRIES);
    const first = document.querySelector("track")?.getAttribute("src");

    rerender(
      <TimelineView
        entries={[{ ...ENTRIES[1], text: "다시 답변했습니다." }]}
        playbackStatus="ready"
        playbackUrl="https://media.example.test/interview.m3u8"
        onSeek={vi.fn()}
      />,
    );

    expect(document.querySelector("track")?.getAttribute("src")).not.toBe(
      first,
    );
    expect(revoked).toContain(first);
  });
});
