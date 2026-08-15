import type { StoreApi } from "zustand/vanilla";

import type {
  InterviewSessionStore,
  InterviewState,
  ServerState,
} from "./sessionStore";

export interface SocketLike {
  readonly readyState: number;
  onopen: (() => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  onmessage: ((event: MessageEvent<string>) => void) | null;
  send(data: string | ArrayBuffer): void;
  close(): void;
}

type Question = Readonly<{
  questionTurnId: string;
  text: string;
  textOnly: boolean;
}>;

type Envelope = Readonly<{
  protocol_version: "1.0";
  message_type: string;
  session_id: string;
  sequence: number;
  idempotency_key: string;
  correlation_id: string;
  sent_at: string;
  payload: Record<string, unknown>;
}>;

export class InterviewProtocolClient {
  private socket: SocketLike | null = null;

  constructor(
    private readonly options: Readonly<{
      sessionId: string;
      equipmentCheckId?: string;
      socketFactory(): SocketLike;
      store: StoreApi<InterviewSessionStore>;
      onQuestion(question: Question): void;
    }>,
  ) {}

  connect(): void {
    if (this.socket?.readyState === 0 || this.socket?.readyState === 1) return;
    const previousConnection = this.options.store.getState().connectionState;
    this.options.store
      .getState()
      .setConnectionState(
        previousConnection === "disconnected" ? "connecting" : "reconnecting",
      );
    const socket = this.options.socketFactory();
    this.socket = socket;
    socket.onopen = () => {
      this.options.store.getState().setConnectionState("connected");
      if (this.options.equipmentCheckId) {
        this.sendEnvelope("session.start", {
          equipment_check_id: this.options.equipmentCheckId,
          expected_state: "preparing",
        });
      }
      const snapshot = this.options.store.getState();
      this.sendEnvelope("session.resume", {
        last_applied_server_sequence: snapshot.serverSequence,
        last_final_turn_id: snapshot.lastFinalTurnId,
        last_uploaded_recording_chunk_sequence:
          snapshot.lastVerifiedRecordingChunkSequence,
      });
    };
    socket.onclose = () => {
      this.options.store.getState().setConnectionState("reconnecting");
    };
    socket.onerror = () => {
      this.options.store.getState().setConnectionState("reconnecting");
    };
    socket.onmessage = (event) => {
      this.handleServerMessage(event.data);
    };
  }

  disconnect(): void {
    const socket = this.socket;
    this.socket = null;
    if (socket?.readyState === 0 || socket?.readyState === 1) socket.close();
    this.options.store.getState().setConnectionState("disconnected");
  }

  completeAnswer(
    input: Readonly<{
      answerTurnId: string;
      lastAudioChunkSequence: number;
      lastRecordingChunkSequence: number;
    }>,
  ): void {
    this.sendEnvelope("answer.complete", {
      answer_turn_id: input.answerTurnId,
      last_audio_chunk_sequence: input.lastAudioChunkSequence,
      last_recording_chunk_sequence: input.lastRecordingChunkSequence,
      expected_state: "awaiting_answer",
    });
  }

  sendAudioFrame(
    input: Readonly<{
      answerTurnId: string;
      chunkSequence: number;
      sha256: string;
      frame: Int16Array;
    }>,
  ): void {
    const bytes = input.frame.byteLength;
    this.sendEnvelope("audio.chunk.begin", {
      answer_turn_id: input.answerTurnId,
      chunk_sequence: input.chunkSequence,
      codec: "pcm_s16le",
      sample_rate_hz: 16000,
      channel_count: 1,
      byte_length: bytes,
      sha256: input.sha256,
    });
    const frame = input.frame.buffer.slice(
      input.frame.byteOffset,
      input.frame.byteOffset + input.frame.byteLength,
    ) as ArrayBuffer;
    this.requireOpenSocket().send(frame);
  }

  repeatQuestion(questionTurnId: string, mode: "repeat" | "clarify"): void {
    this.sendEnvelope("question.repeat", {
      question_turn_id: questionTurnId,
      mode,
    });
  }

  private sendEnvelope(
    messageType: string,
    payload: Record<string, unknown>,
  ): void {
    const store = this.options.store.getState();
    const envelope: Envelope = {
      protocol_version: "1.0",
      message_type: messageType,
      session_id: this.options.sessionId,
      sequence: store.serverSequence,
      idempotency_key: `${messageType}:${crypto.randomUUID()}`,
      correlation_id: crypto.randomUUID(),
      sent_at: new Date().toISOString(),
      payload,
    };
    this.requireOpenSocket().send(JSON.stringify(envelope));
  }

  private requireOpenSocket(): SocketLike {
    if (this.socket?.readyState !== 1) {
      throw new Error("interview websocket is not connected");
    }
    return this.socket;
  }

  private handleServerMessage(raw: string): void {
    const envelope = parseEnvelope(raw, this.options.sessionId);
    if (!envelope) return;

    if (envelope.message_type === "resume.snapshot") {
      const snapshot = parseServerState(envelope.payload);
      if (snapshot) {
        this.options.store.getState().applyResumeSnapshot(snapshot);
      }
      return;
    }

    if (envelope.message_type === "question.ready") {
      const question = parseQuestion(envelope.payload);
      if (!question) return;
      const current = this.options.store.getState();
      current.applyServerState({
        state: "awaiting_answer",
        serverSequence: envelope.sequence,
        lastFinalTurnId: current.lastFinalTurnId,
        lastVerifiedRecordingChunkSequence:
          current.lastVerifiedRecordingChunkSequence,
        degradedModes: question.textOnly
          ? union(current.degradedModes, "text_only")
          : current.degradedModes.filter((mode) => mode !== "text_only"),
      });
      this.options.onQuestion(question);
      return;
    }

    if (envelope.message_type === "session.state_changed") {
      const state = readInterviewState(envelope.payload.state);
      if (!state) return;
      const current = this.options.store.getState();
      current.applyServerState({
        state,
        serverSequence: envelope.sequence,
        lastFinalTurnId: current.lastFinalTurnId,
        lastVerifiedRecordingChunkSequence:
          current.lastVerifiedRecordingChunkSequence,
        degradedModes: current.degradedModes,
      });
      return;
    }

    if (envelope.message_type === "question.preparing") {
      const current = this.options.store.getState();
      const degradedMode = readString(envelope.payload.degraded_mode);
      current.applyServerState({
        state: "preparing_question",
        serverSequence: envelope.sequence,
        lastFinalTurnId: current.lastFinalTurnId,
        lastVerifiedRecordingChunkSequence:
          current.lastVerifiedRecordingChunkSequence,
        degradedModes:
          degradedMode && degradedMode !== "none"
            ? union(current.degradedModes, degradedMode)
            : current.degradedModes,
      });
    }
  }
}

function parseEnvelope(raw: string, sessionId: string): Envelope | null {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(value) || value.protocol_version !== "1.0") return null;
  if (value.session_id !== sessionId) return null;
  if (
    typeof value.message_type !== "string" ||
    typeof value.sequence !== "number" ||
    !isRecord(value.payload)
  ) {
    return null;
  }
  return value as Envelope;
}

function parseServerState(
  payload: Record<string, unknown>,
): ServerState | null {
  const state = readInterviewState(payload.state);
  const serverSequence = readInteger(payload.server_sequence);
  const lastVerifiedRecordingChunkSequence = readInteger(
    payload.last_verified_recording_chunk_sequence,
  );
  if (
    !state ||
    serverSequence === null ||
    lastVerifiedRecordingChunkSequence === null
  ) {
    return null;
  }
  return {
    state,
    serverSequence,
    lastFinalTurnId:
      payload.last_final_turn_id === null
        ? null
        : readString(payload.last_final_turn_id),
    lastVerifiedRecordingChunkSequence,
    degradedModes: Array.isArray(payload.degraded_modes)
      ? payload.degraded_modes.filter(
          (mode): mode is string => typeof mode === "string",
        )
      : [],
  };
}

function parseQuestion(payload: Record<string, unknown>): Question | null {
  const questionTurnId = readString(payload.question_turn_id);
  const text = readString(payload.text);
  if (!questionTurnId || !text || typeof payload.text_only !== "boolean") {
    return null;
  }
  return { questionTurnId, text, textOnly: payload.text_only };
}

function readInterviewState(value: unknown): InterviewState | null {
  return typeof value === "string" &&
    [
      "preparing",
      "in_progress",
      "awaiting_answer",
      "preparing_question",
      "paused",
      "completed",
      "report_generating",
      "reviewable",
    ].includes(value)
    ? (value as InterviewState)
    : null;
}

function readString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function readInteger(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 0
    ? value
    : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function union(values: string[], value: string): string[] {
  return values.includes(value) ? values : [...values, value];
}
