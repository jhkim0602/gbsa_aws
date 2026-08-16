import {
  ArrowLeft,
  BarChart3,
  BriefcaseBusiness,
  ClipboardCheck,
  FileText,
  Info,
  LayoutDashboard,
  ListChecks,
  PencilLine,
  Route,
  Target,
  Timer,
  UserRoundCheck,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";

import { PositionInvitations, type PositionInvitationApi } from "../hiring";
import { summarizeApplicantPipeline } from "./applicantSummary";
import { statusLabel, statusTone } from "./companyFormatters";
import { PositionDashboard } from "./PositionDashboard";
import { CriteriaEditModal, PositionQuickEditModal } from "./PositionSettings";
import {
  countRecruiterPhases,
  recruiterStages,
  type PositionTab,
} from "./positionWorkspaceModel";
import type {
  CompanyCriterionVersion,
  CompanyInvitation,
  CompanyOperationsApi,
  CompanyPosition,
} from "./types";
import { useRecruitingOperations } from "./useRecruitingOperations";

const positionTabs: ReadonlyArray<{
  id: PositionTab;
  label: string;
  icon: typeof Users;
}> = [
  { id: "overview", label: "대시보드", icon: LayoutDashboard },
  { id: "applicants", label: "지원자 목록", icon: Users },
  { id: "statistics", label: "지원자 통계", icon: BarChart3 },
  { id: "stages", label: "면접 단계", icon: Route },
  { id: "information", label: "포지션 정보", icon: Info },
];

export function PositionOperations({
  positionId,
  api,
  invitationApi,
}: {
  positionId: string;
  api: CompanyOperationsApi;
  invitationApi: PositionInvitationApi;
}) {
  const { positions, invitations, loading, error } = useRecruitingOperations(
    api,
    positionId,
  );
  const fetchedPosition = positions.find(
    (item) => item.positionId === positionId,
  );
  const [revisedPosition, setRevisedPosition] =
    useState<CompanyPosition | null>(null);
  const [criteria, setCriteria] = useState<readonly CompanyCriterionVersion[]>(
    [],
  );
  const [criteriaLoading, setCriteriaLoading] = useState(true);
  const [criteriaError, setCriteriaError] = useState("");
  const [activeTab, setActiveTab] = useState<PositionTab>("overview");
  const [quickEditOpen, setQuickEditOpen] = useState(false);
  const [criteriaEditOpen, setCriteriaEditOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const position =
    revisedPosition?.positionId === positionId
      ? revisedPosition
      : fetchedPosition;
  const positionInvitations = invitations.filter(
    (item) => item.positionId === positionId,
  );
  const summary = summarizeApplicantPipeline(positionInvitations);
  const currentCriteria =
    criteria.find((item) => item.status === "published") ?? criteria[0] ?? null;

  useEffect(() => {
    setRevisedPosition(null);
    setActiveTab("overview");
    setQuickEditOpen(false);
    setCriteriaEditOpen(false);
    setNotice("");
  }, [positionId]);

  useEffect(() => {
    let active = true;
    setCriteriaLoading(true);
    setCriteriaError("");
    api
      .listCriterionVersions(positionId)
      .then((items) => {
        if (active) setCriteria(items);
      })
      .catch(() => {
        if (active) setCriteriaError("면접 기준을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (active) setCriteriaLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, positionId]);

  const phaseCounts = useMemo(
    () => countRecruiterPhases(positionInvitations),
    [positionInvitations],
  );

  if (loading) {
    return (
      <div className="async-state" role="status">
        포지션 운영 정보를 불러오는 중입니다.
      </div>
    );
  }
  if (error || !position) {
    return (
      <div className="async-state" role="alert">
        포지션 운영 정보를 불러올 수 없습니다.
      </div>
    );
  }

  function selectTab(index: number) {
    const tab = positionTabs[index];
    if (!tab) return;
    setActiveTab(tab.id);
    window.requestAnimationFrame(() => {
      document.getElementById(`position-tab-${tab.id}`)?.focus();
    });
  }

  function openTab(tab: PositionTab) {
    setActiveTab(tab);
    window.requestAnimationFrame(() => {
      document.getElementById(`position-tab-${tab}`)?.focus();
    });
  }

  function handleTabKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      selectTab((index + 1) % positionTabs.length);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      selectTab((index - 1 + positionTabs.length) % positionTabs.length);
    } else if (event.key === "Home") {
      event.preventDefault();
      selectTab(0);
    } else if (event.key === "End") {
      event.preventDefault();
      selectTab(positionTabs.length - 1);
    }
  }

  return (
    <div className="position-operations position-workspace">
      <header className="position-workspace__header">
        <div className="position-workspace__heading">
          <Link to="/positions" className="position-operations__back">
            <ArrowLeft size={14} aria-hidden="true" />
            채용 포지션
          </Link>
          <div className="position-workspace__identity">
            <span className="position-workspace__icon" aria-hidden="true">
              <BriefcaseBusiness size={21} />
            </span>
            <div>
              <div className="position-workspace__title-line">
                <h1>{position.title}</h1>
                <span className={`status-badge ${statusTone(position.status)}`}>
                  {statusLabel(position.status)}
                </span>
              </div>
              <p>{position.description}</p>
              <div className="position-workspace__meta">
                <span>{position.roleType ?? "직무 미지정"}</span>
                <span>채용 목표 {position.headcount ?? "미정"}명</span>
                <span>{formatRecruitingPeriod(position)}</span>
                <span>지원자 {summary.total}명</span>
              </div>
            </div>
          </div>
        </div>
        <button
          className="button-secondary position-workspace__edit"
          type="button"
          disabled={position.status === "closed"}
          onClick={() => setQuickEditOpen(true)}
        >
          <PencilLine size={15} aria-hidden="true" />
          간편 수정
        </button>
      </header>

      {notice ? (
        <p
          className="form-alert is-success position-workspace__notice"
          role="status"
        >
          {notice}
        </p>
      ) : null}

      <div
        className="position-tabs position-workspace__tabs"
        role="tablist"
        aria-label="포지션 운영 메뉴"
      >
        {positionTabs.map((tab, index) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              id={`position-tab-${tab.id}`}
              className={activeTab === tab.id ? "is-active" : ""}
              type="button"
              role="tab"
              aria-label={tab.label}
              aria-selected={activeTab === tab.id}
              aria-controls={`position-panel-${tab.id}`}
              tabIndex={activeTab === tab.id ? 0 : -1}
              onClick={() => setActiveTab(tab.id)}
              onKeyDown={(event) => handleTabKeyDown(event, index)}
            >
              <Icon size={16} aria-hidden="true" />
              {tab.label}
              {tab.id === "applicants" ? <span>{summary.total}</span> : null}
            </button>
          );
        })}
      </div>

      <main className="position-operations__content position-workspace__content">
        {activeTab === "overview" ? (
          <section
            id="position-panel-overview"
            role="tabpanel"
            aria-labelledby="position-tab-overview"
          >
            <PositionDashboard
              position={position}
              invitations={positionInvitations}
              criteria={currentCriteria}
              phaseCounts={phaseCounts}
              onOpenTab={openTab}
            />
          </section>
        ) : null}

        {activeTab === "applicants" ? (
          <section
            id="position-panel-applicants"
            role="tabpanel"
            aria-labelledby="position-tab-applicants"
          >
            <PositionInvitations
              embedded
              view="workspace"
              positionId={positionId}
              positionName={position.title}
              api={invitationApi}
            />
          </section>
        ) : null}

        {activeTab === "statistics" ? (
          <section
            id="position-panel-statistics"
            role="tabpanel"
            aria-labelledby="position-tab-statistics"
            className="position-statistics"
          >
            <PositionSummary summary={summary} headcount={position.headcount} />
            <ApplicantStatistics
              invitations={positionInvitations}
              phaseCounts={phaseCounts}
            />
          </section>
        ) : null}

        {activeTab === "stages" ? (
          <section
            id="position-panel-stages"
            role="tabpanel"
            aria-labelledby="position-tab-stages"
            className="position-stages"
          >
            <InterviewStages
              counts={phaseCounts}
              total={summary.total}
              criteria={currentCriteria}
            />
          </section>
        ) : null}

        {activeTab === "information" ? (
          <section
            id="position-panel-information"
            role="tabpanel"
            aria-labelledby="position-tab-information"
            className="position-information"
          >
            <PositionInformation
              position={position}
              criteria={currentCriteria}
              loading={criteriaLoading}
              error={criteriaError}
              onEditPosition={() => setQuickEditOpen(true)}
              onEditCriteria={() => setCriteriaEditOpen(true)}
            />
          </section>
        ) : null}
      </main>

      <PositionQuickEditModal
        open={quickEditOpen}
        position={position}
        hasCriteria={Boolean(currentCriteria)}
        api={api}
        onClose={() => setQuickEditOpen(false)}
        onPositionUpdated={(updated, message) => {
          setRevisedPosition(updated);
          setNotice(message);
        }}
      />
      <CriteriaEditModal
        open={criteriaEditOpen}
        position={position}
        currentCriteria={currentCriteria}
        api={api}
        onClose={() => setCriteriaEditOpen(false)}
        onCriteriaUpdated={(updated, message) => {
          setCriteria((items) => [
            updated,
            ...items.filter((item) => item.versionId !== updated.versionId),
          ]);
          setNotice(message);
        }}
      />
    </div>
  );
}

function PositionSummary({
  summary,
  headcount,
}: {
  summary: ReturnType<typeof summarizeApplicantPipeline>;
  headcount?: number | null;
}) {
  return (
    <section className="operations-summary" aria-label="포지션 지원자 요약">
      <article aria-label={`전체 지원자 ${summary.total}명`}>
        <Users size={18} aria-hidden="true" />
        <span>전체 지원자</span>
        <strong>{summary.total}</strong>
      </article>
      <article aria-label={`진행 중인 지원자 ${summary.inProgress}명`}>
        <UserRoundCheck size={18} aria-hidden="true" />
        <span>진행 중</span>
        <strong>{summary.inProgress}</strong>
      </article>
      <article aria-label={`검토 대기 지원자 ${summary.reviewPending}명`}>
        <ClipboardCheck size={18} aria-hidden="true" />
        <span>검토 대기</span>
        <strong>{summary.reviewPending}</strong>
      </article>
      <article aria-label={`완료된 지원자 ${summary.completed}명`}>
        <BriefcaseBusiness size={18} aria-hidden="true" />
        <span>검토 완료</span>
        <strong>{summary.completed}</strong>
      </article>
      <p>
        <Target size={14} aria-hidden="true" />
        채용 목표 <strong>{headcount ?? "미정"}명</strong>
      </p>
    </section>
  );
}

function ApplicantStatistics({
  invitations,
  phaseCounts,
}: {
  invitations: readonly CompanyInvitation[];
  phaseCounts: readonly number[];
}) {
  const total = invitations.length;
  const attention = invitations.filter((item) =>
    ["interrupted", "expired", "revoked"].includes(item.status),
  ).length;

  return (
    <div className="position-statistics__grid">
      <section className="panel position-statistics__funnel">
        <header className="position-section-heading">
          <div>
            <h2>단계별 지원자 분포</h2>
            <p>현재 지원자가 위치한 채용 단계입니다.</p>
          </div>
          <span>총 {total}명</span>
        </header>
        <div className="position-statistics__bars">
          {recruiterStages.map((stage, index) => {
            const count = phaseCounts[index] ?? 0;
            const percentage = total ? Math.round((count / total) * 100) : 0;
            return (
              <div key={stage.phase}>
                <span>{stage.title}</span>
                <div aria-label={`${stage.title} ${count}명`}>
                  <i style={{ width: `${percentage}%` }} />
                </div>
                <strong>{count}명</strong>
                <small>{percentage}%</small>
              </div>
            );
          })}
        </div>
      </section>
      <section className="panel position-statistics__attention">
        <header className="position-section-heading">
          <div>
            <h2>운영 확인 항목</h2>
            <p>재접속, 만료 또는 취소 상태를 우선 확인합니다.</p>
          </div>
        </header>
        <strong>{attention}</strong>
        <span>확인이 필요한 지원자</span>
        <p>
          {attention
            ? "지원자 목록에서 확인 필요 필터를 선택해 상태를 점검하세요."
            : "현재 별도로 확인할 지원자가 없습니다."}
        </p>
      </section>
    </div>
  );
}

function InterviewStages({
  counts,
  total,
  criteria,
}: {
  counts: readonly number[];
  total: number;
  criteria: CompanyCriterionVersion | null;
}) {
  return (
    <>
      <section className="panel position-stage-flow">
        <header className="position-section-heading">
          <div>
            <h2>지원자 면접 흐름</h2>
            <p>채용담당자가 확인하는 네 단계로 진행 상황을 정리합니다.</p>
          </div>
          <span>지원자 {total}명</span>
        </header>
        <ol>
          {recruiterStages.map((stage, index) => (
            <li key={stage.phase}>
              <span>{stage.phase}</span>
              <div>
                <strong>{stage.title}</strong>
                <p>{stage.description}</p>
              </div>
              <b>{counts[index] ?? 0}명</b>
            </li>
          ))}
        </ol>
      </section>
      <section className="panel position-stage-focus">
        <header className="position-section-heading">
          <div>
            <h2>면접에서 확인할 중점</h2>
            <p>
              기업이 설정한 평가기준을 면접 질문과 검토에 동일하게 적용합니다.
            </p>
          </div>
        </header>
        {criteria ? (
          <div className="position-stage-focus__list">
            {criteria.criteria.map((criterion) => (
              <article key={criterion.code}>
                <div>
                  <span>{criterion.required ? "필수" : "선택"}</span>
                  <strong>{criterion.name}</strong>
                  <p>{criterion.description}</p>
                </div>
                <b>{criterion.weight}</b>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <ListChecks size={22} aria-hidden="true" />
            <div>
              <strong>저장된 면접 기준이 없습니다.</strong>
              <p>포지션 정보에서 면접 기준을 입력하세요.</p>
            </div>
          </div>
        )}
      </section>
    </>
  );
}

function PositionInformation({
  position,
  criteria,
  loading,
  error,
  onEditPosition,
  onEditCriteria,
}: {
  position: CompanyPosition;
  criteria: CompanyCriterionVersion | null;
  loading: boolean;
  error: string;
  onEditPosition(): void;
  onEditCriteria(): void;
}) {
  return (
    <>
      <section className="panel position-information__basic">
        <header className="position-section-heading">
          <div>
            <h2>포지션 기본 정보</h2>
            <p>공고와 운영 현황에 표시되는 현재 값입니다.</p>
          </div>
          {position.status !== "closed" ? (
            <button
              className="button-secondary"
              type="button"
              onClick={onEditPosition}
            >
              <PencilLine size={14} aria-hidden="true" />
              기본 정보 수정
            </button>
          ) : null}
        </header>
        <dl className="position-information__facts">
          <div>
            <dt>직무</dt>
            <dd>{position.roleType ?? "미지정"}</dd>
          </div>
          <div>
            <dt>채용 목표</dt>
            <dd>{position.headcount ?? "미정"}명</dd>
          </div>
          <div>
            <dt>모집 기간</dt>
            <dd>{formatRecruitingPeriod(position)}</dd>
          </div>
          <div>
            <dt>운영 상태</dt>
            <dd>{statusLabel(position.status)}</dd>
          </div>
        </dl>
      </section>

      <section className="panel position-information__criteria">
        <header className="position-section-heading">
          <div>
            <h2>현재 적용 중인 면접 기준</h2>
            <p>지원자 질문과 답변 검토에 사용하는 기업 설정값입니다.</p>
          </div>
          {position.status !== "closed" ? (
            <button
              className="button-secondary"
              type="button"
              onClick={onEditCriteria}
            >
              <FileText size={14} aria-hidden="true" />
              면접 기준 수정
            </button>
          ) : null}
        </header>

        {loading ? (
          <div className="async-state" role="status">
            면접 기준을 불러오는 중입니다.
          </div>
        ) : error ? (
          <div className="async-state" role="alert">
            {error}
          </div>
        ) : criteria ? (
          <div className="position-information__criteria-body">
            <section>
              <h3>직무 요구사항</h3>
              {criteria.jobRequirements.length ? (
                <ul className="position-requirement-list">
                  {criteria.jobRequirements.map((requirement, index) => (
                    <li key={`${requirement.criterionCode}-${index}`}>
                      <span
                        className={
                          requirement.requirementType === "required"
                            ? "is-required"
                            : "is-preferred"
                        }
                      >
                        {requirement.requirementType === "required"
                          ? "필수"
                          : "우대"}
                      </span>
                      <strong>{requirement.statement}</strong>
                      <small>
                        중요도 {priorityLabel(requirement.priority)}
                      </small>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="position-information__empty">
                  등록된 직무 요구사항이 없습니다.
                </p>
              )}
            </section>

            <section>
              <h3>평가기준과 검증 가이드</h3>
              <div className="position-criterion-list">
                {criteria.criteria.map((criterion) => (
                  <article key={criterion.code}>
                    <header>
                      <div>
                        <span>{criterion.required ? "필수" : "선택"}</span>
                        <strong>{criterion.name}</strong>
                        <p>{criterion.description}</p>
                      </div>
                      <b>가중치 {criterion.weight}</b>
                    </header>
                    <dl>
                      <div>
                        <dt>확인 요소</dt>
                        <dd>
                          {criterion.verificationGuide.observableDimensions.join(
                            " · ",
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>좋은 답변 신호</dt>
                        <dd>
                          {criterion.verificationGuide.strongAnswerSignals.join(
                            " · ",
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>추가 확인 신호</dt>
                        <dd>
                          {criterion.verificationGuide.weakAnswerSignals.join(
                            " · ",
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>꼬리질문 방향</dt>
                        <dd>
                          {criterion.verificationGuide.followUpDirections.join(
                            " · ",
                          )}
                        </dd>
                      </div>
                    </dl>
                  </article>
                ))}
              </div>
            </section>
          </div>
        ) : (
          <div className="empty-state">
            <ListChecks size={22} aria-hidden="true" />
            <div>
              <strong>저장된 면접 기준이 없습니다.</strong>
              <p>면접 기준을 입력해야 채용을 확정할 수 있습니다.</p>
            </div>
          </div>
        )}
      </section>

      {criteria ? (
        <section className="panel position-information__policy">
          <header className="position-section-heading">
            <div>
              <h2>면접 운영 정책</h2>
              <p>면접 진행 시간과 질문 제한 범위입니다.</p>
            </div>
          </header>
          <div>
            <span>
              <Timer size={17} aria-hidden="true" />
              <small>면접 시간</small>
              <strong>{criteria.interviewDurationMinutes}분</strong>
            </span>
            <span>
              <ClipboardCheck size={17} aria-hidden="true" />
              <small>평가기준</small>
              <strong>{criteria.criteria.length}개</strong>
            </span>
            <span>
              <Info size={17} aria-hidden="true" />
              <small>금지 주제</small>
              <strong>
                {criteria.prohibitedTopics.length
                  ? criteria.prohibitedTopics.join(", ")
                  : "등록 없음"}
              </strong>
            </span>
          </div>
        </section>
      ) : null}
    </>
  );
}

function formatRecruitingPeriod(position: CompanyPosition) {
  if (!position.recruitmentStartAt && !position.recruitmentEndAt) {
    return "상시 채용";
  }
  const start = position.recruitmentStartAt
    ? formatDate(position.recruitmentStartAt)
    : "시작일 미정";
  const end = position.recruitmentEndAt
    ? formatDate(position.recruitmentEndAt)
    : "종료일 미정";
  return `${start} - ${end}`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(`${value}T00:00:00`));
}

function priorityLabel(priority: number) {
  return ["높음", "중간", "보통", "낮음", "참고"][priority - 1] ?? priority;
}
