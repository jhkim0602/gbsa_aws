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
                완료된 면접의 총점과 답변 근거를 기준으로 비교합니다.
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

      <CompetencyDistribution
        insights={insights}
        invitations={invitations}
        limit={4}
        title="평가 기준별 평균"
        description="인사이트에서는 핵심 기준만 요약합니다. 막대에 마우스를 올리면 상위 5명을 확인할 수 있습니다."
      />

      <ApplicantScoreTable
        invitations={invitations}
        insights={insights}
        limit={5}
      />

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
              value={`${criteria.interviewDurationMinutes}분`}
            />
            <SettingValue
              label="면접관"
              value={
                criteria.personaDefinition?.name ??
                interviewLevelLabels[criteria.interviewLevel].name
              }
            />
            <SettingValue
              label="평가 기준"
              value={`${criteria.criteria.length}개 · 합계 100`}
            />
            <div className="grid gap-2 p-4 mw-1050:col-[1/-1] mw-1050:border-t mw-1050:border-border-muted">
              <span className="text-[10px] text-muted">
                채용 관리에서 설정한 평가 가중치
              </span>
              <div className="flex h-2 overflow-hidden rounded-full bg-surface-strong">
                {criteria.criteria.map((criterion, index) => (
                  <i
                    className={index % 2 ? "bg-[#8b97e8]" : "bg-brand"}
                    key={criterion.code}
                    style={{ width: `${criterion.weight}%` }}
                    title={`${criterion.name} ${criterion.weight}`}
                  />
                ))}
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                {criteria.criteria.map((criterion) => (
                  <span className="text-[9px] text-muted" key={criterion.code}>
                    {criterion.required ? "필수" : "우대"} · {criterion.name}{" "}
                    <b className="text-ink">{criterion.weight}</b>
                  </span>
                ))}
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

function SettingValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-r border-border-muted p-4 last:border-r-0 mw-720:border-r-0 mw-720:border-b mw-720:border-border-muted">
      <span className="text-[10px] text-muted">{label}</span>
      <strong className="mt-1.5 block text-[12px] text-ink">{value}</strong>
    </div>
  );
}
