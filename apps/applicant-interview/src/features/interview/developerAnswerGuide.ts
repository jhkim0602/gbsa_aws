const STORAGE_KEY = "whyyou:developer-answer-guide";

type WhyYouDebugCommands = {
  enableAnswerGuide: () => boolean;
  disableAnswerGuide: () => boolean;
  answerGuideStatus: () => boolean;
};

type DeveloperAnswerGuideListener = (
  enabled: boolean,
  requestVersion: number,
) => void;

const changeListeners = new Set<DeveloperAnswerGuideListener>();
let requestVersion = 0;

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
  for (const listener of changeListeners) listener(enabled, requestVersion);
}

function registerDeveloperAnswerGuideCommands() {
  if (window.WhyYouDebug) return;
  const commands: WhyYouDebugCommands = {
    enableAnswerGuide: () => {
      const enabled = saveDeveloperAnswerGuideEnabled(true);
      if (enabled) {
        requestVersion += 1;
        notifyDeveloperAnswerGuideChange(true);
        console.info(
          "[WhyYou] 답변 가이드를 활성화했습니다. 현재 또는 다음 질문의 추천 답변을 이 콘솔에 표시합니다.",
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
  onChange: DeveloperAnswerGuideListener,
) {
  changeListeners.add(onChange);
  return () => {
    changeListeners.delete(onChange);
  };
}

export function getDeveloperAnswerGuideRequestVersion() {
  return requestVersion;
}

if (
  import.meta.env.DEV ||
  import.meta.env.VITE_AUTOMATED_INTERVIEW_ENABLED === "true"
) {
  registerDeveloperAnswerGuideCommands();
}
