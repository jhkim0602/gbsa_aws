import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
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
      startAnswer: vi.fn(),
      completeAnswer: vi.fn(),
      sendAudioFrame: vi.fn(),
      repeatQuestion: vi.fn(),
      submitAutomatedAnswer: vi.fn(),
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
    let sessionStore:
      | Parameters<
          InterviewSessionDependencies["createProtocolClient"]
        >[0]["store"]
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
        sessionStore = input.store;
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

    const onComplete = vi.fn();
    render(
      <InterviewSession
        sessionId="00000000-0000-7000-8000-000000000501"
        equipmentCheckId="00000000-0000-7000-8000-000000000511"
        websocketUrl="ws://localhost/session"
        recordingApi={{ upload: vi.fn() }}
        dependencies={dependencies}
        onComplete={onComplete}
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
    expect(protocol.startAnswer).toHaveBeenCalledWith({
      answerTurnId: expect.any(String),
      sampleRateHz: 16000,
    });
    expect(audioCapture.start).toHaveBeenCalledWith(
      stream,
      expect.any(Function),
    );

    fireEvent.click(screen.getByRole("button", { name: "답변 완료" }));
    await waitFor(() => expect(protocol.completeAnswer).toHaveBeenCalledOnce());
    expect(recorder.stop).toHaveBeenCalledOnce();
    expect(stopTrack).toHaveBeenCalledOnce();

    act(() => {
      sessionStore?.getState().applyServerState({
        state: "completed",
        serverSequence: 2,
        lastFinalTurnId: "00000000-0000-7000-8000-000000000503",
        lastVerifiedRecordingChunkSequence: 0,
        degradedModes: [],
      });
    });
    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());
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
      startAnswer: vi.fn(),
      completeAnswer: vi.fn(),
      sendAudioFrame: vi.fn(),
      repeatQuestion: vi.fn(),
      submitAutomatedAnswer: vi.fn(),
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

  it("runs the fast local interview without camera or microphone access", async () => {
    vi.useFakeTimers();
    try {
      const protocol = {
        connect: vi.fn(),
        disconnect: vi.fn(),
        startAnswer: vi.fn(),
        completeAnswer: vi.fn(),
        sendAudioFrame: vi.fn(),
        repeatQuestion: vi.fn(),
        submitAutomatedAnswer: vi.fn(),
      };
      const stream = {
        getTracks: () => [],
      } as unknown as MediaStream;
      const mediaDevices = { getUserMedia: vi.fn() };
      const recorder = {
        start: vi.fn(),
        stop: vi.fn().mockResolvedValue(undefined),
      };
      const dispose = vi.fn();
      let onQuestion:
        | ((question: {
            questionTurnId: string;
            text: string;
            textOnly: boolean;
          }) => void)
        | undefined;
      const dependencies: Partial<InterviewSessionDependencies> = {
        socketFactory: vi.fn(),
        mediaDevices,
        mediaBuffer: {
          put: vi.fn(),
          list: vi.fn().mockResolvedValue([]),
          removeVerified: vi.fn().mockResolvedValue(undefined),
        },
        createRecorder: vi.fn(() => recorder),
        createAudioCapture: vi.fn(),
        createAutomatedMedia: vi.fn().mockResolvedValue({ stream, dispose }),
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
          sessionId="00000000-0000-7000-8000-000000000520"
          equipmentCheckId="00000000-0000-7000-8000-000000000521"
          websocketUrl="ws://localhost/session"
          recordingApi={{ upload: vi.fn() }}
          dependencies={dependencies}
          automationMode="fast"
        />,
      );

      act(() => {
        onQuestion?.({
          questionTurnId: "00000000-0000-7000-8000-000000000522",
          text: "장애 대응 경험을 설명해 주세요.",
          textOnly: true,
        });
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(900);
        await vi.advanceTimersByTimeAsync(2200);
      });

      expect(mediaDevices.getUserMedia).not.toHaveBeenCalled();
      expect(protocol.startAnswer).not.toHaveBeenCalled();
      expect(recorder.start).toHaveBeenCalledWith(stream);
      expect(protocol.submitAutomatedAnswer).toHaveBeenCalledWith({
        answerTurnId: expect.any(String),
        text: expect.stringContaining("장애 대응 경험을 설명해 주세요."),
        lastRecordingChunkSequence: 0,
      });
      expect(dispose).toHaveBeenCalledOnce();
    } finally {
      vi.useRealTimers();
    }
  });
});
