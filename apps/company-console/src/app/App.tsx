import { BrowserRouter, useRoutes } from "react-router-dom";

import { AppErrorBoundary } from "./AppErrorBoundary";
import { companyRouteObjects } from "./featureRoutes";

export function CompanyRoutes() {
  return useRoutes(companyRouteObjects);
}

export function App() {
  return (
    <AppErrorBoundary>
      <BrowserRouter>
        <CompanyRoutes />
      </BrowserRouter>
    </AppErrorBoundary>
  );
}
