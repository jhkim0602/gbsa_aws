export type LiveTranscript = Readonly<{
  committed: string;
  display: string;
}>;

export const EMPTY_LIVE_TRANSCRIPT: LiveTranscript = {
  committed: "",
  display: "",
};

export function updateLiveTranscript(
  current: LiveTranscript,
  incomingText: string,
  isFinal: boolean,
): LiveTranscript {
  const incoming = normalizeTranscript(incomingText);
  if (!incoming) {
    return {
      committed: current.committed,
      display: current.committed,
    };
  }

  if (isFinal) {
    const committed = mergeTranscript(current.committed, incoming);
    return { committed, display: committed };
  }

  return {
    committed: current.committed,
    display: mergeTranscript(current.committed, incoming),
  };
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
