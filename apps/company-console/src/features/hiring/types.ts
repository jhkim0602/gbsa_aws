export type RequirementType = "required" | "preferred";
export type CriterionImportance = "low" | "medium" | "high";

/** How deep the AI interviewer digs. Mirrors the InterviewLevel contract enum. */
export type InterviewLevel = "entry" | "junior" | "senior";
export type InterviewerTone = "calm" | "friendly" | "analytical" | "concise";
export type SubmissionMaterialId =
  "resume" | "cover_letter" | "career_description" | "projects" | "portfolio";

export type SubmissionRequirementDraft = {
  materialType: SubmissionMaterialId;
  label: string;
  description: string;
  required: boolean;
};

export const interviewLevelLabels: Record<
  InterviewLevel,
  { name: string; hint: string }
> = {
  entry: {
    name: "신입",
    hint: "학습 과정과 직접 해 본 시도를 확인하고, 한 기준당 꼬리질문은 최대 1회입니다.",
  },
  junior: {
    name: "주니어",
    hint: "본인이 수행한 작업과 판단 근거를 확인하고, 설정한 꼬리질문 횟수를 그대로 씁니다.",
  },
  senior: {
    name: "시니어",
    hint: "트레이드오프와 실패 대비를 확인하고, 꼬리질문을 1회 더 허용합니다.",
  },
};

/**
 * The five axes every answer is scored on. Mirrors `shared/assessment_axes.py`, which is where
 * the backend keeps them so Lane A can validate weights against the same set Lane D scores
 * with.
 *
 * These are *채점축* — how an engineering answer is read. They are fixed: a company cannot add
 * one, because each axis carries the guidance the scoring prompt is built from. What a company
 * varies is *평가기준*, of which there is no limit, and the weight each axis carries here.
 */
export const assessmentAxisKeys = [
  "correctness",
  "depth",
  "fundamentals",
  "ownership",
  "communication",
] as const;

export type AssessmentAxisKey = (typeof assessmentAxisKeys)[number];

export const assessmentAxisLabels: Record<AssessmentAxisKey, string> = {
  correctness: "정확성",
  depth: "깊이",
  fundamentals: "CS 기본기",
  ownership: "본인 기여",
  communication: "설명력",
};

/**
 * Weight per axis, all five always present and totalling 100.
 *
 * Same rule as the criterion weights, so one slider means one share on both screens. The API
 * accepts an omitted mapping as "equal weight" for versions published before weights existed,
 * but refuses a partial one — no reading of the absent keys is anything but a silently wrong
 * score. The wizard therefore always holds all five and always sends all five.
 */
export type AxisWeightDraft = Record<AssessmentAxisKey, number>;

export const defaultAxisWeights: AxisWeightDraft = {
  correctness: 20,
  depth: 20,
  fundamentals: 20,
  ownership: 20,
  communication: 20,
};

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
  importance?: CriterionImportance;
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
  interviewLevel: InterviewLevel;
  axisWeights: AxisWeightDraft;
  personaDefinition: {
    name: string;
    tone: InterviewerTone;
    voiceId: string;
  };
}>;

export type HiringWorkspaceApi = Readonly<{
  createPosition(input: {
    title: string;
    description: string;
    roleType?: string;
    headcount?: number;
    interviewCapacity?: number;
    interviewAt?: string;
    recruitmentStartAt?: string;
    recruitmentEndAt?: string;
    submissionRequirements: ReadonlyArray<{
      materialType: SubmissionMaterialId;
      required: boolean;
      enabled: boolean;
    }>;
  }): Promise<{ positionId: string }>;
  publishCriteria(
    positionId: string,
    input: CriteriaConfiguration,
  ): Promise<{ versionId: string }>;
}>;

export type PositionHiringStep = "position" | "application";

export type CriteriaHiringStep = "evaluation" | "interview";

export type HiringStep = PositionHiringStep | CriteriaHiringStep | "complete";

export type HiringDraft = {
  title: string;
  description: string;
  descriptionCompleted: boolean;
  roleType: string;
  techStack: string[];
  headcount: number;
  interviewCapacity: number;
  interviewAt: string;
  recruitmentStartAt: string;
  recruitmentEndAt: string;
  submissionRequirements: SubmissionRequirementDraft[];
  jobRequirements: JobRequirementDraft[];
  criteria: CriterionDraft[];
  prohibitedTopics: string;
  interviewDurationMinutes: number;
  interviewLevel: InterviewLevel;
  axisWeights: AxisWeightDraft;
  interviewerName: string;
  interviewerTone: InterviewerTone;
  interviewerVoiceId: string;
};

export type HiringDraftUpdater = <K extends keyof HiringDraft>(
  key: K,
  value: HiringDraft[K],
) => void;

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
    weight: index === 1 ? 100 : 20,
    importance: "medium",
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
  descriptionCompleted: false,
  roleType: "개발",
  techStack: [],
  headcount: 1,
  interviewCapacity: 1,
  interviewAt: "",
  recruitmentStartAt: "",
  recruitmentEndAt: "",
  submissionRequirements: [
    {
      materialType: "resume",
      label: "이력서",
      description: "경력과 주요 역량",
      required: true,
    },
    {
      materialType: "cover_letter",
      label: "자기소개서",
      description: "지원 동기와 직무 적합성",
      required: true,
    },
    {
      materialType: "career_description",
      label: "경력기술서",
      description: "프로젝트별 역할과 성과",
      required: false,
    },
    {
      materialType: "projects",
      label: "대표 프로젝트",
      description: "공개 Git 저장소",
      required: false,
    },
    {
      materialType: "portfolio",
      label: "포트폴리오",
      description: "주요 결과물과 작업 과정",
      required: false,
    },
  ],
  jobRequirements: [createRequirementDraft(1)],
  criteria: [createCriterionDraft(1)],
  prohibitedTopics: "가족관계, 출신지역, 혼인·임신 여부, 외모",
  interviewDurationMinutes: 30,
  interviewLevel: "junior",
  axisWeights: { ...defaultAxisWeights },
  interviewerName: "실무형 면접관",
  interviewerTone: "analytical",
  interviewerVoiceId: "Seoyeon",
};
