import type {
  CompanyApplicantInsight,
  CompanyCriterionVersion,
  CompanyInvitation,
  CompanyOperationsApi,
  CompanyPosition,
  CompanySubmission,
  CompanyUser,
} from "../features/company";
import type { ReviewReport, ReviewTimeline } from "../features/review";
import type {
  CriteriaConfiguration,
  InvitationApplicant,
  InvitationEmailTemplate,
  InvitationEmailTemplateApi,
  InvitationEmailTemplateState,
  PositionInvitation,
  PositionInvitationApi,
} from "../features/hiring";

type RecruitingFixture = {
  user: CompanyUser;
  positions: CompanyPosition[];
  invitations: CompanyInvitation[];
  criterionVersions: CompanyCriterionVersion[];
  submissionsByInvitation: Record<string, CompanySubmission[]>;
  reportsBySession: Record<
    string,
    { report: ReviewReport; timeline: ReviewTimeline }
  >;
  invitationTemplate: InvitationEmailTemplateState;
};

let fixturePromise: Promise<RecruitingFixture> | null = null;

function loadFixture() {
  fixturePromise ??= fetch(
    `${import.meta.env.BASE_URL}mock-data/recruiting.json`,
    { cache: "no-store" },
  ).then(async (response) => {
    if (!response.ok) {
      throw new Error(`mock recruiting data failed: ${response.status}`);
    }
    return (await response.json()) as RecruitingFixture;
  });
  return fixturePromise;
}

export const mockCompanyOperationsApi: CompanyOperationsApi = {
  async getCurrentUser() {
    return (await loadFixture()).user;
  },
  async listPositions() {
    return [...(await loadFixture()).positions];
  },
  async getPosition(positionId) {
    const position = (await loadFixture()).positions.find(
      (candidate) => candidate.positionId === positionId,
    );
    if (!position) throw new Error("mock position not found");
    return position;
  },
  async listInvitations(positionId) {
    return (await loadFixture()).invitations.filter(
      (invitation) => invitation.positionId === positionId,
    );
  },
  async requestApplicantDeletion(invitationId) {
    const fixture = await loadFixture();
    const index = fixture.invitations.findIndex(
      (invitation) => invitation.invitationId === invitationId,
    );
    if (index >= 0) fixture.invitations.splice(index, 1);
    return {
      deletionRequestId: `mock-deletion-${invitationId}`,
      status: "completed",
      expectedTargets: 1,
      verifiedTargets: 1,
    };
  },
  async getApplicantDeletion(deletionRequestId) {
    return {
      deletionRequestId,
      status: "completed",
      expectedTargets: 1,
      verifiedTargets: 1,
    };
  },
  async updatePosition(input) {
    const fixture = await loadFixture();
    const index = fixture.positions.findIndex(
      (position) => position.positionId === input.positionId,
    );
    if (index < 0) throw new Error("mock position not found");
    const updated: CompanyPosition = {
      ...fixture.positions[index],
      ...input,
      rowVersion: input.rowVersion + 1,
    };
    fixture.positions[index] = updated;
    return updated;
  },
  async listCriterionVersions(positionId) {
    return (await loadFixture()).criterionVersions.filter(
      (version) => version.positionId === positionId,
    );
  },
  async publishCriteria(positionId, input) {
    const fixture = await loadFixture();
    const versionNumber =
      fixture.criterionVersions.filter(
        (version) => version.positionId === positionId,
      ).length + 1;
    const versionId = `mock-version-${positionId}-${versionNumber}`;
    fixture.criterionVersions.push(
      toMockCriterionVersion(versionId, positionId, versionNumber, input),
    );
    return { versionId };
  },
  async listSubmissions(invitationId) {
    return [
      ...((await loadFixture()).submissionsByInvitation[invitationId] ?? []),
    ];
  },
  async listApplicantInsights(positionId) {
    const fixture = await loadFixture();
    return fixture.invitations
      .filter(
        (invitation) =>
          invitation.positionId === positionId &&
          Boolean(invitation.interviewSessionId),
      )
      .flatMap((invitation) => {
        const sessionId = invitation.interviewSessionId;
        if (!sessionId) return [];
        const report = fixture.reportsBySession[sessionId]?.report;
        return report
          ? [
              toApplicantInsight(
                invitation.invitationId,
                sessionId,
                invitation.competencyModelVersionId,
                report,
              ),
            ]
          : [];
      });
  },
  async getApplicantReport(
    interviewSessionId,
    invitationId,
    competencyModelVersionId,
  ) {
    const fixture = await loadFixture();
    const stored = fixture.reportsBySession[interviewSessionId];
    if (!stored) return null;
    const invitation = fixture.invitations.find(
      (candidate) =>
        candidate.invitationId === invitationId &&
        candidate.interviewSessionId === interviewSessionId,
    );
    if (!invitation) return null;
    return {
      insight: toApplicantInsight(
        invitation.invitationId,
        interviewSessionId,
        competencyModelVersionId,
        stored.report,
      ),
      report: stored.report,
      timeline: stored.timeline,
    };
  },
};

export const mockPositionInvitationApi: PositionInvitationApi = {
  async listInvitations(positionId) {
    return (await mockCompanyOperationsApi.listInvitations(
      positionId,
    )) as readonly PositionInvitation[];
  },
  async createInvitations(positionId, applicants, expiresInDays) {
    const fixture = await loadFixture();
    const created = applicants.map((applicant, index) =>
      createMockInvitation(
        positionId,
        applicant,
        expiresInDays,
        fixture.invitations.length + index + 1,
      ),
    );
    fixture.invitations.push(...created);
    return {
      acceptedCount: created.length,
      rejectedCount: 0,
      invitations: created,
    };
  },
};

export const mockInvitationEmailTemplateApi: InvitationEmailTemplateApi = {
  async getCompanyTemplate() {
    return (await loadFixture()).invitationTemplate;
  },
  async saveCompanyTemplate(template) {
    return saveTemplate(template, false);
  },
  async resetCompanyTemplate() {
    return (await loadFixture()).invitationTemplate;
  },
  async getPositionTemplate() {
    return {
      ...(await loadFixture()).invitationTemplate,
      isPositionOverride: false,
    };
  },
  async savePositionTemplate(_positionId, template) {
    return saveTemplate(template, true);
  },
  async resetPositionTemplate() {
    return {
      ...(await loadFixture()).invitationTemplate,
      isPositionOverride: false,
    };
  },
  async previewTemplate(template) {
    return {
      subject: template.subject,
      htmlBody: `<main><h1>${template.headline}</h1><p>${template.intro}</p></main>`,
    };
  },
  async uploadLogo(file) {
    return {
      logoUrl: URL.createObjectURL(file),
      contentType: file.type,
      byteSize: file.size,
    };
  },
  async deleteLogo() {},
};

async function saveTemplate(
  template: InvitationEmailTemplate,
  isPositionOverride: boolean,
) {
  const fixture = await loadFixture();
  fixture.invitationTemplate = {
    ...template,
    logoUrl: fixture.invitationTemplate.logoUrl,
    isPositionOverride,
  };
  return fixture.invitationTemplate;
}

function createMockInvitation(
  positionId: string,
  applicant: InvitationApplicant,
  expiresInDays: number,
  sequence: number,
): PositionInvitation {
  return {
    invitationId: `mock-invitation-${sequence}`,
    positionId,
    competencyModelVersionId: `mock-version-${positionId}-1`,
    applicantEmail: applicant.email,
    applicantDisplayName: applicant.displayName,
    status: "invited",
    expiresAt: new Date(Date.now() + expiresInDays * 86_400_000).toISOString(),
    rowVersion: 1,
  };
}

function toMockCriterionVersion(
  versionId: string,
  positionId: string,
  versionNumber: number,
  input: CriteriaConfiguration,
): CompanyCriterionVersion {
  return {
    versionId,
    positionId,
    versionNumber,
    status: "published",
    rowVersion: 2,
    publishedAt: new Date().toISOString(),
    jobRequirements: input.jobRequirements,
    criteria: input.criteria,
    prohibitedTopics: input.prohibitedTopics,
    interviewDurationMinutes: input.interviewDurationMinutes,
    interviewLevel: input.interviewLevel,
    personaDefinition: input.personaDefinition,
  };
}

function toApplicantInsight(
  invitationId: string,
  interviewSessionId: string,
  competencyModelVersionId: string,
  report: ReviewReport,
): CompanyApplicantInsight {
  const criteria = report.items.map((item) => ({
    criterionId: item.criterionId,
    criterionName: item.criterionName,
    score: item.averageScore,
    assessmentState: item.assessmentState,
    evidenceCount: item.evidence.length,
  }));
  const evidenced = criteria.filter((criterion) => criterion.evidenceCount > 0);
  return {
    invitationId,
    interviewSessionId,
    competencyModelVersionId,
    overallScore: report.overallScore,
    unscoredCriteriaCount: report.unscoredCriteriaCount,
    evidenceCoverage: criteria.length
      ? Math.round((evidenced.length / criteria.length) * 100)
      : 0,
    summary: report.summary,
    criteria,
  } satisfies CompanyApplicantInsight;
}
