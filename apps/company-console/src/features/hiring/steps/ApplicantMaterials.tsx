import {
  BriefcaseBusiness,
  Check,
  FileText,
  FolderKanban,
  GitBranch,
  ScrollText,
} from "lucide-react";

import { HiringAiFlow } from "../components/HiringAiFlow";
import type {
  HiringDraft,
  HiringDraftUpdater,
  SubmissionMaterialId,
} from "../types";

const materialMetadata: Record<
  SubmissionMaterialId,
  {
    icon: typeof FileText;
    aiUse: string;
    output: string;
  }
> = {
  resume: {
    icon: FileText,
    aiUse: "경력·기술·기간을 구조화합니다.",
    output: "경력 타임라인",
  },
  cover_letter: {
    icon: ScrollText,
    aiUse: "지원 동기와 역할 적합성의 근거를 추출합니다.",
    output: "동기·적합성 신호",
  },
  career_description: {
    icon: BriefcaseBusiness,
    aiUse: "프로젝트별 역할, 행동, 성과를 분리합니다.",
    output: "성과 근거",
  },
  projects: {
    icon: GitBranch,
    aiUse: "기술 선택과 구현 기여도를 검증할 단서를 찾습니다.",
    output: "기술 검증 포인트",
  },
  portfolio: {
    icon: FolderKanban,
    aiUse: "결과물과 문제 해결 과정을 평가 기준에 연결합니다.",
    output: "작업 근거",
  },
};

// `.material-row.is-selected` is declared after `.material-row:hover` at equal specificity,
// so a selected row keeps its brand tint on hover. A `hover:` utility would outrank the plain
// one, so the hover background is only emitted when the row is not selected.
const ROW =
  "grid min-h-[78px] cursor-pointer items-center gap-3 border-b px-3 py-2.5" +
  " grid-cols-[24px_44px_minmax(130px,0.8fr)_minmax(240px,1.6fr)_auto_24px]" +
  " transition-[background,border-color] duration-[140ms]" +
  " mw-780:grid-cols-[22px_40px_minmax(0,1fr)_24px]" +
  " mw-620:grid-cols-[22px_36px_minmax(0,1fr)_22px] mw-620:px-1";

const ROW_ICON =
  "grid size-10 place-items-center rounded-md border bg-white";
const ROW_CHECK = "grid size-5 place-items-center rounded-[50%] border";

// `.material-row__ai` shares `.material-row__identity`'s box (both are in the same rule) and
// moves to columns 3–5 below 780px, alongside `__output`, which then hides at 620px.
const ROW_SPAN =
  "grid min-w-0 gap-[3px] mw-780:col-[3/5] mw-620:col-[3/5]";

export function ApplicantMaterials({
  draft,
  update,
}: {
  draft: HiringDraft;
  update: HiringDraftUpdater;
}) {
  return (
    <div className="grid gap-11 mw-620:gap-8">
      <fieldset>
        <legend className="sr-only">필수 제출 자료</legend>
        <div className="border-t border-border">
          {draft.submissionRequirements.map((requirement) => {
            const metadata = materialMetadata[requirement.materialType];
            const Icon = metadata.icon;
            return (
              <label
                className={`${ROW} ${
                  requirement.required
                    ? "border-b-[#5966ce4d] bg-[#5966ce0a]"
                    : "border-b-border-muted hover:bg-surface-muted"
                }`}
                key={requirement.materialType}
              >
                <input
                  className="size-[17px] accent-brand"
                  type="checkbox"
                  checked={requirement.required}
                  onChange={(event) =>
                    update(
                      "submissionRequirements",
                      draft.submissionRequirements.map((item) =>
                        item.materialType === requirement.materialType
                          ? { ...item, required: event.target.checked }
                          : item,
                      ),
                    )
                  }
                />
                <span
                  className={`${ROW_ICON} ${
                    requirement.required
                      ? "border-[#5966ce40] text-brand"
                      : "border-border text-ink-secondary"
                  }`}
                >
                  <Icon aria-hidden="true" size={19} />
                </span>
                <span className="grid min-w-0 gap-[3px]">
                  <strong className="text-[13px] text-ink">
                    {requirement.label}
                  </strong>
                  <small className="text-[10px] text-muted">
                    {requirement.description}
                  </small>
                </span>
                <span className={ROW_SPAN}>
                  <small className="text-[10px] text-muted">AI 처리</small>
                  <span className="text-[11px] leading-[1.45] text-ink-secondary">
                    {metadata.aiUse}
                  </span>
                </span>
                <span className="rounded-[3px] border border-border bg-white px-[7px] py-1 text-[9px] whitespace-nowrap text-muted mw-780:col-[3/5] mw-620:hidden">
                  {metadata.output}
                </span>
                <span
                  className={`${ROW_CHECK} ${
                    requirement.required
                      ? "border-brand bg-brand text-white"
                      : "border-border text-transparent"
                  }`}
                  aria-hidden="true"
                >
                  <Check size={13} />
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <HiringAiFlow
        title="지원 자료가 면접 데이터로 변환되는 방식"
        description="선택한 자료만 파싱하며, 원문과 추출 근거를 함께 보존해 질문과 리포트의 출처를 추적합니다."
        stages={["자료 구조화", "근거·공백 탐지", "개인화 질문·리포트"]}
      />
    </div>
  );
}
