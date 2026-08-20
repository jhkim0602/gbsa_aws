export type AutomatedInterviewMode = "fast" | "speech";

export type AutomatedMedia = Readonly<{
  stream: MediaStream;
  dispose(): void;
}>;

const ANSWERS = [
  "제가 맡았던 프로젝트에서는 먼저 문제 상황과 영향을 수치로 정리했습니다. 로그와 사용자 흐름을 비교해 원인을 좁힌 뒤, 가장 위험이 낮은 해결책부터 적용했습니다. 적용 후에는 오류율과 처리 시간을 다시 측정했고, 같은 문제가 반복되지 않도록 모니터링과 회고 문서를 남겼습니다.",
  "제 역할은 팀의 결정을 그대로 수행하는 것이 아니라 필요한 근거를 수집하고 대안을 비교하는 것이었습니다. 일정, 안정성, 유지보수 비용을 기준으로 선택지를 정리했고, 팀과 합의한 뒤 작은 범위에서 검증했습니다. 결과가 확인된 후 전체 범위로 확장했습니다.",
  "가장 어려웠던 부분은 불확실한 정보 속에서 우선순위를 정하는 일이었습니다. 사용자 영향이 큰 문제를 먼저 처리하고, 확인되지 않은 내용은 가설로 분리했습니다. 작업 결과와 실패한 시도까지 공유해서 다음 담당자가 같은 검증을 반복하지 않도록 했습니다.",
  "결과적으로 핵심 지표가 개선됐지만 단기 성과만으로 끝내지 않았습니다. 자동화된 점검 항목을 추가하고 운영 기준을 문서화했습니다. 이후 유사한 문제가 발생했을 때 탐지와 대응 시간이 줄어든 것을 확인했습니다.",
] as const;

export function automatedAnswer(question: string, index: number) {
  const base = ANSWERS[index % ANSWERS.length];
  return `${base} 질문에서 말씀하신 ${question.trim()} 부분은 당시 판단 근거와 제가 직접 수행한 행동을 중심으로 설명드릴 수 있습니다.`;
}

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
    context.fillStyle = "#eef4e7";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#547735";
    context.font = "bold 26px sans-serif";
    context.fillText("LOCAL AUTOMATED INTERVIEW", 42, 82);
    context.fillStyle = "#243019";
    context.font = "18px sans-serif";
    wrapText(context, label, 42, 132, 550, 30);
    context.fillStyle = "#82ad4e";
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

export async function loadAutomatedPcm(
  url = "/auto-interview-answer.wav",
): Promise<Int16Array> {
  const response = await fetch(url);
  if (!response.ok) throw new Error("automated answer audio is unavailable");
  const context = new AudioContext();
  try {
    const decoded = await context.decodeAudioData(await response.arrayBuffer());
    return resampleToPcm(decoded.getChannelData(0), decoded.sampleRate, 16_000);
  } finally {
    await context.close();
  }
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

function resampleToPcm(
  input: Float32Array,
  inputSampleRate: number,
  outputSampleRate: number,
): Int16Array {
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
    output[index] = Math.round(Math.max(-1, Math.min(1, sample)) * 32767);
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
