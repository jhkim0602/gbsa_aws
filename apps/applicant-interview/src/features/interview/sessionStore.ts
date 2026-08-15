import { createStore, type StoreApi } from "zustand/vanilla";

export type InterviewState =
  | "preparing"
  | "in_progress"
  | "awaiting_answer"
  | "preparing_question"
  | "paused"
  | "completed"
  | "report_generating"
  | "reviewable";

export type ConnectionState =
  "disconnected" | "connecting" | "connected" | "reconnecting";

export type BufferedChunk = Readonly<{
  sequence: number;
  byteSize: number;
  sha256: string;
}>;

export type ServerState = Readonly<{
  state: InterviewState;
  serverSequence: number;
  lastFinalTurnId: string | null;
  lastVerifiedRecordingChunkSequence: number;
  degradedModes: string[];
}>;

export type InterviewSessionStore = {
  state: InterviewState;
  serverSequence: number;
  lastFinalTurnId: string | null;
  lastVerifiedRecordingChunkSequence: number;
  degradedModes: string[];
  connectionState: ConnectionState;
  localChunks: BufferedChunk[];
  applyServerState(snapshot: ServerState): void;
  applyResumeSnapshot(snapshot: ServerState): void;
  setConnectionState(connectionState: ConnectionState): void;
  bufferChunk(chunk: BufferedChunk): void;
  acknowledgeVerifiedChunks(sequence: number): void;
};

export function createInterviewSessionStore(): StoreApi<InterviewSessionStore> {
  return createStore<InterviewSessionStore>((set, get) => ({
    state: "preparing",
    serverSequence: 0,
    lastFinalTurnId: null,
    lastVerifiedRecordingChunkSequence: 0,
    degradedModes: [],
    connectionState: "disconnected",
    localChunks: [],
    applyServerState(snapshot) {
      if (snapshot.serverSequence <= get().serverSequence) return;
      set({
        state: snapshot.state,
        serverSequence: snapshot.serverSequence,
        lastFinalTurnId: snapshot.lastFinalTurnId,
        lastVerifiedRecordingChunkSequence:
          snapshot.lastVerifiedRecordingChunkSequence,
        degradedModes: [...snapshot.degradedModes],
      });
    },
    applyResumeSnapshot(snapshot) {
      if (snapshot.serverSequence < get().serverSequence) return;
      set({
        state: snapshot.state,
        serverSequence: snapshot.serverSequence,
        lastFinalTurnId: snapshot.lastFinalTurnId,
        lastVerifiedRecordingChunkSequence:
          snapshot.lastVerifiedRecordingChunkSequence,
        degradedModes: [...snapshot.degradedModes],
        localChunks: get().localChunks.filter(
          ({ sequence }) =>
            sequence > snapshot.lastVerifiedRecordingChunkSequence,
        ),
      });
    },
    setConnectionState(connectionState) {
      set({ connectionState });
    },
    bufferChunk(chunk) {
      const withoutSameSequence = get().localChunks.filter(
        ({ sequence }) => sequence !== chunk.sequence,
      );
      set({
        localChunks: [...withoutSameSequence, chunk].sort(
          (left, right) => left.sequence - right.sequence,
        ),
      });
    },
    acknowledgeVerifiedChunks(sequence) {
      set({
        lastVerifiedRecordingChunkSequence: Math.max(
          get().lastVerifiedRecordingChunkSequence,
          sequence,
        ),
        localChunks: get().localChunks.filter(
          (chunk) => chunk.sequence > sequence,
        ),
      });
    },
  }));
}
