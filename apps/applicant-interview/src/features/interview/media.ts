export type StoredMediaChunk = Readonly<{
  sessionId: string;
  sequence: number;
  blob: Blob;
  byteSize: number;
  sha256: string;
  sessionStartMs: number;
  sessionEndMs: number;
}>;

export interface LocalMediaBuffer {
  put(chunk: StoredMediaChunk): Promise<void>;
  list(sessionId: string): Promise<StoredMediaChunk[]>;
  removeVerified(sessionId: string, sequence: number): Promise<void>;
}

const DB_NAME = "iep-interview-media";
const STORE_NAME = "recording-chunks";

export class IndexedDbMediaBuffer implements LocalMediaBuffer {
  async put(chunk: StoredMediaChunk): Promise<void> {
    const database = await openDatabase();
    await transactionPromise(database, "readwrite", (store) =>
      store.put(chunk, `${chunk.sessionId}:${chunk.sequence}`),
    );
  }

  async list(sessionId: string): Promise<StoredMediaChunk[]> {
    const database = await openDatabase();
    const values = await requestPromise<StoredMediaChunk[]>(
      database
        .transaction(STORE_NAME, "readonly")
        .objectStore(STORE_NAME)
        .getAll(),
    );
    return values
      .filter((chunk) => chunk.sessionId === sessionId)
      .sort((left, right) => left.sequence - right.sequence);
  }

  async removeVerified(sessionId: string, sequence: number): Promise<void> {
    const database = await openDatabase();
    const chunks = await this.list(sessionId);
    await transactionPromise(database, "readwrite", (store) => {
      for (const chunk of chunks) {
        if (chunk.sequence <= sequence) {
          store.delete(`${chunk.sessionId}:${chunk.sequence}`);
        }
      }
    });
  }
}

export class ChunkedRecorder {
  private recorder: MediaRecorder | null = null;
  private sequence = 0;
  private startedAt = 0;

  constructor(
    private readonly sessionId: string,
    private readonly buffer: LocalMediaBuffer,
    private readonly onChunk: (chunk: StoredMediaChunk) => Promise<void>,
  ) {}

  start(stream: MediaStream, timesliceMs = 2000): void {
    this.startedAt = performance.now();
    this.recorder = new MediaRecorder(stream);
    this.recorder.addEventListener("dataavailable", (event) => {
      void this.persist(event.data);
    });
    this.recorder.start(timesliceMs);
  }

  stop(): void {
    this.recorder?.stop();
    this.recorder = null;
  }

  private async persist(blob: Blob): Promise<void> {
    if (blob.size === 0) return;
    const start = Math.round(performance.now() - this.startedAt);
    this.sequence += 1;
    const digest = await crypto.subtle.digest(
      "SHA-256",
      await blob.arrayBuffer(),
    );
    const sha256 = Array.from(new Uint8Array(digest))
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("");
    const chunk: StoredMediaChunk = {
      sessionId: this.sessionId,
      sequence: this.sequence,
      blob,
      byteSize: blob.size,
      sha256,
      sessionStartMs: Math.max(0, start - 2000),
      sessionEndMs: start,
    };
    await this.buffer.put(chunk);
    await this.onChunk(chunk);
  }
}

export class PcmAudioWorkletCapture {
  private context: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private processor: AudioWorkletNode | null = null;

  async start(
    stream: MediaStream,
    onPcmFrame: (frame: Int16Array) => void,
  ): Promise<void> {
    this.context = new AudioContext({ sampleRate: 16000 });
    await this.context.audioWorklet.addModule(
      new URL("./pcmCapture.worklet.js", import.meta.url),
    );
    this.source = this.context.createMediaStreamSource(stream);
    this.processor = new AudioWorkletNode(this.context, "iep-pcm-capture", {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      outputChannelCount: [1],
    });
    this.processor.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
      onPcmFrame(new Int16Array(event.data));
    };
    this.source.connect(this.processor);
    this.processor.connect(this.context.destination);
  }

  async stop(): Promise<void> {
    this.processor?.disconnect();
    this.source?.disconnect();
    await this.context?.close();
    this.processor = null;
    this.source = null;
    this.context = null;
  }
}

export class PcmFrameBatcher {
  private pending = new Int16Array(0);

  constructor(
    private readonly targetSamples: number,
    private readonly onFrame: (frame: Int16Array) => void,
  ) {}

  push(frame: Int16Array): void {
    const combined = new Int16Array(this.pending.length + frame.length);
    combined.set(this.pending);
    combined.set(frame, this.pending.length);
    let offset = 0;
    while (combined.length - offset >= this.targetSamples) {
      this.onFrame(combined.slice(offset, offset + this.targetSamples));
      offset += this.targetSamples;
    }
    this.pending = combined.slice(offset);
  }

  flush(): void {
    if (this.pending.length > 0) this.onFrame(this.pending);
    this.pending = new Int16Array(0);
  }
}

export type AudioPlaybackState = "idle" | "playing";

export class PcmAudioWorkletPlayer {
  private context: AudioContext | null = null;
  private player: AudioWorkletNode | null = null;

  async start(
    sampleRateHz: number,
    onStateChange: (state: AudioPlaybackState) => void,
  ): Promise<void> {
    await this.stop();
    this.context = new AudioContext({ sampleRate: sampleRateHz });
    await this.context.audioWorklet.addModule(
      new URL("./ttsPlayback.worklet.js", import.meta.url),
    );
    this.player = new AudioWorkletNode(this.context, "iep-tts-playback", {
      numberOfInputs: 0,
      numberOfOutputs: 1,
      outputChannelCount: [1],
    });
    this.player.port.onmessage = (
      event: MessageEvent<{ type?: "playing" | "ended" }>,
    ) => {
      if (event.data.type === "playing") onStateChange("playing");
      if (event.data.type === "ended") onStateChange("idle");
    };
    this.player.connect(this.context.destination);
    await this.context.resume();
  }

  enqueue(chunk: ArrayBuffer): void {
    if (!this.player) return;
    const copy = chunk.slice(0);
    this.player.port.postMessage({ type: "chunk", chunk: copy }, [copy]);
  }

  end(): void {
    this.player?.port.postMessage({ type: "end" });
  }

  async stop(): Promise<void> {
    this.player?.disconnect();
    await this.context?.close();
    this.player = null;
    this.context = null;
  }
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.addEventListener("upgradeneeded", () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        request.result.createObjectStore(STORE_NAME);
      }
    });
    request.addEventListener("success", () => resolve(request.result));
    request.addEventListener("error", () => reject(request.error));
  });
}

function requestPromise<Result>(request: IDBRequest<Result>): Promise<Result> {
  return new Promise((resolve, reject) => {
    request.addEventListener("success", () => resolve(request.result));
    request.addEventListener("error", () => reject(request.error));
  });
}

function transactionPromise(
  database: IDBDatabase,
  mode: IDBTransactionMode,
  operation: (store: IDBObjectStore) => IDBRequest | void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, mode);
    operation(transaction.objectStore(STORE_NAME));
    transaction.addEventListener("complete", () => resolve());
    transaction.addEventListener("error", () => reject(transaction.error));
  });
}
