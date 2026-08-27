import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { CompanyRoutes } from "../App";

describe("company feature routes", () => {
  it.each([
    ["/", "채용의 확신은 ‘느낌’이 아니라 ‘확실한 근거’에서 나옵니다."],
    ["/auth/login", "기업 로그인"],
    ["/auth/signup", "기업 계정 만들기"],
    ["/company", "채용 운영 대시보드"],
    ["/ai-assistant", "AI 채용 어시스턴트"],
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
    expect(screen.getByRole("link", { name: "AI 어시스턴트" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "채용 관리" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "초대 메일 템플릿" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "AI 면접관" })).toBeNull();
    expect(screen.queryByRole("button", { name: "지원자 화면" })).toBeNull();
    expect(screen.queryByRole("button", { name: "알림" })).toBeNull();
    expect(screen.getByRole("link", { name: "WhyYou 홈" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "WhyYou" })).toBeTruthy();
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

  it("opens the local company console through the judge demo action", async () => {
    render(
      <MemoryRouter initialEntries={["/auth/login"]}>
        <CompanyRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole("img", { name: "WhyYou" })).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", { name: "데모 아이디로 들어가기" }),
    );

    expect(
      await screen.findByRole("heading", { name: "채용 운영 대시보드" }),
    ).toBeTruthy();
  });

  it("keeps the public landing page outside the enterprise shell", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <CompanyRoutes />
      </MemoryRouter>,
    );

    expect(screen.queryByLabelText("기업 콘솔 주 탐색")).toBeNull();
    expect(
      screen.getAllByRole("link", { name: "기업 콘솔 로그인" }),
    ).toHaveLength(2);
    expect(
      screen.getByRole("navigation", { name: "랜딩페이지 탐색" }),
    ).toBeTruthy();
  });
});
