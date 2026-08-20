import {
  BarChart3,
  BriefcaseBusiness,
  ClipboardCheck,
  Search,
  UserRoundCheck,
  Users,
} from "lucide-react";
import { useDeferredValue, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ASYNC_STATE,
  INVITATION_STATUS,
  invitationTone,
} from "../../app/styles/primitives";
import { invitationStatusMeta } from "../hiring/PositionInvitations";
import { summarizeApplicantPipeline } from "./applicantSummary";
import type { CompanyInvitation, CompanyOperationsApi } from "./types";
import { useRecruitingOperations } from "./useRecruitingOperations";

type StageFilter = "all" | "progress" | "review" | "completed";
const PAGE_SIZE = 20;

export function ApplicantManagement({ api }: { api: CompanyOperationsApi }) {
  const { positions, invitations, loading, error } =
    useRecruitingOperations(api);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [positionFilter, setPositionFilter] = useState("all");
  const [stageFilter, setStageFilter] = useState<StageFilter>("all");
  const [page, setPage] = useState(1);
  const summary = useMemo(
    () => summarizeApplicantPipeline(invitations),
    [invitations],
  );
  const positionCounts = useMemo(
    () =>
      positions
        .map((position) => ({
          positionId: position.positionId,
          title: position.title,
          count: invitations.filter(
            (item) => item.positionId === position.positionId,
          ).length,
        }))
        .filter((position) => position.count > 0)
        .sort((left, right) => right.count - left.count),
    [invitations, positions],
  );
  const visible = useMemo(() => {
    const normalized = deferredQuery.trim().toLocaleLowerCase("ko-KR");
    return invitations.filter((item) => {
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
        stageFilter === "all" || applicantStage(item) === stageFilter;
      return matchesQuery && matchesPosition && matchesStage;
    });
  }, [deferredQuery, invitations, positionFilter, stageFilter]);
  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const activePage = Math.min(page, pageCount);
  const pageInvitations = visible.slice(
    (activePage - 1) * PAGE_SIZE,
    activePage * PAGE_SIZE,
  );

  function resetFilters() {
    setQuery("");
    setPositionFilter("all");
    setStageFilter("all");
    setPage(1);
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
        <header className="grid grid-cols-[minmax(240px,1fr)_180px_150px_auto] gap-2 border-b border-border-muted p-4 mw-900:grid-cols-2 mw-620:grid-cols-[minmax(0,1fr)]">
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
              setPage(1);
            }}
          >
            <option value="all">전체 포지션</option>
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
              setStageFilter(event.target.value as StageFilter);
              setPage(1);
            }}
          >
            <option value="all">전체 상태</option>
            <option value="progress">진행 중</option>
            <option value="review">검토 대기</option>
            <option value="completed">검토 완료</option>
          </select>
          <button
            className="min-h-10 rounded-lg px-3 text-[10px] font-semibold text-muted hover:bg-surface-muted"
            type="button"
            onClick={resetFilters}
          >
            필터 초기화
          </button>
        </header>

        <div className="grid grid-cols-[minmax(240px,1.1fr)_minmax(170px,0.8fr)_140px_120px] bg-surface-muted px-5 py-3 text-[9px] font-semibold text-muted mw-720:hidden">
          <span>지원자</span>
          <span>포지션</span>
          <span>현재 상태</span>
          <span>면접 결과</span>
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
              return (
                <Link
                  className="grid min-h-16 grid-cols-[minmax(240px,1.1fr)_minmax(170px,0.8fr)_140px_120px] items-center px-5 py-3 hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-brand mw-720:grid-cols-[44px_minmax(0,1fr)_auto] mw-720:gap-x-3 mw-720:gap-y-2"
                  key={invitation.invitationId}
                  to={`/positions/${invitation.positionId}/applicants/${invitation.invitationId}`}
                  aria-label={`${displayName} 리포트 열기`}
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
                    className={`w-fit ${INVITATION_STATUS} ${invitationTone(status.tone)} mw-720:col-[3] mw-720:row-[1]`}
                  >
                    {status.label}
                  </span>
                  <span className="text-[10px] text-muted mw-720:col-[3] mw-720:row-[2]">
                    {invitation.interviewSessionId ? "리포트 확인" : "대기"}
                  </span>
                </Link>
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
      </section>
    </div>
  );
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

function applicantStage(
  invitation: CompanyInvitation,
): Exclude<StageFilter, "all"> {
  if (invitation.status === "reviewed") return "completed";
  if (invitation.status === "completed" || invitation.interviewSessionId)
    return "review";
  return "progress";
}
