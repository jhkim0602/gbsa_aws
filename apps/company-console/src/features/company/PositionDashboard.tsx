import { ArrowRight, BarChart3, ListChecks, Send } from "lucide-react";

import { BUTTON_PRIMARY, BUTTON_SECONDARY } from "../../app/styles/primitives";
import { interviewLevelLabels } from "../hiring";
import {
  ApplicantScoreTable,
  CompetencyDistribution,
} from "./CompetencyInsights";
import type { PositionTab } from "./positionWorkspaceModel";
import type {
  CompanyApplicantInsight,
  CompanyCriterionVersion,
  CompanyInvitation,
  CompanyPosition,
} from "./types";

export function PositionDashboard({
  invitations,
  criteria,
  insights,
  canInvite = true,
  onOpenTab,
  onOpenInvitations,
}: {
  position: CompanyPosition;
  invitations: readonly CompanyInvitation[];
  criteria: CompanyCriterionVersion | null;
  insights: readonly CompanyApplicantInsight[];
  canInvite?: boolean;
  onOpenTab(tab: PositionTab): void;
  onOpenInvitations(): void;
}) {
  const requirementAssessments = insights.flatMap(
    (insight) => insight.requirementAssessments ?? [],
  );
  const mandatoryQuestions =
    criteria?.criteria.flatMap((criterion) => criterion.commonQuestions) ?? [];
  return (
    <div className="grid gap-4">
      <section className="overflow-hidden rounded-lg border border-border bg-surface">
        <header className="flex items-center justify-between gap-5 border-b border-border-muted px-5 py-4 mw-720:flex-col mw-720:items-stretch">
          <div className="flex min-w-0 items-start gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand">
              <BarChart3 size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <h2 className="text-[15px] text-ink">포지션 판단 요약</h2>
              <p className="mt-1 text-[11px] leading-[1.5] text-muted">
                기업이 설정한 필수·우대 자격요건별 충족 상태와 답변 근거를
                비교합니다.
              </p>
            </div>
          </div>
          <div className="flex shrink-0 gap-2 mw-720:w-full">
            <button
              className={`${BUTTON_SECONDARY} mw-720:flex-1`}
              type="button"
              disabled={!canInvite}
              title={
                canInvite ? undefined : "모집 중인 포지션만 초대할 수 있습니다."
              }
              onClick={onOpenInvitations}
            >
              <Send size={14} aria-hidden="true" /> 지원자 초대
            </button>
            <button
              className={`${BUTTON_PRIMARY} mw-720:flex-1`}
              type="button"
              onClick={() => onOpenTab("statistics")}
            >
              전체 분석 <ArrowRight size={14} aria-hidden="true" />
            </button>
          </div>
        </header>
      </section>

      {requirementAssessments.length ? (
        <RequirementStatusOverview insights={insights} />
      ) : (
        <>
          <CompetencyDistribution
            insights={insights}
            invitations={invitations}
            limit={4}
            title="기존 리포트 평가 기준별 평균"
            description="자격요건 판정이 생성되기 전 리포트는 기존 참고 점수로 표시합니다."
          />
          <ApplicantScoreTable
            invitations={invitations}
            insights={insights}
            limit={5}
          />
        </>
      )}

      <section className="overflow-hidden rounded-lg border border-border bg-surface">
        <header className="flex min-h-16 items-center justify-between gap-4 border-b border-border-muted px-5 py-3 mw-720:items-start">
          <div className="flex items-start gap-3">
            <span className="grid size-9 place-items-center rounded-lg bg-brand-soft text-brand">
              <ListChecks size={18} aria-hidden="true" />
            </span>
            <div>
              <h2 className="text-[14px] text-ink">현재 면접 설정</h2>
              <p className="mt-1 text-[11px] text-muted">
                게시된 기준은 지원자 간 일관성을 위해 읽기 전용으로 유지됩니다.
              </p>
            </div>
          </div>
          <button
            className={BUTTON_SECONDARY}
            type="button"
            onClick={() => onOpenTab("information")}
          >
            설정값 보기 <ArrowRight size={14} aria-hidden="true" />
          </button>
        </header>
        {criteria ? (
          <div className="grid grid-cols-[repeat(3,minmax(140px,0.45fr))_minmax(260px,1fr)] mw-1050:grid-cols-3 mw-720:grid-cols-[minmax(0,1fr)]">
            <SettingValue
              label="면접 시간"
              value={`최대 ${criteria.interviewDurationMinutes}분 · 근거 충분 시 조기 종료`}
            />
            <SettingValue
              label="면접관"
              value={
                criteria.personaDefinition?.name ??
                interviewLevelLabels[criteria.interviewLevel].name
              }
            />
            <SettingValue
              label="자격요건"
              value={`${criteria.jobRequirements.length}개`}
            />
            <div className="grid gap-2 p-4 mw-1050:col-[1/-1] mw-1050:border-t mw-1050:border-border-muted">
              <span className="text-[10px] text-muted">
                반드시 물어볼 질문 · {mandatoryQuestions.length}개
              </span>
              <div className="flex flex-wrap gap-1.5">
                {mandatoryQuestions.length ? (
                  mandatoryQuestions.map((question, index) => (
                    <span
                      className="rounded-md border border-border-muted bg-surface-muted px-2.5 py-1.5 text-[9px] text-ink-secondary"
                      key={`${question}-${index}`}
                    >
                      {index + 1}. {question}
                    </span>
                  ))
                ) : (
                  <span className="text-[9px] text-muted">
                    별도 질문 없음 · 자격요건과 지원자 자료를 기준으로 진행
                  </span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <p className="p-5 text-[11px] text-muted">
            저장된 면접 기준이 없습니다.
          </p>
        )}
      </section>
    </div>
  );
}

const requirementStatusMeta = {
  met: { label: "충족", tone: "bg-success-soft text-success" },
  partially_met: { label: "부분 충족", tone: "bg-warning-soft text-warning" },
  not_met: { label: "미충족", tone: "bg-danger-soft text-danger" },
  unknown: { label: "판단 보류", tone: "bg-surface-strong text-muted" },
} as const;

function RequirementStatusOverview({
  insights,
}: {
  insights: readonly CompanyApplicantInsight[];
}) {
  const assessments = insights.flatMap(
    (insight) => insight.requirementAssessments ?? [],
  );
  const totals = Object.fromEntries(
    Object.keys(requirementStatusMeta).map((status) => [
      status,
      assessments.filter((assessment) => assessment.status === status).length,
    ]),
  ) as Record<keyof typeof requirementStatusMeta, number>;
  const statements = Array.from(
    new Map(
      assessments.map((assessment) => [assessment.statement, assessment]),
    ).values(),
  );

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-surface">
      <header className="border-b border-border-muted px-5 py-4">
        <h2 className="text-[14px] text-ink">자격요건 판정 현황</h2>
        <p className="mt-1 text-[10px] text-muted">
          점수 대신 제출 자료와 면접 답변을 함께 확인한 상태를 집계합니다.
        </p>
      </header>
      <dl className="grid grid-cols-4 border-b border-border-muted mw-720:grid-cols-2">
        {Object.entries(requirementStatusMeta).map(([status, meta]) => (
          <div className="border-r border-border-muted p-4 last:border-r-0" key={status}>
            <dt className={`inline-flex rounded-full px-2 py-1 text-[9px] font-bold ${meta.tone}`}>
              {meta.label}
            </dt>
            <dd className="mt-2 font-mono text-[22px] text-ink">
              {totals[status as keyof typeof requirementStatusMeta]}건
            </dd>
          </div>
        ))}
      </dl>
      <div className="grid">
        {statements.map((requirement) => {
          const related = assessments.filter(
            (assessment) => assessment.statement === requirement.statement,
          );
          return (
            <div
              className="grid grid-cols-[72px_minmax(0,1fr)_auto] items-center gap-3 border-b border-border-muted px-5 py-3 last:border-b-0 mw-720:grid-cols-[64px_minmax(0,1fr)]"
              key={requirement.statement}
            >
              <span className="text-[9px] font-bold text-brand">
                {requirement.requirementType === "required" ? "필수" : "우대"}
              </span>
              <strong className="text-[11px] leading-[1.5] text-ink">
                {requirement.statement}
              </strong>
              <span className="text-[9px] text-muted mw-720:col-[2]">
                {related.filter((item) => item.status === "met").length}명 충족 ·{" "}
                {related.filter((item) => item.status === "partially_met").length}명 부분 충족
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function SettingValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-r border-border-muted p-4 last:border-r-0 mw-720:border-r-0 mw-720:border-b mw-720:border-border-muted">
      <span className="text-[10px] text-muted">{label}</span>
      <strong className="mt-1.5 block text-[12px] text-ink">{value}</strong>
    </div>
  );
}
