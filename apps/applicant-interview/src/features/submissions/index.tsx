import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  FileText,
  GitBranch,
  Plus,
  X,
} from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

export type AnalysisReadiness = {
  overallStatus: "waiting" | "analyzing" | "ready" | "partial" | "failed";
  interviewReady: boolean;
  impactSummary?: string;
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
  readiness: AnalysisReadiness | null,
) {
  if (state !== "success") {
    return { label: "분석 대기", tone: "neutral" as const };
  }
  if (!readiness || readiness.overallStatus === "waiting") {
    return { label: "분석 대기", tone: "neutral" as const };
  }
  if (readiness.overallStatus === "analyzing") {
    return { label: "분석 중", tone: "info" as const };
  }
  if (readiness.overallStatus === "ready") {
    return { label: "분석 완료", tone: "success" as const };
  }
  if (readiness.overallStatus === "partial") {
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

export function SubmissionWorkspace({
  api,
  onContinue,
  positionTitle,
  requirements = DEFAULT_SUBMISSION_REQUIREMENTS,
  submittedMaterials = [],
}: {
  api: SubmissionWorkspaceApi;
  onContinue?: () => void;
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

  useEffect(() => {
    void refreshReadiness();
  }, []);

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

  async function refreshReadiness() {
    try {
      setReadiness(await api.getReadiness());
    } catch {
      setReadiness(null);
    }
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

  if (!activeMaterial) {
    return null;
  }

  const activeState = materialStates[activeMaterial.id];
  const activeHasInput =
    activeMaterial.id === "projects"
      ? repositoryCount > 0
      : files[activeMaterial.id as PdfMaterialId] !== null;
  const activeSubmissionStatus = submissionStatus(activeState, activeHasInput);
  const activeAnalysisStatus = analysisStatus(activeState, readiness);
  const canContinue =
    remainingRequiredCount === 0 && readiness?.interviewReady === true;

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
                const analyzed = analysisStatus(state, readiness);
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

            <footer className="mt-auto flex items-center justify-between gap-5 border-t border-border bg-surface-muted px-7 py-4 max-sm:items-start max-sm:flex-col max-sm:px-5">
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

              {canContinue ? (
                <button
                  className="inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-md border border-brand bg-brand px-4 text-xs font-semibold text-white hover:bg-brand-strong"
                  type="button"
                  onClick={onContinue}
                >
                  환경 점검으로 이동
                  <ArrowRight aria-hidden="true" size={15} />
                </button>
              ) : (
                <span className="shrink-0 text-xs font-medium text-muted">
                  {remainingRequiredCount > 0
                    ? `필수 자료 ${remainingRequiredCount}개 남음`
                    : "분석 결과 확인 중"}
                </span>
              )}
            </footer>
          </section>
        </div>
      </section>
    </main>
  );
}
