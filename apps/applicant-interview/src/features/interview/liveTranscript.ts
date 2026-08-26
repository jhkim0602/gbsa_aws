export type LiveTranscript = Readonly<{
  committed: string;
  interim: string;
  display: string;
}>;

export const EMPTY_LIVE_TRANSCRIPT: LiveTranscript = {
  committed: "",
  interim: "",
  display: "",
};

export function updateLiveTranscript(
  current: LiveTranscript,
  incomingText: string,
  isFinal: boolean,
  segments?: Readonly<{ committedText: string; interimText: string }>,
): LiveTranscript {
  if (segments) {
    const committed = normalizeTranscript(segments.committedText);
    const interim = normalizeTranscript(segments.interimText);
    return {
      committed,
      interim,
      display: mergeTranscript(committed, interim),
    };
  }

  const incoming = normalizeTranscript(incomingText);
  if (!incoming) {
    return {
      committed: current.committed,
      interim: "",
      display: current.committed,
    };
  }

  if (isFinal) {
    const committed = mergeTranscript(current.committed, incoming);
    return { committed, interim: "", display: committed };
  }

  const interim = withoutCommittedPrefix(current.committed, incoming);
  return {
    committed: current.committed,
    interim,
    display: mergeTranscript(current.committed, interim),
  };
}

function withoutCommittedPrefix(committed: string, incoming: string): string {
  if (committed && incoming.startsWith(committed)) {
    return incoming.slice(committed.length).trim();
  }
  return incoming;
}

function mergeTranscript(current: string, incoming: string): string {
  if (!current) return incoming;
  if (incoming === current || current.endsWith(incoming)) return current;
  if (incoming.startsWith(current)) return incoming;
  if (current.startsWith(incoming)) return current;
  return `${current} ${incoming}`;
}

function normalizeTranscript(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}
