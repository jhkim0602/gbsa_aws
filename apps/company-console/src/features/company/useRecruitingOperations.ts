import { useEffect, useState } from "react";

import type {
  CompanyInvitation,
  CompanyOperationsApi,
  CompanyPosition,
  CompanyUser,
} from "./types";

export type PositionedInvitation = CompanyInvitation &
  Readonly<{
    positionTitle: string;
  }>;

type RecruitingOperationsState = Readonly<{
  user: CompanyUser | null;
  positions: readonly CompanyPosition[];
  invitations: readonly PositionedInvitation[];
  loading: boolean;
  error: boolean;
}>;

const initialState: RecruitingOperationsState = {
  user: null,
  positions: [],
  invitations: [],
  loading: true,
  error: false,
};

export function useRecruitingOperations(
  api: CompanyOperationsApi,
  positionId?: string,
) {
  const [state, setState] = useState<RecruitingOperationsState>(initialState);

  useEffect(() => {
    let active = true;
    const positionsRequest = positionId
      ? api.getPosition(positionId).then((position) => [position])
      : api.listPositions();
    Promise.all([api.getCurrentUser(), positionsRequest])
      .then(async ([user, positions]) => {
        const invitationBatches = await Promise.all(
          positions.map(async (position) => {
            const invitations = await api.listInvitations(position.positionId);
            return invitations.map((invitation) => ({
              ...invitation,
              positionTitle: position.title,
            }));
          }),
        );
        if (active) {
          setState({
            user,
            positions,
            invitations: invitationBatches.flat(),
            loading: false,
            error: false,
          });
        }
      })
      .catch(() => {
        if (active) {
          setState({ ...initialState, loading: false, error: true });
        }
      });
    return () => {
      active = false;
    };
  }, [api, positionId]);

  return state;
}
