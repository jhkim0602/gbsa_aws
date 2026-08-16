import type { RouteObject } from "react-router-dom";

import { ApplicantShell } from "./ApplicantShell";
import {
  AccessRoute,
  ApplicantHomeRoute,
  InterviewRoute,
  SubmissionsRoute,
} from "./routeAdapters";

export type FeatureRoute = Readonly<{
  path: string;
  feature: "access" | "submissions" | "interview";
  ownerLane: "A" | "B" | "C";
}>;

export const applicantFeatureRoutes = [
  { path: "/access/*", feature: "access", ownerLane: "A" },
  { path: "/submissions/*", feature: "submissions", ownerLane: "B" },
  { path: "/interview/*", feature: "interview", ownerLane: "C" },
] as const satisfies readonly FeatureRoute[];

export const applicantRouteObjects: RouteObject[] = [
  {
    path: "/",
    Component: ApplicantShell,
    children: [
      { index: true, Component: ApplicantHomeRoute },
      { path: "access", Component: AccessRoute },
      { path: "access/:token", Component: AccessRoute },
      { path: "submissions/*", Component: SubmissionsRoute },
      { path: "interview/*", Component: InterviewRoute },
    ],
  },
];
