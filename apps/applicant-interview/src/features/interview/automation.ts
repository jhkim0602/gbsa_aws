export type AutomatedInterviewMode = "fast" | "speech" | "entry-low";

export type AutomatedAnswerProfile = "standard" | "entry_low";

export function automatedAnswerProfile(
  mode: AutomatedInterviewMode,
): AutomatedAnswerProfile {
  return mode === "entry-low" ? "entry_low" : "standard";
}

export type AutomatedMedia = Readonly<{
  stream: MediaStream;
  dispose(): void;
}>;

export async function createAutomatedMedia(
  label: string,
): Promise<AutomatedMedia> {
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 360;
  const context = canvas.getContext("2d");
  if (!context || typeof canvas.captureStream !== "function") {
    throw new Error("automated recording is not supported by this browser");
  }
  let frame = 0;
  const draw = () => {
    frame += 1;
    context.fillStyle = "#f2f3ff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#4653bd";
    context.font = "bold 26px sans-serif";
    context.fillText("LOCAL AUTOMATED INTERVIEW", 42, 82);
    context.fillStyle = "#1a1f36";
    context.font = "18px sans-serif";
    wrapText(context, label, 42, 132, 550, 30);
    context.fillStyle = "#5966ce";
    context.beginPath();
    context.arc(52 + (frame % 520), 316, 8, 0, Math.PI * 2);
    context.fill();
  };
  draw();
  const timer = window.setInterval(draw, 100);
  const stream = canvas.captureStream(10);
  return {
    stream,
    dispose() {
      window.clearInterval(timer);
      for (const track of stream.getTracks()) track.stop();
    },
  };
}

export async function sendAutomatedPcm(
  pcm: Int16Array,
  send: (frame: Int16Array) => void,
): Promise<void> {
  const packetSamples = 640;
  for (let offset = 0; offset < pcm.length; offset += packetSamples) {
    send(pcm.slice(offset, offset + packetSamples));
    await delay((packetSamples / 16_000) * 1000);
  }
}

export function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export function resampleAutomatedPcm(
  input: Int16Array,
  inputSampleRate: number,
  outputSampleRate = 16_000,
): Int16Array {
  if (input.length === 0) return input;
  if (inputSampleRate === outputSampleRate) return input;
  const outputLength = Math.max(
    1,
    Math.round(input.length * (outputSampleRate / inputSampleRate)),
  );
  const output = new Int16Array(outputLength);
  for (let index = 0; index < outputLength; index += 1) {
    const position = index * (inputSampleRate / outputSampleRate);
    const left = Math.floor(position);
    const right = Math.min(input.length - 1, left + 1);
    const ratio = position - left;
    const sample = input[left] * (1 - ratio) + input[right] * ratio;
    output[index] = Math.round(Math.max(-32768, Math.min(32767, sample)));
  }
  return output;
}

function wrapText(
  context: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
) {
  const words = text.split(/\s+/);
  let line = "";
  let lineY = y;
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (context.measureText(candidate).width > maxWidth && line) {
      context.fillText(line, x, lineY);
      line = word;
      lineY += lineHeight;
    } else {
      line = candidate;
    }
  }
  if (line) context.fillText(line, x, lineY);
}
