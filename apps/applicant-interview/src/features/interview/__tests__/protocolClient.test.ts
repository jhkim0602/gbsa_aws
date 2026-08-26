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

  it("starts a newly created session after confirming it is still preparing", () => {
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

    expect(JSON.parse(String(socket.sent[0])).message_type).toBe(
      "session.resume",
    );

    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "resume.snapshot",
      session_id: "00000000-0000-7000-8000-000000000411",
      sequence: 0,
      idempotency_key: "server-resume-preparing",
      correlation_id: "00000000-0000-7000-8000-000000000413",
      sent_at: "2026-08-23T10:00:00Z",
      payload: {
        state: "preparing",
        server_sequence: 0,
        last_final_turn_id: null,
        last_verified_recording_chunk_sequence: 0,
        degraded_modes: [],
      },
    });

    expect(JSON.parse(String(socket.sent[1]))).toMatchObject({
      message_type: "session.start",
      sequence: 0,
      payload: {
        equipment_check_id: "00000000-0000-7000-8000-000000000412",
        expected_state: "preparing",
      },
    });
  });

  it("starts a restored preparing session without the original equipment check id", () => {
    const socket = new FakeSocket();
    const client = new InterviewProtocolClient({
      sessionId: "00000000-0000-7000-8000-000000000414",
      socketFactory: () => socket,
      store: createInterviewSessionStore(),
      onQuestion: vi.fn(),
    });

    client.connect();
    socket.open();
    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "resume.snapshot",
      session_id: "00000000-0000-7000-8000-000000000414",
      sequence: 0,
      idempotency_key: "server-resume-restored-preparing",
      correlation_id: "00000000-0000-7000-8000-000000000415",
      sent_at: "2026-08-23T10:00:00Z",
      payload: {
        state: "preparing",
        server_sequence: 0,
        last_final_turn_id: null,
        last_verified_recording_chunk_sequence: 0,
        degraded_modes: [],
      },
    });

    expect(JSON.parse(String(socket.sent[1]))).toMatchObject({
      message_type: "session.start",
      sequence: 0,
      payload: { expected_state: "preparing" },
    });
    expect(JSON.parse(String(socket.sent[1])).payload).not.toHaveProperty(
      "equipment_check_id",
    );
  });

  it("restores the pending question and reports retryable server errors", () => {
    const socket = new FakeSocket();
    const onQuestion = vi.fn();
    const onError = vi.fn();
    const client = new InterviewProtocolClient({
      sessionId: "00000000-0000-7000-8000-000000000415",
      socketFactory: () => socket,
      store: createInterviewSessionStore(),
      onQuestion,
      onError,
    });
    client.connect();
    socket.open();

    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "resume.snapshot",
      session_id: "00000000-0000-7000-8000-000000000415",
      sequence: 6,
      idempotency_key: "server-resume-0002",
      correlation_id: "00000000-0000-7000-8000-000000000416",
      sent_at: "2026-08-21T10:00:00Z",
      payload: {
        state: "awaiting_answer",
        server_sequence: 6,
        last_final_turn_id: "00000000-0000-7000-8000-000000000417",
        pending_turn: {
          turn_id: "00000000-0000-7000-8000-000000000417",
          speaker: "interviewer",
          status: "final",
          text: "복구된 질문입니다.",
          text_only: true,
        },
        last_verified_recording_chunk_sequence: 3,
        degraded_modes: ["text_only"],
      },
    });
    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "error",
      session_id: "00000000-0000-7000-8000-000000000415",
      sequence: 6,
      idempotency_key: "server-error-0001",
      correlation_id: "00000000-0000-7000-8000-000000000418",
      sent_at: "2026-08-21T10:00:01Z",
      payload: {
        code: "QUESTION_GENERATION_UNAVAILABLE",
        message: "다음 질문을 준비하지 못했습니다.",
        retryable: true,
      },
    });

    expect(onQuestion).toHaveBeenCalledWith({
      questionTurnId: "00000000-0000-7000-8000-000000000417",
      text: "복구된 질문입니다.",
      textOnly: true,
    });
    expect(onError).toHaveBeenCalledWith({
      code: "QUESTION_GENERATION_UNAVAILABLE",
      message: "다음 질문을 준비하지 못했습니다.",
      retryable: true,
    });
  });

  it("keeps an intentional disconnect in the disconnected state", () => {
    const socket = new FakeSocket();
    const store = createInterviewSessionStore();
    const client = new InterviewProtocolClient({
      sessionId: "00000000-0000-7000-8000-000000000419",
      socketFactory: () => socket,
      store,
      onQuestion: vi.fn(),
    });
    client.connect();
    socket.open();

    client.disconnect();

    expect(store.getState().connectionState).toBe("disconnected");
  });

  it("sends a local automated text answer with recording progress", () => {
    const socket = new FakeSocket();
    const client = new InterviewProtocolClient({
      sessionId: "00000000-0000-7000-8000-000000000413",
      socketFactory: () => socket,
      store: createInterviewSessionStore(),
      onQuestion: vi.fn(),
    });
    client.connect();
    socket.open();

    client.submitAutomatedAnswer({
      answerTurnId: "00000000-0000-7000-8000-000000000414",
      text: "자동 면접 답변입니다.",
      lastRecordingChunkSequence: 7,
    });

    expect(JSON.parse(String(socket.sent[1]))).toMatchObject({
      message_type: "answer.automated",
      payload: {
        answer_turn_id: "00000000-0000-7000-8000-000000000414",
        text: "자동 면접 답변입니다.",
        last_recording_chunk_sequence: 7,
        expected_state: "awaiting_answer",
      },
    });
  });

  it("requests and receives a question-grounded automated answer", async () => {
    const socket = new FakeSocket();
    const sessionId = "00000000-0000-7000-8000-000000000430";
    const questionTurnId = "00000000-0000-7000-8000-000000000431";
    const client = new InterviewProtocolClient({
      sessionId,
      socketFactory: () => socket,
      store: createInterviewSessionStore(),
      onQuestion: vi.fn(),
    });
    client.connect();
    socket.open();

    const answerPromise = client.requestAutomatedAnswer({
      questionTurnId,
      includeAudio: false,
      answerProfile: "standard",
    });
    expect(JSON.parse(String(socket.sent[1]))).toMatchObject({
      message_type: "answer.automated.generate",
      payload: {
        question_turn_id: questionTurnId,
        include_audio: false,
        answer_profile: "standard",
      },
    });

    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "answer.automated.ready",
      session_id: sessionId,
      sequence: 2,
      idempotency_key: "server-answer-generated-0001",
      correlation_id: "00000000-0000-7000-8000-000000000432",
      sent_at: "2026-08-23T10:00:00Z",
      payload: {
        question_turn_id: questionTurnId,
        text: "제출 자료의 장애 대응 경험을 바탕으로 답변했습니다.",
        source_reference_count: 3,
        grounded: true,
        audio_stream: false,
      },
    });

    await expect(answerPromise).resolves.toEqual({
      questionTurnId,
      text: "제출 자료의 장애 대응 경험을 바탕으로 답변했습니다.",
      sourceReferenceCount: 3,
      grounded: true,
    });
  });

  it("buffers generated answer audio separately from interviewer audio", async () => {
    const socket = new FakeSocket();
    const sessionId = "00000000-0000-7000-8000-000000000433";
    const questionTurnId = "00000000-0000-7000-8000-000000000434";
    const onQuestionAudioChunk = vi.fn();
    const client = new InterviewProtocolClient({
      sessionId,
      socketFactory: () => socket,
      store: createInterviewSessionStore(),
      onQuestion: vi.fn(),
      onQuestionAudioChunk,
    });
    client.connect();
    socket.open();

    const answerPromise = client.requestAutomatedAnswer({
      questionTurnId,
      includeAudio: true,
      answerProfile: "standard",
    });
    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "answer.automated.ready",
      session_id: sessionId,
      sequence: 2,
      idempotency_key: "server-answer-generated-0002",
      correlation_id: "00000000-0000-7000-8000-000000000435",
      sent_at: "2026-08-23T10:00:00Z",
      payload: {
        question_turn_id: questionTurnId,
        text: "음성으로 변환할 자료 기반 답변입니다.",
        source_reference_count: 1,
        grounded: true,
        audio_stream: true,
      },
    });
    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "answer.automated.audio.begin",
      session_id: sessionId,
      sequence: 2,
      idempotency_key: "server-answer-audio-begin-0001",
      correlation_id: "00000000-0000-7000-8000-000000000435",
      sent_at: "2026-08-23T10:00:00Z",
      payload: {
        question_turn_id: questionTurnId,
        encoding: "pcm_s16le",
        sample_rate_hz: 24000,
        channel_count: 1,
      },
    });
    socket.serverBinary(new Uint8Array([1, 0, 255, 255]).buffer);
    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "answer.automated.audio.end",
      session_id: sessionId,
      sequence: 2,
      idempotency_key: "server-answer-audio-end-0001",
      correlation_id: "00000000-0000-7000-8000-000000000435",
      sent_at: "2026-08-23T10:00:00Z",
      payload: {
        question_turn_id: questionTurnId,
        sample_rate_hz: 24000,
      },
    });

    const answer = await answerPromise;
    expect(Array.from(answer.pcm ?? [])).toEqual([1, -1]);
    expect(answer.sampleRateHz).toBe(24000);
    expect(onQuestionAudioChunk).not.toHaveBeenCalled();
  });

  it("rejects a pending generated answer when the server cannot prepare it", async () => {
    const socket = new FakeSocket();
    const sessionId = "00000000-0000-7000-8000-000000000436";
    const client = new InterviewProtocolClient({
      sessionId,
      socketFactory: () => socket,
      store: createInterviewSessionStore(),
      onQuestion: vi.fn(),
    });
    client.connect();
    socket.open();

    const answerPromise = client.requestAutomatedAnswer({
      questionTurnId: "00000000-0000-7000-8000-000000000437",
      includeAudio: false,
      answerProfile: "entry_low",
    });
    expect(JSON.parse(String(socket.sent[1]))).toMatchObject({
      message_type: "answer.automated.generate",
      payload: {
        answer_profile: "entry_low",
      },
    });
    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "error",
      session_id: sessionId,
      sequence: 2,
      idempotency_key: "server-answer-generated-error-0001",
      correlation_id: "00000000-0000-7000-8000-000000000438",
      sent_at: "2026-08-23T10:00:00Z",
      payload: {
        code: "AUTOMATED_ANSWER_GENERATION_UNAVAILABLE",
        message: "질문에 맞는 자동 답변을 준비하지 못했습니다.",
        retryable: true,
      },
    });

    await expect(answerPromise).rejects.toThrow(
      "질문에 맞는 자동 답변을 준비하지 못했습니다.",
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
      payload: {
        text: "확정 자막 실시간 자막",
        committed_text: "확정 자막",
        interim_text: "실시간 자막",
      },
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
    expect(onTranscript).toHaveBeenCalledWith("확정 자막 실시간 자막", false, {
      committedText: "확정 자막",
      interimText: "실시간 자막",
    });
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

  it("announces the closing message before session completion", () => {
    const socket = new FakeSocket();
    const store = createInterviewSessionStore();
    const onSessionClosing = vi.fn();
    const client = new InterviewProtocolClient({
      sessionId: "00000000-0000-7000-8000-000000000421",
      socketFactory: () => socket,
      store,
      onQuestion: vi.fn(),
      onSessionClosing,
    });
    client.connect();
    socket.open();

    socket.serverMessage({
      protocol_version: "1.0",
      message_type: "session.closing",
      session_id: "00000000-0000-7000-8000-000000000421",
      sequence: 9,
      idempotency_key: "server-closing-0001",
      correlation_id: "00000000-0000-7000-8000-000000000422",
      sent_at: "2026-08-15T10:00:02Z",
      payload: {
        text: "답변 감사합니다. 오늘 면접은 여기까지입니다.",
        audio_stream: true,
      },
    });

    expect(onSessionClosing).toHaveBeenCalledWith({
      text: "답변 감사합니다. 오늘 면접은 여기까지입니다.",
      audioStream: true,
    });
    expect(store.getState().state).not.toBe("completed");
  });
});
