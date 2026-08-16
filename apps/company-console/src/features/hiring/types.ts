export type RequirementType = "required" | "preferred";

export type JobRequirementDraft = {
  id: string;
  requirementType: RequirementType;
  statement: string;
  priority: number;
  criterionCode: string;
};

export type CriterionDraft = {
  id: string;
  code: string;
  name: string;
  description: string;
  weight: number;
  required: boolean;
  observableDimensions: string;
  strongAnswerSignals: string;
  weakAnswerSignals: string;
  followUpDirections: string;
  maxFollowUps: number;
  timeBudgetSeconds: number;
  abstainGuidance: string;
  commonQuestions: string;
};

export type CriteriaConfiguration = Readonly<{
  jobRequirements: ReadonlyArray<{
    requirementType: RequirementType;
    statement: string;
    priority: number;
    criterionCode: string;
  }>;
  criteria: ReadonlyArray<{
    code: string;
    name: string;
    description: string;
    weight: number;
    required: boolean;
    verificationGuide: {
      observableDimensions: string[];
      strongAnswerSignals: string[];
      weakAnswerSignals: string[];
      followUpDirections: string[];
      maxFollowUps: number;
      timeBudgetSeconds: number;
    };
    abstainGuidance: string;
    commonQuestions: string[];
  }>;
  prohibitedTopics: string[];
  interviewDurationMinutes: number;
}>;

export type HiringWorkspaceApi = Readonly<{
  createPosition(input: {
    title: string;
    description: string;
    roleType?: string;
    headcount?: number;
    recruitmentStartAt?: string;
    recruitmentEndAt?: string;
  }): Promise<{ positionId: string }>;
  publishCriteria(
    positionId: string,
    input: CriteriaConfiguration,
  ): Promise<{ versionId: string }>;
}>;

export type HiringStep = "position" | "criteria" | "complete";

export type HiringDraft = {
  title: string;
  description: string;
  roleType: string;
  headcount: number;
  recruitmentStartAt: string;
  recruitmentEndAt: string;
  jobRequirements: JobRequirementDraft[];
  criteria: CriterionDraft[];
  prohibitedTopics: string;
  interviewDurationMinutes: number;
};

export type HiringResourceIds = {
  positionId: string;
  versionId: string;
};

export function createCriterionDraft(index: number): CriterionDraft {
  return {
    id: `criterion-${Date.now()}-${index}`,
    code: `CRITERION_${index}`,
    name: "",
    description: "",
    weight: 20,
    required: index === 1,
    observableDimensions: "상황\n본인이 직접 수행한 행동\n판단 근거\n결과",
    strongAnswerSignals: "구체적인 상황, 본인 역할, 행동과 결과가 포함됨",
    weakAnswerSignals: "팀 활동이나 기술 이름만 있고 본인 행동이 불명확함",
    followUpDirections: "본인이 직접 수행한 행동\n판단 근거\n측정 가능한 결과",
    maxFollowUps: 2,
    timeBudgetSeconds: 300,
    abstainGuidance: "최종 답변 근거가 부족하면 판단을 유보합니다.",
    commonQuestions: "이 역량을 보여준 실제 경험을 설명해 주세요.",
  };
}

export function createRequirementDraft(index: number): JobRequirementDraft {
  return {
    id: `requirement-${Date.now()}-${index}`,
    requirementType: index === 1 ? "required" : "preferred",
    statement: "",
    priority: index,
    criterionCode: `CRITERION_${index}`,
  };
}

export const initialHiringDraft: HiringDraft = {
  title: "",
  description: "",
  roleType: "개발",
  headcount: 1,
  recruitmentStartAt: "",
  recruitmentEndAt: "",
  jobRequirements: [createRequirementDraft(1)],
  criteria: [createCriterionDraft(1)],
  prohibitedTopics: "가족관계, 출신지역, 혼인·임신 여부, 외모",
  interviewDurationMinutes: 30,
};
