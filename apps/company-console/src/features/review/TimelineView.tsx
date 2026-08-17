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
    <section
      className="review-panel timeline-panel"
      aria-labelledby="timeline-title"
    >
      <header className="review-panel__header">
        <div className="review-panel__title">
          <span className="review-panel__icon" aria-hidden="true">
            <Video size={18} />
          </span>
          <span>
            <p>영상 · 자막</p>
            <h2 id="timeline-title">면접 타임라인</h2>
          </span>
        </div>
        <span className={`media-badge media-badge--${playbackStatus}`}>
          <span aria-hidden="true" />
          {playbackLabel(playbackStatus)}
        </span>
      </header>

      <div className="timeline-media">
        {playbackUrl ? (
          <video ref={mediaRef} controls preload="metadata" src={playbackUrl}>
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
          <div className="timeline-media__placeholder">
            <Video size={28} aria-hidden="true" />
            <span>
              <strong>{playbackLabel(playbackStatus)}</strong>
              <small>영상이 준비되면 Evidence 구간을 바로 재생합니다.</small>
            </span>
          </div>
        )}
      </div>

      <label className="timeline-search">
        <span className="sr-only">자막 검색</span>
        <Search size={16} aria-hidden="true" />
        <input
          value={query}
          placeholder="자막 내용 검색"
          onChange={(event) => setQuery(event.target.value)}
        />
        <small>{visible.length}개 구간</small>
      </label>

      <ol className="timeline-list">
        {visible.map((entry) => {
          const Icon = typeIcons[entry.type];
          return (
            <li key={entry.entryId}>
              <button
                className="timeline-entry__seek"
                type="button"
                onClick={() => selectTime(entry.startMs)}
              >
                <span className={`timeline-entry__icon is-${entry.type}`}>
                  <Icon size={15} aria-hidden="true" />
                </span>
                <span className="timeline-entry__body">
                  <span>
                    <strong>{typeLabels[entry.type]}</strong>
                    <time>{formatTime(entry.startMs)}</time>
                  </span>
                  <small>{entry.text ?? "기술 이벤트"}</small>
                </span>
              </button>
              {entry.questionRationale ? (
                <details className="question-rationale">
                  <summary>
                    <FileSearch size={14} aria-hidden="true" />
                    질문 근거
                    <span>
                      {entry.questionRationale.sourceReferences.length}개 자료
                    </span>
                  </summary>
                  <div className="question-rationale__body">
                    <p className="question-rationale__notice">
                      지원자 답변 Evidence가 아닌 질문 생성 참고 자료입니다.
                    </p>
                    <div className="question-rationale__objective">
                      <Target size={14} aria-hidden="true" />
                      <span>
                        <small>검증 목적</small>
                        <strong>{entry.questionRationale.objective}</strong>
                      </span>
                    </div>
                    <span className="question-rationale__type">
                      {targetTypeLabel(
                        entry.questionRationale.verificationTargetType,
                      )}
                    </span>
                    {entry.questionRationale.sourceReferences.length ? (
                      <ul className="question-source-list">
                        {entry.questionRationale.sourceReferences.map(
                          (source) => (
                            <li key={source.sourceId}>
                              <span>
                                {sourceTypeLabel(source.sourceType)}
                                <small>{formatLocator(source.locator)}</small>
                              </span>
                              <p>{source.excerpt}</p>
                            </li>
                          ),
                        )}
                      </ul>
                    ) : (
                      <p className="question-rationale__empty">
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
