import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { CompanyRoutes } from "../App";

describe("company feature routes", () => {
  it.each([
    ["/auth/login", "기업 로그인"],
    ["/company", "채용 운영 대시보드"],
    ["/hiring", "포지션 만들기"],
    ["/review/00000000-0000-7000-8000-000000000001", "지원자 검토"],
    ["/settings/invitation-email", "초대 메일 템플릿"],
  ])(
    "renders %s through the integration route registry",
    async (path, heading) => {
      render(
        <MemoryRouter initialEntries={[path]}>
          <CompanyRoutes />
        </MemoryRouter>,
      );

      expect(
        await screen.findByRole("heading", { name: heading }),
      ).toBeTruthy();
    },
  );

  it("renders the enterprise application shell around protected workflows", () => {
    render(
      <MemoryRouter initialEntries={["/hiring"]}>
        <CompanyRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("기업 콘솔 주 탐색")).toBeTruthy();
    expect(screen.getByRole("link", { name: "대시보드" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "채용 포지션" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "지원자 관리" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "채용 관리" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "초대 메일 템플릿" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "AI 면접관" })).toBeNull();
    expect(screen.getAllByRole("link", { name: "지원자 화면" })).toHaveLength(
      2,
    );
    expect(screen.getByText("InterviewEP")).toBeTruthy();
    expect(screen.getByRole("button", { name: "사용자 메뉴" })).toBeTruthy();
  });

  it("keeps authentication screens outside the enterprise shell", () => {
    render(
      <MemoryRouter initialEntries={["/auth/login"]}>
        <CompanyRoutes />
      </MemoryRouter>,
    );

    expect(screen.queryByLabelText("기업 콘솔 주 탐색")).toBeNull();
  });
});
