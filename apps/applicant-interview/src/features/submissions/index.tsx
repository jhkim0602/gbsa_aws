import { type FormEvent, useState } from "react";

import "./submissions.css";

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

type RequestState = "idle" | "pending" | "success" | "error";
const MAX_PROJECT_URLS = 3;

const STATUS_COPY: Record<
  AnalysisReadiness["overallStatus"],
  Readonly<{ label: string; tone: string }>
> = {
  waiting: { label: "대기", tone: "neutral" },
  analyzing: { label: "분석 중", tone: "info" },
  ready: { label: "완료", tone: "success" },
  partial: { label: "부분 완료", tone: "warning" },
  failed: { label: "실패", tone: "danger" },
};

export function SubmissionWorkspace({
  api,
  onContinue,
}: {
  api: SubmissionWorkspaceApi;
  onContinue?: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [repositoryUrls, setRepositoryUrls] = useState([""]);
  const [documentState, setDocumentState] = useState<RequestState>("idle");
  const [repositoryState, setRepositoryState] = useState<RequestState>("idle");
  const [readinessState, setReadinessState] = useState<RequestState>("idle");
  const [readiness, setReadiness] = useState<AnalysisReadiness | null>(null);

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setDocumentState("pending");
    try {
      await api.uploadDocument(file);
      setDocumentState("success");
    } catch {
      setDocumentState("error");
    }
  }

  async function registerRepository(event: FormEvent) {
    event.preventDefault();
    const urls = repositoryUrls.map((url) => url.trim()).filter(Boolean);
    if (urls.length === 0 || new Set(urls).size !== urls.length) {
      setRepositoryState("error");
      return;
    }
    setRepositoryState("pending");
    try {
      for (const url of urls) {
        await api.registerRepository(url);
      }
      setRepositoryState("success");
    } catch {
      setRepositoryState("error");
    }
  }

  function updateRepositoryUrl(index: number, value: string) {
    setRepositoryUrls((current) =>
      current.map((url, itemIndex) => (itemIndex === index ? value : url)),
    );
    setRepositoryState("idle");
  }

  function addRepositoryUrl() {
    setRepositoryUrls((current) =>
      current.length < MAX_PROJECT_URLS ? [...current, ""] : current,
    );
    setRepositoryState("idle");
  }

  function removeRepositoryUrl(index: number) {
    setRepositoryUrls((current) =>
      current.length === 1
        ? [""]
        : current.filter((_, itemIndex) => itemIndex !== index),
    );
    setRepositoryState("idle");
  }

  async function refreshReadiness() {
    setReadinessState("pending");
    try {
      setReadiness(await api.getReadiness());
      setReadinessState("success");
    } catch {
      setReadinessState("error");
    }
  }

  const status = readiness ? STATUS_COPY[readiness.overallStatus] : null;
  const repositoryCount = repositoryUrls.filter((url) => url.trim()).length;

  return (
    <main className="submission-screen">
      <header className="submission-heading">
        <p>STEP 1 OF 3</p>
        <h1>지원 자료 제출</h1>
        <p>
          제출 자료는 개인화된 면접 질문을 준비하는 데 사용됩니다. 문서나 공개
          저장소 중 실제로 확인할 자료만 등록해 주세요.
        </p>
      </header>

      <section className="submission-list" aria-label="면접 질문 준비 자료">
        <form className="submission-item" onSubmit={upload}>
          <div className="submission-item-heading">
            <div>
              <h2>이력서 또는 자기소개서</h2>
              <p>PDF · 최대 10MB</p>
            </div>
            {documentState === "success" && (
              <span className="submission-state" data-tone="success">
                제출됨
              </span>
            )}
          </div>

          <label className="submission-file-control">
            <span className="submission-file-icon" aria-hidden="true">
              PDF
            </span>
            <span className="submission-file-copy">
              <strong>{file?.name ?? "PDF 자료 선택"}</strong>
              <small>
                {file
                  ? `${Math.max(1, Math.ceil(file.size / 1024))}KB`
                  : "질문 근거가 될 최신 문서를 선택해 주세요."}
              </small>
            </span>
            <span className="submission-file-button">찾아보기</span>
            <input
              type="file"
              aria-label="PDF 자료"
              accept="application/pdf"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setDocumentState("idle");
              }}
            />
          </label>

          <button
            className="submission-action"
            type="submit"
            disabled={!file || documentState === "pending"}
          >
            {documentState === "pending" ? "업로드 중" : "자료 업로드"}
          </button>
          {documentState === "success" && (
            <p className="submission-feedback" role="status">
              문서가 등록되었습니다.
            </p>
          )}
          {documentState === "error" && (
            <p className="submission-feedback" data-tone="danger" role="alert">
              문서를 등록하지 못했습니다. 다시 시도해 주세요.
            </p>
          )}
        </form>

        <form className="submission-item" onSubmit={registerRepository}>
          <div className="submission-item-heading">
            <div>
              <h2>대표 프로젝트</h2>
              <p>공개 Git 저장소 · 최대 3개 · 선택사항</p>
            </div>
            {repositoryState === "success" && (
              <span className="submission-state" data-tone="success">
                등록됨
              </span>
            )}
          </div>
          <div className="submission-url-list">
            {repositoryUrls.map((repositoryUrl, index) => (
              <div className="submission-url-control" key={index}>
                <label htmlFor={`public-repository-url-${index}`}>
                  대표 프로젝트 URL {index + 1}
                </label>
                <div>
                  <input
                    id={`public-repository-url-${index}`}
                    type="url"
                    placeholder="https://github.com/organization/project"
                    value={repositoryUrl}
                    onChange={(event) =>
                      updateRepositoryUrl(index, event.target.value)
                    }
                  />
                  <button
                    className="submission-remove-url"
                    type="button"
                    aria-label={`대표 프로젝트 URL ${index + 1} 삭제`}
                    onClick={() => removeRepositoryUrl(index)}
                  >
                    ×
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="submission-project-actions">
            {repositoryUrls.length < MAX_PROJECT_URLS && (
              <button
                className="submission-secondary-action"
                type="button"
                onClick={addRepositoryUrl}
              >
                <span aria-hidden="true">+</span> 프로젝트 추가
              </button>
            )}
            <button
              className="submission-action"
              type="submit"
              disabled={repositoryCount === 0 || repositoryState === "pending"}
            >
              {repositoryState === "pending" ? "등록 중" : "프로젝트 등록"}
            </button>
          </div>
          {repositoryState === "success" && (
            <p className="submission-feedback" role="status">
              프로젝트 {repositoryCount}개가 등록되었습니다.
            </p>
          )}
          {repositoryState === "error" && (
            <p className="submission-feedback" data-tone="danger" role="alert">
              프로젝트를 등록하지 못했습니다. 중복되지 않은 공개 Git URL인지
              확인해 주세요.
            </p>
          )}
        </form>
      </section>

      <section
        className="submission-readiness"
        aria-labelledby="analysis-status"
      >
        <div className="submission-readiness-heading">
          <div>
            <p>ANALYSIS</p>
            <h2 id="analysis-status">분석 상태</h2>
          </div>
          <button
            className="submission-secondary-action"
            type="button"
            disabled={readinessState === "pending"}
            onClick={() => void refreshReadiness()}
          >
            {readinessState === "pending" ? "확인 중" : "분석 상태 확인"}
          </button>
        </div>

        {readinessState === "idle" && (
          <p className="submission-readiness-empty">
            자료 등록 후 분석 상태를 확인해 주세요.
          </p>
        )}
        {readinessState === "error" && (
          <p className="submission-feedback" data-tone="danger" role="alert">
            분석 상태를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.
          </p>
        )}
        {readiness && status && (
          <div className="submission-readiness-result">
            <div>
              <span className="submission-state" data-tone={status.tone}>
                {status.label}
              </span>
              <strong>
                {readiness.interviewReady ? "면접 진행 가능" : "면접 준비 중"}
              </strong>
            </div>
            {readiness.impactSummary && <p>{readiness.impactSummary}</p>}
          </div>
        )}
      </section>

      {readiness?.interviewReady && (
        <button
          className="submission-continue"
          type="button"
          onClick={onContinue}
        >
          환경 점검으로 이동
        </button>
      )}

      <p className="submission-footnote">
        분석이 일부 완료되지 않아도 면접 가능한 범위와 영향을 명확히 안내합니다.
      </p>
    </main>
  );
}
