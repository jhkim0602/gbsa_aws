import { BrowserRouter, useRoutes } from "react-router-dom";

import { companyRouteObjects } from "./featureRoutes";

export function CompanyRoutes() {
  return useRoutes(companyRouteObjects);
}

export function App() {
  return (
    <BrowserRouter>
      <CompanyRoutes />
    </BrowserRouter>
  );
}
