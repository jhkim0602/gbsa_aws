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
  recruitmentStartAt?: string | null;
  recruitmentEndAt?: string | null;
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
  recruitmentStartAt?: string | null;
  recruitmentEndAt?: string | null;
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
  analysisStatus?: string | null;
  interviewStatus?: string | null;
  reportStatus?: string | null;
  interviewSessionId?: string | null;
}>;

export type CompanyOperationsApi = CompanyWorkspaceApi &
  Readonly<{
    listInvitations(positionId: string): Promise<readonly CompanyInvitation[]>;
    updatePosition(input: CompanyPositionUpdate): Promise<CompanyPosition>;
    listCriterionVersions(
      positionId: string,
    ): Promise<readonly CompanyCriterionVersion[]>;
    publishCriteria(
      positionId: string,
      input: import("../hiring").CriteriaConfiguration,
    ): Promise<{ versionId: string }>;
  }>;
