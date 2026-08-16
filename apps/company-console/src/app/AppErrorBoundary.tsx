import { AlertTriangle, RefreshCw } from "lucide-react";
import { Component, type ReactNode } from "react";

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
      <main className="app-crash">
        <section className="app-crash__panel" role="alert">
          <span className="app-crash__icon" aria-hidden="true">
            <AlertTriangle size={22} />
          </span>
          <p>Application recovery</p>
          <h1>화면을 불러오지 못했습니다.</h1>
          <span>
            브라우저에 남은 이전 화면 자산을 새로 불러오면 계속 사용할 수
            있습니다.
          </span>
          <button
            className="button-primary"
            type="button"
            onClick={this.reload}
          >
            <RefreshCw size={14} aria-hidden="true" />
            새로고침
          </button>
        </section>
      </main>
    );
  }
}
