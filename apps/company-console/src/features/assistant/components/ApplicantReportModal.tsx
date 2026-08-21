import type { ReactNode } from "react";

import {
  displayApplicant,
  invitationProjection,
} from "../../company/recruitingState";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../../hiring/tech-stack-combobox/dialog";
import type { ApplicantReportPreview } from "../types";

export function ApplicantReportModal({
  preview,
  open,
  onOpenChange,
}: {
  preview: ApplicantReportPreview | undefined;
  open: boolean;
  onOpenChange(open: boolean): void;
}) {
  if (!preview) return null;
  const { invitation, insight, positionTitle } = preview;
  const applicantName = displayApplicant(invitation);
  const status = invitationProjection(invitation.status);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="grid max-h-[92vh] w-[min(880px,95vw)] max-w-none grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden rounded-xl border-[#d8d8d4] bg-white p-0">
        <DialogHeader className="sr-only">
          <DialogTitle>지원자 평가 요약서</DialogTitle>
          <DialogDescription>
            {applicantName} 지원자의 AI 평가 근거 요약 문서
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 overflow-y-auto bg-[#efefed] p-6 mw-620:p-2">
          <article className="mx-auto w-full max-w-[780px] border border-[#cfcfca] bg-white px-9 py-8 shadow-[0_2px_10px_rgb(0_0_0_/_7%)] mw-620:px-4 mw-620:py-6">
            <header className="border-b-2 border-ink pb-5 text-center">
              <p className="text-[9px] tracking-[0.22em] text-muted">
                AI 채용 평가 자료
              </p>
              <div className="mt-2 text-[22px] font-bold tracking-[0.14em] text-ink">
                지원자 평가 요약서
              </div>
              <p className="mt-2 text-[9px] text-muted">
                채용 담당자 검토용 · 검색 답변 인용 리포트
              </p>
            </header>

            <section className="mt-6">
              <DocumentSectionTitle number="1" title="지원자 기본정보" />
              <div className="overflow-x-auto">
                <table className="w-full min-w-[620px] border-collapse border-t border-l border-[#bdbdb8] text-[10px]">
                  <tbody>
                    <DocumentInfoRow
                      firstLabel="지원자명"
                      firstValue={applicantName}
                      secondLabel="지원 포지션"
                      secondValue={positionTitle}
                    />
                    <DocumentInfoRow
                      firstLabel="이메일"
                      firstValue={invitation.applicantEmail}
                      secondLabel="진행 상태"
                      secondValue={status.label}
                    />
                    <DocumentInfoRow
                      firstLabel="종합 점수"
                      firstValue={
                        insight.overallScore == null
                          ? "미산출"
                          : `${insight.overallScore}점`
                      }
                      secondLabel="근거 충족률"
                      secondValue={`${insight.evidenceCoverage}%`}
                    />
                    <DocumentInfoRow
                      firstLabel="평가 기준"
                      firstValue={`${insight.criteria.length}개`}
                      secondLabel="판단 보류"
                      secondValue={`${insight.unscoredCriteriaCount}개`}
                    />
                  </tbody>
                </table>
              </div>
            </section>

            <section className="mt-7">
              <DocumentSectionTitle number="2" title="AI 종합 평가 의견" />
              <table className="w-full border-collapse border-t border-l border-[#bdbdb8] text-[10px]">
                <tbody>
                  <tr>
                    <th className="w-28 border-r border-b border-[#bdbdb8] bg-[#f3f3f1] px-3 py-4 text-center font-semibold text-ink">
                      종합 의견
                    </th>
                    <td className="border-r border-b border-[#bdbdb8] px-4 py-4 text-[11px] leading-[1.8] text-ink-secondary">
                      {insight.summary}
                    </td>
                  </tr>
                  <tr>
                    <th className="border-r border-b border-[#bdbdb8] bg-[#f3f3f1] px-3 py-3 text-center font-semibold text-ink">
                      검토 기준
                    </th>
                    <td className="border-r border-b border-[#bdbdb8] px-4 py-3 leading-[1.7] text-muted">
                      답변 근거가 확인된 평가 기준만 점수에 반영하며, 근거가
                      부족한 항목은 판단 보류로 유지함.
                    </td>
                  </tr>
                </tbody>
              </table>
            </section>

            <section className="mt-7">
              <DocumentSectionTitle number="3" title="평가 항목별 결과" />
              <div className="overflow-x-auto">
                <table className="w-full min-w-[680px] border-collapse border-t border-l border-[#bdbdb8] text-[9px]">
                  <thead>
                    <tr className="bg-[#ececea] text-ink">
                      <DocumentHeadCell className="w-11">
                        번호
                      </DocumentHeadCell>
                      <DocumentHeadCell>평가 항목</DocumentHeadCell>
                      <DocumentHeadCell className="w-24">
                        판정
                      </DocumentHeadCell>
                      <DocumentHeadCell className="w-18">
                        점수
                      </DocumentHeadCell>
                      <DocumentHeadCell className="w-20">
                        근거 수
                      </DocumentHeadCell>
                      <DocumentHeadCell className="w-20">
                        가중치
                      </DocumentHeadCell>
                    </tr>
                  </thead>
                  <tbody>
                    {insight.criteria.map((criterion, index) => (
                      <tr key={criterion.criterionId}>
                        <DocumentCell className="text-center font-mono text-muted">
                          {String(index + 1).padStart(2, "0")}
                        </DocumentCell>
                        <DocumentCell className="font-semibold text-ink-secondary">
                          {criterion.criterionName}
                        </DocumentCell>
                        <DocumentCell className="text-center">
                          <span
                            className={`font-semibold ${assessmentDocumentTone(
                              criterion.assessmentState,
                            )}`}
                          >
                            {assessmentLabel(criterion.assessmentState)}
                          </span>
                        </DocumentCell>
                        <DocumentCell className="text-center font-mono font-bold text-ink">
                          {criterion.score ?? "–"}
                        </DocumentCell>
                        <DocumentCell className="text-center">
                          {criterion.evidenceCount}건
                        </DocumentCell>
                        <DocumentCell className="text-center">
                          {criterion.weight == null
                            ? "–"
                            : `${criterion.weight}%`}
                        </DocumentCell>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="bg-[#f7f7f5]">
                      <td
                        className="border-r border-b border-[#bdbdb8] px-3 py-3 text-right font-semibold text-ink"
                        colSpan={3}
                      >
                        종합 결과
                      </td>
                      <td className="border-r border-b border-[#bdbdb8] px-3 py-3 text-center font-mono text-[12px] font-bold text-brand">
                        {insight.overallScore ?? "–"}
                      </td>
                      <td
                        className="border-r border-b border-[#bdbdb8] px-3 py-3 text-center text-muted"
                        colSpan={2}
                      >
                        근거 충족 {insight.evidenceCoverage}%
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </section>

            <section className="mt-7">
              <DocumentSectionTitle number="4" title="검토 시 유의사항" />
              <div className="border border-[#bdbdb8] bg-[#fafaf9] px-4 py-4">
                <ul className="grid gap-2 text-[9px] leading-[1.7] text-ink-secondary">
                  <li>
                    1. 본 문서는 AI가 검색한 지원자 리포트의 요약 자료이며,
                    채용 여부를 단독으로 결정하지 않음.
                  </li>
                  <li>
                    2. 점수와 판정은 실제 답변 근거가 연결된 항목을 기준으로
                    확인해야 함.
                  </li>
                  <li>
                    3. 판단 보류 항목은 낮은 점수로 환산하지 않으며 담당자의
                    추가 검토가 필요함.
                  </li>
                </ul>
              </div>
            </section>

            <footer className="mt-8 grid grid-cols-[1fr_220px] border-t border-[#bdbdb8] pt-5 text-[9px] mw-620:grid-cols-1 mw-620:gap-5">
              <div className="text-muted">
                <p>문서 구분: AI 채용 평가 참고자료</p>
                <p className="mt-1">보안 등급: 사내 검토용</p>
              </div>
              <div className="grid grid-cols-[72px_1fr] border-t border-l border-[#bdbdb8]">
                <DocumentApprovalCell label="검토자" />
                <DocumentApprovalCell label="검토일" />
              </div>
            </footer>
          </article>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function DocumentSectionTitle({
  number,
  title,
}: {
  number: string;
  title: string;
}) {
  return (
    <h3 className="mb-2.5 flex items-center gap-2 text-[11px] font-bold text-ink">
      <span className="grid size-5 place-items-center bg-ink font-mono text-[8px] text-white">
        {number}
      </span>
      {title}
    </h3>
  );
}

function DocumentInfoRow({
  firstLabel,
  firstValue,
  secondLabel,
  secondValue,
}: {
  firstLabel: string;
  firstValue: string;
  secondLabel: string;
  secondValue: string;
}) {
  return (
    <tr>
      <th className="w-24 border-r border-b border-[#bdbdb8] bg-[#f3f3f1] px-3 py-3 text-center font-semibold text-ink">
        {firstLabel}
      </th>
      <td className="border-r border-b border-[#bdbdb8] px-3 py-3 text-ink-secondary">
        {firstValue}
      </td>
      <th className="w-24 border-r border-b border-[#bdbdb8] bg-[#f3f3f1] px-3 py-3 text-center font-semibold text-ink">
        {secondLabel}
      </th>
      <td className="border-r border-b border-[#bdbdb8] px-3 py-3 text-ink-secondary">
        {secondValue}
      </td>
    </tr>
  );
}

function DocumentHeadCell({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <th
      className={`border-r border-b border-[#bdbdb8] px-3 py-3 text-center font-semibold ${className}`}
    >
      {children}
    </th>
  );
}

function DocumentCell({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <td
      className={`border-r border-b border-[#bdbdb8] px-3 py-3 text-ink-secondary ${className}`}
    >
      {children}
    </td>
  );
}

function DocumentApprovalCell({ label }: { label: string }) {
  return (
    <>
      <span className="border-r border-b border-[#bdbdb8] bg-[#f3f3f1] px-2 py-3 text-center font-semibold">
        {label}
      </span>
      <span className="border-r border-b border-[#bdbdb8] px-2 py-3" />
    </>
  );
}

function assessmentDocumentTone(value: string) {
  if (value === "confirmed") return "text-success";
  if (value === "partially_confirmed") return "text-brand";
  if (value === "insufficient_evidence") return "text-warning";
  return "text-muted";
}

function assessmentLabel(value: string) {
  if (value === "confirmed") return "근거 확인";
  if (value === "partially_confirmed") return "일부 확인";
  if (value === "insufficient_evidence") return "근거 부족";
  return "판단 보류";
}
