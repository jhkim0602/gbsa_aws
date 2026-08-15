import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { CompanyRoutes } from "../App";

describe("company feature routes", () => {
  it.each([
    ["/hiring", "채용 캠페인"],
    ["/review/00000000-0000-7000-8000-000000000001", "지원자 검토"],
  ])("renders %s through the integration route registry", (path, heading) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <CompanyRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
  });
});
