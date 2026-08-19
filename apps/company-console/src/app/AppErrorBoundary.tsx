import { AlertTriangle, RefreshCw } from "lucide-react";
import { Component, type ReactNode } from "react";

const CRASH_PANEL =
  "grid w-[min(100%,420px)] justify-items-start gap-2.5 rounded-lg border" +
  " border-border bg-surface p-[26px] shadow-float";

const CRASH_ICON =
  "grid size-[38px] place-items-center rounded-[7px] bg-warning-soft" +
  " text-warning";

// `.app-crash__panel button` adds the mt-1 on top of the shared button-primary.
const CRASH_BUTTON =
  "mt-1 inline-flex min-h-10 items-center justify-center gap-1.5 rounded-lg" +
  " border border-brand bg-brand px-[18px] text-[14px] font-semibold" +
  " text-white shadow-soft hover:not-disabled:bg-brand-strong";

type AppErrorBoundaryProps = {
  children: ReactNode;
  onReload?: () => void;
};

type AppErrorBoundaryState = {
  failed: boolean;
};

export class AppErrorBoundary extends Component<
  AppErrorBoundaryProps,
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch() {
    // The fallback intentionally avoids logging application or applicant data.
  }

  private reload = () => {
    if (this.props.onReload) {
      this.props.onReload();
      return;
    }
    window.location.reload();
  };

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <main className="grid min-h-screen place-items-center bg-surface-muted p-6">
        <section className={CRASH_PANEL} role="alert">
          <span className={CRASH_ICON} aria-hidden="true">
            <AlertTriangle size={22} />
          </span>
          <p className="font-mono text-[9px] text-muted uppercase">
            Application recovery
          </p>
          <h1 className="text-[18px]">화면을 불러오지 못했습니다.</h1>
          <span className="text-[12px] leading-[1.6] text-muted">
            브라우저에 남은 이전 화면 자산을 새로 불러오면 계속 사용할 수
            있습니다.
          </span>
          <button className={CRASH_BUTTON} type="button" onClick={this.reload}>
            <RefreshCw size={14} aria-hidden="true" />
            새로고침
          </button>
        </section>
      </main>
    );
  }
}
