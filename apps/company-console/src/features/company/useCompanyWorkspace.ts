import { useEffect, useState } from "react";

import type {
  CompanyPosition,
  CompanyUser,
  CompanyWorkspaceApi,
} from "./types";

type WorkspaceState = Readonly<{
  user: CompanyUser | null;
  positions: CompanyPosition[];
  loading: boolean;
  error: boolean;
}>;

const initialState: WorkspaceState = {
  user: null,
  positions: [],
  loading: true,
  error: false,
};

export function useCompanyWorkspace(api: CompanyWorkspaceApi) {
  const [state, setState] = useState<WorkspaceState>(initialState);

  useEffect(() => {
    let active = true;
    Promise.all([api.getCurrentUser(), api.listPositions()])
      .then(([user, positions]) => {
        if (active) {
          setState({ user, positions, loading: false, error: false });
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
  }, [api]);

  return state;
}
