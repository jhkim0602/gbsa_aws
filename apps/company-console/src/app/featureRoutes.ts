import type { RouteObject } from "react-router-dom";

import {
  ApplicantDetailRoute,
  ApplicantManagementRoute,
  CompanyAuthCallbackRoute,
  CompanyHomeRoute,
  CompanyLoginRoute,
  CompanyPositionsRoute,
  CompanySignupRoute,
  HiringRoute,
  InvitationEmailSettingsRoute,
  PositionOperationsRoute,
  ReviewRoute,
} from "./routeAdapters";
import { CompanyShell } from "./layouts/CompanyShell";

export const companyRouteObjects: RouteObject[] = [
  { path: "/auth/login", Component: CompanyLoginRoute },
  { path: "/auth/signup", Component: CompanySignupRoute },
  { path: "/auth/callback", Component: CompanyAuthCallbackRoute },
  {
    Component: CompanyShell,
    children: [
      { path: "/", Component: CompanyHomeRoute },
      { path: "/company", Component: CompanyHomeRoute },
      { path: "/positions", Component: CompanyPositionsRoute },
      {
        path: "/positions/:positionId",
        Component: PositionOperationsRoute,
      },
      { path: "/applicants", Component: ApplicantManagementRoute },
      {
        path: "/positions/:positionId/applicants/:invitationId",
        Component: ApplicantDetailRoute,
      },
      { path: "/hiring/*", Component: HiringRoute },
      {
        path: "/settings/invitation-email",
        Component: InvitationEmailSettingsRoute,
      },
      { path: "/review/:sessionId", Component: ReviewRoute },
    ],
  },
];
