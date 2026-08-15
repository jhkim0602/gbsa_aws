import { fireEvent, render, screen } from "@testing-library/react";
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
        onStartAnswer={onStartAnswer}
        onCompleteAnswer={onCompleteAnswer}
        onReconnect={onReconnect}
        onAddExplanation={onAddExplanation}
      />,
    );

    expect(
      screen.getByText("AI가 질문을 진행하며 최종 판단은 사람이 합니다."),
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
  });

  it("keeps avatar timing optional in text-only mode", () => {
    const { rerender } = render(
      <Avatar textOnly={false} speaking speechMarkIndex={2} />,
    );
    expect(screen.getByLabelText("AI 면접관 발화 중")).toBeTruthy();

    rerender(<Avatar textOnly speaking={false} speechMarkIndex={0} />);
    expect(screen.getByText("음성 없이 질문을 표시합니다.")).toBeTruthy();
  });
});
