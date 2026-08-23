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

    expect(navigation.className).toContain(
      "mw-760:[transform:translateX(-105%)]",
    );

    fireEvent.click(screen.getByRole("button", { name: "탐색 열기" }));
    expect(navigation.className).toContain("mw-760:[transform:translateX(0)]");
    fireEvent.click(screen.getByRole("button", { name: "탐색 닫기" }));
    expect(navigation.className).toContain(
      "mw-760:[transform:translateX(-105%)]",
    );

    fireEvent.click(screen.getByRole("button", { name: "탐색 접기" }));

    expect(navigation.getAttribute("aria-hidden")).toBeNull();
    expect(navigation.className).toContain("w-16");
    expect(shell.className).toContain("grid-cols-[64px_minmax(0,1fr)]");
    expect(screen.queryByText("대시보드")).toBeNull();
    expect(
      screen.getByRole("link", { name: "대시보드" }).querySelector("svg"),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "탐색 펼치기" }));

    expect(navigation.getAttribute("aria-hidden")).toBeNull();
    expect(navigation.className).toContain("w-56");
    expect(shell.className).toContain("grid-cols-[224px_minmax(0,1fr)]");

    const applicantLinks = screen.getAllByRole("link", {
      name: "지원자 화면",
    });
    expect(applicantLinks).toHaveLength(2);
    applicantLinks.forEach((link) => {
      expect(link.getAttribute("target")).toBe("_blank");
      expect(link.getAttribute("rel")).toContain("noreferrer");
    });
  });
});
