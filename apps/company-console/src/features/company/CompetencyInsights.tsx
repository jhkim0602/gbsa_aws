import { BarChart3, CircleAlert, Sparkles } from "lucide-react";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";

import { interviewReviewPath } from "../../app/applicantWorkspacePath";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  CompanyApplicantInsight,
  CompanyCriterionVersion,
  CompanyInvitation,
} from "./types";

type CompetencySummary = Readonly<{
  criterionId: string;
  criterionName: string;
  average: number;
  minimum: number;
  maximum: number;
  scores: readonly number[];
}>;

type CompetencyChartRow = {
  criterionId: string;
  criterionName: string;
  average: number;
  minimum: number;
  maximum: number;
  respondents: number;
  candidates: Array<{ invitationId: string; name: string; score: number }>;
};

/** Applies the exact criterion version pinned to each invitation to its score. */
export function applyConfiguredWeights(
  insights: readonly CompanyApplicantInsight[],
  versions: readonly CompanyCriterionVersion[],
): readonly CompanyApplicantInsight[] {
  return insights.map((insight) => {
    const version = versions.find(
      (candidate) => candidate.versionId === insight.competencyModelVersionId,
    );
    if (!version) return insight;
    const weightedCriteria = insight.criteria.map((criterion) => {
      const configured = version.criteria.find(
        (candidate) =>
          candidate.code === criterion.criterionId ||
          candidate.name === criterion.criterionName,
      );
      return { ...criterion, weight: configured?.weight };
    });
    const scored = weightedCriteria.filter(
      (criterion) => criterion.score != null && criterion.weight != null,
    );
    const scoredWeight = scored.reduce(
      (sum, criterion) => sum + (criterion.weight ?? 0),
      0,
    );
    const weightedScore = scoredWeight
      ? Math.round(
          scored.reduce(
            (sum, criterion) =>
              sum + (criterion.score ?? 0) * (criterion.weight ?? 0),
            0,
          ) / scoredWeight,
        )
      : insight.overallScore;
    return {
      ...insight,
      overallScore: weightedScore,
      criteria: weightedCriteria,
    };
  });
}

export function buildCompetencySummaries(
  insights: readonly CompanyApplicantInsight[],
): readonly CompetencySummary[] {
  const grouped = new Map<
    string,
    { criterionId: string; criterionName: string; scores: number[] }
  >();
  insights.forEach((insight) => {
    insight.criteria.forEach((criterion) => {
      if (criterion.score == null) return;
      const current = grouped.get(criterion.criterionId) ?? {
        criterionId: criterion.criterionId,
        criterionName: criterion.criterionName,
        scores: [],
      };
      current.scores.push(criterion.score);
      grouped.set(criterion.criterionId, current);
    });
  });
  return [...grouped.values()].map((criterion) => ({
    ...criterion,
    average: Math.round(
      criterion.scores.reduce((sum, score) => sum + score, 0) /
        criterion.scores.length,
    ),
    minimum: Math.min(...criterion.scores),
    maximum: Math.max(...criterion.scores),
  }));
}

export function CompetencyDistribution({
  insights,
  invitations = [],
  limit = 6,
  title = "평가 기준별 점수 분포",
  description = "기준별 평균을 요약하고, 막대에 마우스를 올리면 상위 지원자를 확인합니다.",
}: {
  insights: readonly CompanyApplicantInsight[];
  invitations?: readonly CompanyInvitation[];
  limit?: number;
  title?: string;
  description?: string;
}) {
  const invitationById = useMemo(
    () => new Map(invitations.map((item) => [item.invitationId, item])),
    [invitations],
  );
  const chartRows = useMemo<CompetencyChartRow[]>(() => {
    const rows = new Map<
      string,
      {
        criterionId: string;
        criterionName: string;
        candidates: Array<{
          invitationId: string;
          name: string;
          score: number;
        }>;
      }
    >();
    insights.forEach((insight) => {
      const invitation = invitationById.get(insight.invitationId);
      const name =
        invitation?.applicantDisplayName ??
        invitation?.applicantEmail.split("@")[0] ??
        "이름 미확인";
      insight.criteria.forEach((criterion) => {
        if (criterion.score == null) return;
        const current = rows.get(criterion.criterionId) ?? {
          criterionId: criterion.criterionId,
          criterionName: criterion.criterionName,
          candidates: [],
        };
        current.candidates.push({
          invitationId: insight.invitationId,
          name,
          score: criterion.score,
        });
        rows.set(criterion.criterionId, current);
      });
    });
    return [...rows.values()].map((row) => {
      const candidates = row.candidates
        .slice()
        .sort((left, right) => right.score - left.score);
      const values = candidates.map((candidate) => candidate.score);
      return {
        ...row,
        candidates,
        average: Math.round(
          values.reduce((sum, value) => sum + value, 0) / values.length,
        ),
        minimum: Math.min(...values),
        maximum: Math.max(...values),
        respondents: values.length,
      };
    });
  }, [insights, invitationById]);
  const visibleRows = chartRows.slice(0, limit);
  const hiddenCriterionCount = Math.max(
    0,
    chartRows.length - visibleRows.length,
  );
  const chartHeight = Math.max(210, visibleRows.length * 62 + 52);

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-surface">
      <header className="flex min-h-18 items-center justify-between gap-4 border-b border-border-muted px-5 py-4 mw-720:items-start">
        <div>
          <p className="text-[9px] font-bold tracking-[0.08em] text-brand uppercase">
            COMPETENCY ANALYTICS
          </p>
          <h2 className="mt-1 text-[15px] text-ink">{title}</h2>
          <p className="mt-1 text-[11px] leading-[1.5] text-muted">
            {description}
          </p>
        </div>
        <span className="rounded-full bg-brand-soft px-3 py-1.5 text-[10px] font-bold text-brand">
          지원자 {insights.length}명
        </span>
      </header>

      {visibleRows.length ? (
        <div className="p-5">
          <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border-muted pb-3 text-[9px] text-muted">
            <span>
              <b className="font-mono text-ink">{chartRows.length}</b>개 평가
              기준
            </span>
            <span>
              <b className="font-mono text-ink">{insights.length}</b>명 집계
            </span>
            <span>막대 선택 시 상위 5명 표시</span>
          </div>
          <div>
            <div
              className="w-full"
              style={{ height: chartHeight }}
              role="img"
              aria-label="평가 기준별 지원자 평균 점수 막대 차트"
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={visibleRows}
                  layout="vertical"
                  margin={{ top: 6, right: 34, bottom: 20, left: 0 }}
                  barCategoryGap="36%"
                >
                  <CartesianGrid stroke="#edf0f5" horizontal={false} />
                  <XAxis
                    type="number"
                    domain={[0, 100]}
                    ticks={[0, 50, 100]}
                    tick={{ fill: "#8b93a7", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="criterionName"
                    width={160}
                    tick={<CompetencyTick />}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    cursor={{ fill: "#f7f8fb" }}
                    content={<CompetencyTooltip />}
                  />
                  <Bar
                    dataKey="average"
                    name="평균 점수"
                    fill="#5966ce"
                    background={{ fill: "#f1f3f8", radius: 5 }}
                    radius={[0, 5, 5, 0]}
                    maxBarSize={18}
                  >
                    <LabelList
                      dataKey="average"
                      position="right"
                      fill="#343b50"
                      fontSize={10}
                      fontWeight={700}
                      formatter={(value) => String(value ?? "")}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[9px] leading-[1.5] text-muted">
            <p>
              100점 기준 · 차트는 기준별 평균이며 총점에는 게시된 가중치가
              적용됩니다.
            </p>
            {hiddenCriterionCount ? (
              <strong className="text-brand">
                외 {hiddenCriterionCount}개 평가 기준
              </strong>
            ) : null}
          </div>
        </div>
      ) : (
        <EmptyInsight />
      )}
    </section>
  );
}

export function ScoreDistribution({
  insights,
}: {
  insights: readonly CompanyApplicantInsight[];
}) {
  const scored = insights.flatMap((insight) =>
    insight.overallScore == null ? [] : [insight.overallScore],
  );
  const bands = [
    { label: "추가 검증", range: "0–54", count: countRange(scored, 0, 54) },
    { label: "보통", range: "55–69", count: countRange(scored, 55, 69) },
    { label: "강함", range: "70–84", count: countRange(scored, 70, 84) },
    { label: "매우 강함", range: "85–100", count: countRange(scored, 85, 100) },
  ];

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-surface">
      <header className="border-b border-border-muted px-5 py-4">
        <h2 className="text-[15px] text-ink">총점 분포</h2>
        <p className="mt-1 text-[11px] text-muted">
          합격 여부가 아닌, 면접에서 확인된 역량 신호의 구간별 분포입니다.
        </p>
      </header>
      {scored.length ? (
        <div className="h-[240px] p-5">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={bands}
              margin={{ top: 10, right: 10, bottom: 8, left: -18 }}
            >
              <CartesianGrid stroke="#edf0f5" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: "#6f778c", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fill: "#8b93a7", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={<ScoreTooltip />}
                cursor={{ fill: "#f7f8fb" }}
              />
              <Bar
                dataKey="count"
                name="지원자"
                fill="#5966ce"
                radius={[5, 5, 0, 0]}
                maxBarSize={56}
              >
                <LabelList
                  dataKey="count"
                  position="top"
                  fill="#343b50"
                  fontSize={11}
                  fontWeight={700}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <EmptyInsight compact />
      )}
    </section>
  );
}

export function ApplicantScoreTable({
  invitations,
  insights,
  limit,
}: {
  invitations: readonly CompanyInvitation[];
  insights: readonly CompanyApplicantInsight[];
  limit?: number;
}) {
  const navigate = useNavigate();
  const invitationById = new Map(
    invitations.map((invitation) => [invitation.invitationId, invitation]),
  );
  const ranked = [...insights]
    .sort(
      (left, right) => (right.overallScore ?? -1) - (left.overallScore ?? -1),
    )
    .slice(0, limit);

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-surface">
      <header className="flex items-center justify-between gap-3 border-b border-border-muted px-5 py-4">
        <div>
          <h2 className="text-[15px] text-ink">지원자 역량 비교</h2>
          <p className="mt-1 text-[11px] text-muted">
            총점, 가장 강한 역량, 답변 근거 충족도를 한 행에서 비교합니다.
          </p>
        </div>
        <BarChart3 className="text-brand" size={20} aria-hidden="true" />
      </header>
      {ranked.length ? (
        <>
          <div className="overflow-x-auto mw-720:hidden">
            <table className="w-full min-w-[760px] border-collapse text-left">
              <thead className="bg-surface-muted text-[9px] font-semibold text-muted">
                <tr>
                  <th className="w-14 px-5 py-3 font-semibold">순위</th>
                  <th className="px-3 py-3 font-semibold">지원자</th>
                  <th className="w-28 px-3 py-3 text-center font-semibold">
                    총점
                  </th>
                  <th className="px-3 py-3 font-semibold">가장 강한 역량</th>
                  <th className="w-44 px-3 py-3 font-semibold">답변 근거</th>
                </tr>
              </thead>
              <tbody>
                {ranked.map((insight, index) => {
                  const invitation = invitationById.get(insight.invitationId);
                  const displayName =
                    invitation?.applicantDisplayName ??
                    invitation?.applicantEmail.split("@")[0] ??
                    "지원자";
                  const strongest = [...insight.criteria]
                    .filter((criterion) => criterion.score != null)
                    .sort(
                      (left, right) => (right.score ?? 0) - (left.score ?? 0),
                    )[0];
                  return (
                    <tr
                      className="cursor-pointer border-t border-border-muted hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-brand"
                      key={insight.invitationId}
                      tabIndex={0}
                      aria-label={`${displayName} 리포트 열기`}
                      onClick={() =>
                        navigate(
                          interviewReviewPath(
                            insight.interviewSessionId,
                            insight.invitationId,
                          ),
                        )
                      }
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          navigate(
                            interviewReviewPath(
                              insight.interviewSessionId,
                              insight.invitationId,
                            ),
                          );
                        }
                      }}
                    >
                      <td className="px-5 py-4 font-mono text-[10px] text-subtle">
                        {String(index + 1).padStart(2, "0")}
                      </td>
                      <td className="px-3 py-4">
                        <span className="grid grid-cols-[34px_minmax(0,1fr)] items-center gap-2.5">
                          <span className="grid size-[34px] place-items-center rounded-lg bg-brand-soft text-[11px] font-bold text-brand">
                            {displayName.slice(0, 1)}
                          </span>
                          <span className="min-w-0">
                            <strong className="block text-[12px] text-ink">
                              {displayName}
                            </strong>
                            <small className="mt-0.5 block text-[9px] text-muted">
                              {invitation?.applicantEmail}
                            </small>
                          </span>
                        </span>
                      </td>
                      <td className="px-3 py-4 text-center">
                        <strong className="inline-flex min-w-12 justify-center rounded-md bg-brand-soft px-2.5 py-1.5 font-mono text-[15px] text-brand">
                          {insight.overallScore ?? "–"}
                        </strong>
                      </td>
                      <td className="px-3 py-4">
                        {strongest ? (
                          <span className="block max-w-[360px] text-[10px] leading-[1.5] text-ink-secondary">
                            {strongest.criterionName}
                            <b className="ml-2 font-mono text-ink">
                              {strongest.score}
                            </b>
                          </span>
                        ) : (
                          <span className="text-[10px] text-muted">
                            평가 근거 확인
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-4">
                        <div className="flex items-center gap-2.5">
                          <span className="h-1.5 min-w-20 flex-1 overflow-hidden rounded-full bg-surface-strong">
                            <i
                              className="block h-full rounded-full bg-success"
                              style={{ width: `${insight.evidenceCoverage}%` }}
                            />
                          </span>
                          <strong className="w-9 text-right font-mono text-[10px] text-ink-secondary">
                            {insight.evidenceCoverage}%
                          </strong>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="hidden divide-y divide-border-muted mw-720:grid">
            {ranked.map((insight, index) => {
              const invitation = invitationById.get(insight.invitationId);
              const displayName =
                invitation?.applicantDisplayName ??
                invitation?.applicantEmail.split("@")[0] ??
                "지원자";
              const strongest = [...insight.criteria]
                .filter((criterion) => criterion.score != null)
                .sort(
                  (left, right) => (right.score ?? 0) - (left.score ?? 0),
                )[0];
              return (
                <Link
                  className="grid gap-3 p-4 hover:bg-surface-muted"
                  key={insight.invitationId}
                  to={interviewReviewPath(
                    insight.interviewSessionId,
                    insight.invitationId,
                  )}
                  aria-label={`${displayName} 리포트 열기`}
                >
                  <span className="flex items-center gap-3">
                    <small className="w-5 font-mono text-[9px] text-subtle">
                      {String(index + 1).padStart(2, "0")}
                    </small>
                    <span className="grid size-9 place-items-center rounded-lg bg-brand-soft text-[11px] font-bold text-brand">
                      {displayName.slice(0, 1)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <strong className="block text-[12px] text-ink">
                        {displayName}
                      </strong>
                      <small className="block truncate text-[9px] text-muted">
                        {invitation?.applicantEmail}
                      </small>
                    </span>
                    <strong className="rounded-md bg-brand-soft px-2.5 py-1.5 font-mono text-[15px] text-brand">
                      {insight.overallScore ?? "–"}
                    </strong>
                  </span>
                  <span className="grid grid-cols-[minmax(0,1fr)_88px] items-end gap-4 pl-8">
                    <span className="min-w-0">
                      <small className="block text-[9px] text-muted">
                        가장 강한 역량
                      </small>
                      <span className="mt-1 block text-[10px] leading-[1.45] text-ink-secondary">
                        {strongest?.criterionName ?? "평가 근거 확인"}
                        {strongest ? (
                          <b className="ml-1.5 font-mono text-ink">
                            {strongest.score}
                          </b>
                        ) : null}
                      </span>
                    </span>
                    <span>
                      <small className="block text-right text-[9px] text-muted">
                        근거 {insight.evidenceCoverage}%
                      </small>
                      <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-surface-strong">
                        <i
                          className="block h-full rounded-full bg-success"
                          style={{ width: `${insight.evidenceCoverage}%` }}
                        />
                      </span>
                    </span>
                  </span>
                </Link>
              );
            })}
          </div>
        </>
      ) : (
        <EmptyInsight compact />
      )}
    </section>
  );
}

export function ApplicantCapabilityBars({
  insight,
}: {
  insight: CompanyApplicantInsight;
}) {
  return (
    <div className="grid gap-4">
      {insight.criteria.map((criterion) => (
        <div className="grid gap-2" key={criterion.criterionId}>
          <div className="flex items-center justify-between gap-3">
            <strong className="text-[12px] text-ink">
              {criterion.criterionName}
              {criterion.weight != null ? (
                <small className="ml-2 font-normal text-muted">
                  가중치 {criterion.weight}%
                </small>
              ) : null}
            </strong>
            <span className="font-mono text-[13px] font-bold text-ink">
              {criterion.score ?? "평가 보류"}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-surface-strong">
            <span
              className="block h-full rounded-full bg-brand"
              style={{ width: `${criterion.score ?? 0}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function CompetencyTick({
  x = 0,
  y = 0,
  payload,
}: {
  x?: number;
  y?: number;
  payload?: { value?: string };
}) {
  const value = payload?.value ?? "";
  const [first, second] = wrapLabel(value, 18);
  return (
    <g transform={`translate(${x},${y})`}>
      <text
        x={-10}
        y={second ? -6 : 3}
        textAnchor="end"
        fill="#343b50"
        fontSize={10}
        fontWeight={650}
      >
        {first}
      </text>
      {second ? (
        <text
          x={-10}
          y={8}
          textAnchor="end"
          fill="#343b50"
          fontSize={10}
          fontWeight={650}
        >
          {second}
        </text>
      ) : null}
    </g>
  );
}

function CompetencyTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload?: CompetencyChartRow }>;
}) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  const topCandidates = row.candidates.slice(0, 5);
  const remaining = row.candidates.length - topCandidates.length;
  return (
    <div className="w-64 rounded-lg border border-border bg-surface p-3 shadow-float">
      <strong className="block text-[10px] leading-[1.45] text-ink">
        {row.criterionName}
      </strong>
      <p className="mt-1 text-[9px] text-muted">
        평균 <b className="font-mono text-ink">{row.average}</b> · 최저{" "}
        {row.minimum} · 최고 {row.maximum}
      </p>
      <div className="mt-3 grid gap-1.5 border-t border-border-muted pt-2.5">
        <small className="text-[8px] font-semibold text-muted">
          상위 지원자
        </small>
        {topCandidates.map((candidate, index) => (
          <span
            className="flex items-center justify-between gap-5 text-[10px]"
            key={candidate.invitationId}
          >
            <span className="min-w-0 truncate text-ink-secondary">
              <i className="mr-1.5 font-mono text-[8px] text-subtle">
                {index + 1}
              </i>
              {candidate.name}
            </span>
            <b className="font-mono text-ink">{candidate.score}점</b>
          </span>
        ))}
        {remaining > 0 ? (
          <span className="pt-0.5 text-[9px] font-semibold text-brand">
            ··· 외 {remaining}명
          </span>
        ) : null}
      </div>
    </div>
  );
}

function ScoreTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value?: number; payload?: { range?: string } }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2 shadow-float">
      <strong className="text-[10px] text-ink">{label}</strong>
      <p className="mt-1 text-[9px] text-muted">
        {payload[0].payload?.range}점 · {payload[0].value}명
      </p>
    </div>
  );
}

function EmptyInsight({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className={`grid place-items-center gap-2 px-5 text-center text-muted ${compact ? "min-h-28" : "min-h-44"}`}
    >
      <span className="grid size-9 place-items-center rounded-full bg-surface-strong text-brand">
        {compact ? <CircleAlert size={17} /> : <Sparkles size={18} />}
      </span>
      <div>
        <strong className="block text-[12px] text-ink-secondary">
          아직 집계할 면접 결과가 없습니다.
        </strong>
        <p className="mt-1 text-[10px]">
          면접 리포트가 생성되면 역량 분포가 자동으로 표시됩니다.
        </p>
      </div>
    </div>
  );
}

function wrapLabel(value: string, width: number) {
  if (value.length <= width) return [value, ""] as const;
  const split = value.lastIndexOf(" ", width);
  const pivot = split > 8 ? split : width;
  return [
    value.slice(0, pivot),
    `${value.slice(pivot).trim().slice(0, width)}${value.length - pivot > width ? "…" : ""}`,
  ] as const;
}

function countRange(
  scores: readonly number[],
  minimum: number,
  maximum: number,
) {
  return scores.filter((score) => score >= minimum && score <= maximum).length;
}
