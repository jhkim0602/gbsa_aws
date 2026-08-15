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
