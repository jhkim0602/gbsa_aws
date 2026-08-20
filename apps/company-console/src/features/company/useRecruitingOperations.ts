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
  lastUpdatedAt: string | null;
}>;

/** Browsers cap per-origin connections anyway; an unbounded fan-out only queues. */
const MAX_CONCURRENT_REQUESTS = 6;

const initialState: RecruitingOperationsState = {
  user: null,
  positions: [],
  invitations: [],
  loading: true,
  error: false,
  lastUpdatedAt: null,
};

export function useRecruitingOperations(
  api: CompanyOperationsApi,
  positionId?: string,
  refreshIntervalMs = 0,
) {
  const [state, setState] = useState<RecruitingOperationsState>(initialState);

  useEffect(() => {
    let active = true;
    let inFlight = false;

    async function load() {
      if (inFlight) return;
      inFlight = true;
      try {
        const positionsRequest = positionId
          ? api.getPosition(positionId).then((position) => [position])
          : api.listPositions();
        const [user, positions] = await Promise.all([
          api.getCurrentUser(),
          positionsRequest,
        ]);
        const batches: PositionedInvitation[][] = positions.map(() => []);
        let next = 0;
        const drain = async () => {
          for (let index = next++; index < positions.length; index = next++) {
            const position = positions[index];
            const invitations = await api.listInvitations(position.positionId);
            batches[index] = invitations.map((invitation) => ({
              ...invitation,
              positionTitle: position.title,
            }));
          }
        };
        await Promise.all(
          Array.from(
            { length: Math.min(MAX_CONCURRENT_REQUESTS, positions.length) },
            drain,
          ),
        );
        if (active) {
          setState({
            user,
            positions,
            invitations: batches.flat(),
            loading: false,
            error: false,
            lastUpdatedAt: new Date().toISOString(),
          });
        }
      } catch {
        if (active) {
          setState((current) =>
            current.lastUpdatedAt
              ? current
              : { ...initialState, loading: false, error: true },
          );
        }
      } finally {
        inFlight = false;
      }
    }

    void load();
    const timer = refreshIntervalMs
      ? window.setInterval(() => void load(), refreshIntervalMs)
      : null;
    return () => {
      active = false;
      if (timer !== null) window.clearInterval(timer);
    };
  }, [api, positionId, refreshIntervalMs]);

  return state;
}
