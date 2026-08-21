import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { CompanyShell } from "../layouts/CompanyShell";

describe("CompanyShell", () => {
  it("collapses and reopens the primary navigation", () => {
    render(
      <MemoryRouter initialEntries={["/ai-assistant"]}>
        <Routes>
          <Route element={<CompanyShell />}>
            <Route path="/ai-assistant" element={<h1>AI 채용 어시스턴트</h1>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    const navigation = screen.getByLabelText("기업 콘솔 주 탐색");
    const shell = navigation.parentElement!;

    fireEvent.click(screen.getByRole("button", { name: "탐색 닫기" }));

    expect(navigation.getAttribute("aria-hidden")).toBe("true");
    expect(navigation.className).toContain("invisible");
    expect(shell.className).toContain("grid-cols-[0_minmax(0,1fr)]");

    fireEvent.click(screen.getByRole("button", { name: "탐색 열기" }));

    expect(navigation.getAttribute("aria-hidden")).toBeNull();
    expect(navigation.className).not.toContain("invisible");
    expect(shell.className).toContain("grid-cols-[224px_minmax(0,1fr)]");
  });
});
