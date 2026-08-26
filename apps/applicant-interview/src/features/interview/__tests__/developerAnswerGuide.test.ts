import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isDeveloperAnswerGuideEnabled,
  subscribeDeveloperAnswerGuide,
} from "../developerAnswerGuide";

describe("developer answer guide commands", () => {
  afterEach(() => {
    window.sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("enables and disables the guide for the current tab", () => {
    const onChange = vi.fn();
    vi.spyOn(console, "info").mockImplementation(() => undefined);
    const unsubscribe = subscribeDeveloperAnswerGuide(onChange);

    expect(window.WhyYouDebug?.answerGuideStatus()).toBe(false);
    expect(window.WhyYouDebug?.enableAnswerGuide()).toBe(true);
    expect(isDeveloperAnswerGuideEnabled()).toBe(true);
    expect(onChange).toHaveBeenLastCalledWith(true);

    expect(window.WhyYouDebug?.disableAnswerGuide()).toBe(true);
    expect(isDeveloperAnswerGuideEnabled()).toBe(false);
    expect(onChange).toHaveBeenLastCalledWith(false);

    unsubscribe();
  });

  it("keeps commands available when the interview route unmounts", () => {
    const unsubscribe = subscribeDeveloperAnswerGuide(vi.fn());
    unsubscribe();

    expect(window.WhyYouDebug?.answerGuideStatus()).toBe(false);
  });
});
