import { useState } from "react";

import "./interview.css";

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
    <main className="interview-shell">
      <header className="interview-header">
        <p className="interview-brand">GBSA Interview Evidence</p>
        <h1>면접 환경 점검</h1>
        <p>카메라, 마이크, 네트워크 상태를 확인합니다.</p>
      </header>

      <section className="equipment-panel" aria-live="polite">
        {(["camera", "microphone", "network"] as const).map((component) => (
          <div className="equipment-row" key={component}>
            <span>{LABELS[component].ready.split(" ")[0]}</span>
            <strong data-status={result?.[component].status ?? "unknown"}>
              {result ? LABELS[component][result[component].status] : "점검 전"}
            </strong>
          </div>
        ))}
      </section>

      <div className="interview-actions">
        <button type="button" className="button-secondary" onClick={check}>
          {checking ? "점검 중" : "장치 점검"}
        </button>
        <button
          type="button"
          className="button-primary"
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
