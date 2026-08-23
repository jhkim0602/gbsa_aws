import type { StoreApi } from "zustand/vanilla";

import type {
  InterviewSessionStore,
  InterviewState,
  ServerState,
} from "./sessionStore";

export interface SocketLike {
  readonly readyState: number;
  binaryType?: BinaryType;
  onopen: (() => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  onmessage: ((event: MessageEvent<string | ArrayBuffer>) => void) | null;
  send(data: string | ArrayBuffer): void;
  close(): void;
}

type Question = Readonly<{
  questionTurnId: string;
  text: string;
  textOnly: boolean;
}>;

export type InterviewProtocolError = Readonly<{
  code: string;
  message: string;
  retryable: boolean;
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

export type QuestionAudioFormat = Readonly<{
  questionTurnId: string;
  encoding: "pcm_s16le";
  sampleRateHz: number;
  channelCount: 1;
}>;

export class InterviewProtocolClient {
  private socket: SocketLike | null = null;
  private startRequested = false;

  constructor(
    private readonly options: Readonly<{
      sessionId: string;
      equipmentCheckId?: string;
      socketFactory(): SocketLike;
      store: StoreApi<InterviewSessionStore>;
      onQuestion(question: Question): void;
      onTranscript?(text: string, isFinal: boolean): void;
      onQuestionAudioStart?(format: QuestionAudioFormat): void;
      onQuestionAudioChunk?(chunk: ArrayBuffer): void;
      onQuestionAudioEnd?(): void;
      onQuestionAudioError?(): void;
      onError?(error: InterviewProtocolError): void;
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
    socket.binaryType = "arraybuffer";
    this.socket = socket;
    socket.onopen = () => {
      this.options.store.getState().setConnectionState("connected");
      this.startRequested = false;
      const snapshot = this.options.store.getState();
      this.sendEnvelope("session.resume", {
        last_applied_server_sequence: snapshot.serverSequence,
        last_final_turn_id: snapshot.lastFinalTurnId,
        last_uploaded_recording_chunk_sequence:
          snapshot.lastVerifiedRecordingChunkSequence,
      });
    };
    const markDisconnected = () => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.options.store.getState().setConnectionState("reconnecting");
    };
    socket.onclose = markDisconnected;
    socket.onerror = () => {
      markDisconnected();
      if (socket.readyState === 0 || socket.readyState === 1) socket.close();
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

  submitAutomatedAnswer(
    input: Readonly<{
      answerTurnId: string;
      text: string;
      lastRecordingChunkSequence: number;
    }>,
  ): void {
    this.sendEnvelope("answer.automated", {
      answer_turn_id: input.answerTurnId,
      text: input.text,
      last_recording_chunk_sequence: input.lastRecordingChunkSequence,
      expected_state: "awaiting_answer",
    });
  }

  startAnswer(
    input: Readonly<{
      answerTurnId: string;
      sampleRateHz: number;
    }>,
  ): void {
    this.sendEnvelope("answer.start", {
      answer_turn_id: input.answerTurnId,
      sample_rate_hz: input.sampleRateHz,
      channel_count: 1,
      codec: "pcm_s16le",
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

  private handleServerMessage(raw: string | ArrayBuffer): void {
    if (raw instanceof ArrayBuffer) {
      this.options.onQuestionAudioChunk?.(raw);
      return;
    }
    const envelope = parseEnvelope(raw, this.options.sessionId);
    if (!envelope) return;

    if (envelope.message_type === "resume.snapshot") {
      const snapshot = parseServerState(envelope.payload);
      if (snapshot) {
        this.options.store.getState().applyResumeSnapshot(snapshot);
        if (snapshot.state === "preparing" && !this.startRequested) {
          this.startRequested = true;
          this.sendEnvelope("session.start", {
            ...(this.options.equipmentCheckId
              ? { equipment_check_id: this.options.equipmentCheckId }
              : {}),
            expected_state: "preparing",
          });
        }
      }
      const pendingQuestion = parsePendingQuestion(
        envelope.payload.pending_turn,
      );
      if (pendingQuestion) this.options.onQuestion(pendingQuestion);
      return;
    }

    if (envelope.message_type === "error") {
      const error = parseProtocolError(envelope.payload);
      if (error) this.options.onError?.(error);
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

    if (
      envelope.message_type === "transcript.partial" ||
      envelope.message_type === "transcript.final"
    ) {
      const text = readString(envelope.payload.text);
      if (text !== null) {
        this.options.onTranscript?.(
          text,
          envelope.message_type === "transcript.final",
        );
      }
      return;
    }

    if (envelope.message_type === "question.audio.begin") {
      const format = parseQuestionAudioFormat(envelope.payload);
      if (format) this.options.onQuestionAudioStart?.(format);
      return;
    }

    if (envelope.message_type === "question.audio.end") {
      this.options.onQuestionAudioEnd?.();
      return;
    }

    if (envelope.message_type === "question.audio.error") {
      this.options.onQuestionAudioError?.();
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

    if (envelope.message_type === "session.completed") {
      const current = this.options.store.getState();
      current.applyServerState({
        state: "completed",
        serverSequence: envelope.sequence,
        lastFinalTurnId:
          readString(envelope.payload.last_turn_id) ?? current.lastFinalTurnId,
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
    lastRecordingEndMs: readInteger(payload.last_recording_end_ms) ?? 0,
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

function parsePendingQuestion(value: unknown): Question | null {
  if (!isRecord(value) || value.speaker !== "interviewer") return null;
  const questionTurnId = readString(value.turn_id);
  const text = readString(value.text);
  if (!questionTurnId || !text) return null;
  return {
    questionTurnId,
    text,
    textOnly: typeof value.text_only === "boolean" ? value.text_only : true,
  };
}

function parseProtocolError(
  payload: Record<string, unknown>,
): InterviewProtocolError | null {
  const code = readString(payload.code);
  const message = readString(payload.message);
  if (!code || !message || typeof payload.retryable !== "boolean") return null;
  return { code, message, retryable: payload.retryable };
}

function parseQuestionAudioFormat(
  payload: Record<string, unknown>,
): QuestionAudioFormat | null {
  const questionTurnId = readString(payload.question_turn_id);
  const sampleRateHz = readInteger(payload.sample_rate_hz);
  if (
    !questionTurnId ||
    payload.encoding !== "pcm_s16le" ||
    sampleRateHz === null ||
    payload.channel_count !== 1
  ) {
    return null;
  }
  return {
    questionTurnId,
    encoding: "pcm_s16le",
    sampleRateHz,
    channelCount: 1,
  };
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
