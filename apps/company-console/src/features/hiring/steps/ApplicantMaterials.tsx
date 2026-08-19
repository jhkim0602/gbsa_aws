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

export function ApplicantMaterials({
  draft,
  update,
}: {
  draft: HiringDraft;
  update: HiringDraftUpdater;
}) {
  return (
    <div className="applicant-materials">
      <fieldset>
        <legend className="sr-only">필수 제출 자료</legend>
        <div className="material-list">
          {draft.submissionRequirements.map((requirement) => {
            const metadata = materialMetadata[requirement.materialType];
            const Icon = metadata.icon;
            return (
              <label
                className={`material-row ${
                  requirement.required ? "is-selected" : ""
                }`}
                key={requirement.materialType}
              >
                <input
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
                <span className="material-row__icon">
                  <Icon aria-hidden="true" size={19} />
                </span>
                <span className="material-row__identity">
                  <strong>{requirement.label}</strong>
                  <small>{requirement.description}</small>
                </span>
                <span className="material-row__ai">
                  <small>AI 처리</small>
                  <span>{metadata.aiUse}</span>
                </span>
                <span className="material-row__output">{metadata.output}</span>
                <span className="material-row__check" aria-hidden="true">
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
