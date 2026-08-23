import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LandingPage } from "../LandingPage";

function renderLanding() {
  render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  );
}

describe("public enterprise landing page", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("moves between real company-console screens in the hero carousel", () => {
    renderLanding();

    fireEvent.click(screen.getByRole("button", { name: "AI 어시스턴트" }));

    expect(
      screen.getByRole("img", {
        name: "WhyYou AI 채용 어시스턴트 대화 화면",
      }),
    ).toBeTruthy();
    expect(screen.queryByText("담당자 검토")).toBeNull();
    expect(screen.queryByText("답변 근거 충족")).toBeNull();
  });

  it("switches the interviewer persona from junior to senior", () => {
    renderLanding();

    expect(screen.getByText("실무형 면접관")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "시니어" }));

    expect(screen.getByText("심층형 면접관")).toBeTruthy();
    expect(
      screen.getByText("대안과 장기적 영향을 깊이 확인합니다."),
    ).toBeTruthy();
  });

  it("moves the four-card hiring flow without document scrolling", () => {
    renderLanding();

    expect(
      screen
        .getByRole("button", { name: "1번 단계부터 보기" })
        .getAttribute("aria-pressed"),
    ).toBe("true");

    fireEvent.click(
      screen.getByRole("button", { name: "다음 채용 단계 보기" }),
    );

    expect(
      screen
        .getByRole("button", { name: "2번 단계부터 보기" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("automatically shows the real hiring setup screens without cropping", () => {
    vi.useFakeTimers();
    renderLanding();

    expect(
      screen.getByRole("img", {
        name: "포지션명과 채용 일정을 설정하는 실제 기업 콘솔 화면",
      }),
    ).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(7200);
    });

    expect(
      screen.getByRole("img", {
        name: "자격요건과 평가 가중치를 설계하는 실제 기업 콘솔 화면",
      }),
    ).toBeTruthy();
  });

  it("moves the hiring setup screen with the previous and next controls", () => {
    renderLanding();

    fireEvent.click(
      screen.getByRole("button", {
        name: "다음 채용 설정 화면 갤러리",
      }),
    );

    expect(
      screen.getByRole("img", {
        name: "지원자에게 받을 제출 자료를 선택하는 실제 기업 콘솔 화면",
      }),
    ).toBeTruthy();
  });

  it("renders the hiring setup tour inside the hero design screen", () => {
    renderLanding();

    fireEvent.click(screen.getByRole("button", { name: "면접 설계" }));

    expect(
      screen.getByRole("region", {
        name: "히어로 면접 설계 화면 갤러리",
      }),
    ).toBeTruthy();
  });

  it("opens the captured applicant evidence screen from the assistant showcase", () => {
    renderLanding();

    fireEvent.click(
      screen.getByRole("button", {
        name: "다음 AI 어시스턴트 근거 화면 갤러리",
      }),
    );

    expect(
      screen.getByRole("img", {
        name: "AI 채용 어시스턴트에서 검색 근거를 클릭해 연 지원자 평가 요약서",
      }),
    ).toBeTruthy();
  });

  it("describes the separated RAG stores and removes the redundant sections", () => {
    renderLanding();

    expect(
      screen.getByRole("heading", {
        name: "두 RAG 저장소를, 쓰임에 맞게 분리했습니다.",
      }),
    ).toBeTruthy();
    expect(
      screen.getByText(/retrieval_documents · applicant scoped/),
    ).toBeTruthy();
    expect(
      screen.getByText(/assistant_retrieval_documents · tenant scoped/),
    ).toBeTruthy();
    expect(screen.queryByText("담당자의 실제 채용 업무를 중심으로")).toBeNull();
    expect(screen.queryByText("AI는 분석하고, 사람은 결정합니다.")).toBeNull();
  });
});
