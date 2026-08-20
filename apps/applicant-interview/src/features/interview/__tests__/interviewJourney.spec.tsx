import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Avatar } from "../Avatar";
import { EquipmentCheck, type EquipmentCheckApi } from "../EquipmentCheck";
import { InterviewRoom } from "../InterviewRoom";

describe("applicant interview journey", () => {
  it("checks browser devices before allowing the interview to start", async () => {
    const api: EquipmentCheckApi = {
      check: vi.fn().mockResolvedValue({
        camera: { status: "ready" },
        microphone: { status: "ready" },
        network: { status: "warning", sanitizedCode: "NETWORK_JITTER" },
        overallStatus: "warning",
      }),
    };
    const onReady = vi.fn();
    render(<EquipmentCheck api={api} onReady={onReady} />);

    expect(
      screen.getByText("기술 문제는 면접 평가에 영향을 주지 않습니다."),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "면접 시작" })).toHaveProperty(
      "disabled",
      true,
    );
    fireEvent.click(screen.getByRole("button", { name: "장치 점검" }));

    expect(await screen.findByText("카메라 준비됨")).toBeTruthy();
    expect(screen.getByText("마이크 준비됨")).toBeTruthy();
    expect(screen.getByText("네트워크 확인 필요")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "면접 시작" }));
    expect(onReady).toHaveBeenCalledOnce();
  });

  it("supports answer completion, reconnect, and text-only question delivery", () => {
    const onStartAnswer = vi.fn();
    const onCompleteAnswer = vi.fn();
    const onReconnect = vi.fn();
    const onAddExplanation = vi.fn();
    const { rerender } = render(
      <InterviewRoom
        question="최근 장애의 원인을 좁힌 순서를 설명해 주세요?"
        state="awaiting_answer"
        connectionState="connected"
        textOnly={false}
        interviewerLevel="junior"
        onStartAnswer={onStartAnswer}
        onCompleteAnswer={onCompleteAnswer}
        onReconnect={onReconnect}
        onAddExplanation={onAddExplanation}
      />,
    );

    expect(
      screen.getByText("AI가 질문을 진행하며 최종 판단은 사람이 합니다."),
    ).toBeTruthy();
    expect(screen.getByRole("img", { name: "주니어 AI 면접관" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "화면 옵션" }));
    fireEvent.click(
      screen.getByRole("menuitem", { name: "작은 창(PiP)으로 보기" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "화면 옵션" }));
    expect(
      screen.getByRole("menuitem", { name: "분할 화면으로 보기" }),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "답변 시작" }));
    expect(onStartAnswer).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "답변 완료" }));
    expect(onCompleteAnswer).toHaveBeenCalledOnce();
    fireEvent.click(
      screen.getByRole("button", { name: "정정 또는 추가 설명" }),
    );
    expect(onAddExplanation).toHaveBeenCalledOnce();

    rerender(
      <InterviewRoom
        question="최근 장애의 원인을 좁힌 순서를 설명해 주세요?"
        state="paused"
        connectionState="reconnecting"
        textOnly
        onStartAnswer={onStartAnswer}
        onCompleteAnswer={onCompleteAnswer}
        onReconnect={onReconnect}
        onAddExplanation={onAddExplanation}
      />,
    );
    expect(
      screen.getByText(
        "연결을 복구하고 있습니다. 녹화 조각은 이 기기에 보관됩니다.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("음성 없이 질문을 표시합니다.")).toBeTruthy();
    expect(
      screen.getByText(
        "기술적인 이유로 면접이 일시 중지되었습니다. 이 상태는 평가에 반영되지 않습니다.",
      ),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "다시 연결" }));
    expect(onReconnect).toHaveBeenCalledOnce();

    rerender(
      <InterviewRoom
        question="최근 장애의 원인을 좁힌 순서를 설명해 주세요?"
        state="completed"
        connectionState="connected"
        textOnly={false}
        onStartAnswer={onStartAnswer}
        onCompleteAnswer={onCompleteAnswer}
        onReconnect={onReconnect}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "면접을 완료하셨습니다" }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "답변 시작" })).toBeNull();
  });

  it("keeps avatar timing optional in text-only mode", () => {
    const { rerender } = render(
      <Avatar textOnly={false} speaking speechMarkIndex={2} />,
    );
    expect(screen.getByLabelText("AI 면접관 발화 중")).toBeTruthy();

    rerender(<Avatar textOnly speaking={false} speechMarkIndex={0} />);
    expect(screen.getByText("음성 없이 질문을 표시합니다.")).toBeTruthy();
  });

  it("animates the interviewer mouth during speech and blinks", () => {
    vi.useFakeTimers();
    try {
      const { rerender } = render(
        <Avatar textOnly={false} speaking speechMarkIndex={0} level="entry" />,
      );
      const avatar = screen.getByLabelText("AI 면접관 발화 중");
      const image = screen.getByRole("img", { name: "신입 AI 면접관" });

      expect(avatar.getAttribute("data-mouth")).toBe("mid");
      expect(image.getAttribute("src")).toBe(
        "/interviewers/entry_eyes_open_mouth_mid.webp",
      );

      act(() => vi.advanceTimersByTime(140));
      expect(avatar.getAttribute("data-mouth")).toBe("open");

      act(() => vi.advanceTimersByTime(3060));
      expect(avatar.getAttribute("data-eyes")).toBe("closed");

      act(() => vi.advanceTimersByTime(140));
      expect(avatar.getAttribute("data-eyes")).toBe("open");

      rerender(
        <Avatar
          textOnly={false}
          speaking={false}
          speechMarkIndex={0}
          level="entry"
        />,
      );
      expect(avatar.getAttribute("data-mouth")).toBe("closed");
    } finally {
      vi.useRealTimers();
    }
  });
});
