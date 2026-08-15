import type { RouteObject } from "react-router-dom";

import { CompanyHomeRoute, HiringRoute, ReviewRoute } from "./routeAdapters";

export type FeatureRoute = Readonly<{
  path: string;
  feature: "company" | "hiring" | "review";
  ownerLane: "A" | "D";
}>;

export const companyFeatureRoutes = [
  { path: "/company", feature: "company", ownerLane: "A" },
  { path: "/hiring/*", feature: "hiring", ownerLane: "A" },
  { path: "/review/*", feature: "review", ownerLane: "D" },
] as const satisfies readonly FeatureRoute[];

export const companyRouteObjects: RouteObject[] = [
  { path: "/", Component: CompanyHomeRoute },
  { path: "/company", Component: CompanyHomeRoute },
  { path: "/hiring/*", Component: HiringRoute },
  { path: "/review/:sessionId", Component: ReviewRoute },
];
