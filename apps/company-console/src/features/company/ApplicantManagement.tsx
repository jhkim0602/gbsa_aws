import { ClipboardCheck, Search, UserRoundCheck, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { invitationStatusMeta } from "../hiring/PositionInvitations";
import { summarizeApplicantPipeline } from "./applicantSummary";
import type { CompanyOperationsApi } from "./types";
import { useRecruitingOperations } from "./useRecruitingOperations";

export function ApplicantManagement({ api }: { api: CompanyOperationsApi }) {
  const { invitations, loading, error } = useRecruitingOperations(api);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const summary = useMemo(
    () => summarizeApplicantPipeline(invitations),
    [invitations],
  );
  const visible = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("ko-KR");
    if (!normalized) return invitations;
    return invitations.filter((item) =>
      [
        item.applicantDisplayName ?? "",
        item.applicantEmail,
        item.positionTitle,
      ].some((value) => value.toLocaleLowerCase("ko-KR").includes(normalized)),
    );
  }, [invitations, query]);
  const pageSize = 20;
  const pageCount = Math.max(1, Math.ceil(visible.length / pageSize));
  const activePage = Math.min(page, pageCount);
  const pageInvitations = visible.slice(
    (activePage - 1) * pageSize,
    activePage * pageSize,
  );

  return (
    <div className="applicant-management">
      <header className="page-header applicant-management__header applicant-management__header--refined">
        <div>
          <h1>지원자 관리</h1>
          <p>
            전체 포지션의 지원자 진행 상태와 검토 대상을 한곳에서 확인합니다.
          </p>
        </div>
        <label className="search-field">
          <Search size={15} aria-hidden="true" />
          <span className="sr-only">지원자 검색</span>
          <input
            aria-label="지원자 검색"
            type="search"
            placeholder="이름, 이메일, 포지션"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
        </label>
      </header>

      <section
        className="operations-summary applicant-management__summary"
        aria-label="전체 지원자 요약"
      >
        <article aria-label={`전체 지원자 ${summary.total}명`}>
          <Users size={17} aria-hidden="true" />
          <span>전체 지원자</span>
          <strong>{summary.total}</strong>
        </article>
        <article aria-label={`진행 중인 지원자 ${summary.inProgress}명`}>
          <UserRoundCheck size={17} aria-hidden="true" />
          <span>진행 중</span>
          <strong>{summary.inProgress}</strong>
        </article>
        <article aria-label={`검토 대기 지원자 ${summary.reviewPending}명`}>
          <ClipboardCheck size={17} aria-hidden="true" />
          <span>검토 대기</span>
          <strong>{summary.reviewPending}</strong>
        </article>
        <article aria-label={`완료된 지원자 ${summary.completed}명`}>
          <ClipboardCheck size={17} aria-hidden="true" />
          <span>검토 완료</span>
          <strong>{summary.completed}</strong>
        </article>
      </section>

      <section className="panel applicant-management__table">
        <header className="section-header applicant-management__table-header">
          <div>
            <h2>지원자 목록</h2>
            <p>이름을 선택하면 제출 자료와 면접 결과를 확인할 수 있습니다.</p>
          </div>
          <span>{visible.length}명 표시</span>
        </header>
        {loading ? (
          <div className="async-state" role="status">
            지원자를 불러오는 중입니다.
          </div>
        ) : error ? (
          <div className="async-state" role="alert">
            지원자 정보를 불러올 수 없습니다.
          </div>
        ) : visible.length ? (
          <div className="invitation-table-wrap">
            <table className="invitation-table">
              <thead>
                <tr>
                  <th>지원자</th>
                  <th>포지션</th>
                  <th>현재 상태</th>
                  <th>면접 결과</th>
                  <th>
                    <span className="sr-only">상세</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {pageInvitations.map((invitation) => {
                  const displayName =
                    invitation.applicantDisplayName ||
                    invitation.applicantEmail.split("@")[0];
                  const status = invitationStatusMeta[invitation.status];
                  const detailPath = `/positions/${invitation.positionId}/applicants/${invitation.invitationId}`;
                  return (
                    <tr key={invitation.invitationId}>
                      <td>
                        <span className="recipient-avatar" aria-hidden="true">
                          {displayName.slice(0, 1)}
                        </span>
                        <span>
                          <Link
                            className="invitation-applicant-link"
                            aria-label={`${displayName} 상세 보기`}
                            to={detailPath}
                          >
                            <strong>{displayName}</strong>
                          </Link>
                          <small>{invitation.applicantEmail}</small>
                        </span>
                      </td>
                      <td>{invitation.positionTitle}</td>
                      <td>
                        <span className={`invitation-status is-${status.tone}`}>
                          {status.label}
                        </span>
                      </td>
                      <td>
                        {invitation.interviewSessionId ? "검토 가능" : "대기"}
                      </td>
                      <td>
                        <Link className="button-quiet" to={detailPath}>
                          상세
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <Users size={24} aria-hidden="true" />
            <div>
              <strong>조건에 맞는 지원자가 없습니다.</strong>
            </div>
          </div>
        )}
        {!loading && !error && visible.length > pageSize ? (
          <footer className="applicant-management__pagination">
            <span>
              {visible.length}명 중 {(activePage - 1) * pageSize + 1}–
              {Math.min(activePage * pageSize, visible.length)}
            </span>
            <div>
              <button
                className="button-secondary"
                type="button"
                disabled={activePage === 1}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                이전
              </button>
              <span>
                {activePage} / {pageCount}
              </span>
              <button
                className="button-secondary"
                type="button"
                disabled={activePage === pageCount}
                onClick={() =>
                  setPage((value) => Math.min(pageCount, value + 1))
                }
              >
                다음
              </button>
            </div>
          </footer>
        ) : null}
      </section>
    </div>
  );
}
