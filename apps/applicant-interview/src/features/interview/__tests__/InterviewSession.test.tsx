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

  it("waits for interviewer audio to finish before an automated answer", async () => {
    vi.useFakeTimers();
    try {
      let onQuestion:
        | ((question: {
            questionTurnId: string;
            text: string;
            textOnly: boolean;
          }) => void)
        | undefined;
      let onQuestionAudioStart:
        ((format: { sampleRateHz: number }) => void) | undefined;
      let onQuestionAudioEnd: (() => void) | undefined;
      let onPlaybackState: ((state: "idle" | "playing") => void) | undefined;
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
      const recorder = {
        start: vi.fn(),
        stop: vi.fn().mockResolvedValue(undefined),
      };
      const audioPlayer = {
        start: vi.fn(
          async (
            _sampleRateHz: number,
            onStateChange: (state: "idle" | "playing") => void,
          ) => {
            onPlaybackState = onStateChange;
          },
        ),
        enqueue: vi.fn(),
        end: vi.fn(),
        stop: vi.fn().mockResolvedValue(undefined),
      };
      const dependencies: Partial<InterviewSessionDependencies> = {
        socketFactory: vi.fn(),
        mediaDevices: { getUserMedia: vi.fn() },
        mediaBuffer: {
          put: vi.fn(),
          list: vi.fn().mockResolvedValue([]),
          removeVerified: vi.fn().mockResolvedValue(undefined),
        },
        createRecorder: vi.fn(() => recorder),
        createAudioCapture: vi.fn(),
        createAudioPlayer: vi.fn(() => audioPlayer),
        createAutomatedMedia: vi.fn().mockResolvedValue({
          stream,
          dispose: vi.fn(),
        }),
        loadAutomatedPcm: vi.fn().mockResolvedValue(new Int16Array()),
        createProtocolClient: vi.fn((input) => {
          onQuestion = input.onQuestion;
          onQuestionAudioStart = input.onQuestionAudioStart;
          onQuestionAudioEnd = input.onQuestionAudioEnd;
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
          sessionId="00000000-0000-7000-8000-000000000540"
          equipmentCheckId="00000000-0000-7000-8000-000000000541"
          websocketUrl="ws://localhost/session"
          recordingApi={{ upload: vi.fn() }}
          dependencies={dependencies}
          automationMode="speech"
        />,
      );

      act(() => {
        onQuestion?.({
          questionTurnId: "00000000-0000-7000-8000-000000000542",
          text: "질문 음성이 끝난 뒤 답변해 주세요.",
          textOnly: false,
        });
        onQuestionAudioStart?.({ sampleRateHz: 24_000 });
      });
      await act(async () => {
        await Promise.resolve();
        await vi.advanceTimersByTimeAsync(5_000);
      });

      expect(recorder.start).not.toHaveBeenCalled();
      expect(protocol.startAnswer).not.toHaveBeenCalled();
      expect(
        (
          screen.getByRole("button", {
            name: "질문 재생 중",
          }) as HTMLButtonElement
        ).disabled,
      ).toBe(true);

      act(() => {
        onPlaybackState?.("playing");
        onQuestionAudioEnd?.();
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1_000);
      });
      expect(recorder.start).not.toHaveBeenCalled();

      act(() => {
        onPlaybackState?.("idle");
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(900);
      });

      expect(recorder.start).toHaveBeenCalledWith(stream);
      expect(protocol.startAnswer).toHaveBeenCalledOnce();
    } finally {
      vi.useRealTimers();
    }
  });

  it("continues when the next fast interview question arrives immediately", async () => {
    vi.useFakeTimers();
    try {
      let onQuestion:
        | ((question: {
            questionTurnId: string;
            text: string;
            textOnly: boolean;
          }) => void)
        | undefined;
      const protocol = {
        connect: vi.fn(),
        disconnect: vi.fn(),
        startAnswer: vi.fn(),
        completeAnswer: vi.fn(),
        sendAudioFrame: vi.fn(),
        repeatQuestion: vi.fn(),
        submitAutomatedAnswer: vi.fn(() => {
          onQuestion?.({
            questionTurnId: "00000000-0000-7000-8000-000000000525",
            text: "문제의 원인을 어떻게 해결했나요?",
            textOnly: true,
          });
        }),
      };
      const stream = {
        getTracks: () => [],
      } as unknown as MediaStream;
      const recorder = {
        start: vi.fn(),
        stop: vi.fn().mockResolvedValue(undefined),
      };
      const dependencies: Partial<InterviewSessionDependencies> = {
        socketFactory: vi.fn(),
        mediaDevices: { getUserMedia: vi.fn() },
        mediaBuffer: {
          put: vi.fn(),
          list: vi.fn().mockResolvedValue([]),
          removeVerified: vi.fn().mockResolvedValue(undefined),
        },
        createRecorder: vi.fn(() => recorder),
        createAudioCapture: vi.fn(),
        createAutomatedMedia: vi.fn().mockResolvedValue({
          stream,
          dispose: vi.fn(),
        }),
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
          sessionId="00000000-0000-7000-8000-000000000523"
          equipmentCheckId="00000000-0000-7000-8000-000000000524"
          websocketUrl="ws://localhost/session"
          recordingApi={{ upload: vi.fn() }}
          dependencies={dependencies}
          automationMode="fast"
        />,
      );

      act(() => {
        onQuestion?.({
          questionTurnId: "00000000-0000-7000-8000-000000000526",
          text: "문제를 발견한 경험을 설명해 주세요.",
          textOnly: true,
        });
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3100);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3100);
      });

      expect(dependencies.createRecorder).toHaveBeenCalledTimes(2);
      expect(protocol.submitAutomatedAnswer).toHaveBeenCalledTimes(2);
      expect(protocol.submitAutomatedAnswer).toHaveBeenLastCalledWith({
        answerTurnId: expect.any(String),
        text: expect.stringContaining("문제의 원인을 어떻게 해결했나요?"),
        lastRecordingChunkSequence: 0,
      });
    } finally {
      vi.useRealTimers();
    }
  });

  it("retries the same fast interview question after reconnecting", async () => {
    vi.useFakeTimers();
    try {
      let sessionStore:
        | Parameters<
            InterviewSessionDependencies["createProtocolClient"]
          >[0]["store"]
        | undefined;
      let onQuestion:
        | ((question: {
            questionTurnId: string;
            text: string;
            textOnly: boolean;
          }) => void)
        | undefined;
      const protocol = {
        connect: vi.fn(() => {
          sessionStore?.getState().setConnectionState("connected");
        }),
        disconnect: vi.fn(() => {
          sessionStore?.getState().setConnectionState("reconnecting");
        }),
        startAnswer: vi.fn(),
        completeAnswer: vi.fn(),
        sendAudioFrame: vi.fn(),
        repeatQuestion: vi.fn(),
        submitAutomatedAnswer: vi.fn(),
      };
      const failedRecorder = {
        start: vi.fn(),
        stop: vi
          .fn()
          .mockRejectedValueOnce(new Error("applicant request failed: 409"))
          .mockResolvedValue(undefined),
      };
      const retriedRecorder = {
        start: vi.fn(),
        stop: vi.fn().mockResolvedValue(undefined),
      };
      const stream = {
        getTracks: () => [],
      } as unknown as MediaStream;
      const dependencies: Partial<InterviewSessionDependencies> = {
        socketFactory: vi.fn(),
        mediaDevices: { getUserMedia: vi.fn() },
        mediaBuffer: {
          put: vi.fn(),
          list: vi.fn().mockResolvedValue([]),
          removeVerified: vi.fn().mockResolvedValue(undefined),
        },
        createRecorder: vi
          .fn()
          .mockReturnValueOnce(failedRecorder)
          .mockReturnValueOnce(retriedRecorder),
        createAudioCapture: vi.fn(),
        createAutomatedMedia: vi.fn().mockResolvedValue({
          stream,
          dispose: vi.fn(),
        }),
        createProtocolClient: vi.fn((input) => {
          sessionStore = input.store;
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
          sessionId="00000000-0000-7000-8000-000000000530"
          equipmentCheckId="00000000-0000-7000-8000-000000000531"
          websocketUrl="ws://localhost/session"
          recordingApi={{ upload: vi.fn() }}
          dependencies={dependencies}
          automationMode="fast"
        />,
      );

      act(() => {
        onQuestion?.({
          questionTurnId: "00000000-0000-7000-8000-000000000532",
          text: "재연결 테스트 질문입니다.",
          textOnly: true,
        });
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3100);
      });

      expect(
        screen.getByText("자동 면접 오류: applicant request failed: 409"),
      ).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: "다시 연결" }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(protocol.connect).toHaveBeenCalledTimes(2);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3100);
      });

      expect(dependencies.createRecorder).toHaveBeenCalledTimes(2);
      expect(protocol.submitAutomatedAnswer).toHaveBeenCalledOnce();
      expect(protocol.submitAutomatedAnswer).toHaveBeenCalledWith({
        answerTurnId: expect.any(String),
        text: expect.stringContaining("재연결 테스트 질문입니다."),
        lastRecordingChunkSequence: 0,
      });
    } finally {
      vi.useRealTimers();
    }
  });
});
