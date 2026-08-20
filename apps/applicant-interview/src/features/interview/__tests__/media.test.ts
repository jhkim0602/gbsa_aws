import { afterEach, describe, expect, it, vi } from "vitest";

import { ChunkedRecorder, PcmFrameBatcher } from "../media";

class FakeMediaRecorder extends EventTarget {
  static instance: FakeMediaRecorder | null = null;

  constructor(_stream: MediaStream) {
    super();
    FakeMediaRecorder.instance = this;
  }

  start() {}

  stop() {
    this.dispatchEvent(new Event("stop"));
  }

  emit(blob: Blob) {
    const event = new Event("dataavailable");
    Object.defineProperty(event, "data", { value: blob });
    this.dispatchEvent(event);
  }
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  FakeMediaRecorder.instance = null;
});

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

describe("ChunkedRecorder", () => {
  it("continues sequence numbers and session time across answer recordings", async () => {
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    vi.spyOn(performance, "now")
      .mockReturnValueOnce(1000)
      .mockReturnValueOnce(3000);
    const put = vi.fn().mockResolvedValue(undefined);
    const onChunk = vi.fn().mockResolvedValue(undefined);
    const recorder = new ChunkedRecorder(
      "session-id",
      {
        put,
        list: vi.fn().mockResolvedValue([]),
        removeVerified: vi.fn().mockResolvedValue(undefined),
      },
      onChunk,
      2,
      5000,
    );

    recorder.start({} as MediaStream);
    FakeMediaRecorder.instance?.emit({
      size: 9,
      arrayBuffer: async () => new TextEncoder().encode("recording").buffer,
    } as Blob);
    await recorder.stop();

    expect(onChunk).toHaveBeenCalledWith(
      expect.objectContaining({
        sequence: 3,
        sessionStartMs: 5000,
        sessionEndMs: 7000,
      }),
    );
  });

  it("keeps a short final chunk contiguous with the previous chunk", async () => {
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    vi.spyOn(performance, "now")
      .mockReturnValueOnce(1000)
      .mockReturnValueOnce(3000)
      .mockReturnValueOnce(3200);
    const onChunk = vi.fn().mockResolvedValue(undefined);
    const recorder = new ChunkedRecorder(
      "session-id",
      {
        put: vi.fn().mockResolvedValue(undefined),
        list: vi.fn().mockResolvedValue([]),
        removeVerified: vi.fn().mockResolvedValue(undefined),
      },
      onChunk,
      0,
      5000,
    );

    recorder.start({} as MediaStream);
    FakeMediaRecorder.instance?.emit({
      size: 21,
      arrayBuffer: async () =>
        new TextEncoder().encode("first recording chunk").buffer,
    } as Blob);
    FakeMediaRecorder.instance?.emit({
      size: 11,
      arrayBuffer: async () => new TextEncoder().encode("final chunk").buffer,
    } as Blob);
    await recorder.stop();

    expect(onChunk.mock.calls.map(([chunk]) => chunk)).toEqual([
      expect.objectContaining({
        sequence: 1,
        sessionStartMs: 5000,
        sessionEndMs: 7000,
      }),
      expect.objectContaining({
        sequence: 2,
        sessionStartMs: 7000,
        sessionEndMs: 7200,
      }),
    ]);
  });
});
