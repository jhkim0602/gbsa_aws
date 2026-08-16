import type { RouteObject } from "react-router-dom";

import {
  ApplicantDetailRoute,
  ApplicantManagementRoute,
  CompanyAuthCallbackRoute,
  CompanyHomeRoute,
  CompanyLoginRoute,
  CompanyPositionsRoute,
  HiringRoute,
  PositionOperationsRoute,
  ReviewRoute,
} from "./routeAdapters";
import { CompanyShell } from "./layouts/CompanyShell";

export type FeatureRoute = Readonly<{
  path: string;
  feature: "company" | "hiring" | "review";
  ownerLane: "A" | "D";
}>;

export const companyFeatureRoutes = [
  { path: "/company", feature: "company", ownerLane: "A" },
  { path: "/positions", feature: "company", ownerLane: "A" },
  { path: "/positions/:positionId", feature: "company", ownerLane: "A" },
  { path: "/applicants", feature: "company", ownerLane: "A" },
  {
    path: "/positions/:positionId/applicants/:invitationId",
    feature: "company",
    ownerLane: "A",
  },
  { path: "/hiring/*", feature: "hiring", ownerLane: "A" },
  { path: "/review/*", feature: "review", ownerLane: "D" },
] as const satisfies readonly FeatureRoute[];

export const companyRouteObjects: RouteObject[] = [
  { path: "/auth/login", Component: CompanyLoginRoute },
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
      { path: "/review/:sessionId", Component: ReviewRoute },
    ],
  },
];
