import type {
  CompanyApplicantInsight,
  CompanyCriterionVersion,
  CompanyInvitation,
  CompanyOperationsApi,
  CompanyPosition,
  CompanyRecruitingStage,
  CompanySubmission,
  CompanyUser,
} from "../features/company";
import type {
  AssistantAnswerResponse,
  RecruitingAssistantApi,
} from "../features/assistant/api";
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
const mockStagesByPosition = new Map<string, CompanyRecruitingStage[]>();
const DEFAULT_STAGE_NAMES = ["보류", "검토", "1차 합격", "최종합격", "불합격"];

const mockAssistantAnswer: AssistantAnswerResponse = {
  scope: "company",
  positionId: null,
  answer:
    "김민준 지원자는 백엔드 플랫폼 엔지니어 포지션에서 시스템 설계와 장애 대응 근거가 가장 구체적으로 확인됩니다.\n\n트래픽 급증 상황에서 병목 지표를 좁히고 ECS 오토 스케일링 정책을 조정한 판단 과정이 답변과 리포트에 함께 남아 있습니다. 최종 판단 전 연결된 원문 근거를 검토해 주세요.",
  degradedMode: null,
  sources: [
    {
      sourceId: "mock-assistant-source-summary",
      positionId: "mock-position-backend",
      applicantId: "mock-applicant-minjun",
      invitationId: "mock-invitation-001",
      reportId: "mock-report-001",
      reportItemId: null,
      criterionId: null,
      documentType: "report_summary",
      excerpt:
        "김민준 지원자는 대규모 트래픽 대응 경험을 구체적인 지표와 운영 판단으로 설명했습니다. 종합 점수 87점, 답변 근거가 충분히 확인됩니다.",
      score: 0.97,
      scoreComponents: { vector: 0.98, lexical: 0.95 },
      metadata: {
        applicant_name: "김민준",
        position_title: "백엔드 플랫폼 엔지니어",
        overall_score: 87,
      },
    },
    {
      sourceId: "mock-assistant-source-system-design",
      positionId: "mock-position-backend",
      applicantId: "mock-applicant-minjun",
      invitationId: "mock-invitation-001",
      reportId: "mock-report-001",
      reportItemId: "mock-report-item-system-design",
      criterionId: "system-design",
      documentType: "report_criterion",
      excerpt:
        "ECS 운영 중 트래픽 급증으로 발생한 장애에서 CPU, 응답 지연, 태스크 수 지표를 순서대로 비교해 병목을 좁혔습니다.",
      score: 0.94,
      scoreComponents: { vector: 0.96, lexical: 0.9 },
      metadata: {
        applicant_name: "김민준",
        criterion_name: "시스템 설계",
        score: 92,
      },
    },
    {
      sourceId: "mock-assistant-source-operation",
      positionId: "mock-position-backend",
      applicantId: "mock-applicant-minjun",
      invitationId: "mock-invitation-001",
      reportId: "mock-report-001",
      reportItemId: "mock-report-item-operation",
      criterionId: "operation",
      documentType: "report_criterion",
      excerpt:
        "오토 스케일링 임계값을 조정하고 재발 방지를 위해 CloudWatch 경보와 부하 테스트 기준을 함께 개선했습니다.",
      score: 0.91,
      scoreComponents: { vector: 0.93, lexical: 0.87 },
      metadata: {
        applicant_name: "김민준",
        criterion_name: "문제 해결력",
        score: 89,
      },
    },
  ],
};

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
    const fixture = await loadFixture();
    const stages = mockStages(positionId);
    return fixture.invitations
      .filter((invitation) => invitation.positionId === positionId)
      .map((invitation) => {
        if (invitation.recruitingStageId) return invitation;
        const stage = stages.find(
          (candidate) => candidate.name === mockDefaultStage(invitation.status),
        );
        const updated = {
          ...invitation,
          recruitingStageId: stage?.recruitingStageId ?? null,
          pipelineRowVersion: invitation.pipelineRowVersion ?? 1,
        };
        const index = fixture.invitations.findIndex(
          (candidate) => candidate.invitationId === invitation.invitationId,
        );
        if (index >= 0) fixture.invitations[index] = updated;
        return updated;
      });
  },
  async listRecruitingStages(positionId) {
    const positions = positionId
      ? [positionId]
      : (await loadFixture()).positions.map((position) => position.positionId);
    return positions.flatMap(mockStages);
  },
  async getApplicantRecruitingState(invitationId) {
    const fixture = await loadFixture();
    const invitation = fixture.invitations.find(
      (candidate) => candidate.invitationId === invitationId,
    );
    if (!invitation) throw new Error("mock invitation not found");
    const stages = mockStages(invitation.positionId);
    const recruitingStageId =
      invitation.recruitingStageId ??
      stages.find((stage) => stage.name === mockDefaultStage(invitation.status))
        ?.recruitingStageId;
    if (!recruitingStageId) throw new Error("mock recruiting stage not found");
    return {
      invitationId,
      positionId: invitation.positionId,
      recruitingStageId,
      pipelineRowVersion: invitation.pipelineRowVersion ?? 1,
      stages: [...stages],
    };
  },
  async createRecruitingStage(positionId, name) {
    const stages = mockStages(positionId);
    const stage: CompanyRecruitingStage = {
      recruitingStageId: `mock-stage-${positionId}-${Date.now()}`,
      positionId,
      name: name.trim(),
      sortOrder: stages.length,
      rowVersion: 1,
    };
    stages.push(stage);
    return stage;
  },
  async updateRecruitingStage(positionId, stageId, name, rowVersion) {
    const stages = mockStages(positionId);
    const index = stages.findIndex(
      (stage) => stage.recruitingStageId === stageId,
    );
    if (index < 0) throw new Error("mock stage not found");
    const updated = {
      ...stages[index],
      name: name.trim(),
      rowVersion: rowVersion + 1,
    };
    stages[index] = updated;
    return updated;
  },
  async reorderRecruitingStages(positionId, orderedStageIds) {
    const byId = new Map(
      mockStages(positionId).map((stage) => [stage.recruitingStageId, stage]),
    );
    const reordered = orderedStageIds.map((stageId, sortOrder) => ({
      ...byId.get(stageId)!,
      sortOrder,
      rowVersion: (byId.get(stageId)?.rowVersion ?? 0) + 1,
    }));
    mockStagesByPosition.set(positionId, reordered);
    return reordered;
  },
  async deleteRecruitingStage(positionId, stageId, replacementStageId) {
    const fixture = await loadFixture();
    fixture.invitations = fixture.invitations.map((invitation) =>
      invitation.positionId === positionId &&
      invitation.recruitingStageId === stageId
        ? {
            ...invitation,
            recruitingStageId: replacementStageId,
            pipelineRowVersion: (invitation.pipelineRowVersion ?? 1) + 1,
          }
        : invitation,
    );
    const remaining = mockStages(positionId)
      .filter((stage) => stage.recruitingStageId !== stageId)
      .map((stage, sortOrder) => ({ ...stage, sortOrder }));
    mockStagesByPosition.set(positionId, remaining);
    return remaining;
  },
  async moveApplicantsToRecruitingStage(positionId, targetStageId, applicants) {
    const fixture = await loadFixture();
    const assignments = applicants.map((move) => {
      const index = fixture.invitations.findIndex(
        (invitation) =>
          invitation.positionId === positionId &&
          invitation.invitationId === move.invitationId,
      );
      if (index < 0) throw new Error("mock invitation not found");
      const pipelineRowVersion = move.expectedVersion + 1;
      fixture.invitations[index] = {
        ...fixture.invitations[index],
        recruitingStageId: targetStageId,
        pipelineRowVersion,
      };
      return {
        invitationId: move.invitationId,
        recruitingStageId: targetStageId,
        pipelineRowVersion,
      };
    });
    return assignments;
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

function mockStages(positionId: string) {
  const existing = mockStagesByPosition.get(positionId);
  if (existing) return existing;
  const created = DEFAULT_STAGE_NAMES.map((name, sortOrder) => ({
    recruitingStageId: `mock-stage-${positionId}-${sortOrder}`,
    positionId,
    name,
    sortOrder,
    rowVersion: 1,
  }));
  mockStagesByPosition.set(positionId, created);
  return created;
}

function mockDefaultStage(status: CompanyInvitation["status"]) {
  if (["interrupted", "expired", "revoked"].includes(status)) return "보류";
  if (status === "completed") return "1차 합격";
  if (status === "reviewed" || status === "deleted") return "최종합격";
  return "검토";
}

export const mockRecruitingAssistantApi: RecruitingAssistantApi = {
  async answerQuestion(request) {
    return answerForScope(request.query, request.positionId);
  },
  async streamAnswer(request, handlers) {
    const response = await answerForScope(request.query, request.positionId);
    handlers.onStart?.({ archivedScope: false });
    const sentences = response.answer.match(/[^\n]+(?:\n|$)/g) ?? [
      response.answer,
    ];
    let accumulated = "";
    for (const sentence of sentences) {
      accumulated += sentence;
      handlers.onDelta?.(sentence, accumulated);
    }
    handlers.onSources?.(response.sources);
    return response;
  },
};

async function answerForScope(
  query: string,
  positionId?: string,
): Promise<AssistantAnswerResponse> {
  const pipelineAnswer = await answerPipelineQuestion(query, positionId);
  return {
    ...mockAssistantAnswer,
    scope: positionId ? "position" : "company",
    positionId: positionId ?? null,
    ...(pipelineAnswer
      ? { answer: pipelineAnswer, sources: [], degradedMode: null }
      : {}),
  };
}

async function answerPipelineQuestion(query: string, positionId?: string) {
  const normalized = query.toLocaleLowerCase().replace(/\s+/g, " ").trim();
  const fixture = await loadFixture();
  const positions = fixture.positions.filter(
    (position) => !positionId || position.positionId === positionId,
  );
  const stagesByPosition = new Map(
    positions.map((position) => [
      position.positionId,
      mockStages(position.positionId),
    ]),
  );
  const stageTerms = [...stagesByPosition.values()]
    .flat()
    .map((stage) => stage.name.toLocaleLowerCase());
  const pipelineTerms = [
    "채용 단계",
    "현재 단계",
    "단계별",
    "칸반",
    "현재 상태",
  ];
  const countTerms = ["몇 명", "몇명", "인원", "명인가", "카운트", "분포"];
  if (
    ![...pipelineTerms, ...countTerms, ...stageTerms].some((term) =>
      normalized.includes(term),
    )
  ) {
    return null;
  }

  const invitations = (
    await Promise.all(
      positions.map((position) =>
        mockCompanyOperationsApi.listInvitations(position.positionId),
      ),
    )
  ).flat();
  const matched = invitations.filter((invitation) => {
    const emailId = invitation.applicantEmail.split("@", 1)[0];
    return [invitation.applicantDisplayName, invitation.applicantEmail, emailId]
      .filter(Boolean)
      .some((value) => normalized.includes(String(value).toLocaleLowerCase()));
  });
  if (matched.length > 0) {
    return matched
      .map((invitation) => {
        const position = positions.find(
          (candidate) => candidate.positionId === invitation.positionId,
        );
        const stage = stagesByPosition
          .get(invitation.positionId)
          ?.find(
            (candidate) =>
              candidate.recruitingStageId === invitation.recruitingStageId,
          );
        return `${invitation.applicantDisplayName ?? invitation.applicantEmail} 지원자는 ${position?.title ?? "해당"} 포지션의 현재 채용 단계가 ${stage?.name ?? "미지정"}입니다.`;
      })
      .join("\n");
  }

  if (
    countTerms.some((term) => normalized.includes(term)) ||
    normalized.includes("단계")
  ) {
    const blocks = positions.map((position) => {
      const stages = stagesByPosition.get(position.positionId) ?? [];
      const positionInvitations = invitations.filter(
        (invitation) => invitation.positionId === position.positionId,
      );
      return `${position.title}: ${stages
        .map(
          (stage) =>
            `${stage.name} ${positionInvitations.filter((invitation) => invitation.recruitingStageId === stage.recruitingStageId).length}명`,
        )
        .join(", ")}`;
    });
    return `현재 채용 단계별 인원은 다음과 같습니다.\n${blocks.join("\n")}`;
  }
  return null;
}

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
