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
