import { describe, expect, it, vi } from "vitest";

import { seekToEvidence } from "../TimelineView";

describe("Evidence seek", () => {
  it("sets the linked session time before requesting playback", async () => {
    const media = {
      currentTime: 0,
      play: vi.fn().mockResolvedValue(undefined),
    };

    await seekToEvidence(media, 2450);

    expect(media.currentTime).toBe(2.45);
    expect(media.play).toHaveBeenCalledOnce();
  });
});
