import { describe, expect, it } from "vitest";

import { createInterviewSessionStore } from "../sessionStore";

describe("interview session store", () => {
  it("applies only newer server sequences and reconciles a resume snapshot", () => {
    const store = createInterviewSessionStore();
    store.getState().applyServerState({
      state: "awaiting_answer",
      serverSequence: 4,
      lastFinalTurnId: "turn-4",
      lastVerifiedRecordingChunkSequence: 2,
      degradedModes: [],
    });
    store.getState().applyServerState({
      state: "in_progress",
      serverSequence: 3,
      lastFinalTurnId: "turn-3",
      lastVerifiedRecordingChunkSequence: 1,
      degradedModes: [],
    });

    expect(store.getState().serverSequence).toBe(4);
    expect(store.getState().state).toBe("awaiting_answer");

    store.getState().bufferChunk({
      sequence: 3,
      byteSize: 1024,
      sha256: "a".repeat(64),
    });
    store.getState().applyResumeSnapshot({
      state: "paused",
      serverSequence: 5,
      lastFinalTurnId: "turn-4",
      lastVerifiedRecordingChunkSequence: 2,
      lastRecordingEndMs: 4200,
      degradedModes: ["context_hot_view"],
    });

    expect(store.getState().serverSequence).toBe(5);
    expect(store.getState().localChunks).toHaveLength(1);
    expect(store.getState().lastRecordingEndMs).toBe(4200);
    expect(store.getState().degradedModes).toEqual(["context_hot_view"]);
  });

  it("removes local chunks only after server verification", () => {
    const store = createInterviewSessionStore();
    store.getState().bufferChunk({
      sequence: 1,
      byteSize: 512,
      sha256: "b".repeat(64),
    });
    store.getState().bufferChunk({
      sequence: 2,
      byteSize: 512,
      sha256: "c".repeat(64),
    });

    store.getState().acknowledgeVerifiedChunks(1);

    expect(
      store.getState().localChunks.map(({ sequence }) => sequence),
    ).toEqual([2]);
  });
});
