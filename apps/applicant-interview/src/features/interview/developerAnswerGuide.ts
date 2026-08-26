const STORAGE_KEY = "whyyou:developer-answer-guide";

type WhyYouDebugCommands = {
  enableAnswerGuide: () => boolean;
  disableAnswerGuide: () => boolean;
  answerGuideStatus: () => boolean;
};

const changeListeners = new Set<(enabled: boolean) => void>();

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

function notifyDeveloperAnswerGuideChange(enabled: boolean) {
  for (const listener of changeListeners) listener(enabled);
}

function registerDeveloperAnswerGuideCommands() {
  if (window.WhyYouDebug) return;
  const commands: WhyYouDebugCommands = {
    enableAnswerGuide: () => {
      const enabled = saveDeveloperAnswerGuideEnabled(true);
      if (enabled) {
        notifyDeveloperAnswerGuideChange(true);
        console.info(
          "[WhyYou] 답변 가이드를 활성화했습니다. 추천 답변은 이 콘솔에 표시됩니다.",
        );
      }
      return enabled;
    },
    disableAnswerGuide: () => {
      const disabled = saveDeveloperAnswerGuideEnabled(false);
      if (disabled) {
        notifyDeveloperAnswerGuideChange(false);
        console.info("[WhyYou] 답변 가이드를 비활성화했습니다.");
      }
      return disabled;
    },
    answerGuideStatus: () => isDeveloperAnswerGuideEnabled(),
  };

  Object.defineProperty(window, "WhyYouDebug", {
    configurable: true,
    enumerable: false,
    value: commands,
  });
}

export function subscribeDeveloperAnswerGuide(
  onChange: (enabled: boolean) => void,
) {
  changeListeners.add(onChange);
  return () => {
    changeListeners.delete(onChange);
  };
}

if (
  import.meta.env.DEV ||
  import.meta.env.VITE_AUTOMATED_INTERVIEW_ENABLED === "true"
) {
  registerDeveloperAnswerGuideCommands();
}
