import { useMemo, useRef, useState } from "react";

type TimelineEntry = {
  entryId: string;
  type: "question" | "answer" | "event" | "evidence";
  startMs: number;
  endMs: number;
  text: string | null;
};

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
  onSeek,
}: {
  entries: TimelineEntry[];
  playbackStatus: "ready" | "partial" | "processing" | "unavailable";
  playbackUrl?: string;
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
  function selectTime(startMs: number) {
    onSeek(startMs);
    if (mediaRef.current) {
      void seekToEvidence(mediaRef.current, startMs);
    }
  }

  return (
    <section aria-labelledby="timeline-title">
      <h2 id="timeline-title">면접 타임라인</h2>
      <p>미디어 상태: {playbackStatus}</p>
      {playbackUrl && (
        <video ref={mediaRef} controls preload="metadata" src={playbackUrl}>
          <track kind="captions" />
        </video>
      )}
      <label>
        자막 검색
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      <ol>
        {visible.map((entry) => (
          <li key={entry.entryId}>
            <button type="button" onClick={() => selectTime(entry.startMs)}>
              {entry.text ?? "기술 이벤트"}
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
