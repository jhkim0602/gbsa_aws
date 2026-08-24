import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCorners,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  ArrowDown,
  ArrowUp,
  Check,
  CheckSquare2,
  GripVertical,
  Pencil,
  Plus,
  Settings2,
  Trash2,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import { invitationStatusMeta } from "../hiring/PositionInvitations";
import type { CompanyPosition, CompanyRecruitingStage } from "./types";
import type { PositionedInvitation } from "./useRecruitingOperations";

const STAGE_STYLES = [
  {
    tone: "bg-[#efefed] text-[#5f5e5b]",
    dot: "bg-[#9b9a97]",
    accent: "bg-[#b4b4b0]",
  },
  {
    tone: "bg-brand-soft text-brand",
    dot: "bg-brand",
    accent: "bg-brand",
  },
  {
    tone: "bg-[#e7f3f8] text-[#2b6f94]",
    dot: "bg-[#55a4ca]",
    accent: "bg-[#55a4ca]",
  },
  {
    tone: "bg-success-soft text-success",
    dot: "bg-success",
    accent: "bg-success",
  },
  {
    tone: "bg-danger-soft text-danger",
    dot: "bg-danger",
    accent: "bg-danger",
  },
] as const;

const AVATAR_TONES = [
  "bg-[#eeeafe] text-[#6554c0]",
  "bg-[#e4f2fb] text-[#176b87]",
  "bg-[#e8f3ec] text-[#287a4b]",
  "bg-[#fff0e5] text-[#a45117]",
  "bg-[#f8e8ef] text-[#9f3f68]",
] as const;

export function ApplicantKanbanBoard({
  position,
  stages,
  invitations,
  totalApplicantCount,
  moving,
  onMove,
  onOpenReport,
  onOpenSettings,
}: {
  position: CompanyPosition;
  stages: readonly CompanyRecruitingStage[];
  invitations: readonly PositionedInvitation[];
  totalApplicantCount: number;
  moving: boolean;
  onMove(
    invitationIds: readonly string[],
    targetStageId: string,
  ): Promise<boolean>;
  onOpenReport(invitation: PositionedInvitation): void;
  onOpenSettings(): void;
}) {
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const [bulkTarget, setBulkTarget] = useState(
    stages[0]?.recruitingStageId ?? "",
  );
  const [activeInvitationId, setActiveInvitationId] = useState<string | null>(
    null,
  );
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );
  const invitationById = useMemo(
    () =>
      new Map(
        invitations.map((invitation) => [invitation.invitationId, invitation]),
      ),
    [invitations],
  );
  const activeInvitation = activeInvitationId
    ? invitationById.get(activeInvitationId)
    : undefined;
  const invitationsByStage = useMemo(() => {
    const grouped = new Map<string, PositionedInvitation[]>();
    for (const invitation of invitations) {
      const stageId = invitation.recruitingStageId;
      if (!stageId) continue;
      const stageInvitations = grouped.get(stageId) ?? [];
      stageInvitations.push(invitation);
      grouped.set(stageId, stageInvitations);
    }
    return grouped;
  }, [invitations]);
  const selectedInView = invitations.filter((invitation) =>
    selectedIds.has(invitation.invitationId),
  );
  const capacity = position.applicantCapacity;
  const overCapacity = capacity != null && totalApplicantCount > capacity;

  function toggleSelection(invitationId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(invitationId)) next.delete(invitationId);
      else next.add(invitationId);
      return next;
    });
  }

  async function moveSelected() {
    if (!bulkTarget || selectedInView.length === 0) return;
    const moved = await onMove(
      selectedInView.map((invitation) => invitation.invitationId),
      bulkTarget,
    );
    if (moved) setSelectedIds(new Set());
  }

  function handleDragStart(event: DragStartEvent) {
    setActiveInvitationId(String(event.active.id));
  }

  async function handleDragEnd(event: DragEndEvent) {
    setActiveInvitationId(null);
    if (!event.over) return;
    const invitationId = String(event.active.id);
    const targetStageId = String(event.over.id).replace(/^stage:/, "");
    const invitation = invitationById.get(invitationId);
    if (!invitation || invitation.recruitingStageId === targetStageId) return;
    const ids = selectedIds.has(invitationId)
      ? selectedInView.map((item) => item.invitationId)
      : [invitationId];
    const moved = await onMove(ids, targetStageId);
    if (moved && selectedIds.has(invitationId)) setSelectedIds(new Set());
  }

  return (
    <section className="overflow-hidden bg-[#f7f7f5]">
      <header className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-border-muted bg-white px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted">
          <strong className="text-[12px] text-ink">{position.title}</strong>
          <span
            className={`rounded-md px-2 py-1 font-mono ${
              overCapacity
                ? "bg-danger-soft text-danger"
                : "bg-surface-strong text-muted"
            }`}
          >
            지원자 {totalApplicantCount}명
            {capacity == null ? " · 정원 미설정" : ` / 정원 ${capacity}명`}
          </span>
          {overCapacity ? (
            <span className="font-semibold text-danger">
              정원을 초과했습니다.
            </span>
          ) : null}
        </div>
        <button
          className="inline-flex min-h-8 items-center gap-1.5 rounded-md border border-border bg-white px-2.5 text-[10px] font-semibold text-ink-secondary shadow-[0_1px_1px_rgb(15_23_42_/_3%)] transition hover:bg-surface-muted hover:text-brand"
          type="button"
          onClick={onOpenSettings}
        >
          <Settings2 size={14} aria-hidden="true" /> 단계·정원 설정
        </button>
      </header>

      {selectedInView.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 border-b border-brand/15 bg-brand-soft/50 px-4 py-3">
          <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-brand">
            <CheckSquare2 size={14} aria-hidden="true" />{" "}
            {selectedInView.length}명 선택
          </span>
          <select
            className="h-9 rounded-lg border border-border bg-white px-3 text-[10px]"
            aria-label="일괄 이동할 단계"
            value={bulkTarget}
            onChange={(event) => setBulkTarget(event.target.value)}
          >
            {stages.map((stage) => (
              <option
                key={stage.recruitingStageId}
                value={stage.recruitingStageId}
              >
                {stage.name}
              </option>
            ))}
          </select>
          <button
            className="min-h-9 rounded-lg bg-brand px-3 text-[10px] font-semibold text-white disabled:opacity-45"
            type="button"
            disabled={moving || !bulkTarget}
            onClick={() => void moveSelected()}
          >
            {moving ? "변경 중…" : "선택 지원자 이동"}
          </button>
          <button
            className="ml-auto grid size-9 place-items-center rounded-lg text-muted hover:bg-white"
            type="button"
            aria-label="선택 해제"
            onClick={() => setSelectedIds(new Set())}
          >
            <X size={15} />
          </button>
        </div>
      ) : null}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragCancel={() => setActiveInvitationId(null)}
        onDragEnd={(event) => void handleDragEnd(event)}
      >
        <div className="flex min-h-[520px] gap-2 overflow-x-auto bg-[#f7f7f5] p-3.5">
          {stages.map((stage, index) => (
            <KanbanColumn
              key={stage.recruitingStageId}
              stage={stage}
              style={STAGE_STYLES[index % STAGE_STYLES.length]}
              invitations={
                invitationsByStage.get(stage.recruitingStageId) ?? []
              }
              selectedIds={selectedIds}
              moving={moving}
              onToggleSelection={toggleSelection}
              onOpenReport={onOpenReport}
            />
          ))}
        </div>
        <DragOverlay>
          {activeInvitation ? (
            <div className="w-[268px] rotate-1 rounded-lg border border-brand/50 bg-white p-3 shadow-float">
              <div className="flex items-center gap-2.5">
                <span
                  className={`grid size-8 shrink-0 place-items-center rounded-md text-[10px] font-bold ${avatarTone(activeInvitation)}`}
                >
                  {initials(displayName(activeInvitation))}
                </span>
                <span className="min-w-0">
                  <strong className="block truncate text-[11px] text-ink">
                    {displayName(activeInvitation)}
                  </strong>
                  <small className="mt-0.5 block truncate text-[9px] text-muted">
                    {activeInvitation.applicantEmail}
                  </small>
                </span>
              </div>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </section>
  );
}

function KanbanColumn({
  stage,
  style,
  invitations,
  selectedIds,
  moving,
  onToggleSelection,
  onOpenReport,
}: {
  stage: CompanyRecruitingStage;
  style: (typeof STAGE_STYLES)[number];
  invitations: readonly PositionedInvitation[];
  selectedIds: ReadonlySet<string>;
  moving: boolean;
  onToggleSelection(invitationId: string): void;
  onOpenReport(invitation: PositionedInvitation): void;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `stage:${stage.recruitingStageId}`,
  });
  return (
    <article
      ref={setNodeRef}
      className={`flex w-[274px] shrink-0 flex-col rounded-xl border p-1.5 transition-colors ${
        isOver
          ? "border-brand/35 bg-brand-soft/40"
          : "border-transparent bg-transparent"
      }`}
    >
      <header className="flex min-h-10 items-center gap-2 px-1.5">
        <span className={`size-2 shrink-0 rounded-full ${style.dot}`} />
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${style.tone}`}
        >
          {stage.name}
        </span>
        <b className="rounded-md bg-[#e9e9e7] px-1.5 py-0.5 font-mono text-[9px] text-muted">
          {invitations.length}
        </b>
      </header>
      <div className="grid content-start gap-2 overflow-y-auto pb-2">
        {invitations.map((invitation) => (
          <KanbanCard
            key={invitation.invitationId}
            invitation={invitation}
            accent={style.accent}
            selected={selectedIds.has(invitation.invitationId)}
            disabled={moving}
            onToggleSelection={onToggleSelection}
            onOpenReport={onOpenReport}
          />
        ))}
        {invitations.length === 0 ? (
          <div className="grid min-h-24 place-items-center rounded-lg border border-dashed border-[#d8d8d5] bg-white/45 px-4 text-center text-[9px] text-muted transition-colors">
            이 단계로 카드를 드래그하세요.
          </div>
        ) : null}
      </div>
    </article>
  );
}

function KanbanCard({
  invitation,
  accent,
  selected,
  disabled,
  onToggleSelection,
  onOpenReport,
}: {
  invitation: PositionedInvitation;
  accent: string;
  selected: boolean;
  disabled: boolean;
  onToggleSelection(invitationId: string): void;
  onOpenReport(invitation: PositionedInvitation): void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: invitation.invitationId,
      disabled,
    });
  const name = displayName(invitation);
  const status = invitationStatusMeta[invitation.status];
  return (
    <article
      ref={setNodeRef}
      className={`group relative overflow-hidden rounded-lg border bg-white shadow-[0_1px_2px_rgb(15_23_42_/_4%)] transition-[border-color,box-shadow,transform,opacity] ${
        selected
          ? "border-brand/70 shadow-[0_0_0_2px_rgb(92_104_238_/_10%)]"
          : "border-[#e4e4e1] hover:-translate-y-px hover:border-[#c9c9c5] hover:shadow-[0_4px_12px_rgb(15_23_42_/_7%)]"
      } ${isDragging ? "opacity-35" : ""}`}
      style={
        transform
          ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
          : undefined
      }
    >
      <span className={`absolute inset-y-0 left-0 w-0.5 ${accent}`} />
      <button
        className="grid w-full gap-3 py-3 pr-[4.75rem] pl-3.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand/40"
        type="button"
        aria-label={`${name} 요약 리포트 열기`}
        onClick={() => onOpenReport(invitation)}
      >
        <span className="flex min-w-0 items-start gap-2.5">
          <span
            className={`grid size-8 shrink-0 place-items-center rounded-md text-[10px] font-bold ${avatarTone(invitation)}`}
          >
            {initials(name)}
          </span>
          <span className="min-w-0 flex-1">
            <strong className="block truncate text-[11px] text-ink">
              {name}
            </strong>
            <small className="mt-0.5 block truncate text-[9px] text-muted">
              {invitation.applicantEmail}
            </small>
          </span>
        </span>
        <span className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 truncate text-[9px] text-muted">
            <span className="size-1.5 shrink-0 rounded-full bg-subtle" />
            {status.label}
          </span>
          <span className="shrink-0 rounded-md bg-surface-muted px-1.5 py-0.5 text-[9px] font-semibold text-ink-secondary">
            종합점수 :{" "}
            <b className="font-mono text-ink">
              {invitation.overallScore == null
                ? "–"
                : `${invitation.overallScore}점`}
            </b>
          </span>
        </span>
      </button>
      <button
        className={`absolute top-2 right-9 grid size-7 place-items-center rounded-md border transition ${
          selected
            ? "border-brand bg-brand text-white"
            : "border-border bg-white text-muted opacity-0 hover:border-brand group-hover:opacity-100 group-focus-within:opacity-100 mw-720:opacity-100"
        }`}
        type="button"
        aria-label={`${name} 선택`}
        aria-pressed={selected}
        onClick={() => onToggleSelection(invitation.invitationId)}
      >
        {selected ? (
          <Check size={13} />
        ) : (
          <span className="size-2.5 rounded-sm border border-current" />
        )}
      </button>
      <button
        className="absolute top-2 right-2 grid size-7 cursor-grab place-items-center rounded-md text-subtle opacity-0 transition hover:bg-surface-muted hover:text-brand group-hover:opacity-100 group-focus-within:opacity-100 active:cursor-grabbing mw-720:opacity-100"
        type="button"
        aria-label={`${name} 카드 드래그`}
        {...attributes}
        {...listeners}
      >
        <GripVertical size={15} />
      </button>
    </article>
  );
}

function initials(name: string) {
  const compact = name.trim().replace(/\s+/g, "");
  return compact.slice(0, 2).toUpperCase() || "?";
}

function avatarTone(invitation: PositionedInvitation) {
  const seed = invitation.invitationId
    .split("")
    .reduce((sum, character) => sum + character.charCodeAt(0), 0);
  return AVATAR_TONES[seed % AVATAR_TONES.length];
}

export function RecruitingStageSettingsDialog({
  position,
  stages,
  busy,
  onClose,
  onSaveCapacity,
  onCreate,
  onRename,
  onReorder,
  onDelete,
}: {
  position: CompanyPosition;
  stages: readonly CompanyRecruitingStage[];
  busy: boolean;
  onClose(): void;
  onSaveCapacity(capacity: number | null): Promise<boolean>;
  onCreate(name: string): Promise<boolean>;
  onRename(stage: CompanyRecruitingStage, name: string): Promise<boolean>;
  onReorder(orderedStageIds: readonly string[]): Promise<boolean>;
  onDelete(stageId: string, replacementStageId: string): Promise<boolean>;
}) {
  const [newName, setNewName] = useState("");
  const [capacity, setCapacity] = useState(
    position.applicantCapacity?.toString() ?? "",
  );
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const replacementOptions = stages.filter(
    (stage) => stage.recruitingStageId !== deletingId,
  );
  const [replacementId, setReplacementId] = useState("");

  async function moveStage(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= stages.length) return;
    const next = stages.map((stage) => stage.recruitingStageId);
    [next[index], next[target]] = [next[target], next[index]];
    await onReorder(next);
  }

  return (
    <div className="fixed inset-0 z-100 grid place-items-center bg-[rgb(20_25_38_/_46%)] p-6">
      <section
        className="flex max-h-[90vh] w-[min(620px,100%)] flex-col overflow-hidden rounded-xl border border-border bg-white shadow-float"
        role="dialog"
        aria-modal="true"
        aria-labelledby="stage-settings-title"
      >
        <header className="flex items-start justify-between gap-4 border-b border-border p-5">
          <div>
            <h2
              className="text-[17px] font-bold text-ink"
              id="stage-settings-title"
            >
              채용 단계·지원자 정원
            </h2>
            <p className="mt-1 text-[10px] text-muted">{position.title}</p>
          </div>
          <button
            className="grid size-9 place-items-center rounded-lg hover:bg-surface-muted"
            type="button"
            aria-label="닫기"
            onClick={onClose}
          >
            <X size={16} />
          </button>
        </header>
        <div className="grid gap-6 overflow-y-auto p-5">
          <section>
            <h3 className="text-[12px] font-semibold text-ink">지원자 정원</h3>
            <p className="mt-1 text-[9px] text-muted">
              정원을 초과해도 초대는 유지되며 칸반에 경고가 표시됩니다.
            </p>
            <div className="mt-3 flex gap-2">
              <input
                className="h-10 min-w-0 flex-1 rounded-lg border border-border px-3 text-[11px]"
                type="number"
                min={1}
                max={100000}
                placeholder="정원 미설정"
                value={capacity}
                onChange={(event) => setCapacity(event.target.value)}
              />
              <button
                className="min-h-10 rounded-lg bg-brand px-4 text-[10px] font-semibold text-white disabled:opacity-45"
                type="button"
                disabled={busy}
                onClick={() =>
                  void onSaveCapacity(capacity ? Number(capacity) : null)
                }
              >
                정원 저장
              </button>
            </div>
          </section>

          <section>
            <h3 className="text-[12px] font-semibold text-ink">채용 단계</h3>
            <p className="mt-1 text-[9px] text-muted">
              최대 20개까지 추가하고 순서를 변경할 수 있습니다.
            </p>
            <div className="mt-3 grid gap-2">
              {stages.map((stage, index) => (
                <div
                  key={stage.recruitingStageId}
                  className="flex min-h-11 items-center gap-2 rounded-lg border border-border-muted px-2.5"
                >
                  <GripVertical
                    className="text-subtle"
                    size={14}
                    aria-hidden="true"
                  />
                  {editingId === stage.recruitingStageId ? (
                    <input
                      className="h-8 min-w-0 flex-1 rounded-md border border-brand px-2 text-[10px]"
                      autoFocus
                      maxLength={40}
                      value={editingName}
                      onChange={(event) => setEditingName(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          void onRename(stage, editingName).then((saved) => {
                            if (saved) setEditingId(null);
                          });
                        }
                      }}
                    />
                  ) : (
                    <strong className="min-w-0 flex-1 truncate text-[10px] text-ink-secondary">
                      {stage.name}
                    </strong>
                  )}
                  <button
                    className="grid size-7 place-items-center rounded-md hover:bg-surface-muted disabled:opacity-30"
                    type="button"
                    aria-label={`${stage.name} 위로 이동`}
                    disabled={busy || index === 0}
                    onClick={() => void moveStage(index, -1)}
                  >
                    <ArrowUp size={13} />
                  </button>
                  <button
                    className="grid size-7 place-items-center rounded-md hover:bg-surface-muted disabled:opacity-30"
                    type="button"
                    aria-label={`${stage.name} 아래로 이동`}
                    disabled={busy || index === stages.length - 1}
                    onClick={() => void moveStage(index, 1)}
                  >
                    <ArrowDown size={13} />
                  </button>
                  {editingId === stage.recruitingStageId ? (
                    <button
                      className="grid size-7 place-items-center rounded-md text-brand hover:bg-brand-soft"
                      type="button"
                      aria-label="단계 이름 저장"
                      disabled={busy}
                      onClick={() =>
                        void onRename(stage, editingName).then(
                          (saved) => saved && setEditingId(null),
                        )
                      }
                    >
                      <Check size={13} />
                    </button>
                  ) : (
                    <button
                      className="grid size-7 place-items-center rounded-md text-muted hover:bg-brand-soft hover:text-brand"
                      type="button"
                      aria-label={`${stage.name} 이름 수정`}
                      onClick={() => {
                        setEditingId(stage.recruitingStageId);
                        setEditingName(stage.name);
                      }}
                    >
                      <Pencil size={13} />
                    </button>
                  )}
                  <button
                    className="grid size-7 place-items-center rounded-md text-muted hover:bg-danger-soft hover:text-danger disabled:opacity-30"
                    type="button"
                    aria-label={`${stage.name} 삭제`}
                    disabled={busy || stages.length <= 1}
                    onClick={() => {
                      setDeletingId(stage.recruitingStageId);
                      setReplacementId(
                        stages.find(
                          (candidate) =>
                            candidate.recruitingStageId !==
                            stage.recruitingStageId,
                        )?.recruitingStageId ?? "",
                      );
                    }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
            <div className="mt-3 flex gap-2">
              <input
                className="h-10 min-w-0 flex-1 rounded-lg border border-border px-3 text-[10px]"
                maxLength={40}
                placeholder="새 단계 이름"
                value={newName}
                onChange={(event) => setNewName(event.target.value)}
              />
              <button
                className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-brand px-3 text-[10px] font-semibold text-brand disabled:opacity-40"
                type="button"
                disabled={busy || !newName.trim() || stages.length >= 20}
                onClick={() =>
                  void onCreate(newName).then(
                    (created) => created && setNewName(""),
                  )
                }
              >
                <Plus size={14} /> 단계 추가
              </button>
            </div>
          </section>
        </div>

        {deletingId ? (
          <div className="border-t border-border bg-danger-soft/45 p-5">
            <p className="text-[10px] font-semibold text-ink">
              이 단계의 지원자를 어디로 이동할까요?
            </p>
            <div className="mt-2 flex gap-2">
              <select
                className="h-10 min-w-0 flex-1 rounded-lg border border-border bg-white px-3 text-[10px]"
                value={replacementId}
                onChange={(event) => setReplacementId(event.target.value)}
              >
                {replacementOptions.map((stage) => (
                  <option
                    key={stage.recruitingStageId}
                    value={stage.recruitingStageId}
                  >
                    {stage.name}
                  </option>
                ))}
              </select>
              <button
                className="min-h-10 rounded-lg bg-danger px-3 text-[10px] font-semibold text-white disabled:opacity-40"
                type="button"
                disabled={busy || !replacementId}
                onClick={() =>
                  void onDelete(deletingId, replacementId).then(
                    (deleted) => deleted && setDeletingId(null),
                  )
                }
              >
                이동 후 삭제
              </button>
              <button
                className="min-h-10 rounded-lg border border-border bg-white px-3 text-[10px]"
                type="button"
                onClick={() => setDeletingId(null)}
              >
                취소
              </button>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function displayName(invitation: PositionedInvitation) {
  return (
    invitation.applicantDisplayName || invitation.applicantEmail.split("@")[0]
  );
}
