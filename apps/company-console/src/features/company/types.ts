import type { InterviewLevel, InterviewerTone } from "../hiring/types";
import type { SubmissionMaterialId } from "../hiring/types";
import type { ReviewReport, ReviewTimeline } from "../review";

export type CompanySubmissionRequirement = Readonly<{
  materialType: SubmissionMaterialId;
  required: boolean;
  enabled: boolean;
  instructions?: string | null;
}>;

export type CompanyUser = Readonly<{
  companyUserId: string;
  companyId: string;
  email: string;
  status: string;
}>;

export type CompanyPosition = Readonly<{
  positionId: string;
  title: string;
  description: string;
  roleType?: string | null;
  headcount?: number | null;
  applicantCapacity?: number | null;
  interviewCapacity?: number | null;
  interviewAt?: string | null;
  recruitmentStartAt?: string | null;
  recruitmentEndAt?: string | null;
  submissionRequirements: readonly CompanySubmissionRequirement[];
  status: string;
  rowVersion: number;
  createdAt: string;
}>;

export type CompanyPositionUpdate = Readonly<{
  positionId: string;
  title: string;
  description: string;
  roleType?: string | null;
  headcount?: number | null;
  applicantCapacity?: number | null;
  interviewCapacity?: number | null;
  interviewAt?: string | null;
  recruitmentStartAt?: string | null;
  recruitmentEndAt?: string | null;
  submissionRequirements: readonly CompanySubmissionRequirement[];
  status: "draft" | "active" | "closed";
  rowVersion: number;
}>;

export type CompanyCriterionVersion = Readonly<{
  versionId: string;
  positionId: string;
  versionNumber: number;
  status: "draft" | "published" | "retired";
  rowVersion: number;
  publishedAt?: string | null;
  jobRequirements: ReadonlyArray<{
    requirementType: "required" | "preferred";
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
      observableDimensions: readonly string[];
      strongAnswerSignals: readonly string[];
      weakAnswerSignals: readonly string[];
      followUpDirections: readonly string[];
      maxFollowUps: number;
      timeBudgetSeconds: number;
    };
    abstainGuidance: string;
    commonQuestions: readonly string[];
  }>;
  prohibitedTopics: readonly string[];
  interviewDurationMinutes: number;
  interviewLevel: InterviewLevel;
  personaDefinition?: Readonly<{
    name: string;
    tone: InterviewerTone;
    voiceId: string;
    systemPrompt: string;
  }>;
}>;

export type CompanyWorkspaceApi = Readonly<{
  getCurrentUser(): Promise<CompanyUser>;
  listPositions(): Promise<CompanyPosition[]>;
  getPosition(positionId: string): Promise<CompanyPosition>;
}>;

export type CompanyInvitationStatus =
  | "invited"
  | "identity_verified"
  | "consented"
  | "materials_submitted"
  | "analyzing"
  | "ready"
  | "interviewing"
  | "interrupted"
  | "completed"
  | "reviewed"
  | "expired"
  | "revoked"
  | "deleted";

export type CompanyInvitation = Readonly<{
  invitationId: string;
  positionId: string;
  competencyModelVersionId: string;
  applicantEmail: string;
  applicantDisplayName?: string | null;
  status: CompanyInvitationStatus;
  expiresAt: string;
  rowVersion: number;
  recruitingStageId?: string | null;
  pipelineRowVersion?: number;
  analysisStatus?: string | null;
  interviewStatus?: string | null;
  reportStatus?: string | null;
  interviewSessionId?: string | null;
  overallScore?: number | null;
  scoredCriteriaCount?: number | null;
  totalCriteriaCount?: number | null;
}>;

export type CompanyRecruitingStage = Readonly<{
  recruitingStageId: string;
  positionId: string;
  name: string;
  sortOrder: number;
  rowVersion: number;
}>;

export type CompanyApplicantRecruitingState = Readonly<{
  invitationId: string;
  positionId: string;
  recruitingStageId: string;
  pipelineRowVersion: number;
  stages: readonly CompanyRecruitingStage[];
}>;

export type CompanyApplicantPipelineMove = Readonly<{
  invitationId: string;
  expectedVersion: number;
}>;

export type CompanyDeletionStatus = Readonly<{
  deletionRequestId: string;
  status:
    | "requested"
    | "enumerating"
    | "deleting"
    | "verifying"
    | "retrying"
    | "partially_completed"
    | "completed";
  expectedTargets: number;
  verifiedTargets: number;
}>;

export type CompanyOperationsApi = CompanyWorkspaceApi &
  Readonly<{
    listInvitations(positionId: string): Promise<readonly CompanyInvitation[]>;
    listRecruitingStages?(
      positionId?: string,
    ): Promise<readonly CompanyRecruitingStage[]>;
    getApplicantRecruitingState?(
      invitationId: string,
    ): Promise<CompanyApplicantRecruitingState>;
    createRecruitingStage?(
      positionId: string,
      name: string,
    ): Promise<CompanyRecruitingStage>;
    updateRecruitingStage?(
      positionId: string,
      stageId: string,
      name: string,
      rowVersion: number,
    ): Promise<CompanyRecruitingStage>;
    reorderRecruitingStages?(
      positionId: string,
      orderedStageIds: readonly string[],
    ): Promise<readonly CompanyRecruitingStage[]>;
    deleteRecruitingStage?(
      positionId: string,
      stageId: string,
      replacementStageId: string,
    ): Promise<readonly CompanyRecruitingStage[]>;
    moveApplicantsToRecruitingStage?(
      positionId: string,
      targetStageId: string,
      applicants: readonly CompanyApplicantPipelineMove[],
    ): Promise<
      ReadonlyArray<{
        invitationId: string;
        recruitingStageId: string;
        pipelineRowVersion: number;
      }>
    >;
    updatePosition(input: CompanyPositionUpdate): Promise<CompanyPosition>;
    listCriterionVersions(
      positionId: string,
    ): Promise<readonly CompanyCriterionVersion[]>;
    publishCriteria(
      positionId: string,
      input: import("../hiring").CriteriaConfiguration,
    ): Promise<{ versionId: string }>;
    listSubmissions(
      invitationId: string,
    ): Promise<readonly CompanySubmission[]>;
    requestApplicantDeletion?(
      invitationId: string,
    ): Promise<CompanyDeletionStatus>;
    getApplicantDeletion?(
      deletionRequestId: string,
    ): Promise<CompanyDeletionStatus>;
    /**
     * Read-only report summaries used for position-level competency analytics.
     * Optional so older API adapters can still render the operational workspace.
     */
    listApplicantInsights?(
      positionId: string,
    ): Promise<readonly CompanyApplicantInsight[]>;
    /** Loads the immutable AI report and its evidence timeline for one session. */
    getApplicantReport?(
      interviewSessionId: string,
      invitationId: string,
      competencyModelVersionId: string,
    ): Promise<CompanyApplicantReport | null>;
  }>;

export type CompanySubmission = Readonly<{
  submissionId: string;
  materialType: SubmissionMaterialId;
  sourceType: string;
  originalFilename?: string | null;
  sourceUrl?: string | null;
  status: string;
  failureCode?: string | null;
  impactSummary?: string | null;
  createdAt: string;
}>;

export type CompanyApplicantCriterionScore = Readonly<{
  criterionId: string;
  criterionName: string;
  score: number | null;
  assessmentState: ReviewReport["items"][number]["assessmentState"];
  evidenceCount: number;
  weight?: number;
}>;

export type CompanyApplicantInsight = Readonly<{
  invitationId: string;
  interviewSessionId: string;
  competencyModelVersionId: string;
  overallScore: number | null;
  unscoredCriteriaCount: number;
  evidenceCoverage: number;
  summary: string;
  criteria: readonly CompanyApplicantCriterionScore[];
}>;

export type CompanyApplicantReport = Readonly<{
  insight: CompanyApplicantInsight;
  report: ReviewReport;
  timeline: ReviewTimeline;
}>;
