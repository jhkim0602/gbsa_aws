import { describe, expect, it, vi } from "vitest";

import { InterviewProtocolClient, type SocketLike } from "../protocolClient";
import { createInterviewSessionStore } from "../sessionStore";

class FakeSocket implements SocketLike {
  readonly sent: Array<string | ArrayBuffer> = [];
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;

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
