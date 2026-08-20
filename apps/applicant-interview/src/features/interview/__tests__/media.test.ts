import { describe, expect, it, vi } from "vitest";

import { PcmFrameBatcher } from "../media";

describe("PcmFrameBatcher", () => {
  it("combines worklet frames into ordered 40ms packets", () => {
    const onFrame = vi.fn();
    const batcher = new PcmFrameBatcher(640, onFrame);

    for (let index = 0; index < 5; index += 1) {
      batcher.push(new Int16Array(128).fill(index + 1));
    }

    expect(onFrame).toHaveBeenCalledOnce();
    const packet = onFrame.mock.calls[0][0] as Int16Array;
    expect(packet).toHaveLength(640);
    expect(Array.from(packet.slice(0, 3))).toEqual([1, 1, 1]);
    expect(Array.from(packet.slice(512, 515))).toEqual([5, 5, 5]);
  });

  it("flushes the final short packet", () => {
    const onFrame = vi.fn();
    const batcher = new PcmFrameBatcher(640, onFrame);
    batcher.push(new Int16Array([1, 2, 3]));

    batcher.flush();

    expect(Array.from(onFrame.mock.calls[0][0] as Int16Array)).toEqual([
      1, 2, 3,
    ]);
  });
});
