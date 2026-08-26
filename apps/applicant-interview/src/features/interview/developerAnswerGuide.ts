const STORAGE_KEY = "whyyou:developer-answer-guide";

type WhyYouDebugCommands = {
  enableAnswerGuide: () => boolean;
  disableAnswerGuide: () => boolean;
  answerGuideStatus: () => boolean;
};

declare global {
  interface Window {
    WhyYouDebug?: WhyYouDebugCommands;
  }
}

export function isDeveloperAnswerGuideEnabled() {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) === "enabled";
  } catch {
    return false;
  }
}

function saveDeveloperAnswerGuideEnabled(enabled: boolean) {
  try {
    if (enabled) {
      window.sessionStorage.setItem(STORAGE_KEY, "enabled");
    } else {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    return false;
  }
  return true;
}

export function installDeveloperAnswerGuideCommands(
  onChange: (enabled: boolean) => void,
) {
  const previousCommands = window.WhyYouDebug;
  const commands: WhyYouDebugCommands = {
    enableAnswerGuide: () => {
      const enabled = saveDeveloperAnswerGuideEnabled(true);
      if (enabled) {
        onChange(true);
        console.info(
          "[WhyYou] 답변 가이드를 활성화했습니다. 추천 답변은 이 콘솔에 표시됩니다.",
        );
      }
      return enabled;
    },
    disableAnswerGuide: () => {
      const disabled = saveDeveloperAnswerGuideEnabled(false);
      if (disabled) {
        onChange(false);
        console.info("[WhyYou] 답변 가이드를 비활성화했습니다.");
      }
      return disabled;
    },
    answerGuideStatus: () => isDeveloperAnswerGuideEnabled(),
  };

  window.WhyYouDebug = commands;
  return () => {
    if (window.WhyYouDebug !== commands) return;
    if (previousCommands) {
      window.WhyYouDebug = previousCommands;
    } else {
      delete window.WhyYouDebug;
    }
  };
}
