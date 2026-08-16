import { ArrowRight, BriefcaseBusiness, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { formatDate, statusLabel, statusTone } from "./companyFormatters";
import type { CompanyOperationsApi, CompanyPosition } from "./types";
import { useRecruitingOperations } from "./useRecruitingOperations";

type Filter = "all" | "active" | "draft";

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
    <div className="positions-page">
      <header className="page-header">
        <div>
          <h1>채용 포지션</h1>
          <p>포지션별 지원자, 면접 진행과 이메일 초대를 관리합니다.</p>
        </div>
        <Link className="button-primary" to="/hiring">
          <Plus size={14} aria-hidden="true" />새 포지션
        </Link>
      </header>

      <nav className="filter-tabs" aria-label="포지션 상태 필터">
        {(
          [
            ["all", "전체"],
            ["active", "운영 중"],
            ["draft", "초안"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            className={filter === value ? "is-active" : ""}
            type="button"
            onClick={() => setFilter(value)}
          >
            {label}
            <span>{countForFilter(positions, value)}</span>
          </button>
        ))}
      </nav>

      <div className="page-content">
        {loading ? (
          <div className="async-state" role="status">
            <p>포지션과 지원자 현황을 불러오는 중입니다.</p>
          </div>
        ) : error ? (
          <div className="async-state" role="alert">
            <p>포지션을 불러오지 못했습니다.</p>
          </div>
        ) : visible.length === 0 ? (
          <div className="panel empty-state">
            <div>
              <BriefcaseBusiness size={25} aria-hidden="true" />
              <p>선택한 상태의 포지션이 없습니다.</p>
            </div>
          </div>
        ) : (
          <div className="panel positions-table-wrap">
            <table className="positions-table">
              <thead>
                <tr>
                  <th>포지션</th>
                  <th>상태</th>
                  <th>채용 인원</th>
                  <th>지원자</th>
                  <th>모집 기간</th>
                  <th>
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
                    <tr key={position.positionId}>
                      <td>
                        <Link to={`/positions/${position.positionId}`}>
                          <strong>{position.title}</strong>
                          <small>{position.description}</small>
                        </Link>
                      </td>
                      <td>
                        <span
                          className={`status-badge ${statusTone(position.status)}`}
                        >
                          {statusLabel(position.status)}
                        </span>
                      </td>
                      <td>
                        <span className="mono-value">
                          {position.headcount
                            ? `${position.headcount}명`
                            : "미설정"}
                        </span>
                      </td>
                      <td>
                        <span className="position-applicant-count">
                          지원자 {applicantCount}명
                        </span>
                      </td>
                      <td>
                        {position.recruitmentStartAt &&
                        position.recruitmentEndAt ? (
                          <span className="position-recruitment-period">
                            <time dateTime={position.recruitmentStartAt}>
                              {formatShortDate(position.recruitmentStartAt)}
                            </time>
                            <span aria-hidden="true">–</span>
                            <time dateTime={position.recruitmentEndAt}>
                              {formatShortDate(position.recruitmentEndAt)}
                            </time>
                          </span>
                        ) : (
                          <span className="mono-value">
                            {formatDate(position.createdAt)}
                          </span>
                        )}
                      </td>
                      <td>
                        <Link
                          className="position-inspect-button"
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
