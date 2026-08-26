import { describe, expect, it } from "vitest";

import { EMPTY_LIVE_TRANSCRIPT, updateLiveTranscript } from "../liveTranscript";

describe("updateLiveTranscript", () => {
  it("accumulates final transcript segments", () => {
    const first = updateLiveTranscript(
      EMPTY_LIVE_TRANSCRIPT,
      "첫 번째 문장입니다.",
      true,
    );
    const second = updateLiveTranscript(first, "두 번째 문장입니다.", true);

    expect(second).toEqual({
      committed: "첫 번째 문장입니다. 두 번째 문장입니다.",
      interim: "",
      display: "첫 번째 문장입니다. 두 번째 문장입니다.",
    });
  });

  it("replaces only the current partial sentence", () => {
    const committed = updateLiveTranscript(
      EMPTY_LIVE_TRANSCRIPT,
      "첫 번째 문장입니다.",
      true,
    );
    const firstPartial = updateLiveTranscript(committed, "두 번째", false);
    const revisedPartial = updateLiveTranscript(
      firstPartial,
      "두 번째 문장입니다.",
      false,
    );

    expect(firstPartial.display).toBe("첫 번째 문장입니다. 두 번째");
    expect(revisedPartial.display).toBe(
      "첫 번째 문장입니다. 두 번째 문장입니다.",
    );
    expect(revisedPartial.committed).toBe("첫 번째 문장입니다.");
    expect(revisedPartial.interim).toBe("두 번째 문장입니다.");
  });

  it("keeps committed and interim streaming segments separate", () => {
    const transcript = updateLiveTranscript(
      EMPTY_LIVE_TRANSCRIPT,
      "확정된 문장 이어지는 단어",
      false,
      {
        committedText: "확정된 문장",
        interimText: "이어지는 단어",
      },
    );

    expect(transcript).toEqual({
      committed: "확정된 문장",
      interim: "이어지는 단어",
      display: "확정된 문장 이어지는 단어",
    });
  });

  it("accepts a provider transcript that already contains prior text", () => {
    const committed = updateLiveTranscript(
      EMPTY_LIVE_TRANSCRIPT,
      "첫 번째 문장입니다.",
      true,
    );
    const cumulative = updateLiveTranscript(
      committed,
      "첫 번째 문장입니다. 두 번째 문장입니다.",
      true,
    );

    expect(cumulative.display).toBe("첫 번째 문장입니다. 두 번째 문장입니다.");
  });
});
