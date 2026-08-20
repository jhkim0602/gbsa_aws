import { ArrowRight, BriefcaseBusiness, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  ASYNC_STATE,
  BUTTON_PRIMARY,
  PAGE_CONTENT,
  PAGE_HEADER,
  PAGE_HEADER_TEXT,
  PAGE_HEADER_TITLE,
  PANEL,
  STATUS_BADGE,
  STATUS_BADGE_TONE,
} from "../../app/styles/primitives";
import { formatDate, statusLabel, statusTone } from "./companyFormatters";
import type { CompanyOperationsApi, CompanyPosition } from "./types";
import { useRecruitingOperations } from "./useRecruitingOperations";

type Filter = "all" | "active" | "draft";

const FILTER_TABS =
  "flex min-h-[42px] border-b border-border px-6 mw-620:overflow-x-auto mw-620:px-2";
const FILTER_TAB =
  "inline-flex items-center gap-1.5 border-b-2 px-[14px] text-[11px]";
const FILTER_TAB_COUNT =
  "min-w-[19px] rounded-full bg-surface-strong px-[5px] py-px font-mono text-[9px]";

// `.empty-state` is the same box as `.async-state`; only its `> div` adds anything.
const EMPTY_STATE_INNER = "grid justify-items-center gap-[11px]";

// `.positions-table th` is declared twice, so both halves merge onto every header cell.
const TABLE_HEAD_CELL =
  "border-b border-border px-[15px] py-[11px] text-left font-mono text-[9px]" +
  " font-medium text-muted";
// `tbody tr + tr` — the divider belongs to every row but the first.
const TABLE_ROW =
  "not-first:border-t not-first:border-t-border-muted hover:bg-surface-muted";
const TABLE_CELL = "text-[10px] text-muted";
// `td:first-child` is a grid, and `td:first-child > a` repeats it on the link inside.
const TABLE_CELL_TITLE = `${TABLE_CELL} grid min-w-[320px] gap-[3px]`;
const TABLE_LINK = "grid min-w-0 gap-[3px]";

const MONO_VALUE = "font-mono";

export function CompanyPositions({ api }: { api: CompanyOperationsApi }) {
  const { positions, invitations, loading, error } =
    useRecruitingOperations(api);
  const [filter, setFilter] = useState<Filter>("all");
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

  return (
    <div>
      <header className={PAGE_HEADER}>
        <div>
          <h1 className={PAGE_HEADER_TITLE}>채용 포지션</h1>
          <p className={PAGE_HEADER_TEXT}>
            포지션별 지원자, 면접 진행과 이메일 초대를 관리합니다.
          </p>
        </div>
        <Link className={BUTTON_PRIMARY} to="/hiring">
          <Plus size={14} aria-hidden="true" />새 포지션
        </Link>
      </header>

      <nav className={FILTER_TABS} aria-label="포지션 상태 필터">
        {(
          [
            ["all", "전체"],
            ["active", "운영 중"],
            ["draft", "초안"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            className={`${FILTER_TAB} ${
              filter === value
                ? "border-b-brand font-[650] text-brand"
                : "border-b-transparent text-muted"
            }`}
            type="button"
            onClick={() => setFilter(value)}
          >
            {label}
            <span className={FILTER_TAB_COUNT}>
              {countForFilter(positions, value)}
            </span>
          </button>
        ))}
      </nav>

      <div className={PAGE_CONTENT}>
        {loading ? (
          <div className={ASYNC_STATE} role="status">
            <p className="text-[12px]">
              포지션과 지원자 현황을 불러오는 중입니다.
            </p>
          </div>
        ) : error ? (
          <div className={ASYNC_STATE} role="alert">
            <p className="text-[12px]">포지션을 불러오지 못했습니다.</p>
          </div>
        ) : visible.length === 0 ? (
          <div className={`${PANEL} ${ASYNC_STATE}`}>
            <div className={EMPTY_STATE_INNER}>
              <BriefcaseBusiness size={25} aria-hidden="true" />
              <p className="text-[12px]">선택한 상태의 포지션이 없습니다.</p>
            </div>
          </div>
        ) : (
          <div className={`${PANEL} overflow-x-auto`}>
            <table className="w-full min-w-[680px] border-collapse">
              <thead>
                <tr>
                  <th className={TABLE_HEAD_CELL}>포지션</th>
                  <th className={TABLE_HEAD_CELL}>상태</th>
                  <th className={TABLE_HEAD_CELL}>채용 인원</th>
                  <th className={TABLE_HEAD_CELL}>지원자</th>
                  <th className={TABLE_HEAD_CELL}>모집 기간</th>
                  <th className={TABLE_HEAD_CELL}>
                    <span className="sr-only">운영 보기</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((position) => {
                  const applicantCount = invitations.filter(
                    (item) => item.positionId === position.positionId,
                  ).length;
                  return (
                    <tr className={TABLE_ROW} key={position.positionId}>
                      <td className={TABLE_CELL_TITLE}>
                        <Link
                          className={TABLE_LINK}
                          to={`/positions/${position.positionId}`}
                        >
                          <strong className="text-[12px] font-[550] text-brand">
                            {position.title}
                          </strong>
                          <small className="max-w-[520px] overflow-hidden text-[10px] text-ellipsis whitespace-nowrap text-muted">
                            {position.description}
                          </small>
                        </Link>
                      </td>
                      <td className={TABLE_CELL}>
                        <span
                          className={`${STATUS_BADGE} ${
                            STATUS_BADGE_TONE[statusTone(position.status)]
                          }`}
                        >
                          {statusLabel(position.status)}
                        </span>
                      </td>
                      <td className={TABLE_CELL}>
                        <span className={MONO_VALUE}>
                          {position.headcount
                            ? `${position.headcount}명`
                            : "미설정"}
                        </span>
                      </td>
                      <td className={TABLE_CELL}>
                        <span className="text-[10px] font-semibold text-ink">
                          지원자 {applicantCount}명
                        </span>
                      </td>
                      <td className={TABLE_CELL}>
                        {position.recruitmentStartAt &&
                        position.recruitmentEndAt ? (
                          <span className="inline-flex items-center gap-1 font-mono text-[9px] whitespace-nowrap">
                            <time dateTime={position.recruitmentStartAt}>
                              {formatShortDate(position.recruitmentStartAt)}
                            </time>
                            <span aria-hidden="true">–</span>
                            <time dateTime={position.recruitmentEndAt}>
                              {formatShortDate(position.recruitmentEndAt)}
                            </time>
                          </span>
                        ) : (
                          <span className={MONO_VALUE}>
                            {formatDate(position.createdAt)}
                          </span>
                        )}
                      </td>
                      <td className={TABLE_CELL}>
                        <Link
                          className="inline-grid size-[30px] place-items-center rounded-lg border border-border bg-surface text-muted hover:border-brand hover:bg-brand-soft hover:text-brand"
                          aria-label={`${position.title} 운영 보기`}
                          to={`/positions/${position.positionId}`}
                        >
                          <ArrowRight size={15} aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
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
