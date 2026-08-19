import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type MutableRefObject,
} from "react";

import type { InterviewerLevel } from "./Avatar";
import { InterviewRoom } from "./InterviewRoom";
import {
  ChunkedRecorder,
  IndexedDbMediaBuffer,
  PcmAudioWorkletCapture,
  type LocalMediaBuffer,
  type StoredMediaChunk,
} from "./media";
import { InterviewProtocolClient, type SocketLike } from "./protocolClient";
import { createInterviewSessionStore } from "./sessionStore";

export interface RecordingUploadApi {
  upload(chunk: StoredMediaChunk): Promise<void>;
}

type ProtocolClient = Pick<
  InterviewProtocolClient,
  | "connect"
  | "disconnect"
  | "completeAnswer"
  | "sendAudioFrame"
  | "repeatQuestion"
>;

type Recorder = Pick<ChunkedRecorder, "start" | "stop">;
type AudioCapture = Pick<PcmAudioWorkletCapture, "start" | "stop">;

export type InterviewSessionDependencies = Readonly<{
  socketFactory(): SocketLike;
  mediaDevices: Pick<MediaDevices, "getUserMedia">;
  mediaBuffer: LocalMediaBuffer;
  createRecorder(
    sessionId: string,
    buffer: LocalMediaBuffer,
    onChunk: (chunk: StoredMediaChunk) => Promise<void>,
  ): Recorder;
  createAudioCapture(): AudioCapture;
  createProtocolClient(input: {
    sessionId: string;
    equipmentCheckId?: string;
    socketFactory(): SocketLike;
    store: ReturnType<typeof createInterviewSessionStore>;
    onQuestion(question: {
      questionTurnId: string;
      text: string;
      textOnly: boolean;
    }): void;
  }): ProtocolClient;
}>;

export function InterviewSession({
  sessionId,
  equipmentCheckId,
  websocketUrl,
  recordingApi,
  interviewerLevel,
  dependencies,
  onComplete,
}: {
  sessionId: string;
  equipmentCheckId: string;
  websocketUrl: string;
  recordingApi: RecordingUploadApi;
  interviewerLevel?: InterviewerLevel;
  dependencies?: Partial<InterviewSessionDependencies>;
  onComplete?: () => void;
}) {
  const store = useMemo(() => createInterviewSessionStore(), []);
  const snapshot = useSyncExternalStore(
    store.subscribe,
    store.getState,
    store.getInitialState,
  );
  const [question, setQuestion] = useState("질문을 준비하고 있습니다.");
  const [questionTurnId, setQuestionTurnId] = useState<string | null>(null);
  const mediaBuffer = useMemo(
    () => dependencies?.mediaBuffer ?? new IndexedDbMediaBuffer(),
    [dependencies?.mediaBuffer],
  );
  const clientRef = useRef<ProtocolClient | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<Recorder | null>(null);
  const audioCaptureRef = useRef<AudioCapture | null>(null);
  const answerTurnIdRef = useRef<string | null>(null);
  const audioSequenceRef = useRef(0);
  const lastRecordingSequenceRef = useRef(0);
  const completionNotifiedRef = useRef(false);

  const resolved = useMemo<InterviewSessionDependencies>(
    () => ({
      socketFactory:
        dependencies?.socketFactory ??
        (() => new WebSocket(websocketUrl) as SocketLike),
      mediaDevices: dependencies?.mediaDevices ?? navigator.mediaDevices,
      mediaBuffer,
      createRecorder:
        dependencies?.createRecorder ??
        ((activeSessionId, buffer, onChunk) =>
          new ChunkedRecorder(activeSessionId, buffer, onChunk)),
      createAudioCapture:
        dependencies?.createAudioCapture ??
        (() => new PcmAudioWorkletCapture()),
      createProtocolClient:
        dependencies?.createProtocolClient ??
        ((input) => new InterviewProtocolClient(input)),
    }),
    [dependencies, mediaBuffer, websocketUrl],
  );

  useEffect(() => {
    const client = resolved.createProtocolClient({
      sessionId,
      equipmentCheckId,
      socketFactory: resolved.socketFactory,
      store,
      onQuestion(nextQuestion) {
        setQuestion(nextQuestion.text);
        setQuestionTurnId(nextQuestion.questionTurnId);
      },
    });
    clientRef.current = client;
    client.connect();
    return () => {
      client.disconnect();
      stopMedia(audioCaptureRef, recorderRef, streamRef, answerTurnIdRef);
    };
  }, [equipmentCheckId, resolved, sessionId, store]);

  useEffect(() => {
    if (snapshot.lastVerifiedRecordingChunkSequence === 0) return;
    void mediaBuffer.removeVerified(
      sessionId,
      snapshot.lastVerifiedRecordingChunkSequence,
    );
  }, [mediaBuffer, sessionId, snapshot.lastVerifiedRecordingChunkSequence]);

  useEffect(() => {
    const terminal =
      snapshot.state === "completed" ||
      snapshot.state === "report_generating" ||
      snapshot.state === "reviewable";
    if (!terminal || completionNotifiedRef.current) return;
    completionNotifiedRef.current = true;
    onComplete?.();
  }, [onComplete, snapshot.state]);

  async function uploadChunk(chunk: StoredMediaChunk): Promise<void> {
    store.getState().bufferChunk({
      sequence: chunk.sequence,
      byteSize: chunk.byteSize,
      sha256: chunk.sha256,
    });
    lastRecordingSequenceRef.current = Math.max(
      lastRecordingSequenceRef.current,
      chunk.sequence,
    );
    await recordingApi.upload(chunk);
  }

  async function replayBufferedChunks(): Promise<void> {
    const chunks = await mediaBuffer.list(sessionId);
    for (const chunk of chunks) {
      if (chunk.sequence > snapshot.lastVerifiedRecordingChunkSequence) {
        await uploadChunk(chunk);
      }
    }
  }

  async function startAnswer(): Promise<void> {
    if (streamRef.current) return;
    const stream = await resolved.mediaDevices.getUserMedia({
      audio: true,
      video: true,
    });
    streamRef.current = stream;
    answerTurnIdRef.current = crypto.randomUUID();
    audioSequenceRef.current = 0;

    const recorder = resolved.createRecorder(
      sessionId,
      mediaBuffer,
      uploadChunk,
    );
    recorderRef.current = recorder;
    recorder.start(stream);

    const audioCapture = resolved.createAudioCapture();
    audioCaptureRef.current = audioCapture;
    await audioCapture.start(stream, (frame) => {
      const answerTurnId = answerTurnIdRef.current;
      if (!answerTurnId) return;
      audioSequenceRef.current += 1;
      const chunkSequence = audioSequenceRef.current;
      void sha256Hex(frame).then((sha256) => {
        clientRef.current?.sendAudioFrame({
          answerTurnId,
          chunkSequence,
          sha256,
          frame,
        });
      });
    });
  }

  async function completeAnswer(): Promise<void> {
    const answerTurnId = answerTurnIdRef.current;
    if (!answerTurnId) return;
    await stopMedia(audioCaptureRef, recorderRef, streamRef, answerTurnIdRef);
    clientRef.current?.completeAnswer({
      answerTurnId,
      lastAudioChunkSequence: audioSequenceRef.current,
      lastRecordingChunkSequence: lastRecordingSequenceRef.current,
    });
  }

  function reconnect(): void {
    clientRef.current?.connect();
    void replayBufferedChunks();
  }

  function addExplanation(): void {
    if (questionTurnId) {
      clientRef.current?.repeatQuestion(questionTurnId, "clarify");
    }
  }

  return (
    <InterviewRoom
      question={question}
      state={snapshot.state}
      connectionState={snapshot.connectionState}
      textOnly={snapshot.degradedModes.includes("text_only")}
      interviewerLevel={interviewerLevel}
      onStartAnswer={() => void startAnswer()}
      onCompleteAnswer={() => void completeAnswer()}
      onReconnect={reconnect}
      onAddExplanation={questionTurnId ? addExplanation : undefined}
    />
  );
}

async function stopMedia(
  audioCaptureRef: MutableRefObject<AudioCapture | null>,
  recorderRef: MutableRefObject<Recorder | null>,
  streamRef: MutableRefObject<MediaStream | null>,
  answerTurnIdRef: MutableRefObject<string | null>,
): Promise<void> {
  recorderRef.current?.stop();
  recorderRef.current = null;
  await audioCaptureRef.current?.stop();
  audioCaptureRef.current = null;
  for (const track of streamRef.current?.getTracks() ?? []) track.stop();
  streamRef.current = null;
  answerTurnIdRef.current = null;
}

async function sha256Hex(frame: Int16Array): Promise<string> {
  const bytes = new Uint8Array(frame.byteLength);
  bytes.set(new Uint8Array(frame.buffer, frame.byteOffset, frame.byteLength));
  const digest = await crypto.subtle.digest("SHA-256", bytes.buffer);
  return Array.from(new Uint8Array(digest))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}
