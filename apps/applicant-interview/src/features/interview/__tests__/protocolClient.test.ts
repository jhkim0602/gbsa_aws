import { describe, expect, it, vi } from "vitest";

import { InterviewProtocolClient, type SocketLike } from "../protocolClient";
import { createInterviewSessionStore } from "../sessionStore";

class FakeSocket implements SocketLike {
  readonly sent: Array<string | ArrayBuffer> = [];
  readyState = 0;
  binaryType: BinaryType = "blob";
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string | ArrayBuffer>) => void) | null =
    null;

  send(data: string | ArrayBuffer) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }

  open() {
    this.readyState = 1;
    this.onopen?.();
  }

  serverMessage(message: object) {
    this.onmessage?.({ data: JSON.stringify(message) } as MessageEvent<string>);
  }

  serverBinary(chunk: ArrayBuffer) {
    this.onmessage?.({ data: chunk } as MessageEvent<ArrayBuffer>);
  }
}

describe("interview protocol client", () => {
  it("resumes from server sequence and sends one idempotent answer completion", () => {
    const socket = new FakeSocket();
    const store = createInterviewSessionStore();
    store.getState().applyServerState({
      state: "awaiting_answer",
      serverSequence: 4,
      lastFinalTurnId: "00000000-0000-7000-8000-000000000401",
      lastVerifiedRecordingChunkSequence: 2,
      degradedModes: [],
    });
    const client = new InterviewProtocolClient({
      sessionId: "00000000-0000-7000-8000-000000000402",
      socketFactory: () => socket,
      store,
      onQuestion: vi.fn(),
    });

    client.connect();
    socket.open();
    expect(JSON.parse(String(socket.sent[0]))).toMatchObject({
      message_type: "session.resume",
      sequence: 4,
      payload: {
        last_uploaded_recording_chunk_sequence: 2,
      },
    });

    client.completeAnswer({
      answerTurnId: "00000000-0000-7000-8000-000000000403",
      lastAudioChunkSequence: 3,
      lastRecordingChunkSequence: 2,
    });
    const complete = JSON.parse(String(socket.sent[1]));
    expect(complete.message_type).toBe("answer.complete");
    expect(complete.sequence).toBe(4);
    expect(complete.payload.expected_state).toBe("awaiting_answer");
    expect(complete.idempotency_key).toBeTruthy();
  });

  it("starts a newly created session before requesting its recovery snapshot", () => {
    const socket = new FakeSocket();
    const client = new InterviewProtocolClient({
      sessionId: "00000000-0000-7000-8000-000000000411",
      equipmentCheckId: "00000000-0000-7000-8000-000000000412",
      socketFactory: () => socket,
      store: createInterviewSessionStore(),
      onQuestion: vi.fn(),
    });

    client.connect();
    socket.open();

    expect(JSON.parse(String(socket.sent[0]))).toMatchObject({
      message_type: "session.start",
      sequence: 0,
      payload: {
        equipment_check_id: "00000000-0000-7000-8000-000000000412",
        expected_state: "preparing",
      },
    });
    expect(JSON.parse(String(socket.sent[1])).message_type).toBe(
      "session.resume",
    );
  });

  it("applies question and resume messages, preserving text-only degraded mode", () => {
    const socket = new FakeSocket();
    const store = createInterviewSessionStore();
    const onQuestion = vi.fn();
    const client = new InterviewProtocolClient({
      sessionId: "00000000-0000-7000-8000-000000000404",
      socketFactory: () => socket,
      store,
      onQuestion,
    });
    client.connect();
    socket.open();

    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "question.ready",
      session_id: "00000000-0000-7000-8000-000000000404",
      sequence: 5,
      idempotency_key: "server-question-0001",
      correlation_id: "00000000-0000-7000-8000-000000000405",
      sent_at: "2026-08-15T10:00:00Z",
      payload: {
        question_turn_id: "00000000-0000-7000-8000-000000000406",
        text: "최근 장애 대응의 대안을 설명해 주세요.",
        target_criterion_id: "00000000-0000-7000-8000-000000000407",
        text_only: true,
      },
    });
    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "resume.snapshot",
      session_id: "00000000-0000-7000-8000-000000000404",
      sequence: 6,
      idempotency_key: "server-resume-0001",
      correlation_id: "00000000-0000-7000-8000-000000000408",
      sent_at: "2026-08-15T10:00:01Z",
      payload: {
        state: "awaiting_answer",
        server_sequence: 6,
        last_final_turn_id: null,
        last_verified_recording_chunk_sequence: 3,
        degraded_modes: ["text_only"],
      },
    });

    expect(onQuestion).toHaveBeenCalledWith({
      questionTurnId: "00000000-0000-7000-8000-000000000406",
      text: "최근 장애 대응의 대안을 설명해 주세요.",
      textOnly: true,
    });
    expect(store.getState().serverSequence).toBe(6);
    expect(store.getState().degradedModes).toEqual(["text_only"]);
  });

  it("sends audio metadata before the matching binary PCM frame", () => {
    const socket = new FakeSocket();
    const client = new InterviewProtocolClient({
      sessionId: "00000000-0000-7000-8000-000000000409",
      socketFactory: () => socket,
      store: createInterviewSessionStore(),
      onQuestion: vi.fn(),
    });
    client.connect();
    socket.open();

    client.sendAudioFrame({
      answerTurnId: "00000000-0000-7000-8000-000000000410",
      chunkSequence: 1,
      sha256: "a".repeat(64),
      frame: new Int16Array([1, 2, 3]),
    });

    expect(JSON.parse(String(socket.sent[1])).message_type).toBe(
      "audio.chunk.begin",
    );
    expect(socket.sent[2]).toBeInstanceOf(ArrayBuffer);
  });

  it("routes streaming captions and binary question audio", () => {
    const socket = new FakeSocket();
    const onTranscript = vi.fn();
    const onQuestionAudioStart = vi.fn();
    const onQuestionAudioChunk = vi.fn();
    const onQuestionAudioEnd = vi.fn();
    const client = new InterviewProtocolClient({
      sessionId: "00000000-0000-7000-8000-000000000421",
      socketFactory: () => socket,
      store: createInterviewSessionStore(),
      onQuestion: vi.fn(),
      onTranscript,
      onQuestionAudioStart,
      onQuestionAudioChunk,
      onQuestionAudioEnd,
    });
    client.connect();
    socket.open();

    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "transcript.partial",
      session_id: "00000000-0000-7000-8000-000000000421",
      sequence: 1,
      idempotency_key: "server-transcript-0001",
      correlation_id: "00000000-0000-7000-8000-000000000422",
      sent_at: "2026-08-20T10:00:00Z",
      payload: { text: "실시간 자막" },
    });
    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "question.audio.begin",
      session_id: "00000000-0000-7000-8000-000000000421",
      sequence: 2,
      idempotency_key: "server-audio-0001",
      correlation_id: "00000000-0000-7000-8000-000000000423",
      sent_at: "2026-08-20T10:00:01Z",
      payload: {
        question_turn_id: "00000000-0000-7000-8000-000000000424",
        encoding: "pcm_s16le",
        sample_rate_hz: 24000,
        channel_count: 1,
      },
    });
    const chunk = new Uint8Array([1, 2, 3, 4]).buffer;
    socket.serverBinary(chunk);
    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "question.audio.end",
      session_id: "00000000-0000-7000-8000-000000000421",
      sequence: 2,
      idempotency_key: "server-audio-0002",
      correlation_id: "00000000-0000-7000-8000-000000000423",
      sent_at: "2026-08-20T10:00:02Z",
      payload: {},
    });

    expect(socket.binaryType).toBe("arraybuffer");
    expect(onTranscript).toHaveBeenCalledWith("실시간 자막", false);
    expect(onQuestionAudioStart).toHaveBeenCalledWith({
      questionTurnId: "00000000-0000-7000-8000-000000000424",
      encoding: "pcm_s16le",
      sampleRateHz: 24000,
      channelCount: 1,
    });
    expect(onQuestionAudioChunk).toHaveBeenCalledWith(chunk);
    expect(onQuestionAudioEnd).toHaveBeenCalledOnce();
  });

  it("moves the applicant journey to completion on session.completed", () => {
    const socket = new FakeSocket();
    const store = createInterviewSessionStore();
    const client = new InterviewProtocolClient({
      sessionId: "00000000-0000-7000-8000-000000000421",
      socketFactory: () => socket,
      store,
      onQuestion: vi.fn(),
    });
    client.connect();
    socket.open();

    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "session.completed",
      session_id: "00000000-0000-7000-8000-000000000421",
      sequence: 9,
      idempotency_key: "server-completed-0001",
      correlation_id: "00000000-0000-7000-8000-000000000422",
      sent_at: "2026-08-15T10:00:02Z",
      payload: {
        state: "completed",
        completed_at: "2026-08-15T10:00:02Z",
        last_turn_id: "00000000-0000-7000-8000-000000000423",
        post_processing_status: "queued",
      },
    });

    expect(store.getState()).toMatchObject({
      state: "completed",
      serverSequence: 9,
      lastFinalTurnId: "00000000-0000-7000-8000-000000000423",
    });
  });
});
