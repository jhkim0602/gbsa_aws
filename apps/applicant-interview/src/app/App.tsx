import { BrowserRouter, useRoutes } from "react-router-dom";

import { applicantRouteObjects } from "./featureRoutes";

export function ApplicantRoutes() {
  return useRoutes(applicantRouteObjects);
}

export function App() {
  return (
    <BrowserRouter>
      <ApplicantRoutes />
    </BrowserRouter>
  );
}
