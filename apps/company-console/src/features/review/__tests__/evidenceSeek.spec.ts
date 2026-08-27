import { describe, expect, it, vi } from "vitest";

import { seekToEvidence } from "../TimelineView";

describe("Evidence seek", () => {
  it("sets the linked session time before requesting playback", async () => {
    const media = {
      currentTime: 0,
      readyState: 1,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      play: vi.fn().mockResolvedValue(undefined),
    };

    await seekToEvidence(media, 2450);

    expect(media.currentTime).toBe(2.45);
    expect(media.play).toHaveBeenCalledOnce();
  });

  it("waits for video metadata before seeking and playing", async () => {
    const listeners = new Map<string, EventListener>();
    const media = {
      currentTime: 0,
      readyState: 0,
      play: vi.fn().mockResolvedValue(undefined),
      addEventListener: vi.fn(
        (type: string, listener: EventListenerOrEventListenerObject) => {
          if (typeof listener === "function") listeners.set(type, listener);
        },
      ),
      removeEventListener: vi.fn((type: string) => listeners.delete(type)),
    };

    const playback = seekToEvidence(media, 62_000);

    expect(media.currentTime).toBe(0);
    expect(media.play).not.toHaveBeenCalled();

    listeners.get("loadedmetadata")?.(new Event("loadedmetadata"));
    await playback;

    expect(media.currentTime).toBe(62);
    expect(media.play).toHaveBeenCalledOnce();
  });
});
