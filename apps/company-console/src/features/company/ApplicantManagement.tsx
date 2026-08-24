import {
  BarChart3,
  BriefcaseBusiness,
  ClipboardCheck,
  LayoutGrid,
  List,
  Search,
  Trash2,
  UserRoundCheck,
  Users,
} from "lucide-react";
import {
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Link } from "react-router-dom";

import {
  ASYNC_STATE,
  INVITATION_STATUS,
  invitationTone,
} from "../../app/styles/primitives";
import { invitationStatusMeta } from "../hiring/PositionInvitations";
import { applicantWorkspacePath } from "../../app/applicantWorkspacePath";
import { ApplicantReportModal } from "../assistant/components/ApplicantReportModal";
import type { ApplicantReportPreview } from "../assistant/types";
import { summarizeApplicantPipeline } from "./applicantSummary";
import {
  ApplicantKanbanBoard,
  RecruitingStageSettingsDialog,
} from "./ApplicantKanbanBoard";
import type {
  CompanyDeletionStatus,
  CompanyInvitation,
  CompanyOperationsApi,
  CompanyPosition,
  CompanyRecruitingStage,
} from "./types";
import {
  useRecruitingOperations,
  type PositionedInvitation,
} from "./useRecruitingOperations";

type ApplicantDeletionStatus = CompanyDeletionStatus &
  Readonly<{ applicantDisplayName: string }>;
const PAGE_SIZE = 20;
const DELETION_STORAGE_KEY = "iep_active_applicant_deletions";
const VIEW_STORAGE_KEY = "iep_applicant_management_view_v1";
const DEFAULT_STAGE_NAMES = ["보류", "검토", "1차 합격", "최종합격", "불합격"];

export function ApplicantManagement({ api }: { api: CompanyOperationsApi }) {
  const {
    positions,
    invitations,
    loading,
    error,
    updateInvitations,
    updatePositions,
  } = useRecruitingOperations(api);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [positionFilter, setPositionFilter] = useState("all");
  const [stageFilter, setStageFilter] = useState("all");
  const [view, setView] = useState<"list" | "kanban">(() =>
    localStorage.getItem(VIEW_STORAGE_KEY) === "kanban" ? "kanban" : "list",
  );
  const [stages, setStages] = useState<readonly CompanyRecruitingStage[]>([]);
  const [stagesLoading, setStagesLoading] = useState(true);
  const [pipelineBusy, setPipelineBusy] = useState(false);
  const [pipelineNotice, setPipelineNotice] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [selectedReport, setSelectedReport] =
    useState<ApplicantReportPreview>();
  const [page, setPage] = useState(1);
  const [hiddenInvitationIds, setHiddenInvitationIds] = useState(
    () => new Set<string>(),
  );
  const [deletionTarget, setDeletionTarget] =
    useState<PositionedInvitation | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deletionError, setDeletionError] = useState(false);
  const [deletionNotice, setDeletionNotice] = useState("");
  const [deletionNoticeTone, setDeletionNoticeTone] = useState<
    "success" | "warning" | "danger"
  >("success");
  const [deletions, setDeletions] = useState<
    Readonly<Record<string, ApplicantDeletionStatus>>
  >(loadStoredApplicantDeletions);
  const activeInvitations = useMemo(() => {
    const stagesByPosition = new Map<
      string,
      readonly CompanyRecruitingStage[]
    >();
    for (const stage of stages) {
      stagesByPosition.set(stage.positionId, [
        ...(stagesByPosition.get(stage.positionId) ?? []),
        stage,
      ]);
    }
    return invitations
      .filter(
        (invitation) =>
          invitation.status !== "deleted" &&
          !hiddenInvitationIds.has(invitation.invitationId),
      )
      .map((invitation) => ({
        ...invitation,
        recruitingStageId:
          invitation.recruitingStageId ??
          stagesByPosition
            .get(invitation.positionId)
            ?.find((stage) => stage.name === defaultStageName(invitation))
            ?.recruitingStageId ??
          null,
        pipelineRowVersion: invitation.pipelineRowVersion ?? 1,
      }));
  }, [hiddenInvitationIds, invitations, stages]);
  const summary = useMemo(
    () => summarizeApplicantPipeline(activeInvitations),
    [activeInvitations],
  );
  const positionCounts = useMemo(
    () =>
      positions
        .map((position) => ({
          positionId: position.positionId,
          title: position.title,
          count: activeInvitations.filter(
            (item) => item.positionId === position.positionId,
          ).length,
        }))
        .filter((position) => position.count > 0)
        .sort((left, right) => right.count - left.count),
    [activeInvitations, positions],
  );
  const visible = useMemo(() => {
    const normalized = deferredQuery.trim().toLocaleLowerCase("ko-KR");
    return activeInvitations.filter((item) => {
      const matchesQuery =
        !normalized ||
        [
          item.applicantDisplayName ?? "",
          item.applicantEmail,
          item.positionTitle,
        ].some((value) =>
          value.toLocaleLowerCase("ko-KR").includes(normalized),
        );
      const matchesPosition =
        positionFilter === "all" || item.positionId === positionFilter;
      const matchesStage =
        stageFilter === "all" || item.recruitingStageId === stageFilter;
      return matchesQuery && matchesPosition && matchesStage;
    });
  }, [activeInvitations, deferredQuery, positionFilter, stageFilter]);
  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const activePage = Math.min(page, pageCount);
  const pageInvitations = visible.slice(
    (activePage - 1) * PAGE_SIZE,
    activePage * PAGE_SIZE,
  );
  const activeDeletionRequests = useMemo(
    () =>
      Object.entries(deletions).filter(([, deletion]) =>
        isDeletionActive(deletion.status),
      ),
    [deletions],
  );
  const currentPosition = positions.find(
    (position) => position.positionId === positionFilter,
  );
  const currentStages = [...stages]
    .filter((stage) => stage.positionId === positionFilter)
    .sort((left, right) => left.sortOrder - right.sortOrder);

  useEffect(() => {
    localStorage.setItem(VIEW_STORAGE_KEY, view);
  }, [view]);

  useEffect(() => {
    if (loading) return;
    let active = true;
    setStagesLoading(true);
    const request = api.listRecruitingStages
      ? api.listRecruitingStages()
      : Promise.resolve(virtualStages(positions));
    request
      .then((loadedStages) => {
        if (active) setStages(loadedStages);
      })
      .catch(() => {
        if (active) {
          setStages(virtualStages(positions));
          setPipelineNotice(
            "채용 단계를 불러오지 못해 기본 단계로 표시합니다.",
          );
        }
      })
      .finally(() => {
        if (active) setStagesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, loading, positions]);

  useEffect(() => {
    if (
      view !== "kanban" ||
      positionFilter !== "all" ||
      positions.length === 0
    ) {
      return;
    }
    const firstWithApplicants = positions.find((position) =>
      activeInvitations.some(
        (invitation) => invitation.positionId === position.positionId,
      ),
    );
    setPositionFilter((firstWithApplicants ?? positions[0]).positionId);
    setStageFilter("all");
  }, [activeInvitations, positionFilter, positions, view]);

  useEffect(() => {
    persistActiveApplicantDeletions(deletions);
  }, [deletions]);

  useEffect(() => {
    const getApplicantDeletion = api.getApplicantDeletion;
    if (!getApplicantDeletion || activeDeletionRequests.length === 0) {
      return;
    }
    let active = true;
    let polling = false;

    async function pollDeletionProgress() {
      if (polling) return;
      polling = true;
      const updates = await Promise.all(
        activeDeletionRequests.map(async ([invitationId, deletion]) => {
          try {
            const progress = await getApplicantDeletion!(
              deletion.deletionRequestId,
            );
            return { invitationId, deletion, progress };
          } catch {
            return null;
          }
        }),
      );
      polling = false;
      if (!active) return;

      const completed = updates.filter(
        (update) => update?.progress.status === "completed",
      );
      const partiallyCompleted = updates.filter(
        (update) => update?.progress.status === "partially_completed",
      );
      setDeletions((current) => {
        let next = current;
        for (const update of updates) {
          if (!update) continue;
          const existing = current[update.invitationId];
          if (
            !existing ||
            existing.deletionRequestId !== update.progress.deletionRequestId
          ) {
            continue;
          }
          if (
            existing.status === update.progress.status &&
            existing.expectedTargets === update.progress.expectedTargets &&
            existing.verifiedTargets === update.progress.verifiedTargets
          ) {
            continue;
          }
          if (next === current) next = { ...current };
          next = {
            ...next,
            [update.invitationId]: {
              ...update.progress,
              applicantDisplayName: existing.applicantDisplayName,
            },
          };
        }
        return next;
      });

      if (completed.length > 0) {
        setHiddenInvitationIds((current) => {
          const next = new Set(current);
          for (const update of completed) {
            if (update) next.add(update.invitationId);
          }
          return next;
        });
        const latest = completed.at(-1);
        if (latest) {
          setDeletionNoticeTone("success");
          setDeletionNotice(
            `${latest.deletion.applicantDisplayName} 지원자의 데이터 삭제를 완료했습니다.`,
          );
        }
      } else if (partiallyCompleted.length > 0) {
        const latest = partiallyCompleted.at(-1);
        if (latest) {
          setDeletionNoticeTone("danger");
          setDeletionNotice(
            `${latest.deletion.applicantDisplayName} 지원자의 일부 데이터를 삭제하지 못했습니다. 다시 시도해 주세요.`,
          );
        }
      } else if (updates.every((update) => update === null)) {
        setDeletionNoticeTone("warning");
        setDeletionNotice(
          "삭제는 진행 중이지만 현재 상태 확인이 지연되고 있습니다.",
        );
      }
    }

    void pollDeletionProgress();
    const timer = window.setInterval(() => void pollDeletionProgress(), 1500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [activeDeletionRequests, api]);

  function resetFilters() {
    setQuery("");
    setPositionFilter("all");
    setStageFilter("all");
    setPage(1);
  }

  async function confirmApplicantDeletion() {
    if (!deletionTarget || !api.requestApplicantDeletion) return;
    setDeleting(true);
    setDeletionError(false);
    try {
      const applicantDisplayName =
        deletionTarget.applicantDisplayName || deletionTarget.applicantEmail;
      const progress = await api.requestApplicantDeletion(
        deletionTarget.invitationId,
      );
      setDeletions((current) => ({
        ...current,
        [deletionTarget.invitationId]: {
          ...progress,
          applicantDisplayName,
        },
      }));
      if (progress.status === "completed") {
        setHiddenInvitationIds((current) => {
          const next = new Set(current);
          next.add(deletionTarget.invitationId);
          return next;
        });
        setDeletionNoticeTone("success");
        setDeletionNotice(
          `${applicantDisplayName} 지원자의 데이터 삭제를 완료했습니다.`,
        );
      } else {
        setDeletionNoticeTone("warning");
        setDeletionNotice(
          `${applicantDisplayName} 지원자의 삭제 요청을 접수했습니다. 실제 삭제가 끝날 때까지 목록에 표시됩니다.`,
        );
      }
      setDeletionTarget(null);
    } catch {
      setDeletionError(true);
    } finally {
      setDeleting(false);
    }
  }

  function openApplicantReport(invitation: PositionedInvitation) {
    setSelectedReport({
      invitation,
      positionTitle: invitation.positionTitle,
      recruitingStageName: stages.find(
        (stage) => stage.recruitingStageId === invitation.recruitingStageId,
      )?.name,
    });
  }

  async function moveSelectedApplicant(stageId: string) {
    if (!selectedReport) return false;
    return moveApplicants([selectedReport.invitation.invitationId], stageId);
  }

  async function moveApplicants(
    invitationIds: readonly string[],
    targetStageId: string,
  ) {
    if (!currentPosition || !api.moveApplicantsToRecruitingStage) {
      setPipelineNotice("현재 환경에서는 채용 단계를 변경할 수 없습니다.");
      return false;
    }
    const idSet = new Set(invitationIds);
    const before = new Map(
      activeInvitations
        .filter((invitation) => idSet.has(invitation.invitationId))
        .map((invitation) => [
          invitation.invitationId,
          {
            recruitingStageId: invitation.recruitingStageId,
            pipelineRowVersion: invitation.pipelineRowVersion ?? 1,
          },
        ]),
    );
    if (before.size === 0) return false;
    setPipelineBusy(true);
    setPipelineNotice("");
    updateInvitations((current) =>
      current.map((invitation) =>
        idSet.has(invitation.invitationId)
          ? { ...invitation, recruitingStageId: targetStageId }
          : invitation,
      ),
    );
    try {
      const assignments = await api.moveApplicantsToRecruitingStage(
        currentPosition.positionId,
        targetStageId,
        [...before].map(([invitationId, snapshot]) => ({
          invitationId,
          expectedVersion: snapshot.pipelineRowVersion,
        })),
      );
      const assignmentById = new Map(
        assignments.map((assignment) => [assignment.invitationId, assignment]),
      );
      updateInvitations((current) =>
        current.map((invitation) => {
          const assignment = assignmentById.get(invitation.invitationId);
          return assignment
            ? {
                ...invitation,
                recruitingStageId: assignment.recruitingStageId,
                pipelineRowVersion: assignment.pipelineRowVersion,
              }
            : invitation;
        }),
      );
      setPipelineNotice(`${assignments.length}명의 채용 단계를 변경했습니다.`);
      return true;
    } catch {
      updateInvitations((current) =>
        current.map((invitation) => {
          const snapshot = before.get(invitation.invitationId);
          return snapshot ? { ...invitation, ...snapshot } : invitation;
        }),
      );
      setPipelineNotice(
        "단계를 변경하지 못했습니다. 다른 담당자의 변경사항을 확인한 뒤 다시 시도해 주세요.",
      );
      return false;
    } finally {
      setPipelineBusy(false);
    }
  }

  async function saveApplicantCapacity(capacity: number | null) {
    if (!currentPosition) return false;
    setPipelineBusy(true);
    try {
      const updated = await api.updatePosition({
        positionId: currentPosition.positionId,
        title: currentPosition.title,
        description: currentPosition.description,
        roleType: currentPosition.roleType,
        headcount: currentPosition.headcount,
        applicantCapacity: capacity,
        interviewCapacity: currentPosition.interviewCapacity,
        interviewAt: currentPosition.interviewAt,
        recruitmentStartAt: currentPosition.recruitmentStartAt,
        recruitmentEndAt: currentPosition.recruitmentEndAt,
        submissionRequirements: currentPosition.submissionRequirements,
        status: currentPosition.status as "draft" | "active" | "closed",
        rowVersion: currentPosition.rowVersion,
      });
      updatePositions((current) =>
        current.map((position) =>
          position.positionId === updated.positionId ? updated : position,
        ),
      );
      setPipelineNotice(
        capacity == null
          ? "지원자 정원을 해제했습니다."
          : `지원자 정원을 ${capacity}명으로 저장했습니다.`,
      );
      return true;
    } catch {
      setPipelineNotice("지원자 정원을 저장하지 못했습니다.");
      return false;
    } finally {
      setPipelineBusy(false);
    }
  }

  async function createStage(name: string) {
    if (!currentPosition || !api.createRecruitingStage) return false;
    setPipelineBusy(true);
    try {
      const created = await api.createRecruitingStage(
        currentPosition.positionId,
        name,
      );
      setStages((current) => [...current, created]);
      setPipelineNotice(`${created.name} 단계를 추가했습니다.`);
      return true;
    } catch {
      setPipelineNotice(
        "단계를 추가하지 못했습니다. 이름이 중복되지 않는지 확인해 주세요.",
      );
      return false;
    } finally {
      setPipelineBusy(false);
    }
  }

  async function renameStage(stage: CompanyRecruitingStage, name: string) {
    if (!currentPosition || !api.updateRecruitingStage || !name.trim())
      return false;
    setPipelineBusy(true);
    try {
      const updated = await api.updateRecruitingStage(
        currentPosition.positionId,
        stage.recruitingStageId,
        name,
        stage.rowVersion,
      );
      setStages((current) =>
        current.map((candidate) =>
          candidate.recruitingStageId === updated.recruitingStageId
            ? updated
            : candidate,
        ),
      );
      setPipelineNotice("단계 이름을 변경했습니다.");
      return true;
    } catch {
      setPipelineNotice("단계 이름을 변경하지 못했습니다.");
      return false;
    } finally {
      setPipelineBusy(false);
    }
  }

  async function reorderStages(orderedStageIds: readonly string[]) {
    if (!currentPosition || !api.reorderRecruitingStages) return false;
    setPipelineBusy(true);
    try {
      const reordered = await api.reorderRecruitingStages(
        currentPosition.positionId,
        orderedStageIds,
      );
      setStages((current) => [
        ...current.filter(
          (stage) => stage.positionId !== currentPosition.positionId,
        ),
        ...reordered,
      ]);
      setPipelineNotice("단계 순서를 변경했습니다.");
      return true;
    } catch {
      setPipelineNotice("단계 순서를 변경하지 못했습니다.");
      return false;
    } finally {
      setPipelineBusy(false);
    }
  }

  async function deleteStage(stageId: string, replacementStageId: string) {
    if (!currentPosition || !api.deleteRecruitingStage) return false;
    setPipelineBusy(true);
    try {
      const remaining = await api.deleteRecruitingStage(
        currentPosition.positionId,
        stageId,
        replacementStageId,
      );
      setStages((current) => [
        ...current.filter(
          (stage) => stage.positionId !== currentPosition.positionId,
        ),
        ...remaining,
      ]);
      updateInvitations((current) =>
        current.map((invitation) =>
          invitation.positionId === currentPosition.positionId &&
          invitation.recruitingStageId === stageId
            ? {
                ...invitation,
                recruitingStageId: replacementStageId,
                pipelineRowVersion: (invitation.pipelineRowVersion ?? 1) + 1,
              }
            : invitation,
        ),
      );
      setStageFilter("all");
      setPipelineNotice("단계를 삭제하고 포함된 지원자를 이동했습니다.");
      return true;
    } catch {
      setPipelineNotice("단계를 삭제하지 못했습니다.");
      return false;
    } finally {
      setPipelineBusy(false);
    }
  }

  return (
    <div className="grid gap-4 px-8 pt-7 pb-12 mw-720:px-4 mw-720:pt-5 mw-720:pb-8">
      <header className="flex items-end justify-between gap-5 mw-720:flex-col mw-720:items-stretch">
        <div>
          <p className="text-[9px] font-bold tracking-[0.08em] text-brand uppercase">
            Applicant analytics
          </p>
          <h1 className="mt-1 text-[26px] font-bold text-ink">지원자 관리</h1>
          <p className="mt-1.5 text-[12px] leading-[1.5] text-muted">
            전체 지원자의 분포와 검토 대상을 확인한 뒤 지원자 리포트로
            이동합니다.
          </p>
        </div>
      </header>

      <section
        className="grid grid-cols-4 overflow-hidden rounded-lg border border-border bg-surface mw-720:grid-cols-2"
        aria-label="전체 지원자 통계"
      >
        <SummaryMetric
          icon={<Users size={17} />}
          label="전체 지원자"
          value={`${summary.total}명`}
        />
        <SummaryMetric
          icon={<BriefcaseBusiness size={17} />}
          label="지원 포지션"
          value={`${positionCounts.length}개`}
        />
        <SummaryMetric
          icon={<UserRoundCheck size={17} />}
          label="진행 중"
          value={`${summary.inProgress}명`}
        />
        <SummaryMetric
          icon={<ClipboardCheck size={17} />}
          label="검토 대기"
          value={`${summary.reviewPending}명`}
        />
      </section>

      <section className="grid grid-cols-[minmax(0,1.2fr)_minmax(260px,0.8fr)] overflow-hidden rounded-lg border border-border bg-surface mw-900:grid-cols-[minmax(0,1fr)]">
        <div className="border-r border-border-muted p-5 mw-900:border-r-0 mw-900:border-b">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-[14px] text-ink">포지션별 지원자 분포</h2>
              <p className="mt-1 text-[10px] text-muted">
                현재 명단이 연결된 포지션 기준입니다.
              </p>
            </div>
            <BarChart3 size={18} className="text-brand" aria-hidden="true" />
          </div>
          <div className="mt-4 grid gap-3">
            {positionCounts.slice(0, 5).map((position) => {
              const maximum = positionCounts[0]?.count ?? 1;
              return (
                <div
                  className="grid grid-cols-[minmax(0,1fr)_44px] items-center gap-3"
                  key={position.positionId}
                >
                  <span className="grid gap-1.5">
                    <span className="truncate text-[10px] font-semibold text-ink-secondary">
                      {position.title}
                    </span>
                    <span className="h-1.5 overflow-hidden rounded-full bg-surface-strong">
                      <i
                        className="block h-full rounded-full bg-brand"
                        style={{
                          width: `${(position.count / maximum) * 100}%`,
                        }}
                      />
                    </span>
                  </span>
                  <b className="text-right font-mono text-[11px] text-ink">
                    {position.count}명
                  </b>
                </div>
              );
            })}
          </div>
        </div>
        <div className="grid content-center gap-3 bg-surface-muted p-5">
          <h2 className="text-[13px] text-ink">검토 현황</h2>
          <PipelineFact
            label="진행 중"
            value={summary.inProgress}
            total={summary.total}
            tone="bg-brand"
          />
          <PipelineFact
            label="검토 대기"
            value={summary.reviewPending}
            total={summary.total}
            tone="bg-warning"
          />
          <PipelineFact
            label="검토 완료"
            value={summary.completed}
            total={summary.total}
            tone="bg-success"
          />
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border border-border bg-surface">
        {deletionNotice ? (
          <p
            className={`border-b border-border-muted px-5 py-3 text-[11px] font-semibold ${deletionNoticeClass(deletionNoticeTone)}`}
            role="status"
          >
            {deletionNotice}
          </p>
        ) : null}
        {pipelineNotice ? (
          <p
            className="border-b border-border-muted bg-brand-soft/45 px-5 py-3 text-[10px] font-semibold text-brand"
            role="status"
          >
            {pipelineNotice}
          </p>
        ) : null}
        <header className="grid grid-cols-[minmax(240px,1fr)_180px_150px_auto] gap-2 border-b border-border-muted bg-[#fbfbfa] p-3.5 mw-900:grid-cols-2 mw-620:grid-cols-[minmax(0,1fr)]">
          <div className="col-[1/-1] -mx-3.5 -mt-3.5 mb-1.5 flex min-h-12 items-center gap-3 border-b border-border-muted bg-white px-3.5 mw-620:flex-wrap mw-620:gap-2 mw-620:py-2">
            <span className="text-[9px] font-semibold tracking-[0.08em] text-subtle">
              보기
            </span>
            <div
              className="inline-flex w-fit items-center gap-0.5"
              role="tablist"
              aria-label="지원자 보기 방식"
            >
              <button
                className={`relative inline-flex min-h-8 items-center gap-1.5 rounded-md px-2.5 text-[10px] font-semibold transition-colors ${
                  view === "list"
                    ? "bg-surface-strong text-ink"
                    : "text-muted hover:bg-surface-muted hover:text-ink-secondary"
                }`}
                type="button"
                role="tab"
                aria-selected={view === "list"}
                onClick={() => setView("list")}
              >
                <List size={14} aria-hidden="true" /> 목록형
              </button>
              <button
                className={`relative inline-flex min-h-8 items-center gap-1.5 rounded-md px-2.5 text-[10px] font-semibold transition-colors ${
                  view === "kanban"
                    ? "bg-brand-soft text-brand"
                    : "text-muted hover:bg-surface-muted hover:text-ink-secondary"
                }`}
                type="button"
                role="tab"
                aria-selected={view === "kanban"}
                onClick={() => setView("kanban")}
              >
                <LayoutGrid size={14} aria-hidden="true" /> 칸반보드형
              </button>
            </div>
            <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-surface-muted px-2.5 py-1.5 text-[9px] text-muted mw-620:ml-0">
              <span className="size-1.5 rounded-full bg-brand/70" />
              {view === "kanban"
                ? "한 포지션의 단계를 카드로 관리합니다."
                : "전체 포지션을 표로 확인합니다."}
            </span>
          </div>
          <label className="relative flex items-center">
            <Search
              className="absolute left-3 text-subtle"
              size={15}
              aria-hidden="true"
            />
            <span className="sr-only">지원자 검색</span>
            <input
              className="h-10 w-full rounded-lg border border-border bg-surface pl-9 pr-3 text-[11px]"
              aria-label="지원자 검색"
              type="search"
              placeholder="이름, 이메일, 포지션 검색"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <select
            className="h-10 rounded-lg border border-border bg-surface px-3 text-[11px] text-ink-secondary"
            aria-label="포지션 필터"
            value={positionFilter}
            onChange={(event) => {
              setPositionFilter(event.target.value);
              setStageFilter("all");
              setPage(1);
            }}
          >
            {view === "list" ? <option value="all">전체 포지션</option> : null}
            {positions.map((position) => (
              <option key={position.positionId} value={position.positionId}>
                {position.title}
              </option>
            ))}
          </select>
          <select
            className="h-10 rounded-lg border border-border bg-surface px-3 text-[11px] text-ink-secondary"
            aria-label="진행 상태 필터"
            value={stageFilter}
            onChange={(event) => {
              setStageFilter(event.target.value);
              setPage(1);
            }}
          >
            <option value="all">전체 채용 단계</option>
            {[...stages]
              .filter(
                (stage) =>
                  positionFilter === "all" ||
                  stage.positionId === positionFilter,
              )
              .sort((left, right) =>
                left.positionId === right.positionId
                  ? left.sortOrder - right.sortOrder
                  : left.positionId.localeCompare(right.positionId),
              )
              .map((stage) => {
                const position = positions.find(
                  (candidate) => candidate.positionId === stage.positionId,
                );
                return (
                  <option
                    key={stage.recruitingStageId}
                    value={stage.recruitingStageId}
                  >
                    {positionFilter === "all"
                      ? `${position?.title ?? "포지션"} · `
                      : ""}
                    {stage.name}
                  </option>
                );
              })}
          </select>
          <button
            className="min-h-10 rounded-lg px-3 text-[10px] font-semibold text-muted hover:bg-surface-muted"
            type="button"
            onClick={resetFilters}
          >
            필터 초기화
          </button>
        </header>

        {view === "kanban" ? (
          loading || stagesLoading ? (
            <div className={ASYNC_STATE} role="status">
              칸반보드를 불러오는 중입니다.
            </div>
          ) : error || !currentPosition ? (
            <div className={ASYNC_STATE} role="alert">
              선택한 포지션의 칸반보드를 불러올 수 없습니다.
            </div>
          ) : (
            <ApplicantKanbanBoard
              position={currentPosition}
              stages={currentStages}
              invitations={visible}
              totalApplicantCount={
                activeInvitations.filter(
                  (invitation) =>
                    invitation.positionId === currentPosition.positionId,
                ).length
              }
              moving={pipelineBusy}
              onMove={moveApplicants}
              onOpenReport={openApplicantReport}
              onOpenSettings={() => setSettingsOpen(true)}
            />
          )
        ) : (
          <>
            <div className="grid grid-cols-[minmax(240px,1.1fr)_minmax(170px,0.8fr)_140px_120px_56px] bg-surface-muted px-5 py-3 text-[9px] font-semibold text-muted mw-720:hidden">
              <span>지원자</span>
              <span>포지션</span>
              <span>현재 채용 단계</span>
              <span>시스템 진행</span>
              <span className="sr-only">관리</span>
            </div>
            {loading ? (
              <div className={ASYNC_STATE} role="status">
                지원자를 불러오는 중입니다.
              </div>
            ) : error ? (
              <div className={ASYNC_STATE} role="alert">
                지원자 정보를 불러올 수 없습니다.
              </div>
            ) : pageInvitations.length ? (
              <div className="divide-y divide-border-muted">
                {pageInvitations.map((invitation) => {
                  const displayName =
                    invitation.applicantDisplayName ||
                    invitation.applicantEmail.split("@")[0];
                  const status = invitationStatusMeta[invitation.status];
                  const recruitingStage = stages.find(
                    (stage) =>
                      stage.recruitingStageId === invitation.recruitingStageId,
                  );
                  const deletion = deletions[invitation.invitationId];
                  const deletionActive = deletion
                    ? isDeletionActive(deletion.status)
                    : false;
                  const deletionNeedsAttention =
                    deletion?.status === "partially_completed";
                  return (
                    <div
                      className="grid grid-cols-[minmax(0,1fr)_56px]"
                      key={invitation.invitationId}
                    >
                      <Link
                        className={`grid min-h-16 grid-cols-[minmax(240px,1.1fr)_minmax(170px,0.8fr)_140px_120px] items-center px-5 py-3 hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-brand mw-720:grid-cols-[44px_minmax(0,1fr)_auto] mw-720:gap-x-3 mw-720:gap-y-2 ${deletionActive ? "pointer-events-none opacity-60" : ""}`}
                        to={applicantWorkspacePath(invitation)}
                        aria-label={`${displayName} 리포트 열기`}
                        aria-disabled={deletionActive}
                      >
                        <span className="flex min-w-0 items-center gap-3 mw-720:contents">
                          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-brand-soft text-[11px] font-bold text-brand">
                            {displayName.slice(0, 1)}
                          </span>
                          <span className="min-w-0 mw-720:col-[2]">
                            <strong className="block text-[11px] text-ink">
                              {displayName}
                            </strong>
                            <small className="mt-0.5 block truncate text-[9px] text-muted">
                              {invitation.applicantEmail}
                            </small>
                          </span>
                        </span>
                        <span className="truncate text-[10px] font-semibold text-ink-secondary mw-720:col-[2] mw-720:row-[2]">
                          {invitation.positionTitle}
                        </span>
                        <span
                          className={`w-fit ${INVITATION_STATUS} ${invitationTone(
                            deletionActive || deletionNeedsAttention
                              ? "attention"
                              : status.tone,
                          )} mw-720:col-[3] mw-720:row-[1]`}
                        >
                          {deletion
                            ? deletionStatusLabel(deletion)
                            : (recruitingStage?.name ?? "미지정")}
                        </span>
                        <span className="text-[10px] text-muted mw-720:col-[3] mw-720:row-[2]">
                          {deletionActive ? "완료 확인 중" : status.label}
                        </span>
                      </Link>
                      <button
                        className="m-2 grid size-10 place-items-center self-center rounded-lg border border-border bg-surface text-muted transition hover:border-danger hover:bg-danger-soft hover:text-danger disabled:cursor-not-allowed disabled:opacity-35"
                        type="button"
                        aria-label={`${displayName} 지원자 ${deletionActive ? "삭제 진행 중" : "삭제"}`}
                        title={deletionActive ? "삭제 진행 중" : "지원자 삭제"}
                        disabled={
                          !api.requestApplicantDeletion || deletionActive
                        }
                        onClick={() => {
                          setDeletionError(false);
                          setDeletionTarget(invitation);
                        }}
                      >
                        <Trash2 size={15} aria-hidden="true" />
                      </button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className={`${ASYNC_STATE} min-h-44`}>
                <Users size={24} />
                <strong>조건에 맞는 지원자가 없습니다.</strong>
              </div>
            )}

            {!loading && !error ? (
              <footer className="flex min-h-14 items-center justify-between border-t border-border-muted px-5 text-[10px] text-muted">
                <span>{visible.length}명 표시</span>
                <span className="flex items-center gap-2">
                  <button
                    className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40"
                    type="button"
                    disabled={activePage === 1}
                    onClick={() => setPage((value) => Math.max(1, value - 1))}
                  >
                    이전
                  </button>
                  <b className="font-mono text-ink">
                    {activePage} / {pageCount}
                  </b>
                  <button
                    className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40"
                    type="button"
                    disabled={activePage === pageCount}
                    onClick={() =>
                      setPage((value) => Math.min(pageCount, value + 1))
                    }
                  >
                    다음
                  </button>
                </span>
              </footer>
            ) : null}
          </>
        )}
      </section>

      {deletionTarget ? (
        <div className="fixed inset-0 z-100 grid place-items-center bg-[rgb(20_25_38_/_46%)] p-6">
          <section
            className="w-[min(100%,440px)] rounded-xl border border-border bg-surface p-6 shadow-float"
            role="dialog"
            aria-modal="true"
            aria-labelledby="applicant-deletion-title"
          >
            <h2
              className="text-[18px] font-bold text-ink"
              id="applicant-deletion-title"
            >
              지원자를 삭제할까요?
            </h2>
            <p className="mt-3 text-[12px] leading-6 text-muted">
              <strong className="text-ink">
                {deletionTarget.applicantDisplayName ||
                  deletionTarget.applicantEmail}
              </strong>
              님의 초대 정보, 제출 자료, 분석 결과와 면접 기록을 삭제합니다. 이
              작업은 백그라운드에서 진행되며 완료 전까지 목록에 표시됩니다. 삭제
              완료 후에는 되돌릴 수 없습니다.
            </p>
            {deletionError ? (
              <p
                className="mt-3 text-[11px] font-semibold text-danger"
                role="alert"
              >
                삭제 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.
              </p>
            ) : null}
            <div className="mt-6 flex justify-end gap-2">
              <button
                className="min-h-10 rounded-lg border border-border bg-surface px-4 text-[11px] font-semibold text-ink-secondary hover:bg-surface-muted disabled:opacity-40"
                type="button"
                disabled={deleting}
                onClick={() => setDeletionTarget(null)}
              >
                취소
              </button>
              <button
                className="min-h-10 rounded-lg bg-danger px-4 text-[11px] font-semibold text-white hover:opacity-90 disabled:opacity-40"
                type="button"
                disabled={deleting}
                onClick={() => void confirmApplicantDeletion()}
              >
                {deleting ? "삭제 요청 중..." : "삭제"}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {settingsOpen && currentPosition ? (
        <RecruitingStageSettingsDialog
          position={currentPosition}
          stages={currentStages}
          busy={pipelineBusy}
          onClose={() => setSettingsOpen(false)}
          onSaveCapacity={saveApplicantCapacity}
          onCreate={createStage}
          onRename={renameStage}
          onReorder={reorderStages}
          onDelete={deleteStage}
        />
      ) : null}

      <ApplicantReportModal
        preview={selectedReport}
        open={Boolean(selectedReport)}
        api={api}
        stages={currentStages}
        moving={pipelineBusy}
        onChangeStage={moveSelectedApplicant}
        onOpenChange={(open) => {
          if (!open) setSelectedReport(undefined);
        }}
      />
    </div>
  );
}

function isDeletionActive(status: CompanyDeletionStatus["status"]) {
  return status !== "completed" && status !== "partially_completed";
}

function deletionStatusLabel(deletion: CompanyDeletionStatus) {
  if (deletion.status === "completed") return "삭제 완료";
  if (deletion.status === "partially_completed") return "삭제 확인 필요";
  if (deletion.status === "retrying") return "삭제 재시도 중";
  if (deletion.expectedTargets === 0 || deletion.verifiedTargets === 0) {
    return "삭제 준비 중";
  }
  const percentage = Math.min(
    99,
    Math.round((deletion.verifiedTargets / deletion.expectedTargets) * 100),
  );
  return deletion.status === "verifying"
    ? `삭제 확인 중 ${percentage}%`
    : `삭제 진행 중 ${percentage}%`;
}

function loadStoredApplicantDeletions(): Readonly<
  Record<string, ApplicantDeletionStatus>
> {
  try {
    const stored = localStorage.getItem(DELETION_STORAGE_KEY);
    if (!stored) return {};
    const parsed = JSON.parse(stored) as Record<
      string,
      ApplicantDeletionStatus
    >;
    return Object.fromEntries(
      Object.entries(parsed).filter(
        ([, deletion]) =>
          typeof deletion?.deletionRequestId === "string" &&
          typeof deletion?.applicantDisplayName === "string" &&
          typeof deletion?.expectedTargets === "number" &&
          typeof deletion?.verifiedTargets === "number" &&
          isDeletionActive(deletion?.status),
      ),
    );
  } catch {
    return {};
  }
}

function persistActiveApplicantDeletions(
  deletions: Readonly<Record<string, ApplicantDeletionStatus>>,
) {
  try {
    const active = Object.fromEntries(
      Object.entries(deletions).filter(([, deletion]) =>
        isDeletionActive(deletion.status),
      ),
    );
    if (Object.keys(active).length === 0) {
      localStorage.removeItem(DELETION_STORAGE_KEY);
      return;
    }
    localStorage.setItem(DELETION_STORAGE_KEY, JSON.stringify(active));
  } catch {
    return;
  }
}

function deletionNoticeClass(tone: "success" | "warning" | "danger") {
  if (tone === "danger") return "bg-danger-soft text-danger";
  if (tone === "warning") return "bg-warning-soft text-warning";
  return "bg-success-soft text-success";
}

function SummaryMetric({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <article
      className="grid min-h-20 grid-cols-[30px_minmax(0,1fr)] items-center gap-3 border-r border-border-muted px-4 last:border-r-0 mw-720:nth-2:border-r-0 mw-720:nth-[-n+2]:border-b mw-720:nth-[-n+2]:border-border-muted"
      aria-label={`${label} ${value}`}
    >
      <span className="grid size-8 place-items-center rounded-lg bg-brand-soft text-brand">
        {icon}
      </span>
      <span>
        <small className="block text-[9px] text-muted">{label}</small>
        <strong className="mt-1 block font-mono text-[17px] text-ink">
          {value}
        </strong>
      </span>
    </article>
  );
}

function PipelineFact({
  label,
  value,
  total,
  tone,
}: {
  label: string;
  value: number;
  total: number;
  tone: string;
}) {
  const width = total ? Math.round((value / total) * 100) : 0;
  return (
    <div className="grid gap-1.5">
      <span className="flex justify-between text-[9px] text-muted">
        <span>{label}</span>
        <b className="font-mono text-ink">{value}명</b>
      </span>
      <span className="h-1.5 overflow-hidden rounded-full bg-surface-strong">
        <i
          className={`block h-full rounded-full ${tone}`}
          style={{ width: `${width}%` }}
        />
      </span>
    </div>
  );
}

function defaultStageName(invitation: CompanyInvitation) {
  if (["interrupted", "expired", "revoked"].includes(invitation.status)) {
    return "보류";
  }
  if (invitation.status === "completed") return "1차 합격";
  if (invitation.status === "reviewed" || invitation.status === "deleted") {
    return "최종합격";
  }
  return "검토";
}

function virtualStages(positions: readonly CompanyPosition[]) {
  return positions.flatMap((position) =>
    DEFAULT_STAGE_NAMES.map((name, sortOrder) => ({
      recruitingStageId: `virtual-${position.positionId}-${sortOrder}`,
      positionId: position.positionId,
      name,
      sortOrder,
      rowVersion: 1,
    })),
  );
}
