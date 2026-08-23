import {
  CameraOff,
  Captions,
  Clock3,
  EllipsisVertical,
  Mic,
  MicOff,
  PictureInPicture2,
  RefreshCcw,
  SplitSquareHorizontal,
  VideoOff,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Avatar, INTERVIEWER_LEVELS, type InterviewerLevel } from "./Avatar";
import { InterviewComplete } from "./InterviewComplete";
import type { ConnectionState, InterviewState } from "./sessionStore";

// `interview-room` declares nothing itself — it is a hook two ancestor selectors in
// `app/styles/shell.css` read, so it is not convertible to a utility and stays:
//   .applicant-app:has(.interview-room) > .applicant-product-bar { display: none }
//   .applicant-content > main:not(.interview-room) { width; margin-inline; padding-block }
// The first hides the journey bar for this full-bleed room; nothing on this element can reach
// an ancestor's sibling. The second is an opt-out the class keeps this <main> excluded from.
// `interview-shell` is gone: both rules naming it are gated on `:not(.interview-room)`, which
// this element always matches away, so it never applied here.
const SHELL =
  "interview-room min-h-screen w-full max-w-none bg-canvas px-4 py-5" +
  " text-slate-950 sm:px-6 lg:px-10 lg:py-8";

const CANDIDATE_PANEL =
  "relative min-h-[320px] overflow-hidden rounded-lg border border-slate-200" +
  " bg-slate-50 shadow-sm";

const STAGE_LABEL =
  "absolute left-4 top-4 z-20 inline-flex h-10 items-center gap-2 rounded-lg" +
  " border border-slate-200 bg-white/95 px-3 text-sm font-semibold" +
  " text-slate-900 shadow-sm";

const PANEL_MENU_TRIGGER =
  "grid size-10 place-items-center rounded-lg border border-slate-200" +
  " bg-white/95 text-slate-600 shadow-sm transition hover:bg-slate-100" +
  " hover:text-slate-950";

const PANEL_MENU_ITEM =
  "flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm" +
  " font-medium text-slate-700 hover:bg-slate-100";

const HEADER_PILL =
  "inline-flex h-10 items-center gap-2 rounded-full border border-slate-200" +
  " bg-white px-4 shadow-sm";

// No `position` here on purpose: the split-view frame is `relative` and the PiP frame is
// `absolute`, and Tailwind emits `.relative` after `.absolute`, so sharing one would pin both
// to `relative` and unstick the PiP overlay.
const AVATAR_FRAME =
  "overflow-hidden rounded-lg border-2 border-brand/45 bg-brand-soft";

const QUESTION_OVERLAY =
  "pointer-events-none absolute bottom-5 left-1/2 z-20" +
  " w-[min(760px,calc(100%_-_40px))] -translate-x-1/2 rounded-lg border" +
  " border-white/70 bg-white/90 px-5 py-4 shadow-xl backdrop-blur-md";

const NOTICE = "rounded-lg border px-4 py-3 text-sm";
const NOTICE_AMBER = "border-amber-200 bg-amber-50 text-amber-900";
const NOTICE_BLUE = "border-brand/25 bg-brand-soft text-brand-strong";

const FOOTER_ACTION =
  "inline-flex h-11 items-center gap-2 rounded-lg border border-slate-200" +
  " bg-white px-4 text-sm font-semibold text-slate-700 shadow-sm transition" +
  " hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40";

const FOOTER_ICON_ACTION =
  "grid size-11 place-items-center rounded-lg border border-slate-200 bg-white" +
  " text-slate-600 shadow-sm transition hover:bg-slate-100" +
  " disabled:cursor-not-allowed disabled:opacity-40";

const FOOTER_SUBMIT =
  "inline-flex h-11 items-center gap-2 rounded-lg bg-red-500 px-5 text-sm" +
  " font-bold text-white shadow-sm transition hover:bg-red-600" +
  " disabled:cursor-not-allowed disabled:opacity-40";

function formatElapsedTime(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function CandidatePanel({
  menuOpen,
  pictureInPicture,
  recording,
  onMenuToggle,
  onPictureInPictureToggle,
}: {
  menuOpen: boolean;
  pictureInPicture: boolean;
  recording: boolean;
  onMenuToggle(): void;
  onPictureInPictureToggle(): void;
}) {
  return (
    <section className={CANDIDATE_PANEL} aria-label="지원자 화면">
      <div className={STAGE_LABEL}>
        <span
          className={`h-2 w-2 rounded-full ${recording ? "bg-red-500" : "bg-slate-400"}`}
          aria-hidden="true"
        />
        지원자
      </div>

      <div className="absolute right-3 top-3 z-30">
        <button
          type="button"
          className={PANEL_MENU_TRIGGER}
          aria-label="화면 옵션"
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          onClick={onMenuToggle}
        >
          <EllipsisVertical className="size-5" aria-hidden="true" />
        </button>
        {menuOpen ? (
          <div
            className="absolute right-0 top-12 w-56 rounded-lg border border-slate-200 bg-white p-1.5 shadow-xl"
            role="menu"
          >
            <button
              type="button"
              className={PANEL_MENU_ITEM}
              role="menuitem"
              onClick={onPictureInPictureToggle}
            >
              {pictureInPicture ? (
                <SplitSquareHorizontal
                  className="size-4 text-slate-500"
                  aria-hidden="true"
                />
              ) : (
                <PictureInPicture2
                  className="size-4 text-slate-500"
                  aria-hidden="true"
                />
              )}
              {pictureInPicture
                ? "분할 화면으로 보기"
                : "작은 창(PiP)으로 보기"}
            </button>
          </div>
        ) : null}
      </div>

      <div className="grid h-full min-h-[320px] place-items-center px-6 text-center text-slate-500">
        <div>
          <CameraOff
            className="mx-auto mb-3 size-10 stroke-[1.6]"
            aria-hidden="true"
          />
          <p className="text-sm font-medium">
            {recording ? "답변을 녹음하고 있습니다" : "카메라 꺼짐"}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            {recording ? "답변 완료를 눌러 제출하세요." : "음성으로 진행 중"}
          </p>
        </div>
      </div>
    </section>
  );
}

export function InterviewRoom({
  question,
  transcript = "",
  interviewerSpeaking = false,
  questionInProgress = interviewerSpeaking,
  state,
  connectionState,
  textOnly,
  interviewerLevel = "entry",
  initialElapsedSeconds = 0,
  onStartAnswer,
  onCompleteAnswer,
  onReconnect,
  onAddExplanation,
}: {
  question: string;
  transcript?: string;
  interviewerSpeaking?: boolean;
  questionInProgress?: boolean;
  state: InterviewState;
  connectionState: ConnectionState;
  textOnly: boolean;
  interviewerLevel?: InterviewerLevel;
  initialElapsedSeconds?: number;
  onStartAnswer(): void;
  onCompleteAnswer(): void;
  onReconnect(): void;
  onAddExplanation?(): void;
}) {
  const [recording, setRecording] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [pictureInPicture, setPictureInPicture] = useState(false);
  const [captionsVisible, setCaptionsVisible] = useState(true);
  const [elapsedSeconds, setElapsedSeconds] = useState(initialElapsedSeconds);
  const levelInfo = INTERVIEWER_LEVELS[interviewerLevel];

  useEffect(() => {
    const timer = window.setInterval(() => {
      setElapsedSeconds((current) => current + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  function startAnswer() {
    if (questionInProgress) return;
    setRecording(true);
    onStartAnswer();
  }

  function completeAnswer() {
    setRecording(false);
    onCompleteAnswer();
  }

  function togglePictureInPicture() {
    setPictureInPicture((current) => !current);
    setMenuOpen(false);
  }

  if (
    state === "completed" ||
    state === "report_generating" ||
    state === "reviewable"
  ) {
    return <InterviewComplete />;
  }

  return (
    <main className={SHELL}>
      <div className="mx-auto flex min-h-[calc(100vh-40px)] max-w-[1720px] flex-col gap-5 lg:min-h-[calc(100vh-64px)]">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="inline-flex h-10 items-center rounded-full bg-brand px-5 text-sm font-bold text-white shadow-sm">
              LIVE INTERVIEW
            </span>
            <span className="inline-flex min-h-10 items-center rounded-full border border-slate-200 bg-white px-4 text-sm font-medium text-slate-500">
              직무 기반 모의면접 · 서비스 백엔드
            </span>
          </div>
          <div className="flex items-center gap-2.5">
            <span
              className={`${HEADER_PILL} text-sm font-semibold text-slate-600`}
            >
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  connectionState === "connected" ? "bg-brand" : "bg-amber-500"
                }`}
                aria-hidden="true"
              />
              {connectionState === "connected" ? "Connected" : "Connecting"}
            </span>
            <span
              className={`${HEADER_PILL} font-mono text-sm font-bold text-slate-800`}
            >
              <Clock3 className="size-4 text-brand" aria-hidden="true" />
              {formatElapsedTime(elapsedSeconds)}
            </span>
          </div>
        </header>

        {connectionState === "reconnecting" ? (
          <section
            className={`flex flex-wrap items-center justify-between gap-3 ${NOTICE} ${NOTICE_AMBER}`}
            role="status"
          >
            <p>연결을 복구하고 있습니다. 녹화 조각은 이 기기에 보관됩니다.</p>
            <button
              type="button"
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-amber-300 bg-white px-3 font-semibold hover:bg-amber-100"
              onClick={onReconnect}
            >
              <RefreshCcw className="size-4" aria-hidden="true" />
              다시 연결
            </button>
          </section>
        ) : null}

        <div
          className={`relative grid flex-1 gap-4 ${
            pictureInPicture
              ? "grid-cols-1"
              : "grid-cols-1 lg:grid-cols-[minmax(0,1.03fr)_minmax(360px,1fr)]"
          }`}
        >
          {!pictureInPicture ? (
            <section
              className={`relative ${AVATAR_FRAME} min-h-[360px] shadow-lg`}
            >
              <Avatar
                textOnly={textOnly}
                speaking={interviewerSpeaking && !textOnly}
                speechMarkIndex={0}
                level={interviewerLevel}
              />
              <div className={STAGE_LABEL} title={levelInfo.description}>
                <span
                  className="h-2 w-2 rounded-full bg-brand"
                  aria-hidden="true"
                />
                {levelInfo.shortLabel} 면접관
              </div>
            </section>
          ) : null}

          <CandidatePanel
            menuOpen={menuOpen}
            pictureInPicture={pictureInPicture}
            recording={recording}
            onMenuToggle={() => setMenuOpen((current) => !current)}
            onPictureInPictureToggle={togglePictureInPicture}
          />

          {pictureInPicture ? (
            <section
              className={`absolute ${AVATAR_FRAME} bottom-5 right-5 z-20 aspect-video w-[min(42%,380px)] min-w-48 shadow-2xl`}
            >
              <Avatar
                textOnly={textOnly}
                speaking={interviewerSpeaking && !textOnly}
                speechMarkIndex={0}
                level={interviewerLevel}
              />
              <span
                className="absolute left-2.5 top-2.5 rounded-md bg-white/90 px-2 py-1 text-xs font-semibold shadow-sm"
                title={levelInfo.description}
              >
                {levelInfo.shortLabel} 면접관
              </span>
            </section>
          ) : null}

          <section
            className={QUESTION_OVERLAY}
            aria-labelledby="current-question"
          >
            <h1 id="current-question" className="text-sm leading-6">
              <span className="mr-2 font-bold text-brand-strong">
                {levelInfo.shortLabel}
              </span>
              <span className="font-semibold text-slate-900">{question}</span>
            </h1>
          </section>

          {captionsVisible && transcript ? (
            <section
              className="pointer-events-none absolute bottom-28 left-1/2 z-20 w-[min(700px,calc(100%_-_48px))] -translate-x-1/2 rounded-lg bg-slate-950/80 px-5 py-3 text-center text-sm font-medium leading-6 text-white shadow-lg backdrop-blur"
              aria-live="polite"
              aria-label="실시간 답변 자막"
            >
              {transcript}
            </section>
          ) : null}
        </div>

        {state === "preparing_question" ? (
          <p className={`${NOTICE} ${NOTICE_BLUE}`} role="status">
            답변을 바탕으로 다음 질문을 준비하고 있습니다.
          </p>
        ) : null}
        {state === "paused" ? (
          <p className={`${NOTICE} ${NOTICE_AMBER}`} role="status">
            기술적인 이유로 면접이 일시 중지되었습니다. 이 상태는 평가에
            반영되지 않습니다.
          </p>
        ) : null}

        <footer className="flex flex-col gap-4 border-t border-slate-200 pt-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="mb-1.5 flex flex-wrap items-center gap-2 text-sm">
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 font-semibold text-slate-700">
                면접 진행중
              </span>
              <span className="font-semibold text-slate-500">
                핵심 역량 검증
              </span>
            </div>
            <p className="text-sm font-semibold text-slate-900">
              면접 단계: introduction
            </p>
            <p className="mt-1 text-xs text-slate-400">
              AI가 질문을 진행하며 최종 판단은 사람이 합니다.
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2">
            <button
              type="button"
              className={FOOTER_ACTION}
              disabled={recording || state === "paused" || questionInProgress}
              onClick={startAnswer}
            >
              <Mic className="size-4" aria-hidden="true" />
              {questionInProgress ? "질문 재생 중" : "답변 시작"}
            </button>
            {onAddExplanation ? (
              <button
                type="button"
                className={FOOTER_ICON_ACTION}
                aria-label="정정 또는 추가 설명"
                title="정정 또는 추가 설명"
                disabled={recording || state === "paused" || questionInProgress}
                onClick={onAddExplanation}
              >
                <RefreshCcw className="size-4" aria-hidden="true" />
              </button>
            ) : null}
            <button
              type="button"
              className="grid size-11 place-items-center rounded-lg bg-brand text-white shadow-sm transition hover:bg-brand-strong"
              aria-label="자막 보기"
              title="자막 보기"
              aria-pressed={captionsVisible}
              onClick={() => setCaptionsVisible((current) => !current)}
            >
              <Captions className="size-5" aria-hidden="true" />
            </button>
            <button
              type="button"
              className={FOOTER_SUBMIT}
              disabled={!recording || state === "paused"}
              onClick={completeAnswer}
            >
              {recording ? (
                <MicOff className="size-4" aria-hidden="true" />
              ) : (
                <VideoOff className="size-4" aria-hidden="true" />
              )}
              답변 완료
            </button>
            <span className="sr-only" aria-live="polite">
              {recording ? "답변을 녹음하고 있습니다" : "답변 준비"}
            </span>
            <span className="sr-only">
              답변 완료를 누를 때만 최종 답변으로 확정됩니다.
            </span>
          </div>
        </footer>
      </div>
    </main>
  );
}
