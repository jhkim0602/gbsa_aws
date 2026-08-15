import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  InterviewSession,
  type InterviewSessionDependencies,
} from "../InterviewSession";
import type { StoredMediaChunk } from "../media";

describe("InterviewSession", () => {
  it("connects server state to media capture and answer completion", async () => {
    const protocol = {
      connect: vi.fn(),
      disconnect: vi.fn(),
      completeAnswer: vi.fn(),
      sendAudioFrame: vi.fn(),
      repeatQuestion: vi.fn(),
    };
    const stopTrack = vi.fn();
    const stream = {
      getTracks: () => [{ stop: stopTrack }],
    } as unknown as MediaStream;
    const mediaBuffer = {
      put: vi.fn(),
      list: vi.fn().mockResolvedValue([]),
      removeVerified: vi.fn().mockResolvedValue(undefined),
    };
    const recorder = { start: vi.fn(), stop: vi.fn() };
    const audioCapture = {
      start: vi.fn().mockResolvedValue(undefined),
      stop: vi.fn().mockResolvedValue(undefined),
    };
    let onQuestion:
      | ((question: {
          questionTurnId: string;
          text: string;
          textOnly: boolean;
        }) => void)
      | undefined;
    const dependencies: Partial<InterviewSessionDependencies> = {
      socketFactory: vi.fn(),
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
      mediaBuffer,
      createRecorder: vi.fn(() => recorder),
      createAudioCapture: vi.fn(() => audioCapture),
      createProtocolClient: vi.fn((input) => {
        onQuestion = input.onQuestion;
        input.store.getState().setConnectionState("connected");
        input.store.getState().applyServerState({
          state: "awaiting_answer",
          serverSequence: 1,
          lastFinalTurnId: null,
          lastVerifiedRecordingChunkSequence: 0,
          degradedModes: [],
        });
        return protocol;
      }),
    };

    render(
      <InterviewSession
        sessionId="00000000-0000-7000-8000-000000000501"
        equipmentCheckId="00000000-0000-7000-8000-000000000511"
        websocketUrl="ws://localhost/session"
        recordingApi={{ upload: vi.fn() }}
        dependencies={dependencies}
      />,
    );

    expect(protocol.connect).toHaveBeenCalledOnce();
    onQuestion?.({
      questionTurnId: "00000000-0000-7000-8000-000000000502",
      text: "장애 복구 순서를 설명해 주세요.",
      textOnly: true,
    });
    expect(
      await screen.findByText("장애 복구 순서를 설명해 주세요."),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "답변 시작" }));
    await waitFor(() => expect(recorder.start).toHaveBeenCalledWith(stream));
    expect(audioCapture.start).toHaveBeenCalledWith(
      stream,
      expect.any(Function),
    );

    fireEvent.click(screen.getByRole("button", { name: "답변 완료" }));
    await waitFor(() => expect(protocol.completeAnswer).toHaveBeenCalledOnce());
    expect(recorder.stop).toHaveBeenCalledOnce();
    expect(stopTrack).toHaveBeenCalledOnce();
  });

  it("replays locally buffered recording chunks after reconnect", async () => {
    const buffered: StoredMediaChunk = {
      sessionId: "00000000-0000-7000-8000-000000000503",
      sequence: 2,
      blob: new Blob(["recording"]),
      byteSize: 9,
      sha256: "b".repeat(64),
      sessionStartMs: 0,
      sessionEndMs: 2000,
    };
    const upload = vi.fn().mockResolvedValue(undefined);
    const protocol = {
      connect: vi.fn(),
      disconnect: vi.fn(),
      completeAnswer: vi.fn(),
      sendAudioFrame: vi.fn(),
      repeatQuestion: vi.fn(),
    };
    const dependencies: Partial<InterviewSessionDependencies> = {
      socketFactory: vi.fn(),
      mediaDevices: { getUserMedia: vi.fn() },
      mediaBuffer: {
        put: vi.fn(),
        list: vi.fn().mockResolvedValue([buffered]),
        removeVerified: vi.fn().mockResolvedValue(undefined),
      },
      createRecorder: vi.fn(),
      createAudioCapture: vi.fn(),
      createProtocolClient: vi.fn((input) => {
        input.store.getState().setConnectionState("reconnecting");
        return protocol;
      }),
    };

    render(
      <InterviewSession
        sessionId={buffered.sessionId}
        equipmentCheckId="00000000-0000-7000-8000-000000000512"
        websocketUrl="ws://localhost/session"
        recordingApi={{ upload }}
        dependencies={dependencies}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "다시 연결" }));
    await waitFor(() => expect(upload).toHaveBeenCalledWith(buffered));
    expect(protocol.connect).toHaveBeenCalledTimes(2);
  });
});
