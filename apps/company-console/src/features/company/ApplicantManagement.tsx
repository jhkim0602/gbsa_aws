import { ClipboardCheck, Search, UserRoundCheck, Users } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ASYNC_STATE,
  BUTTON_QUIET,
  INVITATION_APPLICANT_LINK,
  INVITATION_STATUS,
  INVITATION_TABLE,
  INVITATION_TABLE_BODY,
  INVITATION_TABLE_CELL_AT,
  INVITATION_TABLE_EMAIL,
  INVITATION_TABLE_HEAD,
  INVITATION_TABLE_HEAD_CELL,
  INVITATION_TABLE_IDENTITY_TEXT,
  INVITATION_TABLE_NAME,
  INVITATION_TABLE_ROW,
  INVITATION_TABLE_WRAP,
  invitationTone,
  RECIPIENT_AVATAR,
  SEARCH_FIELD,
} from "../../app/styles/primitives";
import { invitationStatusMeta } from "../hiring/PositionInvitations";
import { summarizeApplicantPipeline } from "./applicantSummary";
import type { CompanyOperationsApi } from "./types";
import { useRecruitingOperations } from "./useRecruitingOperations";

/*
 * `.applicant-management__header--refined` replaces the shared `.page-header` box rather than
 * extending it, so `PAGE_HEADER` is not the base: it is declared after `.page-header`'s 680px
 * block, which means its own padding wins at every width and the horizontal padding moves out
 * to the page wrapper. Only the flex box, the gap and `.page-header p`'s colour survive.
 */
const HEADER =
  "flex min-h-28 items-end justify-between gap-5 pt-[26px] pb-4" +
  " mw-720:pt-5 mw-720:pb-[14px] mw-620:items-stretch";
const HEADER_TITLE = "text-[26px] font-bold";
const HEADER_TEXT = "mt-1.5 text-[13px] leading-[1.5] text-muted";
const HEADER_SEARCH = `${SEARCH_FIELD} w-[min(360px,100%)]`;
const HEADER_SEARCH_INPUT =
  "h-10 w-full rounded-[7px] border border-border bg-surface pr-2.5 pl-8" +
  " text-[12px]";

/*
 * `.operations-summary`, narrowed to four columns by `.applicant-management__summary`. That
 * modifier also flattens the margin to `0 0 16px`, but it is declared *before* the shared
 * 720px block, so below 720px the base `14px 16px 0` comes back.
 */
const SUMMARY =
  "mb-4 grid grid-cols-[repeat(4,minmax(140px,1fr))] overflow-hidden rounded-lg" +
  " border border-border bg-surface mw-1050:grid-cols-2" +
  " mw-720:mx-4 mw-720:mt-[14px] mw-720:mb-0" +
  " mw-480:grid-cols-[minmax(0,1fr)]";
// There are exactly four cells, so `nth-child(n+3)` is the source's 3-and-4 pair.
const SUMMARY_CELL =
  "grid min-h-18 grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-2.5" +
  " px-4 py-3 not-first:border-l not-first:border-l-border-muted" +
  " mw-1050:nth-[n+3]:border-t mw-1050:nth-[n+3]:border-t-border-muted" +
  " mw-1050:nth-3:border-l-0 mw-720:min-h-[62px]" +
  " mw-720:grid-cols-[24px_minmax(0,1fr)_auto] mw-720:px-3 mw-720:py-2.5" +
  " mw-480:not-first:border-t mw-480:not-first:border-t-border-muted" +
  " mw-480:not-first:border-l-0";
const SUMMARY_LABEL = "text-[12px] text-muted";
const SUMMARY_VALUE = "text-[22px] mw-720:text-[19px]";

// `.applicant-management__table` drops `.panel`'s shadow and rounds to 8px.
const TABLE_PANEL =
  "overflow-hidden rounded-lg border border-border bg-surface";
const TABLE_HEADER =
  "flex min-h-17 items-center justify-between gap-[14px] border-b border-border" +
  " px-[18px] py-[14px]";
const TABLE_COUNT = "text-muted";

const PAGINATION =
  "flex min-h-16 items-center justify-between border-t border-border px-[18px]" +
  " py-3 text-[12px] text-muted mw-720:flex-col mw-720:items-stretch mw-720:gap-2.5";
const PAGINATION_CONTROLS = "flex items-center gap-2.5 mw-720:justify-between";
/*
 * `.applicant-management__pagination .button-secondary` (0,2,0) shrinks the shared button and
 * drops its shadow. `BUTTON_SECONDARY` is not the base: Tailwind emits `px-[13px]`,
 * `text-[11px]` and `shadow-none` *before* the `px-[18px]`/`text-[14px]`/`shadow-soft` they
 * have to beat, so composing them would lose. Only the parts that survive are restated.
 */
const PAGINATION_BUTTON =
  "inline-flex min-h-[34px] items-center justify-center gap-1.5 rounded-lg" +
  " border border-border bg-white px-[13px] text-[11px] font-semibold text-ink" +
  " hover:not-disabled:bg-surface-muted";

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
    <div className="grid gap-4 px-8 pb-12 mw-720:px-4 mw-720:pb-8">
      <header className={HEADER}>
        <div>
          <h1 className={HEADER_TITLE}>지원자 관리</h1>
          <p className={HEADER_TEXT}>
            전체 포지션의 지원자 진행 상태와 검토 대상을 한곳에서 확인합니다.
          </p>
        </div>
        <label className={HEADER_SEARCH}>
          <Search
            className="absolute left-2.5 text-subtle"
            size={15}
            aria-hidden="true"
          />
          <span className="sr-only">지원자 검색</span>
          <input
            className={HEADER_SEARCH_INPUT}
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

      <section className={SUMMARY} aria-label="전체 지원자 요약">
        <SummaryMetric
          icon={<Users size={17} aria-hidden="true" />}
          label="전체 지원자"
          value={summary.total}
          ariaLabel={`전체 지원자 ${summary.total}명`}
        />
        <SummaryMetric
          icon={<UserRoundCheck size={17} aria-hidden="true" />}
          label="진행 중"
          value={summary.inProgress}
          ariaLabel={`진행 중인 지원자 ${summary.inProgress}명`}
        />
        <SummaryMetric
          icon={<ClipboardCheck size={17} aria-hidden="true" />}
          label="검토 대기"
          value={summary.reviewPending}
          ariaLabel={`검토 대기 지원자 ${summary.reviewPending}명`}
        />
        <SummaryMetric
          icon={<ClipboardCheck size={17} aria-hidden="true" />}
          label="검토 완료"
          value={summary.completed}
          ariaLabel={`완료된 지원자 ${summary.completed}명`}
        />
      </section>

      <section className={TABLE_PANEL}>
        <header className={TABLE_HEADER}>
          <div>
            <h2 className="text-[15px]">지원자 목록</h2>
            <p className="mt-0.5 text-[11px] text-muted">
              이름을 선택하면 제출 자료와 면접 결과를 확인할 수 있습니다.
            </p>
          </div>
          <span className={TABLE_COUNT}>{visible.length}명 표시</span>
        </header>
        {loading ? (
          <div className={ASYNC_STATE} role="status">
            지원자를 불러오는 중입니다.
          </div>
        ) : error ? (
          <div className={ASYNC_STATE} role="alert">
            지원자 정보를 불러올 수 없습니다.
          </div>
        ) : visible.length ? (
          <div className={INVITATION_TABLE_WRAP}>
            <table className={INVITATION_TABLE}>
              <thead className={INVITATION_TABLE_HEAD}>
                <tr>
                  <th className={INVITATION_TABLE_HEAD_CELL}>지원자</th>
                  <th className={INVITATION_TABLE_HEAD_CELL}>포지션</th>
                  <th className={INVITATION_TABLE_HEAD_CELL}>현재 상태</th>
                  <th className={INVITATION_TABLE_HEAD_CELL}>면접 결과</th>
                  <th className={INVITATION_TABLE_HEAD_CELL}>
                    <span className="sr-only">상세</span>
                  </th>
                </tr>
              </thead>
              <tbody className={INVITATION_TABLE_BODY}>
                {pageInvitations.map((invitation) => {
                  const displayName =
                    invitation.applicantDisplayName ||
                    invitation.applicantEmail.split("@")[0];
                  const status = invitationStatusMeta[invitation.status];
                  const detailPath = `/positions/${invitation.positionId}/applicants/${invitation.invitationId}`;
                  return (
                    <tr
                      className={INVITATION_TABLE_ROW}
                      key={invitation.invitationId}
                    >
                      <td className={INVITATION_TABLE_CELL_AT[0]}>
                        <span className={RECIPIENT_AVATAR} aria-hidden="true">
                          {displayName.slice(0, 1)}
                        </span>
                        <span className={INVITATION_TABLE_IDENTITY_TEXT}>
                          <Link
                            className={INVITATION_APPLICANT_LINK}
                            aria-label={`${displayName} 상세 보기`}
                            to={detailPath}
                          >
                            <strong className={INVITATION_TABLE_NAME}>
                              {displayName}
                            </strong>
                          </Link>
                          <small className={INVITATION_TABLE_EMAIL}>
                            {invitation.applicantEmail}
                          </small>
                        </span>
                      </td>
                      <td
                        className={`${INVITATION_TABLE_CELL_AT[1]} font-semibold text-ink-secondary`}
                      >
                        {invitation.positionTitle}
                      </td>
                      <td className={INVITATION_TABLE_CELL_AT[2]}>
                        <span
                          className={`${INVITATION_STATUS} ${invitationTone(
                            status.tone,
                          )}`}
                        >
                          {status.label}
                        </span>
                      </td>
                      <td className={INVITATION_TABLE_CELL_AT[3]}>
                        {invitation.interviewSessionId ? "검토 가능" : "대기"}
                      </td>
                      <td className={INVITATION_TABLE_CELL_AT[4]}>
                        <Link className={BUTTON_QUIET} to={detailPath}>
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
          <div className={ASYNC_STATE}>
            <Users size={24} aria-hidden="true" />
            <div className="grid justify-items-center gap-[11px]">
              <strong>조건에 맞는 지원자가 없습니다.</strong>
            </div>
          </div>
        )}
        {!loading && !error && visible.length > pageSize ? (
          <footer className={PAGINATION}>
            <span>
              {visible.length}명 중 {(activePage - 1) * pageSize + 1}–
              {Math.min(activePage * pageSize, visible.length)}
            </span>
            <div className={PAGINATION_CONTROLS}>
              <button
                className={PAGINATION_BUTTON}
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
                className={PAGINATION_BUTTON}
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

function SummaryMetric({
  icon,
  label,
  value,
  ariaLabel,
}: {
  icon: ReactNode;
  label: string;
  value: number;
  ariaLabel: string;
}) {
  return (
    <article className={SUMMARY_CELL} aria-label={ariaLabel}>
      <span className="text-muted">{icon}</span>
      <span className={SUMMARY_LABEL}>{label}</span>
      <strong className={SUMMARY_VALUE}>{value}</strong>
    </article>
  );
}
