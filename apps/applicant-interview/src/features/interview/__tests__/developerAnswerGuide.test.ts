import { afterEach, describe, expect, it, vi } from "vitest";

import {
  installDeveloperAnswerGuideCommands,
  isDeveloperAnswerGuideEnabled,
} from "../developerAnswerGuide";

describe("developer answer guide commands", () => {
  afterEach(() => {
    window.sessionStorage.clear();
    delete window.WhyYouDebug;
    vi.restoreAllMocks();
  });

  it("enables and disables the guide for the current tab", () => {
    const onChange = vi.fn();
    vi.spyOn(console, "info").mockImplementation(() => undefined);
    const uninstall = installDeveloperAnswerGuideCommands(onChange);

    expect(window.WhyYouDebug?.answerGuideStatus()).toBe(false);
    expect(window.WhyYouDebug?.enableAnswerGuide()).toBe(true);
    expect(isDeveloperAnswerGuideEnabled()).toBe(true);
    expect(onChange).toHaveBeenLastCalledWith(true);

    expect(window.WhyYouDebug?.disableAnswerGuide()).toBe(true);
    expect(isDeveloperAnswerGuideEnabled()).toBe(false);
    expect(onChange).toHaveBeenLastCalledWith(false);

    uninstall();
    expect(window.WhyYouDebug).toBeUndefined();
  });

  it("restores an existing debug command object when uninstalled", () => {
    const previousCommands = {
      enableAnswerGuide: () => false,
      disableAnswerGuide: () => false,
      answerGuideStatus: () => false,
    };
    window.WhyYouDebug = previousCommands;

    const uninstall = installDeveloperAnswerGuideCommands(vi.fn());
    expect(window.WhyYouDebug).not.toBe(previousCommands);

    uninstall();
    expect(window.WhyYouDebug).toBe(previousCommands);
  });
});
