import {
  CheckCircle2,
  CircleAlert,
  FileUp,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  RefreshCw,
  Search,
  Send,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

export type InvitationStatus =
  | "invited"
  | "identity_verified"
  | "consented"
  | "materials_submitted"
  | "analyzing"
  | "ready"
  | "interviewing"
  | "interrupted"
  | "completed"
  | "reviewed"
  | "expired"
  | "revoked"
  | "deleted";

export type PositionInvitation = Readonly<{
  invitationId: string;
  positionId: string;
  competencyModelVersionId: string;
  applicantEmail: string;
  applicantDisplayName?: string | null;
  status: InvitationStatus;
  expiresAt: string;
  rowVersion: number;
  analysisStatus?: string | null;
  interviewStatus?: string | null;
  reportStatus?: string | null;
  interviewSessionId?: string | null;
}>;

export type InvitationApplicant = Readonly<{
  displayName: string;
  email: string;
}>;

type InvitationDraftRow = Readonly<{
  id: string;
  displayName: string;
  email: string;
}>;

type InvitationDraftState = "empty" | "valid" | "invalid" | "duplicate";

type ValidatedInvitationDraft = InvitationDraftRow &
  Readonly<{
    state: InvitationDraftState;
    message: string;
    applicant: InvitationApplicant | null;
  }>;

export type PositionInvitationApi = Readonly<{
  listInvitations(positionId: string): Promise<readonly PositionInvitation[]>;
  createInvitations(
    positionId: string,
    applicants: readonly InvitationApplicant[],
    expiresInDays: number,
  ): Promise<{
    acceptedCount: number;
    rejectedCount: number;
    invitations: readonly PositionInvitation[];
  }>;
}>;

type InvitationFilter =
  "all" | "waiting" | "progress" | "completed" | "attention";

export const invitationStatusMeta: Record<
  InvitationStatus,
  { label: string; stage: number; tone: string }
> = {
  invited: { label: "초대 발송", stage: 1, tone: "neutral" },
  identity_verified: { label: "본인 확인", stage: 2, tone: "progress" },
  consented: { label: "동의 완료", stage: 3, tone: "progress" },
  materials_submitted: { label: "자료 제출", stage: 4, tone: "progress" },
  analyzing: { label: "자료 분석", stage: 5, tone: "progress" },
  ready: { label: "면접 준비", stage: 6, tone: "ready" },
  interviewing: { label: "면접 진행", stage: 7, tone: "progress" },
  interrupted: { label: "재접속 필요", stage: 7, tone: "attention" },
  completed: { label: "면접 완료", stage: 8, tone: "completed" },
  reviewed: { label: "검토 완료", stage: 9, tone: "completed" },
  expired: { label: "만료", stage: 0, tone: "attention" },
  revoked: { label: "취소", stage: 0, tone: "attention" },
  deleted: { label: "삭제", stage: 0, tone: "muted" },
};

export const recruiterPhaseCount = 4;

export function invitationRecruiterPhase(status: InvitationStatus) {
  const internalStage = invitationStatusMeta[status].stage;
  if (internalStage <= 0) return 0;
  if (internalStage <= 3) return 1;
  if (internalStage <= 5) return 2;
  if (internalStage <= 7) return 3;
  return 4;
}

const waitingStatuses = new Set<InvitationStatus>([
  "invited",
  "identity_verified",
  "consented",
]);
const progressStatuses = new Set<InvitationStatus>([
  "materials_submitted",
  "analyzing",
  "ready",
  "interviewing",
  "interrupted",
]);
const completedStatuses = new Set<InvitationStatus>(["completed", "reviewed"]);
const attentionStatuses = new Set<InvitationStatus>(["expired", "revoked"]);
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
let draftRowSequence = 0;

export function PositionInvitations({
  positionId,
  positionName,
  api,
  embedded = false,
  view = "all",
}: {
  positionId: string;
  positionName?: string;
  api: PositionInvitationApi;
  embedded?: boolean;
  view?: "all" | "roster" | "invite" | "workspace";
}) {
  const [invitations, setInvitations] = useState<readonly PositionInvitation[]>(
    [],
  );
  const [draftRows, setDraftRows] = useState<readonly InvitationDraftRow[]>([
    createDraftRow(),
  ]);
  const [expiryDays, setExpiryDays] = useState(7);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<InvitationFilter>("all");
  const [loading, setLoading] = useState(true);
  const [issuing, setIssuing] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [invitePanelOpen, setInvitePanelOpen] = useState(true);
  const workspace = view === "workspace";
  const validatedDrafts = useMemo(
    () =>
      validateInvitationDrafts(
        draftRows,
        new Set(
          invitations.map((invitation) =>
            invitation.applicantEmail.toLocaleLowerCase("en-US"),
          ),
        ),
      ),
    [draftRows, invitations],
  );
  const validationSummary = useMemo(
    () => ({
      valid: validatedDrafts.filter((row) => row.state === "valid").length,
      invalid: validatedDrafts.filter((row) => row.state === "invalid").length,
      duplicate: validatedDrafts.filter((row) => row.state === "duplicate")
        .length,
      hasInput: validatedDrafts.some((row) => row.state !== "empty"),
    }),
    [validatedDrafts],
  );

  async function loadInvitations() {
    setError("");
    try {
      setInvitations(await api.listInvitations(positionId));
    } catch {
      setError(
        "지원자 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    api
      .listInvitations(positionId)
      .then((items) => {
        if (active) setInvitations(items);
      })
      .catch(() => {
        if (active) {
          setError(
            "지원자 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, positionId]);

  const metrics = useMemo(
    () => ({
      total: invitations.length,
      waiting: invitations.filter((item) => waitingStatuses.has(item.status))
        .length,
      progress: invitations.filter((item) => progressStatuses.has(item.status))
        .length,
      completed: invitations.filter((item) =>
        completedStatuses.has(item.status),
      ).length,
      attention: invitations.filter((item) =>
        attentionStatuses.has(item.status),
      ).length,
    }),
    [invitations],
  );

  const filteredInvitations = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("ko-KR");
    return invitations.filter((invitation) => {
      const matchesQuery =
        !normalizedQuery ||
        invitation.applicantEmail
          .toLocaleLowerCase("ko-KR")
          .includes(normalizedQuery) ||
        (invitation.applicantDisplayName ?? "")
          .toLocaleLowerCase("ko-KR")
          .includes(normalizedQuery);
      if (!matchesQuery) return false;
      if (filter === "waiting") return waitingStatuses.has(invitation.status);
      if (filter === "progress") return progressStatuses.has(invitation.status);
      if (filter === "completed") {
        return completedStatuses.has(invitation.status);
      }
      if (filter === "attention") {
        return attentionStatuses.has(invitation.status);
      }
      return true;
    });
  }, [filter, invitations, query]);

  async function createInvitations(applicants: readonly InvitationApplicant[]) {
    setIssuing(true);
    setError("");
    setNotice("");
    try {
      const result = await api.createInvitations(
        positionId,
        applicants,
        expiryDays,
      );
      setNotice(`${result.acceptedCount}명의 초대를 발송했습니다.`);
      setDraftRows([createDraftRow()]);
      await loadInvitations();
    } catch {
      setError(
        "초대 발송을 완료하지 못했습니다. 이메일 형식과 채용 관리 상태를 확인해 주세요.",
      );
    } finally {
      setIssuing(false);
    }
  }

  function updateDraftRow(
    id: string,
    field: "displayName" | "email",
    value: string,
  ) {
    setDraftRows((current) =>
      current.map((row) => (row.id === id ? { ...row, [field]: value } : row)),
    );
  }

  function addDraftRow() {
    setDraftRows((current) =>
      current.length >= 1000 ? current : [...current, createDraftRow()],
    );
  }

  function removeDraftRow(id: string) {
    setDraftRows((current) => {
      const next = current.filter((row) => row.id !== id);
      return next.length ? next : [createDraftRow()];
    });
  }

  async function importApplicants(file: File | undefined) {
    if (!file) return;
    setError("");
    setNotice("");
    try {
      const imported = parseInvitationImport(file.name, await file.text());
      if (!imported.length) {
        throw new Error("empty_import");
      }
      setDraftRows(
        imported
          .slice(0, 1000)
          .map((applicant) =>
            createDraftRow(applicant.displayName, applicant.email),
          ),
      );
    } catch {
      setError(
        "파일을 불러오지 못했습니다. CSV의 이름·이메일 열 또는 JSON 배열 형식을 확인해 주세요.",
      );
    }
  }

  return (
    <div className={`position-invitations ${embedded ? "is-embedded" : ""}`}>
      {!embedded ? (
        <header className="page-header position-invitations__header">
          <div>
            <p className="page-eyebrow">Position applicants</p>
            <h1>지원자 관리</h1>
            <p>
              {positionName ?? "선택한 포지션"}의 지원자와 면접 상태를
              관리합니다.
            </p>
          </div>
        </header>
      ) : null}

      <div
        className={`${embedded ? "" : "page-content"} position-invitations__content`}
      >
        {notice ? (
          <p className="form-alert is-success" role="status">
            {notice}
          </p>
        ) : null}
        {error ? (
          <p className="form-alert" role="alert">
            {error}
          </p>
        ) : null}

        <div
          className={
            workspace
              ? `invitation-workspace ${invitePanelOpen ? "" : "is-collapsed"}`
              : "position-invitations__layout"
          }
        >
          {view !== "invite" ? (
            <section className="panel invitation-roster">
              <header className="section-header invitation-roster__header">
                <div>
                  <h2>지원자 목록</h2>
                  <p>지원자별 본인 확인부터 면접 완료까지 현재 상태입니다.</p>
                </div>
                <div className="invitation-roster__actions">
                  <label className="search-field">
                    <Search size={15} aria-hidden="true" />
                    <span className="sr-only">지원자 검색</span>
                    <input
                      aria-label="지원자 검색"
                      type="search"
                      value={query}
                      placeholder="이름 또는 이메일"
                      onChange={(event) => setQuery(event.target.value)}
                    />
                  </label>
                  <button
                    className="button-quiet"
                    type="button"
                    disabled={loading}
                    onClick={() => void loadInvitations()}
                  >
                    <RefreshCw size={14} aria-hidden="true" />
                    새로고침
                  </button>
                </div>
              </header>
              <div className="filter-tabs invitation-filter-tabs">
                {(
                  [
                    ["all", "전체", metrics.total],
                    ["waiting", "응답 대기", metrics.waiting],
                    ["progress", "진행 중", metrics.progress],
                    ["completed", "완료", metrics.completed],
                    ["attention", "확인 필요", metrics.attention],
                  ] as const
                ).map(([value, label, count]) => (
                  <button
                    key={value}
                    type="button"
                    className={filter === value ? "is-active" : ""}
                    aria-pressed={filter === value}
                    onClick={() => setFilter(value)}
                  >
                    {label}
                    <span>{count}</span>
                  </button>
                ))}
              </div>
              {loading ? (
                <div className="async-state" role="status">
                  지원자 목록을 불러오는 중입니다.
                </div>
              ) : filteredInvitations.length ? (
                <InvitationTable
                  invitations={filteredInvitations}
                  issuing={issuing}
                  onReissue={(applicant) => void createInvitations([applicant])}
                />
              ) : (
                <div className="empty-state">
                  <Users size={24} aria-hidden="true" />
                  <div>
                    <strong>아직 지원자가 없습니다.</strong>
                    <p>
                      {view === "roster"
                        ? "지원자 초대 도구에서 첫 지원자를 등록하세요."
                        : "초대 관리 패널에서 첫 지원자를 등록하세요."}
                    </p>
                  </div>
                </div>
              )}
            </section>
          ) : null}

          {workspace && !invitePanelOpen ? (
            <button
              className="invitation-workspace__expand"
              type="button"
              aria-label="초대 패널 펼치기"
              title="초대 패널 펼치기"
              onClick={() => setInvitePanelOpen(true)}
            >
              <PanelRightOpen size={17} aria-hidden="true" />
              <span>지원자 초대</span>
            </button>
          ) : null}

          {view !== "roster" && (!workspace || invitePanelOpen) ? (
            <aside
              className={workspace ? "invitation-workspace__aside" : undefined}
            >
              <section className="panel invitation-composer">
                <header className="section-header invitation-composer__header">
                  <div>
                    <h2>{workspace ? "지원자 초대 관리" : "지원자 초대"}</h2>
                    <p>
                      이름과 이메일을 확인한 뒤 유효한 행만 일괄 발송합니다.
                    </p>
                  </div>
                  <div className="invitation-import-actions">
                    {workspace ? (
                      <button
                        className="icon-button invitation-panel-toggle"
                        type="button"
                        title="초대 패널 접기"
                        aria-label="초대 패널 접기"
                        onClick={() => setInvitePanelOpen(false)}
                      >
                        <PanelRightClose size={16} aria-hidden="true" />
                      </button>
                    ) : null}
                    <label className="button-secondary invitation-file-button">
                      <FileUp size={14} aria-hidden="true" />
                      CSV/JSON 가져오기
                      <input
                        className="sr-only"
                        aria-label="CSV 또는 JSON 가져오기"
                        type="file"
                        accept=".csv,.json,text/csv,application/json"
                        onChange={(event) => {
                          const file = event.currentTarget.files?.[0];
                          void importApplicants(file);
                          event.currentTarget.value = "";
                        }}
                      />
                    </label>
                    <button
                      className="button-secondary"
                      type="button"
                      disabled={draftRows.length >= 1000}
                      aria-label="지원자 행 추가"
                      onClick={addDraftRow}
                    >
                      <Plus size={14} aria-hidden="true" />행 추가
                    </button>
                    <span className="invitation-limit">최대 1,000명</span>
                  </div>
                </header>
                <div className="invitation-entry-table-wrap">
                  <table className="invitation-entry-table">
                    <thead>
                      <tr>
                        <th scope="col">No.</th>
                        <th scope="col">이름</th>
                        <th scope="col">이메일</th>
                        <th scope="col">검증 결과</th>
                        <th scope="col">
                          <span className="sr-only">행 삭제</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {validatedDrafts.map((row, index) => (
                        <tr key={row.id} className={`is-${row.state}`}>
                          <td data-label="번호">{index + 1}</td>
                          <td data-label="이름">
                            <input
                              aria-label={`지원자 ${index + 1} 이름`}
                              value={row.displayName}
                              placeholder="홍길동"
                              maxLength={200}
                              onChange={(event) =>
                                updateDraftRow(
                                  row.id,
                                  "displayName",
                                  event.target.value,
                                )
                              }
                            />
                          </td>
                          <td data-label="이메일">
                            <input
                              aria-label={`지원자 ${index + 1} 이메일`}
                              value={row.email}
                              placeholder="hong@example.com"
                              inputMode="email"
                              maxLength={320}
                              onChange={(event) =>
                                updateDraftRow(
                                  row.id,
                                  "email",
                                  event.target.value,
                                )
                              }
                            />
                          </td>
                          <td data-label="검증 결과">
                            <DraftValidationStatus row={row} />
                          </td>
                          <td data-label="행 삭제">
                            <button
                              className="icon-button invitation-row-remove"
                              type="button"
                              title="행 삭제"
                              aria-label={`지원자 ${index + 1} 행 삭제`}
                              onClick={() => removeDraftRow(row.id)}
                            >
                              <Trash2 size={14} aria-hidden="true" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="invitation-composer__footer">
                  <div className="invitation-validation" aria-live="polite">
                    {validationSummary.hasInput ? (
                      <>
                        <span className="is-valid">
                          발송 가능 {validationSummary.valid}명
                        </span>
                        <span
                          className={
                            validationSummary.invalid ? "is-warning" : undefined
                          }
                        >
                          확인 필요 {validationSummary.invalid}명
                        </span>
                        <span
                          className={
                            validationSummary.duplicate
                              ? "is-duplicate"
                              : undefined
                          }
                        >
                          중복 제외 {validationSummary.duplicate}명
                        </span>
                      </>
                    ) : (
                      <span>
                        이름과 이메일을 입력하면 검증 결과가 표시됩니다.
                      </span>
                    )}
                  </div>
                  <div className="invitation-composer__actions">
                    <fieldset className="segmented-control">
                      <legend>초대 링크 유효기간</legend>
                      {[3, 7, 14].map((days) => (
                        <button
                          key={days}
                          type="button"
                          className={expiryDays === days ? "is-active" : ""}
                          aria-pressed={expiryDays === days}
                          onClick={() => setExpiryDays(days)}
                        >
                          {days}일
                        </button>
                      ))}
                    </fieldset>
                    <button
                      className="button-primary"
                      type="button"
                      disabled={!validationSummary.valid || issuing}
                      onClick={() =>
                        void createInvitations(
                          validatedDrafts.flatMap((row) =>
                            row.applicant ? [row.applicant] : [],
                          ),
                        )
                      }
                    >
                      <Send size={15} aria-hidden="true" />
                      {issuing
                        ? "초대 발송 중"
                        : `${validationSummary.valid}명에게 초대 보내기`}
                    </button>
                  </div>
                </div>
              </section>
            </aside>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function InvitationTable({
  invitations,
  issuing,
  onReissue,
}: {
  invitations: readonly PositionInvitation[];
  issuing: boolean;
  onReissue(applicant: InvitationApplicant): void;
}) {
  return (
    <div className="invitation-table-wrap">
      <table className="invitation-table">
        <thead>
          <tr>
            <th>지원자</th>
            <th>현재 상태</th>
            <th>진행 단계</th>
            <th>링크 만료</th>
            <th>
              <span className="sr-only">작업</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {invitations.map((invitation) => {
            const status = invitationStatusMeta[invitation.status];
            const recruiterPhase = invitationRecruiterPhase(invitation.status);
            const displayName =
              invitation.applicantDisplayName ||
              invitation.applicantEmail.split("@")[0];
            const canReissue = attentionStatuses.has(invitation.status);
            return (
              <tr key={invitation.invitationId}>
                <td data-label="지원자">
                  <span className="recipient-avatar" aria-hidden="true">
                    {displayName.slice(0, 1).toLocaleUpperCase("ko-KR")}
                  </span>
                  <span>
                    <Link
                      className="invitation-applicant-link"
                      aria-label={`${displayName} 상세 보기`}
                      to={`/positions/${invitation.positionId}/applicants/${invitation.invitationId}`}
                    >
                      <strong>{displayName}</strong>
                    </Link>
                    <small>{invitation.applicantEmail}</small>
                  </span>
                </td>
                <td data-label="현재 상태">
                  <span className={`invitation-status is-${status.tone}`}>
                    {status.label}
                  </span>
                </td>
                <td data-label="진행 단계">
                  <div
                    className="recipient-progress"
                    aria-label={
                      recruiterPhase
                        ? `전체 4단계 중 ${recruiterPhase}단계`
                        : "채용 진행 단계 없음"
                    }
                  >
                    <span>
                      <i
                        style={{
                          width: `${(recruiterPhase / recruiterPhaseCount) * 100}%`,
                        }}
                      />
                    </span>
                    <small>{recruiterPhase || "-"} / 4</small>
                  </div>
                </td>
                <td data-label="링크 만료">
                  <time dateTime={invitation.expiresAt}>
                    {formatDate(invitation.expiresAt)}
                  </time>
                </td>
                <td data-label="작업">
                  {canReissue ? (
                    <button
                      className="button-quiet"
                      type="button"
                      aria-label={`${displayName} 다시 초대`}
                      disabled={issuing}
                      onClick={() =>
                        onReissue({
                          displayName,
                          email: invitation.applicantEmail,
                        })
                      }
                    >
                      다시 초대
                    </button>
                  ) : (
                    <span className="invitation-row-complete">정상</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DraftValidationStatus({ row }: { row: ValidatedInvitationDraft }) {
  if (row.state === "valid") {
    return (
      <span className="draft-validation is-valid">
        <CheckCircle2 size={13} aria-hidden="true" />
        발송 가능
      </span>
    );
  }
  if (row.state === "invalid") {
    return (
      <span className="draft-validation is-invalid">
        <CircleAlert size={13} aria-hidden="true" />
        {row.message}
      </span>
    );
  }
  if (row.state === "duplicate") {
    return (
      <span className="draft-validation is-duplicate">
        <X size={13} aria-hidden="true" />
        {row.message}
      </span>
    );
  }
  return <span className="draft-validation is-empty">입력 대기</span>;
}

function createDraftRow(displayName = "", email = ""): InvitationDraftRow {
  draftRowSequence += 1;
  return {
    id: `invitation-draft-${draftRowSequence}`,
    displayName,
    email,
  };
}

function validateInvitationDrafts(
  rows: readonly InvitationDraftRow[],
  existingEmails: ReadonlySet<string>,
): ValidatedInvitationDraft[] {
  const seenEmails = new Set<string>();
  return rows.map((row) => {
    const displayName = row.displayName.trim();
    const email = row.email.trim().toLocaleLowerCase("en-US");
    if (!displayName && !email) {
      return {
        ...row,
        state: "empty",
        message: "",
        applicant: null,
      };
    }
    if (!displayName) {
      return {
        ...row,
        state: "invalid",
        message: "이름을 입력하세요.",
        applicant: null,
      };
    }
    if (!emailPattern.test(email)) {
      return {
        ...row,
        state: "invalid",
        message: "이메일 형식을 확인하세요.",
        applicant: null,
      };
    }
    if (existingEmails.has(email)) {
      return {
        ...row,
        state: "duplicate",
        message: "이미 등록된 지원자",
        applicant: null,
      };
    }
    if (seenEmails.has(email)) {
      return {
        ...row,
        state: "duplicate",
        message: "입력 명단 내 중복",
        applicant: null,
      };
    }
    seenEmails.add(email);
    return {
      ...row,
      state: "valid",
      message: "발송 가능",
      applicant: { displayName, email },
    };
  });
}

export function parseInvitationImport(
  fileName: string,
  content: string,
): InvitationApplicant[] {
  if (fileName.toLocaleLowerCase("en-US").endsWith(".json")) {
    return parseInvitationJson(content);
  }
  return parseInvitationCsv(content);
}

function parseInvitationJson(content: string): InvitationApplicant[] {
  const parsed: unknown = JSON.parse(content);
  const records =
    typeof parsed === "object" &&
    parsed !== null &&
    !Array.isArray(parsed) &&
    "applicants" in parsed
      ? (parsed as { applicants?: unknown }).applicants
      : parsed;
  if (!Array.isArray(records)) {
    throw new Error("invalid_json_shape");
  }
  return records.slice(0, 1000).map((record) => {
    if (typeof record !== "object" || record === null) {
      return { displayName: "", email: "" };
    }
    const values = record as Record<string, unknown>;
    return {
      displayName: firstString(values, [
        "displayName",
        "display_name",
        "name",
        "이름",
      ]),
      email: firstString(values, ["email", "e-mail", "이메일"]),
    };
  });
}

function parseInvitationCsv(content: string): InvitationApplicant[] {
  const rows = parseCsvRows(content.replace(/^\uFEFF/, "")).filter((row) =>
    row.some((cell) => cell.trim()),
  );
  if (!rows.length) return [];
  const normalizedHeader = rows[0].map(normalizeHeader);
  const nameIndex = normalizedHeader.findIndex((value) =>
    ["name", "displayname", "이름"].includes(value),
  );
  const emailIndex = normalizedHeader.findIndex((value) =>
    ["email", "이메일"].includes(value),
  );
  const hasHeader = nameIndex >= 0 || emailIndex >= 0;
  const resolvedNameIndex = nameIndex >= 0 ? nameIndex : 0;
  const resolvedEmailIndex = emailIndex >= 0 ? emailIndex : 1;
  return rows
    .slice(hasHeader ? 1 : 0, (hasHeader ? 1 : 0) + 1000)
    .map((row) => ({
      displayName: (row[resolvedNameIndex] ?? "").trim(),
      email: (row[resolvedEmailIndex] ?? "").trim(),
    }));
}

function parseCsvRows(content: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let value = "";
  let quoted = false;

  for (let index = 0; index < content.length; index += 1) {
    const character = content[index];
    if (character === '"') {
      if (quoted && content[index + 1] === '"') {
        value += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
      continue;
    }
    if (character === "," && !quoted) {
      row.push(value);
      value = "";
      continue;
    }
    if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && content[index + 1] === "\n") {
        index += 1;
      }
      row.push(value);
      rows.push(row);
      row = [];
      value = "";
      continue;
    }
    value += character;
  }
  row.push(value);
  rows.push(row);
  return rows;
}

function normalizeHeader(value: string) {
  return value
    .trim()
    .toLocaleLowerCase("en-US")
    .replace(/[\s_-]/g, "");
}

function firstString(record: Record<string, unknown>, keys: readonly string[]) {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string") return value.trim();
  }
  return "";
}

export function parseInvitationApplicants(value: string): {
  applicants: InvitationApplicant[];
  invalidLines: string[];
  duplicateCount: number;
} {
  const rows = parseInvitationCsv(
    value
      .split(/\r?\n/)
      .map((line) => line.replace(/\t/g, ","))
      .join("\n"),
  ).map((applicant) => createDraftRow(applicant.displayName, applicant.email));
  const validated = validateInvitationDrafts(rows, new Set());
  return {
    applicants: validated.flatMap((row) =>
      row.applicant ? [row.applicant] : [],
    ),
    invalidLines: validated
      .filter((row) => row.state === "invalid")
      .map((row) => [row.displayName, row.email].filter(Boolean).join(", ")),
    duplicateCount: validated.filter((row) => row.state === "duplicate").length,
  };
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
