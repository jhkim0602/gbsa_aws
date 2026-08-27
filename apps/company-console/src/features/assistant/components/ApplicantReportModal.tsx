import { ApplicantDetail } from "../../company/ApplicantDetail";
import { displayApplicant } from "../../company/recruitingState";
import type {
  CompanyOperationsApi,
  CompanyRecruitingStage,
} from "../../company/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../../hiring/tech-stack-combobox/dialog";
import type { ApplicantReportPreview } from "../types";

export function ApplicantReportModal({
  preview,
  open,
  api,
  onOpenChange,
}: {
  preview: ApplicantReportPreview | undefined;
  open: boolean;
  api: CompanyOperationsApi;
  stages?: readonly CompanyRecruitingStage[];
  moving?: boolean;
  onChangeStage?(stageId: string): Promise<boolean>;
  onOpenChange(open: boolean): void;
}) {
  const invitation = preview?.invitation;
  if (!preview || !invitation) return null;

  const applicantName = displayApplicant(invitation);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="grid max-h-[94vh] w-[min(1180px,96vw)] max-w-none grid-rows-[minmax(0,1fr)] gap-0 overflow-hidden rounded-xl border-border bg-[#f6f7fa] p-0">
        <DialogHeader className="sr-only">
          <DialogTitle>지원자 상세</DialogTitle>
          <DialogDescription>
            {applicantName} 지원자의 상세 정보와 분석 리포트
          </DialogDescription>
        </DialogHeader>
        <div className="min-h-0 overflow-y-auto">
          <ApplicantDetail
            embedded
            positionId={invitation.positionId}
            invitationId={invitation.invitationId}
            api={api}
            initialInvitation={{
              ...invitation,
              positionTitle: preview.positionTitle,
            }}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
