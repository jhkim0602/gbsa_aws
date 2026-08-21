import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type MutableRefObject,
} from "react";

import type { InterviewerLevel } from "./Avatar";
import {
  automatedAnswer,
  createAutomatedMedia,
  delay,
  loadAutomatedPcm,
  sendAutomatedPcm,
  type AutomatedInterviewMode,
  type AutomatedMedia,
} from "./automation";
import { InterviewRoom } from "./InterviewRoom";
import {
  ChunkedRecorder,
  IndexedDbMediaBuffer,
  PcmAudioWorkletCapture,
  PcmAudioWorkletPlayer,
  PcmFrameBatcher,
  type AudioPlaybackState,
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
  | "startAnswer"
  | "sendAudioFrame"
  | "repeatQuestion"
  | "submitAutomatedAnswer"
>;

type Recorder = Readonly<{
  start(stream: MediaStream): void;
  stop(): void | Promise<void>;
}>;
type AudioCapture = Pick<PcmAudioWorkletCapture, "start" | "stop">;
type AudioPlayer = Pick<
  PcmAudioWorkletPlayer,
  "start" | "enqueue" | "end" | "stop"
>;

export type InterviewSessionDependencies = Readonly<{
  socketFactory(): SocketLike;
  mediaDevices: Pick<MediaDevices, "getUserMedia">;
  mediaBuffer: LocalMediaBuffer;
  createRecorder(
    sessionId: string,
    buffer: LocalMediaBuffer,
    onChunk: (chunk: StoredMediaChunk) => Promise<void>,
    initialSequence: number,
    initialSessionStartMs: number,
  ): Recorder;
  createAudioCapture(): AudioCapture;
  createAudioPlayer(): AudioPlayer;
  createAutomatedMedia(label: string): Promise<AutomatedMedia>;
  loadAutomatedPcm(): Promise<Int16Array>;
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
    onTranscript?(text: string, isFinal: boolean): void;
    onQuestionAudioStart?(format: { sampleRateHz: number }): void;
    onQuestionAudioChunk?(chunk: ArrayBuffer): void;
    onQuestionAudioEnd?(): void;
    onQuestionAudioError?(): void;
  }): ProtocolClient;
}>;

export function InterviewSession({
  sessionId,
  equipmentCheckId,
  websocketUrl,
  recordingApi,
  interviewerLevel,
  dependencies,
  automationMode,
  onComplete,
}: {
  sessionId: string;
  equipmentCheckId: string;
  websocketUrl: string;
  recordingApi: RecordingUploadApi;
  interviewerLevel?: InterviewerLevel;
  dependencies?: Partial<InterviewSessionDependencies>;
  automationMode?: AutomatedInterviewMode;
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
  const [transcript, setTranscript] = useState("");
  const [interviewerSpeaking, setInterviewerSpeaking] = useState(false);
  const [questionPlaybackComplete, setQuestionPlaybackComplete] =
    useState(false);
  const [automationStatus, setAutomationStatus] = useState("");
  const [automationRunVersion, setAutomationRunVersion] = useState(0);
  const mediaBuffer = useMemo(
    () => dependencies?.mediaBuffer ?? new IndexedDbMediaBuffer(),
    [dependencies?.mediaBuffer],
  );
  const clientRef = useRef<ProtocolClient | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<Recorder | null>(null);
  const audioCaptureRef = useRef<AudioCapture | null>(null);
  const answerTurnIdRef = useRef<string | null>(null);
  const audioBatcherRef = useRef<PcmFrameBatcher | null>(null);
  const audioSendChainRef = useRef<Promise<void>>(Promise.resolve());
  const audioPlayerRef = useRef<AudioPlayer | null>(null);
  const audioPlaybackChainRef = useRef<Promise<void>>(Promise.resolve());
  const audioSequenceRef = useRef(0);
  const lastRecordingSequenceRef = useRef(0);
  const lastRecordingEndMsRef = useRef(0);
  const completionNotifiedRef = useRef(false);
  const automatedQuestionRef = useRef<string | null>(null);
  const automatedAnswerIndexRef = useRef(0);
  const automationRunningRef = useRef(false);
  const reconnectRunningRef = useRef(false);
  const automatedMediaRef = useRef<AutomatedMedia | null>(null);

  const resolved = useMemo<InterviewSessionDependencies>(
    () => ({
      socketFactory:
        dependencies?.socketFactory ??
        (() => new WebSocket(websocketUrl) as SocketLike),
      mediaDevices: dependencies?.mediaDevices ?? navigator.mediaDevices,
      mediaBuffer,
      createRecorder:
        dependencies?.createRecorder ??
        ((
          activeSessionId,
          buffer,
          onChunk,
          initialSequence,
          initialSessionStartMs,
        ) =>
          new ChunkedRecorder(
            activeSessionId,
            buffer,
            onChunk,
            initialSequence,
            initialSessionStartMs,
          )),
      createAudioCapture:
        dependencies?.createAudioCapture ??
        (() => new PcmAudioWorkletCapture()),
      createAudioPlayer:
        dependencies?.createAudioPlayer ?? (() => new PcmAudioWorkletPlayer()),
      createAutomatedMedia:
        dependencies?.createAutomatedMedia ?? createAutomatedMedia,
      loadAutomatedPcm: dependencies?.loadAutomatedPcm ?? loadAutomatedPcm,
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
        setQuestionPlaybackComplete(nextQuestion.textOnly);
        if (nextQuestion.textOnly) setInterviewerSpeaking(false);
      },
      onTranscript(text) {
        setTranscript(text);
      },
      onQuestionAudioStart(format) {
        setQuestionPlaybackComplete(false);
        const player = audioPlayerRef.current ?? resolved.createAudioPlayer();
        audioPlayerRef.current = player;
        audioPlaybackChainRef.current = audioPlaybackChainRef.current
          .catch(() => undefined)
          .then(() =>
            player.start(format.sampleRateHz, (state: AudioPlaybackState) => {
              setInterviewerSpeaking(state === "playing");
              if (state === "idle") setQuestionPlaybackComplete(true);
            }),
          )
          .catch(() => {
            setInterviewerSpeaking(false);
            setQuestionPlaybackComplete(true);
          });
      },
      onQuestionAudioChunk(chunk) {
        audioPlaybackChainRef.current = audioPlaybackChainRef.current
          .catch(() => undefined)
          .then(() => {
            audioPlayerRef.current?.enqueue(chunk);
          });
      },
      onQuestionAudioEnd() {
        audioPlaybackChainRef.current = audioPlaybackChainRef.current
          .catch(() => undefined)
          .then(() => {
            audioPlayerRef.current?.end();
          });
      },
      onQuestionAudioError() {
        setInterviewerSpeaking(false);
        setQuestionPlaybackComplete(true);
        audioPlaybackChainRef.current = audioPlaybackChainRef.current
          .catch(() => undefined)
          .then(() => audioPlayerRef.current?.stop());
      },
    });
    clientRef.current = client;
    client.connect();
    return () => {
      client.disconnect();
      stopMedia(audioCaptureRef, recorderRef, streamRef, answerTurnIdRef);
      automatedMediaRef.current?.dispose();
      void audioPlayerRef.current?.stop();
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

  useEffect(() => {
    if (
      !automationMode ||
      snapshot.connectionState !== "connected" ||
      snapshot.state !== "awaiting_answer" ||
      !questionTurnId ||
      !questionPlaybackComplete ||
      automatedQuestionRef.current === questionTurnId ||
      automationRunningRef.current
    ) {
      return;
    }
    automatedQuestionRef.current = questionTurnId;
    automationRunningRef.current = true;
    void runAutomatedAnswer()
      .catch((error: unknown) => {
        automatedQuestionRef.current = null;
        automationRunningRef.current = false;
        setAutomationStatus(
          error instanceof Error
            ? `자동 면접 오류: ${error.message}`
            : "자동 면접을 계속 진행할 수 없습니다.",
        );
        clientRef.current?.disconnect();
      })
      .finally(() => {
        automationRunningRef.current = false;
        setAutomationRunVersion((version) => version + 1);
      });
  }, [
    automationMode,
    automationRunVersion,
    questionPlaybackComplete,
    questionTurnId,
    snapshot.connectionState,
    snapshot.state,
  ]);

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
    lastRecordingEndMsRef.current = Math.max(
      lastRecordingEndMsRef.current,
      chunk.sessionEndMs,
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
    if (streamRef.current || !questionPlaybackComplete) return;
    const stream = await resolved.mediaDevices.getUserMedia({
      audio: true,
      video: true,
    });
    streamRef.current = stream;
    answerTurnIdRef.current = crypto.randomUUID();
    audioSequenceRef.current = 0;
    audioSendChainRef.current = Promise.resolve();
    setTranscript("");
    clientRef.current?.startAnswer({
      answerTurnId: answerTurnIdRef.current,
      sampleRateHz: 16000,
    });

    const recorder = resolved.createRecorder(
      sessionId,
      mediaBuffer,
      uploadChunk,
      lastRecordingSequenceRef.current,
      lastRecordingEndMsRef.current,
    );
    recorderRef.current = recorder;
    recorder.start(stream);

    const audioCapture = resolved.createAudioCapture();
    audioCaptureRef.current = audioCapture;
    audioBatcherRef.current = new PcmFrameBatcher(640, queueAudioFrame);
    await audioCapture.start(stream, (frame) => {
      audioBatcherRef.current?.push(frame);
    });
  }

  function queueAudioFrame(frame: Int16Array): void {
    const answerTurnId = answerTurnIdRef.current;
    if (!answerTurnId) return;
    audioSequenceRef.current += 1;
    const chunkSequence = audioSequenceRef.current;
    audioSendChainRef.current = audioSendChainRef.current.then(async () => {
      const sha256 = await sha256Hex(frame);
      clientRef.current?.sendAudioFrame({
        answerTurnId,
        chunkSequence,
        sha256,
        frame,
      });
    });
  }

  async function completeAnswer(): Promise<void> {
    const answerTurnId = answerTurnIdRef.current;
    if (!answerTurnId) return;
    await recorderRef.current?.stop();
    recorderRef.current = null;
    await audioCaptureRef.current?.stop();
    audioCaptureRef.current = null;
    audioBatcherRef.current?.flush();
    audioBatcherRef.current = null;
    await audioSendChainRef.current;
    for (const track of streamRef.current?.getTracks() ?? []) track.stop();
    streamRef.current = null;
    answerTurnIdRef.current = null;
    clientRef.current?.completeAnswer({
      answerTurnId,
      lastAudioChunkSequence: audioSequenceRef.current,
      lastRecordingChunkSequence: lastRecordingSequenceRef.current,
    });
  }

  async function runAutomatedAnswer(): Promise<void> {
    if (!automationMode) return;
    await delay(900);
    const answerIndex = automatedAnswerIndexRef.current;
    const answer = automatedAnswer(question, answerIndex);
    setTranscript(answer);
    setAutomationStatus(
      automationMode === "speech"
        ? `음성 자동 답변 ${answerIndex + 1}개를 전송하고 있습니다.`
        : `빠른 자동 답변 ${answerIndex + 1}개를 처리하고 있습니다.`,
    );

    const media = await resolved.createAutomatedMedia(answer);
    automatedMediaRef.current = media;
    let recorder: Recorder | null = null;
    let recorderStopped = false;
    try {
      streamRef.current = media.stream;
      const answerTurnId = crypto.randomUUID();
      answerTurnIdRef.current = answerTurnId;
      audioSequenceRef.current = 0;
      audioSendChainRef.current = Promise.resolve();
      if (automationMode === "speech") {
        clientRef.current?.startAnswer({ answerTurnId, sampleRateHz: 16000 });
      }

      recorder = resolved.createRecorder(
        sessionId,
        mediaBuffer,
        uploadChunk,
        lastRecordingSequenceRef.current,
        lastRecordingEndMsRef.current,
      );
      recorderRef.current = recorder;
      recorder.start(media.stream);

      if (automationMode === "speech") {
        const pcm = await resolved.loadAutomatedPcm();
        await sendAutomatedPcm(pcm, queueAudioFrame);
      } else {
        await delay(2200);
      }

      await recorder.stop();
      recorderStopped = true;
      recorderRef.current = null;
      await audioSendChainRef.current;

      if (automationMode === "speech") {
        clientRef.current?.completeAnswer({
          answerTurnId,
          lastAudioChunkSequence: audioSequenceRef.current,
          lastRecordingChunkSequence: lastRecordingSequenceRef.current,
        });
      } else {
        clientRef.current?.submitAutomatedAnswer({
          answerTurnId,
          text: answer,
          lastRecordingChunkSequence: lastRecordingSequenceRef.current,
        });
      }
      automatedAnswerIndexRef.current += 1;
    } finally {
      if (recorder && !recorderStopped) {
        await Promise.resolve(recorder.stop()).catch(() => undefined);
      }
      recorderRef.current = null;
      streamRef.current = null;
      answerTurnIdRef.current = null;
      media.dispose();
      automatedMediaRef.current = null;
    }
  }

  function reconnect(): void {
    if (reconnectRunningRef.current) return;
    reconnectRunningRef.current = true;
    if (automationMode) {
      setAutomationStatus("저장된 녹화를 복구한 뒤 다시 연결합니다.");
    }
    void replayBufferedChunks()
      .then(() => {
        clientRef.current?.connect();
      })
      .catch((error: unknown) => {
        if (automationMode) {
          setAutomationStatus(
            error instanceof Error
              ? `녹화 복구 오류: ${error.message}`
              : "저장된 녹화를 복구할 수 없습니다.",
          );
        }
      })
      .finally(() => {
        reconnectRunningRef.current = false;
      });
  }

  function addExplanation(): void {
    if (questionTurnId) {
      setQuestionPlaybackComplete(false);
      clientRef.current?.repeatQuestion(questionTurnId, "clarify");
    }
  }

  return (
    <>
      {automationMode ? (
        <p
          className="fixed top-3 left-1/2 z-200 -translate-x-1/2 rounded-full bg-brand-strong px-4 py-2 text-[11px] font-semibold text-white shadow-lg"
          role="status"
        >
          {automationStatus || "자동 면접을 준비하고 있습니다."}
        </p>
      ) : null}
      <InterviewRoom
        question={question}
        transcript={transcript}
        interviewerSpeaking={interviewerSpeaking}
        questionInProgress={!questionPlaybackComplete}
        state={snapshot.state}
        connectionState={snapshot.connectionState}
        textOnly={snapshot.degradedModes.includes("text_only")}
        interviewerLevel={interviewerLevel}
        onStartAnswer={() => void startAnswer()}
        onCompleteAnswer={() => void completeAnswer()}
        onReconnect={reconnect}
        onAddExplanation={questionTurnId ? addExplanation : undefined}
      />
    </>
  );
}

async function stopMedia(
  audioCaptureRef: MutableRefObject<AudioCapture | null>,
  recorderRef: MutableRefObject<Recorder | null>,
  streamRef: MutableRefObject<MediaStream | null>,
  answerTurnIdRef: MutableRefObject<string | null>,
): Promise<void> {
  await recorderRef.current?.stop();
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
