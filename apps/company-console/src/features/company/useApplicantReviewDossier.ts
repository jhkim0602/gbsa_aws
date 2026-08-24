import { useEffect, useState } from "react";

import { applyConfiguredWeights } from "./CompetencyInsights";
import type {
  CompanyApplicantReport,
  CompanyInvitation,
  CompanyOperationsApi,
  CompanySubmission,
} from "./types";

type ApplicantReviewDossierState = Readonly<{
  submissions: readonly CompanySubmission[];
  report: CompanyApplicantReport | null;
  loading: boolean;
  error: boolean;
}>;

const EMPTY_DOSSIER: ApplicantReviewDossierState = {
  submissions: [],
  report: null,
  loading: false,
  error: false,
};

export function useApplicantReviewDossier({
  api,
  invitation,
  enabled,
}: {
  api: CompanyOperationsApi;
  invitation: CompanyInvitation | undefined;
  enabled: boolean;
}): ApplicantReviewDossierState {
  const [state, setState] = useState(EMPTY_DOSSIER);
  const invitationId = invitation?.invitationId;
  const positionId = invitation?.positionId;
  const interviewSessionId = invitation?.interviewSessionId;
  const competencyModelVersionId = invitation?.competencyModelVersionId;

  useEffect(() => {
    if (!enabled || !invitationId || !positionId || !competencyModelVersionId) {
      setState(EMPTY_DOSSIER);
      return;
    }
    let active = true;
    setState({ ...EMPTY_DOSSIER, loading: true });
    const reportRequest =
      interviewSessionId && api.getApplicantReport
        ? api.getApplicantReport(
            interviewSessionId,
            invitationId,
            competencyModelVersionId,
          )
        : Promise.resolve(null);

    void Promise.allSettled([
      api.listSubmissions(invitationId),
      reportRequest,
      api.listCriterionVersions(positionId),
    ]).then(([submissionResult, reportResult, criteriaResult]) => {
      if (!active) return;
      const submissions =
        submissionResult.status === "fulfilled" ? submissionResult.value : [];
      const loadedReport =
        reportResult.status === "fulfilled" ? reportResult.value : null;
      const versions =
        criteriaResult.status === "fulfilled" ? criteriaResult.value : [];
      const report = loadedReport
        ? {
            ...loadedReport,
            insight:
              applyConfiguredWeights([loadedReport.insight], versions)[0] ??
              loadedReport.insight,
          }
        : null;
      setState({
        submissions,
        report,
        loading: false,
        error:
          submissionResult.status === "rejected" ||
          reportResult.status === "rejected" ||
          criteriaResult.status === "rejected",
      });
    });
    return () => {
      active = false;
    };
  }, [
    api,
    competencyModelVersionId,
    enabled,
    interviewSessionId,
    invitationId,
    positionId,
  ]);

  return state;
}
