import { FormEvent, useState } from "react";

export type AnalysisReadiness = {
  overallStatus: "waiting" | "analyzing" | "ready" | "partial" | "failed";
  interviewReady: boolean;
  impactSummary?: string;
};

export type SubmissionWorkspaceApi = {
  uploadDocument(file: File): Promise<void>;
  registerRepository(url: string): Promise<void>;
  getReadiness(): Promise<AnalysisReadiness>;
};

export function SubmissionWorkspace({ api }: { api: SubmissionWorkspaceApi }) {
  const [file, setFile] = useState<File | null>(null);
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [documentMessage, setDocumentMessage] = useState("");
  const [repositoryMessage, setRepositoryMessage] = useState("");
  const [readiness, setReadiness] = useState<AnalysisReadiness | null>(null);

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    await api.uploadDocument(file);
    setDocumentMessage("문서가 등록되었습니다.");
  }

  async function registerRepository(event: FormEvent) {
    event.preventDefault();
    await api.registerRepository(repositoryUrl);
    setRepositoryMessage("저장소가 등록되었습니다.");
  }

  async function refreshReadiness() {
    setReadiness(await api.getReadiness());
  }

  const statusLabel = readiness
    ? {
        waiting: "대기",
        analyzing: "분석 중",
        ready: "완료",
        partial: "부분 완료",
        failed: "실패",
      }[readiness.overallStatus]
    : null;

  return (
    <main>
      <header>
        <p>GBSA Interview Evidence</p>
        <h1>면접 자료 제출</h1>
      </header>

      <form onSubmit={upload}>
        <h2>문서 자료</h2>
        <label>
          PDF 자료
          <input
            type="file"
            accept="application/pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button type="submit" disabled={!file}>
          자료 업로드
        </button>
        {documentMessage && <p role="status">{documentMessage}</p>}
      </form>

      <form onSubmit={registerRepository}>
        <h2>공개 코드 저장소</h2>
        <label>
          공개 Git 저장소
          <input
            type="url"
            required
            value={repositoryUrl}
            onChange={(event) => setRepositoryUrl(event.target.value)}
          />
        </label>
        <button type="submit">저장소 등록</button>
        {repositoryMessage && <p role="status">{repositoryMessage}</p>}
      </form>

      <section aria-labelledby="analysis-status">
        <h2 id="analysis-status">분석 상태</h2>
        <button type="button" onClick={refreshReadiness}>
          분석 상태 확인
        </button>
        {readiness && (
          <div>
            <strong>{statusLabel}</strong>
            {readiness.impactSummary && <p>{readiness.impactSummary}</p>}
            <p>
              {readiness.interviewReady ? "면접 진행 가능" : "면접 준비 중"}
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
