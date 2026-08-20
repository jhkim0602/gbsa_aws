import {
  ArrowRight,
  BriefcaseBusiness,
  CalendarClock,
  CalendarDays,
  Plus,
  Target,
  Users,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ASYNC_STATE,
  BUTTON_PRIMARY,
  PAGE_CONTENT,
  PAGE_HEADER,
  PAGE_HEADER_TEXT,
  PAGE_HEADER_TITLE,
  STATUS_BADGE,
  STATUS_BADGE_TONE,
} from "../../app/styles/primitives";
import { statusLabel, statusTone } from "./companyFormatters";
import type { CompanyOperationsApi, CompanyPosition } from "./types";
import { useRecruitingOperations } from "./useRecruitingOperations";

type Filter = "all" | "active" | "draft";

const LIST_COLUMNS =
  "grid-cols-[minmax(0,1.7fr)_minmax(62px,0.55fr)_minmax(108px,0.9fr)_minmax(46px,0.45fr)_minmax(52px,0.45fr)_minmax(90px,0.8fr)_14px]";

export function CompanyPositions({ api }: { api: CompanyOperationsApi }) {
  const { positions, invitations, loading, error } =
    useRecruitingOperations(api);
  const [filter, setFilter] = useState<Filter>("all");
  const invitationCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const invitation of invitations) {
      counts.set(
        invitation.positionId,
        (counts.get(invitation.positionId) ?? 0) + 1,
      );
    }
    return counts;
  }, [invitations]);
  const visible = useMemo(
    () =>
      positions.filter((position) => {
        if (filter === "all") return true;
        if (filter === "active") {
          return ["active", "open", "published"].includes(position.status);
        }
        return position.status === "draft";
      }),
    [filter, positions],
  );
  const activeCount = countForFilter(positions, "active");
  const targetCount = positions.reduce(
    (sum, position) => sum + (position.headcount ?? 0),
    0,
  );

  return (
    <div>
      <header className={`${PAGE_HEADER} mw-680:flex-col`}>
        <div>
          <h1 className={PAGE_HEADER_TITLE}>채용 포지션</h1>
          <p className={PAGE_HEADER_TEXT}>
            포지션별 채용 목표와 지원자 현황을 확인하고 운영 화면으로
            이동합니다.
          </p>
        </div>
        <Link className={BUTTON_PRIMARY} to="/hiring">
          <Plus size={14} aria-hidden="true" />새 포지션
        </Link>
      </header>

      <div className={`${PAGE_CONTENT} grid gap-4`}>
        <section
          className="grid grid-cols-4 overflow-hidden rounded-lg border border-border bg-surface mw-720:grid-cols-2"
          aria-label="포지션 운영 요약"
        >
          <PositionMetric
            icon={<BriefcaseBusiness size={17} />}
            label="전체 포지션"
            value={`${positions.length}개`}
          />
          <PositionMetric
            icon={<CalendarDays size={17} />}
            label="운영 중"
            value={`${activeCount}개`}
          />
          <PositionMetric
            icon={<Users size={17} />}
            label="전체 지원자"
            value={`${invitations.length}명`}
          />
          <PositionMetric
            icon={<Target size={17} />}
            label="전체 채용 목표"
            value={`${targetCount}명`}
          />
        </section>

        <section className="overflow-hidden rounded-lg border border-border bg-surface">
          <header className="flex items-center justify-between gap-4 border-b border-border-muted px-5 py-4 mw-620:flex-col mw-620:items-stretch">
            <div>
              <h2 className="text-[15px] text-ink">포지션 운영 목록</h2>
              <p className="mt-1 text-[10px] text-muted">
                행 전체를 누르면 해당 포지션의 인사이트와 지원자를 확인합니다.
              </p>
            </div>
            <nav
              className="flex w-max shrink-0 rounded-lg bg-surface-muted p-1"
              aria-label="포지션 상태 필터"
            >
              {(
                [
                  ["all", "전체"],
                  ["active", "운영 중"],
                  ["draft", "초안"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  className={`inline-flex min-h-8 flex-none items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-3 text-[10px] font-semibold ${
                    filter === value
                      ? "bg-surface text-brand shadow-sm"
                      : "text-muted"
                  }`}
                  type="button"
                  aria-pressed={filter === value}
                  onClick={() => setFilter(value)}
                >
                  {label}
                  <span className="font-mono text-[9px]">
                    {countForFilter(positions, value)}
                  </span>
                </button>
              ))}
            </nav>
          </header>

          {loading ? (
            <div className={ASYNC_STATE} role="status">
              포지션과 지원자 현황을 불러오는 중입니다.
            </div>
          ) : error ? (
            <div className={ASYNC_STATE} role="alert">
              포지션을 불러오지 못했습니다.
            </div>
          ) : visible.length ? (
            <div>
              <div
                className={`grid ${LIST_COLUMNS} gap-3 border-b border-border-muted bg-surface-muted px-5 py-2.5 text-[8px] font-semibold tracking-[0.02em] text-muted mw-1180:hidden`}
                aria-hidden="true"
              >
                <span>포지션</span>
                <span>상태</span>
                <span>일정</span>
                <span className="text-right">지원자</span>
                <span className="text-right">채용 목표</span>
                <span>지원 현황</span>
                <span />
              </div>
              <div className="grid [content-visibility:auto]">
                {visible.map((position) => (
                  <PositionListRow
                    key={position.positionId}
                    position={position}
                    applicantCount={
                      invitationCounts.get(position.positionId) ?? 0
                    }
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className={`${ASYNC_STATE} min-h-52`}>
              <BriefcaseBusiness size={25} aria-hidden="true" />
              <p className="text-[12px]">선택한 상태의 포지션이 없습니다.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function PositionListRow({
  position,
  applicantCount,
}: {
  position: CompanyPosition;
  applicantCount: number;
}) {
  const target = position.headcount ?? 0;
  const progress = target
    ? Math.min(100, Math.round((applicantCount / target) * 100))
    : 0;
  return (
    <Link
      className={`group grid w-full min-w-0 overflow-hidden ${LIST_COLUMNS} min-h-[86px] items-center gap-3 px-5 py-3 text-inherit not-first:border-t not-first:border-border-muted hover:bg-[#fafaff] focus-visible:outline-2 focus-visible:outline-brand mw-1180:grid-cols-[minmax(0,1fr)_auto] mw-1180:gap-x-3`}
      to={`/positions/${position.positionId}`}
      aria-label={`${position.title} 포지션 열기`}
    >
      <span className="flex min-w-0 items-center gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand">
          <BriefcaseBusiness size={16} aria-hidden="true" />
        </span>
        <span className="min-w-0">
          <strong className="block truncate text-[12px] text-ink group-hover:text-brand">
            {position.title}
          </strong>
          <small className="mt-1 block truncate text-[9px] text-muted">
            {position.roleType ?? "직무 미설정"} · {position.description}
          </small>
        </span>
      </span>

      <span
        className={`${STATUS_BADGE} justify-center whitespace-nowrap ${STATUS_BADGE_TONE[statusTone(position.status)]}`}
      >
        {statusLabel(position.status)}
      </span>

      <span className="grid min-w-0 gap-1 text-[9px] text-muted mw-1180:col-[1/-1] mw-1180:ml-12 mw-1180:grid-cols-2">
        <span className="flex min-w-0 items-center gap-1.5">
          <CalendarDays className="shrink-0" size={12} aria-hidden="true" />
          <span className="truncate">{formatRecruitmentPeriod(position)}</span>
        </span>
        <span className="flex min-w-0 items-center gap-1.5">
          <CalendarClock className="shrink-0" size={12} aria-hidden="true" />
          <span className="truncate">
            {formatInterviewAt(position.interviewAt)}
          </span>
        </span>
      </span>

      <ListFact label="지원자" value={`${applicantCount}명`} />
      <ListFact label="채용 목표" value={target ? `${target}명` : "미설정"} />
      <span className="hidden gap-4 text-[9px] text-muted mw-1180:col-[1] mw-1180:row-[3] mw-1180:ml-12 mw-1180:flex">
        <span>
          지원자 <b className="ml-1 font-mono text-ink">{applicantCount}명</b>
        </span>
        <span>
          채용 목표{" "}
          <b className="ml-1 font-mono text-ink">
            {target ? `${target}명` : "미설정"}
          </b>
        </span>
      </span>

      <span className="grid min-w-0 gap-1.5 mw-1180:col-[2] mw-1180:row-[3] mw-1180:min-w-[170px] mw-1180:grid-cols-[auto_96px] mw-1180:items-center mw-1180:gap-2 mw-620:col-[1/-1] mw-620:row-[4] mw-620:ml-12 mw-620:min-w-0 mw-620:grid-cols-[auto_minmax(80px,1fr)]">
        <span className="flex items-center justify-between text-[8px] text-muted mw-1180:gap-1 mw-1180:whitespace-nowrap">
          <span>목표 대비</span>
          <b className="font-mono text-ink">{progress}%</b>
        </span>
        <span
          className="h-1.5 overflow-hidden rounded-full bg-surface-strong mw-1180:h-1"
          role="progressbar"
          aria-label={`${position.title} 지원 현황 ${progress}%`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
        >
          <i
            className="block h-full rounded-full bg-brand"
            style={{ width: `${progress}%` }}
          />
        </span>
      </span>

      <ArrowRight
        className="text-subtle group-hover:text-brand mw-1180:hidden"
        size={15}
        aria-hidden="true"
      />
    </Link>
  );
}

function PositionMetric({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <article className="grid min-h-20 grid-cols-[30px_minmax(0,1fr)] items-center gap-3 border-r border-border-muted px-4 last:border-r-0 mw-720:nth-2:border-r-0 mw-720:nth-[-n+2]:border-b mw-720:nth-[-n+2]:border-border-muted">
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

function ListFact({ label, value }: { label: string; value: string }) {
  return (
    <span className="whitespace-nowrap text-right mw-1180:col-auto mw-1180:hidden">
      <small className="sr-only">{label}</small>
      <b className="font-mono text-[11px] text-ink-secondary">{value}</b>
    </span>
  );
}

function formatRecruitmentPeriod(position: CompanyPosition) {
  if (!position.recruitmentStartAt || !position.recruitmentEndAt) {
    return "모집 기간 미설정";
  }
  return `${formatShortDate(position.recruitmentStartAt)}–${formatShortDate(position.recruitmentEndAt)}`;
}

function formatInterviewAt(value?: string | null) {
  if (!value) return "면접 일정 미설정";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatShortDate(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(`${value}T00:00:00`));
}

function countForFilter(positions: readonly CompanyPosition[], filter: Filter) {
  if (filter === "all") return positions.length;
  if (filter === "active") {
    return positions.filter((position) =>
      ["active", "open", "published"].includes(position.status),
    ).length;
  }
  return positions.filter((position) => position.status === "draft").length;
}
