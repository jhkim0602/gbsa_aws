import {
  AlertCircle,
  ArrowRight,
  Code2,
  CheckCircle2,
  FileText,
  GitBranch,
  Plus,
  RefreshCw,
  X,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useState } from "react";

export type AnalysisReadiness = {
  overallStatus: "waiting" | "analyzing" | "ready" | "partial" | "failed";
  interviewReady: boolean;
  impactSummary?: string;
  materialStatuses?: Partial<Record<SubmissionMaterialId, string>>;
  strategyId?: string;
  strategyVersion?: number;
};

export type SubmissionMaterialId =
  "resume" | "cover-letter" | "career-description" | "projects" | "portfolio";

export type SubmissionRequirement = Readonly<{
  id: SubmissionMaterialId;
  required: boolean;
  enabled?: boolean;
  instructions?: string;
}>;

export type SubmissionWorkspaceApi = {
  uploadDocument(file: File, materialId: SubmissionMaterialId): Promise<void>;
  registerRepository(
    url: string,
    materialId: SubmissionMaterialId,
  ): Promise<void>;
  getReadiness(): Promise<AnalysisReadiness>;
  getWorkspace(): Promise<SubmissionWorkspaceData>;
  getAnalysisDebug?(): Promise<unknown>;
};

export type SubmissionWorkspaceData = Readonly<{
  positionTitle: string;
  requirements: readonly SubmissionRequirement[];
  submissions: readonly {
    materialId: SubmissionMaterialId;
    status: string;
  }[];
}>;

type PdfMaterialId = Exclude<SubmissionMaterialId, "projects">;
type RequestState = "idle" | "pending" | "success" | "error";
type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";

type AnalysisDebugDocument = Readonly<{
  source_id?: string;
  material_type?: string;
  locator?: Readonly<{
    page_number?: number;
    section?: string;
    start_line?: number;
    end_line?: number;
  }>;
  text?: string;
  embedding_model?: string;
  embedding_version?: string;
}>;

type AnalysisDebugData = Readonly<{
  submissions?: readonly Readonly<{
    original_filename?: string;
    material_type?: string;
    status?: string;
  }>[];
  analyses?: readonly Readonly<{
    extractor_version?: string;
    status?: string;
    claims?: readonly Readonly<{
      type?: string;
      chunk_count?: number;
    }>[];
  }>[];
  extracted_documents?: readonly AnalysisDebugDocument[];
  strategy?: Readonly<{
    strategy_version?: number;
    status?: string;
    common_topics?: readonly string[];
    verification_points?: readonly Readonly<{
      criterion_id?: string;
      prompt?: string;
      source_ids?: readonly string[];
    }>[];
    follow_up_directions?: Readonly<Record<string, readonly string[]>>;
    time_budget?: Readonly<{ total_seconds?: number }>;
    required_evidence_plan?: Readonly<Record<string, number>>;
    source_reference_candidates?: readonly unknown[];
    model_config_version?: string;
  }> | null;
}>;

type MaterialDefinition = Readonly<{
  id: SubmissionMaterialId;
  label: string;
  shortDescription: string;
  format: string;
  kind: "pdf" | "repository";
}>;

type ConfiguredMaterial = MaterialDefinition &
  Readonly<{
    required: boolean;
    instructions?: string;
  }>;

const MAX_PROJECT_URLS = 3;
const READINESS_POLL_INTERVAL_MS = 2_000;

const MATERIAL_DEFINITIONS: Record<SubmissionMaterialId, MaterialDefinition> = {
  resume: {
    id: "resume",
    label: "이력서",
    shortDescription: "경력과 주요 역량을 확인하는 기본 자료",
    format: "PDF · 최대 10MB",
    kind: "pdf",
  },
  "cover-letter": {
    id: "cover-letter",
    label: "자기소개서",
    shortDescription: "지원 동기와 직무 적합성을 확인하는 자료",
    format: "PDF · 최대 10MB",
    kind: "pdf",
  },
  "career-description": {
    id: "career-description",
    label: "경력기술서",
    shortDescription: "프로젝트별 역할과 성과를 확인하는 자료",
    format: "PDF · 최대 10MB",
    kind: "pdf",
  },
  projects: {
    id: "projects",
    label: "대표 프로젝트",
    shortDescription: "공개 저장소를 통해 작업 근거를 확인하는 자료",
    format: "공개 Git 저장소 · 최대 3개",
    kind: "repository",
  },
  portfolio: {
    id: "portfolio",
    label: "포트폴리오",
    shortDescription: "주요 결과물과 작업 과정을 확인하는 자료",
    format: "PDF · 최대 20MB",
    kind: "pdf",
  },
};

export const DEFAULT_SUBMISSION_REQUIREMENTS: readonly SubmissionRequirement[] =
  [
    { id: "resume", required: true },
    { id: "cover-letter", required: true },
    { id: "career-description", required: false },
    { id: "projects", required: false },
    { id: "portfolio", required: false },
  ];

const INITIAL_FILES: Record<PdfMaterialId, File | null> = {
  resume: null,
  "cover-letter": null,
  "career-description": null,
  portfolio: null,
};

const INITIAL_STATES: Record<SubmissionMaterialId, RequestState> = {
  resume: "idle",
  "cover-letter": "idle",
  "career-description": "idle",
  projects: "idle",
  portfolio: "idle",
};

const STATUS_TONE_CLASSES: Record<StatusTone, string> = {
  neutral: "border-border bg-surface text-muted",
  info: "border-brand/25 bg-brand-soft text-brand-strong",
  success: "border-success/25 bg-success-soft text-success",
  warning: "border-warning/30 bg-warning-soft text-warning",
  danger: "border-danger/25 bg-danger-soft text-danger",
};

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function submissionStatus(state: RequestState, hasInput: boolean) {
  if (state === "success") {
    return { label: "제출 완료", tone: "success" as const };
  }
  if (state === "pending") {
    return { label: "제출 중", tone: "info" as const };
  }
  if (state === "error") {
    return { label: "확인 필요", tone: "danger" as const };
  }
  if (hasInput) {
    return { label: "제출 준비", tone: "info" as const };
  }
  return { label: "미제출", tone: "neutral" as const };
}

function analysisStatus(
  state: RequestState,
  submissionAnalysisStatus?: string,
) {
  if (state !== "success") {
    return { label: "분석 대기", tone: "neutral" as const };
  }
  if (
    !submissionAnalysisStatus ||
    submissionAnalysisStatus === "received" ||
    submissionAnalysisStatus === "validating"
  ) {
    return { label: "분석 대기", tone: "neutral" as const };
  }
  if (submissionAnalysisStatus === "analyzing") {
    return { label: "분석 중", tone: "info" as const };
  }
  if (submissionAnalysisStatus === "ready") {
    return { label: "분석 완료", tone: "success" as const };
  }
  if (submissionAnalysisStatus === "partial") {
    return { label: "일부 완료", tone: "warning" as const };
  }
  return { label: "분석 보류", tone: "danger" as const };
}

function StatusBadge({ label, tone }: { label: string; tone: StatusTone }) {
  return (
    <span
      className={cn(
        "inline-flex min-h-6 items-center rounded-full border px-2 text-[11px] font-semibold whitespace-nowrap",
        STATUS_TONE_CLASSES[tone],
      )}
    >
      {label}
    </span>
  );
}

function PdfSubmissionEditor({
  material,
  file,
  state,
  onFileChange,
  onSubmit,
}: {
  material: ConfiguredMaterial;
  file: File | null;
  state: RequestState;
  onFileChange(file: File | null): void;
  onSubmit(event: FormEvent<HTMLFormElement>): void;
}) {
  return (
    <form className="space-y-3" onSubmit={onSubmit}>
      <div
        className={cn(
          "flex overflow-hidden rounded-lg border bg-surface max-sm:flex-col",
          file ? "border-brand/35" : "border-border-strong",
        )}
      >
        <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 px-4 py-4 hover:bg-surface-muted">
          <span className="grid size-10 shrink-0 place-items-center rounded-md border border-border bg-canvas text-danger">
            <FileText aria-hidden="true" size={19} strokeWidth={1.8} />
          </span>
          <span className="min-w-0 flex-1">
            <strong className="block truncate text-sm font-semibold text-ink">
              {file?.name ?? "PDF 파일 선택"}
            </strong>
            <small className="mt-1 block text-xs text-muted">
              {file
                ? `${Math.max(1, Math.ceil(file.size / 1024))}KB · ${material.format}`
                : (material.instructions ?? material.shortDescription)}
            </small>
          </span>
          <span className="shrink-0 text-xs font-semibold text-brand-strong">
            {file ? "파일 변경" : "찾아보기"}
          </span>
          <input
            className="sr-only"
            type="file"
            aria-label={`${material.label} PDF`}
            accept="application/pdf"
            onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
          />
        </label>

        {file ? (
          <button
            className="min-w-24 border-l border-brand bg-brand px-4 text-sm font-semibold text-white hover:bg-brand-strong disabled:border-border disabled:bg-surface-strong disabled:text-subtle max-sm:min-h-11 max-sm:border-t max-sm:border-l-0"
            type="submit"
            disabled={state === "pending"}
          >
            {state === "pending" ? "제출 중" : "제출하기"}
          </button>
        ) : null}
      </div>

      {state === "success" ? (
        <p
          className="flex items-center gap-2 text-xs font-medium text-success"
          role="status"
        >
          <CheckCircle2 aria-hidden="true" size={15} />
          {material.label}가 제출되었습니다.
        </p>
      ) : null}

      {state === "error" ? (
        <p
          className="flex items-center gap-2 text-xs font-medium text-danger"
          role="alert"
        >
          <AlertCircle aria-hidden="true" size={15} />
          제출하지 못했습니다. 파일을 확인한 후 다시 시도해 주세요.
        </p>
      ) : null}
    </form>
  );
}

function RepositorySubmissionEditor({
  urls,
  state,
  onUpdate,
  onAdd,
  onRemove,
  onSubmit,
}: {
  urls: readonly string[];
  state: RequestState;
  onUpdate(index: number, value: string): void;
  onAdd(): void;
  onRemove(index: number): void;
  onSubmit(event: FormEvent<HTMLFormElement>): void;
}) {
  const repositoryCount = urls.filter((url) => url.trim()).length;

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <div className="space-y-3">
        {urls.map((repositoryUrl, index) => (
          <div className="space-y-1.5" key={index}>
            <label
              className="text-xs font-semibold text-ink"
              htmlFor={`public-repository-url-${index}`}
            >
              저장소 URL {index + 1}
            </label>
            <div className="grid grid-cols-[minmax(0,1fr)_40px] gap-2">
              <input
                className="min-h-10 min-w-0 rounded-md border border-border-strong bg-surface px-3 text-sm text-ink outline-none placeholder:text-subtle focus:border-brand"
                id={`public-repository-url-${index}`}
                type="url"
                placeholder="https://github.com/organization/project"
                value={repositoryUrl}
                onChange={(event) => onUpdate(index, event.target.value)}
              />
              <button
                className="grid size-10 place-items-center rounded-md border border-border bg-surface text-muted hover:border-danger/40 hover:text-danger"
                type="button"
                aria-label={`저장소 URL ${index + 1} 삭제`}
                title="저장소 삭제"
                onClick={() => onRemove(index)}
              >
                <X aria-hidden="true" size={17} />
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        {urls.length < MAX_PROJECT_URLS ? (
          <button
            className="grid size-9 place-items-center rounded-md border border-border bg-surface text-ink hover:border-brand/40 hover:text-brand-strong"
            type="button"
            aria-label="저장소 추가"
            title="저장소 추가"
            onClick={onAdd}
          >
            <Plus aria-hidden="true" size={17} />
          </button>
        ) : (
          <span className="text-xs text-muted">
            최대 3개까지 등록할 수 있습니다.
          </span>
        )}

        {repositoryCount > 0 ? (
          <button
            className="inline-flex min-h-9 items-center rounded-md border border-brand bg-brand px-4 text-xs font-semibold text-white hover:bg-brand-strong disabled:border-border disabled:bg-surface-strong disabled:text-subtle"
            type="submit"
            disabled={state === "pending"}
          >
            {state === "pending" ? "제출 중" : "프로젝트 제출"}
          </button>
        ) : null}
      </div>

      {state === "success" ? (
        <p
          className="flex items-center gap-2 text-xs font-medium text-success"
          role="status"
        >
          <CheckCircle2 aria-hidden="true" size={15} />
          프로젝트 {repositoryCount}개가 제출되었습니다.
        </p>
      ) : null}

      {state === "error" ? (
        <p
          className="flex items-center gap-2 text-xs font-medium text-danger"
          role="alert"
        >
          <AlertCircle aria-hidden="true" size={15} />
          중복되지 않은 공개 Git URL인지 확인해 주세요.
        </p>
      ) : null}
    </form>
  );
}

function AnalysisDebugPanel({
  result,
  state,
  onRefresh,
}: {
  result: unknown;
  state: RequestState;
  onRefresh: () => void;
}) {
  const debugData = isRecord(result) ? (result as AnalysisDebugData) : null;
  const strategy = debugData?.strategy ?? null;
  const analyses = debugData?.analyses ?? [];
  const documents = debugData?.extracted_documents ?? [];
  const submissions = debugData?.submissions ?? [];
  const documentsById = new Map(
    documents
      .filter((document) => document.source_id)
      .map((document) => [document.source_id as string, document]),
  );
  const totalSeconds = strategy?.time_budget?.total_seconds;
  const evidenceTargetCount = Object.values(
    strategy?.required_evidence_plan ?? {},
  ).reduce((total, count) => total + count, 0);

  return (
    <section className="mt-4 rounded-lg border border-dashed border-brand/35 bg-brand-soft/35 p-5">
      <div className="flex items-center justify-between gap-4 max-sm:items-start max-sm:flex-col">
        <div className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-md bg-brand-soft text-brand-strong">
            <Code2 aria-hidden="true" size={18} />
          </span>
          <div>
            <p className="m-0 font-mono text-[10px] font-bold tracking-wide text-brand">
              LOCAL DEVELOPMENT ONLY
            </p>
            <h2 className="mt-1 text-sm font-bold text-ink">
              분석 디버그 결과
            </h2>
            <p className="mt-1 text-xs leading-5 text-muted">
              최종 면접 전략과 질문 근거를 먼저 확인하고, 필요할 때 추출 문서와
              원본 JSON을 펼쳐볼 수 있습니다.
            </p>
          </div>
        </div>
        <button
          className="inline-flex min-h-9 shrink-0 items-center gap-2 rounded-md border border-brand/30 bg-surface px-3 text-xs font-semibold text-brand-strong hover:bg-brand-soft disabled:cursor-wait disabled:opacity-60"
          type="button"
          disabled={state === "pending"}
          onClick={onRefresh}
        >
          <RefreshCw
            aria-hidden="true"
            className={state === "pending" ? "animate-spin" : undefined}
            size={14}
          />
          {state === "pending"
            ? "분석 결과 불러오는 중"
            : result
              ? "분석 결과 새로고침"
              : "분석 결과 불러오기"}
        </button>
      </div>

      {state === "error" ? (
        <p className="mt-4 text-xs font-medium text-danger" role="alert">
          로컬 분석 결과를 불러오지 못했습니다.
        </p>
      ) : null}

      {debugData ? (
        <div className="mt-4 space-y-4">
          <section className="rounded-lg border border-border bg-surface p-5">
            <div className="flex items-start justify-between gap-4 max-sm:flex-col">
              <div>
                <p className="m-0 text-[11px] font-semibold text-brand">
                  FINAL INTERVIEW STRATEGY
                </p>
                <h3 className="mt-1 text-base font-bold text-ink">
                  최종 면접 전략
                </h3>
                <p className="mt-1 text-xs leading-5 text-muted">
                  제출 자료에서 추출한 근거를 바탕으로 생성된 면접 주제와
                  질문입니다.
                </p>
              </div>
              {strategy ? (
                <span className="inline-flex min-h-7 shrink-0 items-center rounded-full bg-success-soft px-3 text-xs font-semibold text-success">
                  버전 {strategy.strategy_version ?? "-"} ·{" "}
                  {strategy.status === "ready" ? "준비 완료" : strategy.status}
                </span>
              ) : null}
            </div>

            {strategy ? (
              <>
                <div className="mt-5 grid grid-cols-3 gap-3 max-md:grid-cols-1">
                  <DebugMetric
                    label="전체 면접 시간"
                    value={
                      typeof totalSeconds === "number"
                        ? `${Math.round(totalSeconds / 60)}분`
                        : "미설정"
                    }
                  />
                  <DebugMetric
                    label="확보할 답변 근거"
                    value={`${evidenceTargetCount}개`}
                  />
                  <DebugMetric
                    label="질문 생성 후보"
                    value={`${strategy.source_reference_candidates?.length ?? 0}개 문단`}
                  />
                </div>

                <div className="mt-5">
                  <h4 className="m-0 text-xs font-bold text-ink">핵심 주제</h4>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(strategy.common_topics ?? []).map((topic) => (
                      <span
                        key={topic}
                        className="rounded-full border border-brand/20 bg-brand-soft px-3 py-1.5 text-xs font-semibold text-brand-strong"
                      >
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="mt-5 space-y-3">
                  <h4 className="m-0 text-xs font-bold text-ink">
                    대표 질문과 꼬리질문
                  </h4>
                  {(strategy.verification_points ?? []).map(
                    (verificationPoint, index) => {
                      const criterionId = verificationPoint.criterion_id ?? "";
                      const followUps =
                        strategy.follow_up_directions?.[criterionId] ?? [];
                      return (
                        <article
                          key={`${criterionId}-${index}`}
                          className="rounded-md border border-border bg-surface-muted p-4"
                        >
                          <p className="m-0 text-[11px] font-semibold text-brand">
                            대표 질문 {index + 1}
                          </p>
                          <p className="mt-1 text-sm font-semibold leading-6 text-ink">
                            {verificationPoint.prompt ?? "질문 내용 없음"}
                          </p>
                          {followUps.length > 0 ? (
                            <div className="mt-3 border-t border-border pt-3">
                              <p className="m-0 text-[11px] font-semibold text-muted">
                                꼬리질문
                              </p>
                              <ol className="mt-2 space-y-1.5 pl-5 text-xs leading-5 text-ink">
                                {followUps.map((followUp) => (
                                  <li key={followUp}>{followUp}</li>
                                ))}
                              </ol>
                            </div>
                          ) : null}
                        </article>
                      );
                    },
                  )}
                </div>

                <p className="mt-4 text-[11px] text-muted">
                  전략 생성 설정: {strategy.model_config_version ?? "확인 불가"}
                </p>
              </>
            ) : (
              <p className="mt-4 text-xs text-muted">
                아직 생성된 면접 전략이 없습니다.
              </p>
            )}
          </section>

          {strategy?.verification_points?.length ? (
            <details
              className="rounded-lg border border-border bg-surface p-5"
              open
            >
              <summary className="cursor-pointer text-sm font-bold text-ink">
                질문 근거 문단
              </summary>
              <div className="mt-4 space-y-4">
                {strategy.verification_points.map(
                  (verificationPoint, index) => (
                    <article key={`${verificationPoint.criterion_id}-${index}`}>
                      <p className="m-0 text-xs font-semibold text-ink">
                        대표 질문 {index + 1}의 근거
                      </p>
                      <div className="mt-2 space-y-2">
                        {(verificationPoint.source_ids ?? []).map(
                          (sourceId) => {
                            const document = documentsById.get(sourceId);
                            return (
                              <div
                                key={sourceId}
                                className="rounded-md border border-border bg-surface-muted p-3"
                              >
                                <p className="m-0 text-[11px] font-semibold text-brand-strong">
                                  {formatDocumentLocation(document)}
                                </p>
                                <p className="mt-1 whitespace-pre-wrap text-xs leading-5 text-ink">
                                  {document?.text ?? `문단 ID: ${sourceId}`}
                                </p>
                              </div>
                            );
                          },
                        )}
                      </div>
                    </article>
                  ),
                )}
              </div>
            </details>
          ) : null}

          <details className="rounded-lg border border-border bg-surface p-5">
            <summary className="cursor-pointer text-sm font-bold text-ink">
              분석 처리 정보 · 제출 {submissions.length}건 · 분석{" "}
              {analyses.length}건
            </summary>
            <div className="mt-4 grid gap-2">
              {analyses.map((analysis, index) => {
                const chunkCount = analysis.claims?.find(
                  (claim) => claim.type === "document_extracted",
                )?.chunk_count;
                return (
                  <div
                    key={`${analysis.extractor_version}-${index}`}
                    className="flex items-center justify-between gap-4 rounded-md bg-surface-muted px-3 py-2 text-xs"
                  >
                    <span className="font-medium text-ink">
                      {analysis.extractor_version ?? "분석기 확인 불가"}
                    </span>
                    <span className="text-muted">
                      {analysis.status ?? "상태 없음"}
                      {typeof chunkCount === "number"
                        ? ` · ${chunkCount}개 문단`
                        : ""}
                    </span>
                  </div>
                );
              })}
            </div>
          </details>

          <details className="rounded-lg border border-border bg-surface p-5">
            <summary className="cursor-pointer text-sm font-bold text-ink">
              추출 문서 전체 보기 · {documents.length}개 문단
            </summary>
            <div className="mt-4 max-h-[560px] space-y-2 overflow-auto pr-1">
              {documents.map((document, index) => (
                <article
                  key={document.source_id ?? index}
                  className="rounded-md border border-border bg-surface-muted p-3"
                >
                  <p className="m-0 text-[11px] font-semibold text-brand-strong">
                    {formatDocumentLocation(document)}
                  </p>
                  <p className="mt-1 whitespace-pre-wrap text-xs leading-5 text-ink">
                    {document.text ?? "추출된 텍스트 없음"}
                  </p>
                </article>
              ))}
            </div>
          </details>

          <details className="rounded-lg border border-border bg-surface p-5">
            <summary className="cursor-pointer text-sm font-bold text-ink">
              원본 JSON 보기
            </summary>
            <pre className="mt-4 max-h-[560px] overflow-auto whitespace-pre-wrap break-words rounded-md border border-border bg-ink p-4 font-mono text-[11px] leading-5 text-white">
              {JSON.stringify(result, null, 2)}
            </pre>
          </details>
        </div>
      ) : null}
    </section>
  );
}

function DebugMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-surface-muted px-4 py-3">
      <p className="m-0 text-[11px] font-medium text-muted">{label}</p>
      <p className="mt-1 text-sm font-bold text-ink">{value}</p>
    </div>
  );
}

function formatDocumentLocation(document?: AnalysisDebugDocument) {
  if (!document) return "근거 문단 위치 확인 불가";
  const location = [
    document.locator?.page_number
      ? `${document.locator.page_number}페이지`
      : null,
    document.locator?.section ?? null,
    document.material_type ?? null,
  ].filter(Boolean);
  return location.join(" · ") || "문서 위치 정보 없음";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function SubmissionWorkspace({
  api,
  onContinue,
  positionTitle,
  requirements = DEFAULT_SUBMISSION_REQUIREMENTS,
  submittedMaterials = [],
}: {
  api: SubmissionWorkspaceApi;
  onContinue?: (strategyId: string) => void;
  positionTitle?: string;
  requirements?: readonly SubmissionRequirement[];
  submittedMaterials?: SubmissionWorkspaceData["submissions"];
}) {
  const configuredMaterials = requirements
    .filter((requirement) => requirement.enabled !== false)
    .map((requirement) => ({
      ...MATERIAL_DEFINITIONS[requirement.id],
      required: requirement.required,
      instructions: requirement.instructions,
    }));
  const initialMaterial = configuredMaterials[0]?.id ?? "resume";
  const [selectedMaterial, setSelectedMaterial] =
    useState<SubmissionMaterialId>(initialMaterial);
  const [files, setFiles] = useState(INITIAL_FILES);
  const [repositoryUrls, setRepositoryUrls] = useState([""]);
  const [materialStates, setMaterialStates] = useState(() => ({
    ...INITIAL_STATES,
    ...Object.fromEntries(
      submittedMaterials.map((submission) => [
        submission.materialId,
        submission.status === "failed" ? "error" : "success",
      ]),
    ),
  }));
  const [readiness, setReadiness] = useState<AnalysisReadiness | null>(null);
  const [debugResult, setDebugResult] = useState<unknown>(null);
  const [debugState, setDebugState] = useState<RequestState>("idle");

  const refreshReadiness = useCallback(async () => {
    try {
      setReadiness(await api.getReadiness());
    } catch {
      setReadiness(null);
    }
  }, [api]);
  const readinessSettled =
    readiness?.interviewReady === true || readiness?.overallStatus === "failed";
  const debugEnabled =
    import.meta.env.DEV && api.getAnalysisDebug !== undefined;

  useEffect(() => {
    if (readinessSettled) return;
    void refreshReadiness();
    const intervalId = window.setInterval(() => {
      void refreshReadiness();
    }, READINESS_POLL_INTERVAL_MS);
    return () => window.clearInterval(intervalId);
  }, [readinessSettled, refreshReadiness]);

  const activeMaterial =
    configuredMaterials.find((material) => material.id === selectedMaterial) ??
    configuredMaterials[0];
  const repositoryCount = repositoryUrls.filter((url) => url.trim()).length;
  const requiredMaterials = configuredMaterials.filter(
    (material) => material.required,
  );
  const completedRequiredCount = requiredMaterials.filter(
    (material) => materialStates[material.id] === "success",
  ).length;
  const remainingRequiredCount =
    requiredMaterials.length - completedRequiredCount;
  const requiredProgress =
    requiredMaterials.length === 0
      ? 100
      : Math.round((completedRequiredCount / requiredMaterials.length) * 100);

  function updateMaterialState(
    materialId: SubmissionMaterialId,
    state: RequestState,
  ) {
    setMaterialStates((current) => ({ ...current, [materialId]: state }));
  }

  async function uploadPdf(
    event: FormEvent<HTMLFormElement>,
    materialId: PdfMaterialId,
  ) {
    event.preventDefault();
    const file = files[materialId];
    if (!file) return;

    updateMaterialState(materialId, "pending");
    try {
      await api.uploadDocument(file, materialId);
      updateMaterialState(materialId, "success");
      void refreshReadiness();
    } catch {
      updateMaterialState(materialId, "error");
    }
  }

  async function registerRepository(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const urls = repositoryUrls.map((url) => url.trim()).filter(Boolean);
    if (urls.length === 0 || new Set(urls).size !== urls.length) {
      updateMaterialState("projects", "error");
      return;
    }

    updateMaterialState("projects", "pending");
    try {
      for (const url of urls) {
        await api.registerRepository(url, "projects");
      }
      updateMaterialState("projects", "success");
      void refreshReadiness();
    } catch {
      updateMaterialState("projects", "error");
    }
  }

  function updateRepositoryUrl(index: number, value: string) {
    setRepositoryUrls((current) =>
      current.map((url, itemIndex) => (itemIndex === index ? value : url)),
    );
    updateMaterialState("projects", "idle");
  }

  function addRepositoryUrl() {
    setRepositoryUrls((current) =>
      current.length < MAX_PROJECT_URLS ? [...current, ""] : current,
    );
    updateMaterialState("projects", "idle");
  }

  function removeRepositoryUrl(index: number) {
    setRepositoryUrls((current) =>
      current.length === 1
        ? [""]
        : current.filter((_, itemIndex) => itemIndex !== index),
    );
    updateMaterialState("projects", "idle");
  }

  async function refreshAnalysisDebug() {
    if (!api.getAnalysisDebug) return;
    setDebugState("pending");
    try {
      setDebugResult(await api.getAnalysisDebug());
      setDebugState("success");
    } catch {
      setDebugState("error");
    }
  }

  if (!activeMaterial) {
    return null;
  }

  const activeState = materialStates[activeMaterial.id];
  const activeHasInput =
    activeMaterial.id === "projects"
      ? repositoryCount > 0
      : files[activeMaterial.id as PdfMaterialId] !== null;
  const activeSubmissionStatus = submissionStatus(activeState, activeHasInput);
  const activeAnalysisStatus = analysisStatus(
    activeState,
    readiness?.materialStatuses?.[activeMaterial.id],
  );
  const canContinue =
    remainingRequiredCount === 0 &&
    readiness?.interviewReady === true &&
    Boolean(readiness.strategyId);

  return (
    <main className="mx-auto w-full max-w-[1120px] px-6 py-10 max-sm:px-4 max-sm:py-7">
      <header className="mb-6 flex items-end justify-between gap-8 max-md:items-start max-md:flex-col">
        <div>
          <p className="mb-2 font-mono text-[11px] font-bold text-brand">
            INTERVIEW PREP · 2 / 5
          </p>
          <h1 className="m-0 text-[28px] font-bold tracking-normal text-ink max-sm:text-2xl">
            지원 자료 제출
          </h1>
          <p className="mt-2 text-sm leading-6 text-muted">
            {positionTitle
              ? `${positionTitle} 포지션 자료는 RAG 기반 검색에 활용되어 맞춤형 질문과 실제 면접처럼 이어지는 꼬리질문을 생성합니다.`
              : "제출 자료는 RAG 기반 검색에 활용되어 모의면접에서 맞춤형 질문과 실제 면접처럼 이어지는 꼬리질문을 생성합니다."}
          </p>
        </div>

        <div className="w-64 shrink-0 max-md:w-full">
          <div className="mb-2 flex items-center justify-between text-xs">
            <span className="font-semibold text-ink">필수 자료</span>
            <span className="text-muted">
              {completedRequiredCount} / {requiredMaterials.length} 제출
            </span>
          </div>
          <div
            className="h-1.5 overflow-hidden rounded-full bg-surface-strong"
            role="progressbar"
            aria-label="필수 자료 제출 진행률"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={requiredProgress}
          >
            <div
              className="h-full rounded-full bg-brand"
              style={{ width: `${requiredProgress}%` }}
            />
          </div>
        </div>
      </header>

      <section
        className="overflow-hidden rounded-lg border border-border bg-surface shadow-soft"
        aria-label="포지션 요청 자료"
      >
        <div className="grid min-h-[520px] grid-cols-[340px_minmax(0,1fr)] max-lg:grid-cols-[300px_minmax(0,1fr)] max-md:min-h-0 max-md:grid-cols-1">
          <aside className="border-r border-border bg-surface-muted max-md:border-r-0 max-md:border-b">
            <div className="flex min-h-14 items-center justify-between border-b border-border px-5">
              <div>
                <strong className="block text-sm text-ink">요청 자료</strong>
                <small className="mt-0.5 block text-[11px] text-muted">
                  필수 {requiredMaterials.length} · 선택{" "}
                  {configuredMaterials.length - requiredMaterials.length}
                </small>
              </div>
              <span className="text-[11px] text-muted">제출 · 분석</span>
            </div>

            <nav
              className="divide-y divide-border max-md:grid max-md:grid-cols-2 max-sm:grid-cols-1"
              aria-label="제출 자료 선택"
            >
              {configuredMaterials.map((material) => {
                const state = materialStates[material.id];
                const hasInput =
                  material.id === "projects"
                    ? repositoryCount > 0
                    : files[material.id as PdfMaterialId] !== null;
                const submitted = submissionStatus(state, hasInput);
                const analyzed = analysisStatus(
                  state,
                  readiness?.materialStatuses?.[material.id],
                );
                const selected = activeMaterial.id === material.id;

                return (
                  <button
                    key={material.id}
                    className={cn(
                      "grid min-h-[84px] w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-l-[3px] px-4 py-3 text-left hover:bg-surface",
                      selected
                        ? "border-l-brand bg-surface"
                        : "border-l-transparent bg-transparent",
                    )}
                    type="button"
                    aria-label={`${material.label} 선택`}
                    aria-current={selected ? "true" : undefined}
                    onClick={() => setSelectedMaterial(material.id)}
                  >
                    <span className="min-w-0">
                      <span className="flex min-w-0 items-center gap-2">
                        <strong className="truncate text-[13px] text-ink">
                          {material.label}
                        </strong>
                        <small
                          className={cn(
                            "shrink-0 text-[10px] font-semibold",
                            material.required
                              ? "text-brand-strong"
                              : "text-muted",
                          )}
                        >
                          {material.required ? "필수" : "선택"}
                        </small>
                      </span>
                      <small className="mt-1 block truncate text-[11px] text-muted">
                        {material.format}
                      </small>
                    </span>

                    <span className="grid justify-items-end gap-1">
                      <StatusBadge
                        label={submitted.label}
                        tone={submitted.tone}
                      />
                      <small
                        className={cn(
                          "text-[10px] font-medium whitespace-nowrap",
                          analyzed.tone === "success"
                            ? "text-success"
                            : analyzed.tone === "danger"
                              ? "text-danger"
                              : analyzed.tone === "info"
                                ? "text-brand-strong"
                                : "text-muted",
                        )}
                      >
                        {analyzed.label}
                      </small>
                    </span>
                  </button>
                );
              })}
            </nav>
          </aside>

          <section
            className="flex min-w-0 flex-col"
            aria-labelledby="selected-material-title"
          >
            <header className="flex items-start justify-between gap-5 border-b border-border px-7 py-6 max-sm:px-5 max-sm:py-5">
              <div>
                <div className="mb-2 flex items-center gap-2">
                  {activeMaterial.kind === "repository" ? (
                    <GitBranch
                      className="text-brand"
                      aria-hidden="true"
                      size={17}
                    />
                  ) : (
                    <FileText
                      className="text-brand"
                      aria-hidden="true"
                      size={17}
                    />
                  )}
                  <span className="text-[11px] font-semibold text-brand-strong">
                    포지션 요청 자료
                  </span>
                </div>
                <h2
                  className="m-0 text-xl font-bold text-ink"
                  id="selected-material-title"
                >
                  {activeMaterial.label}
                </h2>
                <p className="mt-1.5 text-xs text-muted">
                  {activeMaterial.format}
                </p>
              </div>
              <span
                className={cn(
                  "inline-flex min-h-7 shrink-0 items-center rounded-full border px-2.5 text-xs font-semibold",
                  activeMaterial.required
                    ? "border-brand/25 bg-brand-soft text-brand-strong"
                    : "border-border bg-surface text-muted",
                )}
              >
                {activeMaterial.required ? "필수" : "선택"}
              </span>
            </header>

            <div className="px-7 py-6 max-sm:px-5 max-sm:py-5">
              <div className="mb-4">
                <h3 className="m-0 text-sm font-semibold text-ink">
                  {activeMaterial.kind === "repository"
                    ? "공개 저장소 등록"
                    : "제출 파일"}
                </h3>
                <p className="mt-1 text-xs leading-5 text-muted">
                  {activeMaterial.instructions ??
                    activeMaterial.shortDescription}
                </p>
              </div>

              {activeMaterial.kind === "repository" ? (
                <RepositorySubmissionEditor
                  urls={repositoryUrls}
                  state={materialStates.projects}
                  onUpdate={updateRepositoryUrl}
                  onAdd={addRepositoryUrl}
                  onRemove={removeRepositoryUrl}
                  onSubmit={registerRepository}
                />
              ) : (
                <PdfSubmissionEditor
                  material={activeMaterial}
                  file={files[activeMaterial.id as PdfMaterialId]}
                  state={activeState}
                  onFileChange={(file) => {
                    setFiles((current) => ({
                      ...current,
                      [activeMaterial.id]: file,
                    }));
                    updateMaterialState(activeMaterial.id, "idle");
                  }}
                  onSubmit={(event) =>
                    void uploadPdf(event, activeMaterial.id as PdfMaterialId)
                  }
                />
              )}
            </div>

            <footer className="mt-auto flex items-center gap-5 border-t border-border bg-surface-muted px-7 py-4 max-sm:items-start max-sm:flex-col max-sm:px-5">
              <div className="flex min-w-0 items-center gap-3">
                <span
                  className={cn(
                    "grid size-8 shrink-0 place-items-center rounded-full",
                    activeSubmissionStatus.tone === "success"
                      ? "bg-success-soft text-success"
                      : "bg-surface-strong text-muted",
                  )}
                >
                  {activeSubmissionStatus.tone === "success" ? (
                    <CheckCircle2 aria-hidden="true" size={17} />
                  ) : (
                    <FileText aria-hidden="true" size={16} />
                  )}
                </span>
                <span className="min-w-0">
                  <strong className="block text-xs font-semibold text-ink">
                    {activeSubmissionStatus.label} ·{" "}
                    {activeAnalysisStatus.label}
                  </strong>
                  <small className="mt-0.5 block truncate text-[11px] text-muted">
                    {readiness?.impactSummary ??
                      "제출 완료 후 분석 상태가 자동으로 반영됩니다."}
                  </small>
                </span>
              </div>
            </footer>
          </section>
        </div>
      </section>

      <section
        className="mt-4 flex items-center justify-between gap-6 rounded-lg border border-border bg-surface px-6 py-5 shadow-soft max-sm:items-start max-sm:flex-col"
        aria-label="다음 단계"
      >
        <div>
          <p className="m-0 text-sm font-bold text-ink">
            모든 제출 자료 통합 상태
          </p>
          <p className="mt-1 text-xs leading-5 text-muted">
            {canContinue
              ? "필수 자료 분석이 완료되었습니다. 환경 점검을 진행할 수 있습니다."
              : remainingRequiredCount > 0
                ? `필수 자료 ${remainingRequiredCount}개를 더 제출해 주세요.`
                : "제출된 자료의 분석 결과를 확인하고 있습니다."}
          </p>
        </div>
        {canContinue ? (
          <button
            className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-md border border-brand bg-brand px-5 text-sm font-semibold text-white hover:bg-brand-strong"
            type="button"
            onClick={() => {
              if (readiness?.strategyId) onContinue?.(readiness.strategyId);
            }}
          >
            환경 점검으로 이동
            <ArrowRight aria-hidden="true" size={16} />
          </button>
        ) : null}
      </section>

      {debugEnabled ? (
        <AnalysisDebugPanel
          result={debugResult}
          state={debugState}
          onRefresh={() => void refreshAnalysisDebug()}
        />
      ) : null}
    </main>
  );
}
