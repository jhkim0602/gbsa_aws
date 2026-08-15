import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ApplicantRoutes } from "../App";
import { serializeEquipmentComponent } from "../routeAdapters";

describe("applicant feature routes", () => {
  it.each([
    ["/access/token-value", "지원자 면접"],
    ["/submissions", "면접 자료 제출"],
    ["/interview", "면접 환경 점검"],
  ])("renders %s through the integration route registry", (path, heading) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <ApplicantRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
  });

  it("serializes browser equipment results to the frozen HTTP contract", async () => {
    const serialized = serializeEquipmentComponent({
      status: "failed",
      sanitizedCode: "CAMERA_UNAVAILABLE",
    });

    expect(serialized).toEqual({
      status: "failed",
      sanitized_code: "CAMERA_UNAVAILABLE",
    });
    expect(serialized).not.toHaveProperty("sanitizedCode");
  });
});
