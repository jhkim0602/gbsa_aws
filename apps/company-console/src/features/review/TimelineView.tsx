import {
  Bot,
  CirclePlay,
  FileSearch,
  MessageCircle,
  Search,
  Target,
  UserRound,
  Video,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { buildCaptionTrack } from "./captions";
import { formatLocator, sourceTypeLabel } from "./questionSources";
import type { ReviewTimelineEntry } from "./types";

const typeLabels: Record<ReviewTimelineEntry["type"], string> = {
  question: "AI 질문",
  answer: "지원자 답변",
  event: "기술 이벤트",
  evidence: "Evidence",
};

const typeIcons = {
  question: Bot,
  answer: UserRound,
  event: MessageCircle,
  evidence: CirclePlay,
} as const;

// `.review-panel` + `.review-panel__*`, shared with ReportView/HumanReview.
const PANEL = "overflow-hidden rounded-md border border-border bg-surface";

const PANEL_HEADER =
  "flex min-h-[58px] items-center justify-between gap-3 border-b border-border-muted" +
  " px-[14px] py-3 max-[520px]:items-start";

const PANEL_ICON =
  "grid size-[30px] flex-[0_0_30px] place-items-center rounded-md border" +
  " border-border-muted bg-surface-muted text-brand-strong";

// The shared badge base (`.immutable-badge, …, .media-badge`) plus `.media-badge` itself.
// The 520px `max-width`/`white-space` override only names the two review badges, not this one.
const MEDIA_BADGE =
  "inline-flex min-h-[22px] items-center gap-[5px] rounded-full bg-surface-muted" +
  " px-[7px] text-[8px] font-[650] whitespace-nowrap text-muted";

// `.media-badge > span`; `--ready`/`--partial` have no rule, so they keep the base green.
const MEDIA_DOT: Record<
  "ready" | "partial" | "processing" | "unavailable",
  string
> = {
  ready: "bg-success",
  partial: "bg-success",
  processing: "bg-warning",
  unavailable: "bg-subtle",
};

const SEARCH_INPUT =
  "h-8 w-full rounded-[5px] border border-border bg-surface pr-[62px] pl-[31px]" +
  " text-[9px] focus:border-brand focus:outline-2" +
  " focus:outline-[rgb(89_102_206_/_12%)] focus:outline-offset-0";

// `.timeline-list li + li` — every child of the list is an `li`, so `not-first:` is exact.
const TIMELINE_LIST =
  "grid max-h-[calc(100vh-390px)] overflow-auto px-2.5 pb-2.5" +
  " max-[820px]:max-h-[360px]";

const ENTRY_SEEK =
  "grid w-full grid-cols-[26px_minmax(0,1fr)] items-start gap-2 rounded-sm px-1" +
  " py-2.5 text-left hover:bg-surface-muted";

const ENTRY_ICON = "grid size-[26px] place-items-center rounded-[5px]";

// `.timeline-entry__icon.is-answer, .is-evidence`; `is-question`/`is-event` are base-toned.
const ENTRY_ICON_TONE: Record<ReviewTimelineEntry["type"], string> = {
  question: "bg-surface-strong text-muted",
  answer: "bg-[rgb(89_102_206_/_9%)] text-brand-strong",
  event: "bg-surface-strong text-muted",
  evidence: "bg-[rgb(89_102_206_/_9%)] text-brand-strong",
};

// Preflight makes `summary` a `list-item`, so the flex display and the marker resets both
// have to be restated here exactly as the source rule did.
const RATIONALE_SUMMARY =
  "flex min-h-8 list-none cursor-pointer items-center gap-1.5 px-[9px] py-[7px]" +
  " text-[9px] font-[650] text-ink-secondary" +
  " [&::-webkit-details-marker]:hidden";

// `.question-source-list p` and `.question-rationale__empty` share one rule.
const SOURCE_PROSE = "text-[8px] leading-[1.55] text-muted";

export function seekToEvidence(
  media: Pick<HTMLMediaElement, "currentTime" | "play">,
  startMs: number,
) {
  media.currentTime = startMs / 1000;
  return media.play();
}

export function TimelineView({
  entries,
  playbackStatus,
  playbackUrl,
  selectedStartMs,
  onSeek,
}: {
  entries: ReviewTimelineEntry[];
  playbackStatus: "ready" | "partial" | "processing" | "unavailable";
  playbackUrl?: string;
  selectedStartMs?: number | null;
  onSeek(startMs: number): void;
}) {
  const [query, setQuery] = useState("");
  const mediaRef = useRef<HTMLVideoElement>(null);
  const visible = useMemo(
    () =>
      entries.filter((entry) =>
        (entry.text ?? "").toLowerCase().includes(query.toLowerCase()),
      ),
    [entries, query],
  );

  useEffect(() => {
    if (selectedStartMs == null || !mediaRef.current) return;
    void seekToEvidence(mediaRef.current, selectedStartMs);
  }, [selectedStartMs]);

  // The cue text comes from the transcript already in memory; a blob URL keeps it
  // out of a second request that could not carry the tenant token.
  const [captionUrl, setCaptionUrl] = useState<string>();
  const captionTrack = useMemo(() => buildCaptionTrack(entries), [entries]);

  useEffect(() => {
    if (!hasCues(captionTrack)) {
      setCaptionUrl(undefined);
      return;
    }
    const url = URL.createObjectURL(
      new Blob([captionTrack], { type: "text/vtt" }),
    );
    setCaptionUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [captionTrack]);

  function selectTime(startMs: number) {
    onSeek(startMs);
    if (mediaRef.current) {
      void seekToEvidence(mediaRef.current, startMs);
    }
  }

  return (
    <section className={PANEL} aria-labelledby="timeline-title">
      <header className={PANEL_HEADER}>
        <div className="flex min-w-0 items-center gap-[9px]">
          <span className={PANEL_ICON} aria-hidden="true">
            <Video size={18} />
          </span>
          <span className="grid min-w-0 gap-px">
            <p className="font-mono text-[8px] font-semibold uppercase text-muted">
              영상 · 자막
            </p>
            <h2 id="timeline-title" className="text-[12px] font-[650]">
              면접 타임라인
            </h2>
          </span>
        </div>
        <span className={MEDIA_BADGE}>
          <span
            className={`size-1.5 rounded-full ${MEDIA_DOT[playbackStatus]}`}
            aria-hidden="true"
          />
          {playbackLabel(playbackStatus)}
        </span>
      </header>

      <div className="border-b border-border-muted p-2.5">
        {playbackUrl ? (
          <video
            className="aspect-video w-full rounded-sm bg-[#111318]"
            ref={mediaRef}
            controls
            preload="metadata"
            src={playbackUrl}
          >
            {captionUrl ? (
              <track
                kind="captions"
                label="한국어 자막"
                srcLang="ko"
                src={captionUrl}
                default
              />
            ) : null}
          </video>
        ) : (
          <div className="flex min-h-[162px] items-center justify-center gap-2.5 rounded-sm bg-surface-strong text-muted">
            <Video size={28} aria-hidden="true" />
            <span className="grid gap-0.5">
              <strong className="text-[10px]">
                {playbackLabel(playbackStatus)}
              </strong>
              <small className="max-w-[190px] text-[8px] leading-[1.45]">
                영상이 준비되면 Evidence 구간을 바로 재생합니다.
              </small>
            </span>
          </div>
        )}
      </div>

      <label className="relative m-2.5 flex items-center">
        <span className="sr-only">자막 검색</span>
        <Search
          className="absolute left-[9px] text-subtle"
          size={16}
          aria-hidden="true"
        />
        <input
          className={SEARCH_INPUT}
          value={query}
          placeholder="자막 내용 검색"
          onChange={(event) => setQuery(event.target.value)}
        />
        <small className="absolute right-[9px] font-mono text-[8px] text-subtle">
          {visible.length}개 구간
        </small>
      </label>

      <ol className={TIMELINE_LIST}>
        {visible.map((entry) => {
          const Icon = typeIcons[entry.type];
          return (
            <li
              key={entry.entryId}
              className="not-first:border-t not-first:border-border-muted"
            >
              <button
                className={ENTRY_SEEK}
                type="button"
                onClick={() => selectTime(entry.startMs)}
              >
                <span
                  className={`${ENTRY_ICON} ${ENTRY_ICON_TONE[entry.type]}`}
                >
                  <Icon size={15} aria-hidden="true" />
                </span>
                <span className="grid gap-1">
                  <span className="flex items-center justify-between">
                    <strong className="text-[9px]">
                      {typeLabels[entry.type]}
                    </strong>
                    <time className="font-mono text-[8px] text-subtle">
                      {formatTime(entry.startMs)}
                    </time>
                  </span>
                  <small className="text-[9px] leading-[1.5] text-muted">
                    {entry.text ?? "기술 이벤트"}
                  </small>
                </span>
              </button>
              {entry.questionRationale ? (
                <details className="mr-1 mb-2.5 ml-[38px] rounded-[5px] border border-border-muted bg-surface-muted">
                  <summary className={RATIONALE_SUMMARY}>
                    <FileSearch size={14} aria-hidden="true" />
                    질문 근거
                    <span className="ml-auto font-mono text-[8px] text-subtle">
                      {entry.questionRationale.sourceReferences.length}개 자료
                    </span>
                  </summary>
                  <div className="grid gap-[9px] border-t border-border-muted px-[9px] pb-[9px]">
                    <p className="mt-2 text-[8px] leading-[1.45] text-muted">
                      지원자 답변 Evidence가 아닌 질문 생성 참고 자료입니다.
                    </p>
                    <div className="grid grid-cols-[18px_minmax(0,1fr)] items-start gap-[5px] text-brand-strong">
                      <Target size={14} aria-hidden="true" />
                      <span className="grid gap-0.5">
                        <small className="text-[8px] text-subtle">
                          검증 목적
                        </small>
                        <strong className="text-[9px] font-semibold leading-[1.5] text-ink-secondary">
                          {entry.questionRationale.objective}
                        </strong>
                      </span>
                    </div>
                    <span className="w-fit rounded-sm bg-warning-soft px-1.5 py-[3px] text-[8px] font-[650] text-warning">
                      {targetTypeLabel(
                        entry.questionRationale.verificationTargetType,
                      )}
                    </span>
                    {entry.questionRationale.sourceReferences.length ? (
                      <ul className="grid gap-1.5">
                        {entry.questionRationale.sourceReferences.map(
                          (source) => (
                            <li
                              key={source.sourceId}
                              className="grid gap-[5px] rounded-sm border border-border-muted bg-surface p-2"
                            >
                              <span className="flex items-center gap-[7px] text-[8px] font-[650] text-ink-secondary">
                                {sourceTypeLabel(source.sourceType)}
                                <small className="font-mono text-[7px] text-subtle">
                                  {formatLocator(source.locator)}
                                </small>
                              </span>
                              <p className={SOURCE_PROSE}>{source.excerpt}</p>
                            </li>
                          ),
                        )}
                      </ul>
                    ) : (
                      <p className={SOURCE_PROSE}>
                        공통 평가 질문으로 진행되어 참고 자료가 없습니다.
                      </p>
                    )}
                  </div>
                </details>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** A header-only track would show an empty caption menu, so treat it as absent. */
function hasCues(track: string) {
  return track.includes("-->");
}

function targetTypeLabel(
  type: NonNullable<
    ReviewTimelineEntry["questionRationale"]
  >["verificationTargetType"],
) {
  return {
    not_mentioned: "자료 미언급",
    claim_found: "경험 확인",
    detail_missing: "세부 내용 부족",
    source_conflict: "자료 간 차이 확인",
    ownership_uncertain: "본인 기여 확인",
  }[type];
}

function playbackLabel(
  status: "ready" | "partial" | "processing" | "unavailable",
) {
  return {
    ready: "재생 가능",
    partial: "일부 구간",
    processing: "처리 중",
    unavailable: "영상 없음",
  }[status];
}

function formatTime(milliseconds: number) {
  const seconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(
    2,
    "0",
  )}`;
}
