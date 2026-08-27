export type RequirementType = "required" | "preferred";

export const evaluationCriterionCodes = {
  technical: "TECHNICAL_COMPETENCY",
  project: "PROJECT_EXECUTION",
  behavioral: "COLLABORATION_BEHAVIOR",
} as const;

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
    hint: "기초 이해와 학습 과정, 직접 해 본 시도를 중심으로 확인합니다.",
  },
  junior: {
    name: "주니어",
    hint: "본인이 수행한 작업과 문제 해결 과정, 판단 근거를 중심으로 확인합니다.",
  },
  senior: {
    name: "시니어",
    hint: "설계 트레이드오프와 복잡한 의사결정, 실패 대비를 중심으로 확인합니다.",
  },
};

export function interviewerVoiceLabel(voiceId?: string) {
  if (!voiceId || voiceId === "Seoyeon") return "한국어 남성 음성";
  return voiceId;
}

/**
 * The five axes every answer is scored on. Mirrors `shared/assessment_axes.py`, which is where
 * the backend keeps them so Lane A can validate weights against the same set Lane D scores
 * with.
 *
 * These are *채점축* — how an interview answer is read. They are fixed because each axis carries
 * the guidance the scoring prompt is built from. Job requirements are assessed separately and
 * never become score criteria.
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

export type PositionDraftInput = Readonly<{
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
}>;

export type HiringWorkspaceApi = Readonly<{
  createPosition(
    input: PositionDraftInput,
  ): Promise<{ positionId: string; rowVersion: number }>;
  publishCriteria(
    positionId: string,
    input: CriteriaConfiguration,
  ): Promise<{ versionId: string }>;
  activatePosition(
    positionId: string,
    rowVersion: number,
    input: PositionDraftInput,
  ): Promise<void>;
}>;

export type PositionHiringStep = "position" | "application";

export type CriteriaHiringStep = "evaluation" | "interview";

export type HiringStep = PositionHiringStep | CriteriaHiringStep | "complete";

export type HiringDraft = {
  title: string;
  description: string;
  descriptionCompleted: boolean;
  roleType: string;
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
  positionRowVersion: number;
  versionId: string;
};

export function createDefaultCriteria(): CriterionDraft[] {
  return [
    {
      id: "criterion-technical",
      code: evaluationCriterionCodes.technical,
      name: "기술 역량",
      description:
        "기술 선택과 구현 방식, 원리, 대안과 검증 과정을 평가합니다.",
      weight: 30,
      required: true,
      observableDimensions:
        "기술 선택 이유\n구현 방식\n원리 이해\n대안과 트레이드오프\n검증 결과",
      strongAnswerSignals:
        "직접 사용한 기술의 선택 이유와 구현 방식, 검증 결과를 구체적으로 설명함",
      weakAnswerSignals:
        "기술 이름만 나열하거나 원리와 직접 수행한 내용이 불명확함",
      followUpDirections: "기술 선택 이유\n구현 세부사항\n대안 비교\n검증 방법",
      maxFollowUps: 2,
      timeBudgetSeconds: 540,
      abstainGuidance:
        "기술 역량을 확인할 답변 근거가 부족하면 판단을 유보합니다.",
      commonQuestions:
        "지원 직무와 관련해 직접 사용한 기술 하나를 선택해, 적용 이유와 구현 방식을 설명해 주세요.",
    },
    {
      id: "criterion-project",
      code: evaluationCriterionCodes.project,
      name: "프로젝트 실행 역량",
      description:
        "프로젝트 목표, 본인 역할, 문제 해결 과정, 결과와 회고를 평가합니다.",
      weight: 40,
      required: true,
      observableDimensions:
        "프로젝트 목표\n본인 역할\n설계·구현 범위\n문제 해결 과정\n결과와 회고",
      strongAnswerSignals:
        "하나의 프로젝트에서 본인 역할과 판단, 실행, 결과를 연결해 설명함",
      weakAnswerSignals:
        "프로젝트 소개만 있고 본인 기여나 의사결정 근거가 불명확함",
      followUpDirections: "본인 기여\n핵심 의사결정\n문제 해결\n성과와 회고",
      maxFollowUps: 2,
      timeBudgetSeconds: 720,
      abstainGuidance:
        "프로젝트 수행 역량을 확인할 근거가 부족하면 판단을 유보합니다.",
      commonQuestions:
        "가장 자신 있는 프로젝트에서 맡은 역할과 핵심적으로 해결한 문제를 설명해 주세요.",
    },
    {
      id: "criterion-behavioral",
      code: evaluationCriterionCodes.behavioral,
      name: "협업·행동 역량",
      description:
        "역할 조율, 의사소통, 피드백 수용, 책임감과 협업 방식을 평가합니다.",
      weight: 30,
      required: true,
      observableDimensions:
        "협업 상황\n상대방과 역할\n본인이 취한 행동\n의견 조율\n결과와 배운 점",
      strongAnswerSignals:
        "실제 협업 상황에서 본인이 취한 행동과 조율 과정, 결과를 구체적으로 설명함",
      weakAnswerSignals:
        "팀이 한 일을 설명하지만 본인의 행동이나 상호작용이 불명확함",
      followUpDirections: "상대방과 역할\n의견 차이\n조율 행동\n결과와 배운 점",
      maxFollowUps: 2,
      timeBudgetSeconds: 540,
      abstainGuidance:
        "협업 역량을 확인할 답변 근거가 부족하면 판단을 유보합니다.",
      commonQuestions:
        "협업 과정에서 의견이나 역할을 조율했던 경험과 본인이 취한 행동을 설명해 주세요.",
    },
  ];
}

export function createRequirementDraft(index: number): JobRequirementDraft {
  return {
    id: `requirement-${Date.now()}-${index}`,
    requirementType: index === 1 ? "required" : "preferred",
    statement: "",
    priority: Math.min(index, 5),
    criterionCode: evaluationCriterionCodes.technical,
  };
}

export function inferRequirementCriterionCode(statement: string): string {
  const normalized = statement.toLocaleLowerCase();
  const behavioralTerms = [
    "협업",
    "소통",
    "커뮤니케이션",
    "조율",
    "피드백",
    "갈등",
    "리더십",
    "팀워크",
    "stakeholder",
    "collaboration",
    "communication",
  ];
  if (behavioralTerms.some((term) => normalized.includes(term))) {
    return evaluationCriterionCodes.behavioral;
  }
  const projectTerms = [
    "프로젝트",
    "제품",
    "서비스 구축",
    "서비스 출시",
    "운영 경험",
    "성과",
    "포트폴리오",
    "project",
    "production",
    "launch",
  ];
  if (projectTerms.some((term) => normalized.includes(term))) {
    return evaluationCriterionCodes.project;
  }
  return evaluationCriterionCodes.technical;
}

export const initialHiringDraft: HiringDraft = {
  title: "",
  description: "",
  descriptionCompleted: false,
  roleType: "개발",
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
  criteria: createDefaultCriteria(),
  prohibitedTopics: "가족관계, 출신지역, 혼인·임신 여부, 외모",
  interviewDurationMinutes: 30,
  interviewLevel: "junior",
  axisWeights: { ...defaultAxisWeights },
  interviewerName: "주니어 면접관",
  interviewerTone: "analytical",
  interviewerVoiceId: "Seoyeon",
};
