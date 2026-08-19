import { useState } from "react";

export type EquipmentStatus = "ready" | "warning" | "failed";

export type EquipmentComponentResult = Readonly<{
  status: EquipmentStatus;
  sanitizedCode?: string;
}>;

export type EquipmentCheckResult = Readonly<{
  camera: EquipmentComponentResult;
  microphone: EquipmentComponentResult;
  network: EquipmentComponentResult;
  overallStatus: EquipmentStatus;
}>;

export type EquipmentCheckApi = {
  check(): Promise<EquipmentCheckResult>;
};

// `.applicant-content > .interview-shell:not(.interview-room)` (0,3,0) outranks
// `.applicant-content > main:not(.interview-room)` (0,2,1) in shell.css, so the 920px /
// 56px-88px block wins at every width. Same string as InterviewComplete.
const SHELL =
  "mx-auto w-[min(calc(100%-48px),920px)] bg-canvas py-[56px] pb-[88px] text-ink" +
  " max-[680px]:w-[min(calc(100%-32px),920px)] max-[680px]:py-[38px] max-[680px]:pb-[64px]";

const EYEBROW =
  "mb-2 font-[ui-monospace,SFMono-Regular,Consolas,monospace] text-[11px]" +
  " font-semibold text-muted";

// `.interview-header > p:not(.interview-brand)` is (0,2,1), which outranks
// `.interview-header > .equipment-assurance` (0,2,0) despite coming first, so the assurance
// line has always rendered with the sibling paragraph's 9px margin and muted color rather
// than its own `margin-top: 3px` / `--applicant-text`. Kept as it renders.
const HEADER_COPY =
  "mt-[9px] max-w-[620px] text-[14px] leading-[1.65] text-muted";

const PREVIEW =
  "group grid min-h-[220px] place-items-center rounded-panel border border-border" +
  " bg-surface shadow-soft data-[status=ready]:border-[#82d39a]" +
  " data-[status=ready]:bg-[#f0fff4] max-[680px]:min-h-[180px]";

const PREVIEW_LABEL =
  "font-[ui-monospace,SFMono-Regular,Consolas,monospace] text-[11px] tracking-normal" +
  " text-subtle group-data-[status=ready]:text-success";

const PANEL =
  "grid content-center rounded-panel border border-border bg-surface px-[18px] py-3" +
  " shadow-soft";

const ROW =
  "grid min-h-[62px] grid-cols-[10px_1fr] items-center gap-3 border-b border-b-border" +
  " last:border-b-0";

const STATUS_DOT =
  "size-2 rounded-full bg-border data-[status=ready]:bg-success" +
  " data-[status=warning]:bg-[#bf8700] data-[status=failed]:bg-danger";

const STATUS_TEXT =
  "text-[12px] font-medium text-muted data-[status=ready]:text-success" +
  " data-[status=warning]:text-warning data-[status=failed]:text-danger";

const NOTICE =
  "mt-3 rounded-panel border border-[#dfe2ff] bg-brand-soft px-[13px] py-[11px]" +
  " text-[12px] leading-[1.55] text-muted";

// `.interview-actions button`; the color trio lives on each variant so no two conflicting
// utilities ever land on the same element.
const ACTION_BUTTON =
  "inline-flex min-h-11 items-center justify-center rounded-panel border px-4" +
  " text-[13px] font-[650] disabled:opacity-45 max-[680px]:flex-[1_1_0]";

const BUTTON_SECONDARY = `${ACTION_BUTTON} border-border bg-surface text-ink`;

const BUTTON_PRIMARY = `${ACTION_BUTTON} border-brand bg-brand text-white`;

const LABELS = {
  camera: {
    ready: "카메라 준비됨",
    warning: "카메라 확인 필요",
    failed: "카메라 사용 불가",
  },
  microphone: {
    ready: "마이크 준비됨",
    warning: "마이크 확인 필요",
    failed: "마이크 사용 불가",
  },
  network: {
    ready: "네트워크 준비됨",
    warning: "네트워크 확인 필요",
    failed: "네트워크 연결 불가",
  },
} as const;

export function EquipmentCheck({
  api,
  onReady,
}: {
  api: EquipmentCheckApi;
  onReady(result: EquipmentCheckResult): void;
}) {
  const [result, setResult] = useState<EquipmentCheckResult | null>(null);
  const [checking, setChecking] = useState(false);

  async function check() {
    setChecking(true);
    try {
      setResult(await api.check());
    } finally {
      setChecking(false);
    }
  }

  return (
    <main className={SHELL}>
      <header className="mb-6">
        <p className={EYEBROW}>STEP 2 OF 4</p>
        <h1 className="text-[26px] leading-[1.35] tracking-normal max-[680px]:text-[22px]">
          면접 환경 점검
        </h1>
        <p className={HEADER_COPY}>
          카메라, 마이크, 네트워크 상태를 확인합니다.
        </p>
        <p className={HEADER_COPY}>
          기술 문제는 면접 평가에 영향을 주지 않습니다.
        </p>
      </header>

      <section className="grid grid-cols-[minmax(180px,0.75fr)_minmax(280px,1.25fr)] gap-3 max-[680px]:grid-cols-[1fr]">
        <div
          className={PREVIEW}
          data-status={result?.camera.status ?? "unknown"}
          aria-label="카메라 미리보기 상태"
        >
          <span className={PREVIEW_LABEL} aria-hidden="true">
            {result?.camera.status === "ready" ? "LIVE" : "NO SIGNAL"}
          </span>
        </div>
        <div className={PANEL} aria-live="polite">
          {(["camera", "microphone", "network"] as const).map((component) => (
            <div className={ROW} key={component}>
              <span
                className={STATUS_DOT}
                data-status={result?.[component].status ?? "unknown"}
                aria-hidden="true"
              />
              <div className="flex items-center justify-between gap-3">
                <span className="text-[14px] font-semibold">
                  {LABELS[component].ready.split(" ")[0]}
                </span>
                <strong
                  className={STATUS_TEXT}
                  data-status={result?.[component].status ?? "unknown"}
                >
                  {result
                    ? LABELS[component][result[component].status]
                    : "점검 전"}
                </strong>
              </div>
            </div>
          ))}
        </div>
      </section>

      <p className={NOTICE}>
        브라우저 권한은 장치 점검과 면접 진행에만 사용됩니다.
      </p>
      <div className="mt-4 flex justify-end gap-2 max-[680px]:w-full">
        <button type="button" className={BUTTON_SECONDARY} onClick={check}>
          {checking ? "점검 중" : "장치 점검"}
        </button>
        <button
          type="button"
          className={BUTTON_PRIMARY}
          disabled={!result || result.overallStatus === "failed"}
          onClick={() => result && onReady(result)}
        >
          면접 시작
        </button>
      </div>
    </main>
  );
}

export function createBrowserEquipmentCheckApi(): EquipmentCheckApi {
  return {
    async check() {
      let camera: EquipmentComponentResult = {
        status: "failed",
        sanitizedCode: "CAMERA_UNAVAILABLE",
      };
      let microphone: EquipmentComponentResult = {
        status: "failed",
        sanitizedCode: "MICROPHONE_UNAVAILABLE",
      };
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: true,
        });
        camera = {
          status: stream.getVideoTracks().length > 0 ? "ready" : "failed",
        };
        microphone = {
          status: stream.getAudioTracks().length > 0 ? "ready" : "failed",
        };
        stream.getTracks().forEach((track) => track.stop());
      } catch {
        // Only sanitized component codes leave the browser boundary.
      }
      const network: EquipmentComponentResult = navigator.onLine
        ? { status: "ready" }
        : { status: "failed", sanitizedCode: "NETWORK_OFFLINE" };
      const statuses = [camera.status, microphone.status, network.status];
      const overallStatus: EquipmentStatus = statuses.includes("failed")
        ? "failed"
        : statuses.includes("warning")
          ? "warning"
          : "ready";
      return { camera, microphone, network, overallStatus };
    },
  };
}
