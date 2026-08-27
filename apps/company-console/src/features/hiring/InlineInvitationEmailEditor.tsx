import { Check, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";

import {
  BUTTON_PRIMARY,
  BUTTON_QUIET,
  formAlertClass,
} from "../../app/styles/primitives";
import {
  normalizeBrandColor,
  templateEquals,
  type InvitationEmailTemplate,
  type InvitationEmailTemplateApi,
  type InvitationEmailTemplateState,
} from "./invitationEmailTemplate";
import { POSITION_DESCRIPTION_MAX_LENGTH } from "./types";

const descriptionExample = `우리 팀은 기업 고객이 사용하는 AI 기반 업무 자동화 서비스를 만들고 있습니다.
이번 포지션은 서버 API, 비즈니스 로직과 데이터 처리 기능을 구현하고 안정적으로 운영합니다.
기획자와 프론트엔드 개발자와 협업하며 제품 개선 전 과정에 참여합니다.
사용자가 믿고 사용할 수 있는 서비스를 함께 만들 분을 찾습니다.`;

const fallbackTemplate: InvitationEmailTemplateState = {
  subject: "[{{회사명}}] {{포지션명}} 온라인 면접 안내",
  headline: "지원해주셔서 감사합니다",
  intro:
    "{{지원자명}}님, {{회사명}} {{포지션명}} 포지션에 지원해주셔서 감사합니다.\n서류 검토 결과 다음 단계인 온라인 구조화 면접에 초대드립니다.",
  guides: [],
  ctaLabel: "면접 시작하기",
  outro: "좋은 결과로 만나뵙기를 기대합니다.",
  footer: "본 메일은 발신 전용입니다",
  brandColor: "#5966ce",
  useApplicantName: true,
  emphasizeDeadline: true,
  showSecurityNotice: true,
  logoUrl: null,
  isPositionOverride: false,
};

const EDITABLE =
  "w-full rounded-md border border-transparent bg-transparent px-2 py-1 outline-none" +
  " transition-colors hover:border-border hover:bg-white/70 focus:border-brand focus:bg-white" +
  " focus:shadow-[0_0_0_3px_#5966ce1a]";

export function InlineInvitationEmailEditor({
  api,
  initialTemplate,
  positionTitle,
  positionDescription,
  descriptionCompleted,
  onPositionDescriptionChange,
  onDescriptionCompleted,
  onTemplateSaved,
}: {
  api?: InvitationEmailTemplateApi;
  initialTemplate: InvitationEmailTemplate | null;
  positionTitle: string;
  positionDescription: string;
  descriptionCompleted: boolean;
  onPositionDescriptionChange(value: string): void;
  onDescriptionCompleted(completed: boolean): void;
  onTemplateSaved(template: InvitationEmailTemplate): void;
}) {
  const initialState = initialTemplate
    ? toTemplateState(initialTemplate)
    : fallbackTemplate;
  const [saved, setSaved] =
    useState<InvitationEmailTemplateState>(initialState);
  const [draft, setDraft] =
    useState<InvitationEmailTemplateState>(initialState);
  const [loading, setLoading] = useState(Boolean(api && !initialTemplate));
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (initialTemplate) {
      const restored = toTemplateState(initialTemplate);
      setSaved(restored);
      setDraft(restored);
      setLoading(false);
      return;
    }
    if (!api) return;
    let active = true;
    setLoading(true);
    api
      .getCompanyTemplate()
      .then((template) => {
        if (!active) return;
        setSaved(template);
        setDraft(template);
      })
      .catch(() => {
        if (active) setError("초대 메일을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, initialTemplate]);

  function update<K extends keyof InvitationEmailTemplateState>(
    key: K,
    value: InvitationEmailTemplateState[K],
  ) {
    setNotice("");
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function save() {
    if (!positionDescription.trim() || saving) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const template = toTemplate(draft);
      setSaved(draft);
      onTemplateSaved(template);
      onDescriptionCompleted(true);
      setNotice("포지션 상세와 초대 메일을 저장했습니다.");
    } catch {
      setError("저장하지 못했습니다. 입력 내용을 확인해 주세요.");
    } finally {
      setSaving(false);
    }
  }

  function resetCopy() {
    setDraft((current) => ({
      ...fallbackTemplate,
      logoUrl: current.logoUrl,
      isPositionOverride: current.isPositionOverride,
    }));
    setNotice("");
  }

  const dirty = !templateEquals(toTemplate(draft), toTemplate(saved));
  const ready = Boolean(
    draft.subject.trim() &&
    draft.headline.trim() &&
    draft.intro.trim() &&
    draft.ctaLabel.trim() &&
    positionDescription.trim(),
  );

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-soft">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border-muted bg-surface-muted px-4 py-3">
        <div>
          <strong className="block text-[12px] text-ink">초대 메일</strong>
          <p className="mt-0.5 text-[9px] text-muted">
            미리보기 안의 내용을 클릭하면 바로 수정할 수 있습니다.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className={BUTTON_QUIET} type="button" onClick={resetCopy}>
            <RotateCcw aria-hidden="true" size={13} />
            기본 문구
          </button>
          <button
            className={BUTTON_PRIMARY}
            disabled={!ready || saving || (!dirty && descriptionCompleted)}
            type="button"
            onClick={save}
          >
            <Check aria-hidden="true" size={14} />
            {saving ? "저장 중…" : "저장"}
          </button>
        </div>
      </header>

      {loading ? (
        <p className="p-5 text-center text-[10px] text-muted" role="status">
          초대 메일을 불러오는 중입니다.
        </p>
      ) : (
        <div className="grid gap-3 bg-canvas p-4 mw-620:p-2.5">
          {notice ? (
            <p className={formAlertClass("panel", "success")} role="status">
              {notice}
            </p>
          ) : null}
          {error ? (
            <p className={formAlertClass()} role="alert">
              {error}
            </p>
          ) : null}

          <label className="grid gap-1 text-[9px] font-semibold text-muted">
            메일 제목
            <input
              aria-label="메일 제목"
              className={`${EDITABLE} border-border bg-surface text-[11px] font-medium text-ink`}
              maxLength={200}
              value={draft.subject}
              onChange={(event) => update("subject", event.target.value)}
            />
          </label>

          <article className="mx-auto w-full max-w-[650px] overflow-hidden rounded-xl border border-border bg-white shadow-soft">
            <label
              className="relative block h-1 cursor-pointer"
              style={{ backgroundColor: draft.brandColor }}
              title="클릭해서 브랜드 색상 변경"
            >
              <span className="sr-only">브랜드 색상</span>
              <input
                aria-label="브랜드 색상"
                className="absolute inset-0 size-full cursor-pointer opacity-0"
                type="color"
                value={draft.brandColor}
                onChange={(event) =>
                  update("brandColor", normalizeBrandColor(event.target.value))
                }
              />
            </label>

            <div className="flex items-center justify-between border-b border-border-muted px-7 py-5 mw-620:px-4">
              <strong className="text-[15px]">WhyYou</strong>
              <span className="font-mono text-[9px] font-semibold text-subtle">
                ONLINE INTERVIEW
              </span>
            </div>

            <div className="grid gap-3 px-7 pt-7 mw-620:px-4">
              <span
                className="text-[10px] font-semibold"
                style={{ color: draft.brandColor }}
              >
                {positionTitle || "포지션명"}
              </span>
              <input
                aria-label="초대 메일 헤드라인"
                className={`${EDITABLE} -mx-2 text-[22px] font-bold tracking-[-0.03em] text-ink`}
                maxLength={200}
                value={draft.headline}
                onChange={(event) => update("headline", event.target.value)}
              />
              <textarea
                aria-label="초대 메일 본문"
                className={`${EDITABLE} -mx-2 min-h-[82px] resize-y text-[12px] leading-6 text-ink-secondary`}
                maxLength={2000}
                value={draft.intro}
                onChange={(event) => update("intro", event.target.value)}
              />
            </div>

            <div className="mx-7 mt-5 grid grid-cols-[72px_minmax(0,1fr)] gap-y-2 rounded-lg border border-border-muted bg-surface-muted px-4 py-3 text-[11px] mw-620:mx-4">
              <span className="text-muted">포지션</span>
              <strong>{positionTitle || "포지션명"}</strong>
              <span className="text-muted">응시 마감</span>
              <strong className="text-ink-secondary">
                면접 일정에 맞춰 자동 설정
              </strong>
            </div>

            <div className="mx-7 mt-6 mw-620:mx-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <strong className="text-[12px]">포지션 상세</strong>
                <button
                  className="text-[9px] font-semibold text-brand hover:underline"
                  type="button"
                  onClick={() =>
                    onPositionDescriptionChange(descriptionExample)
                  }
                >
                  예시 적용
                </button>
              </div>
              <textarea
                aria-label="포지션 설명"
                className={`${EDITABLE} min-h-[118px] resize-y border-border-muted bg-surface-muted text-[11px] leading-5 text-ink-secondary`}
                maxLength={POSITION_DESCRIPTION_MAX_LENGTH}
                placeholder="회사와 팀, 주요 업무, 협업 방식, 찾는 동료를 3~4줄로 설명해 주세요."
                value={positionDescription}
                onChange={(event) => {
                  onPositionDescriptionChange(event.target.value);
                  if (descriptionCompleted) onDescriptionCompleted(false);
                }}
              />
              <span className="mt-1 block text-right font-mono text-[8px] text-subtle">
                {positionDescription.length} / {POSITION_DESCRIPTION_MAX_LENGTH}
              </span>
            </div>

            <div className="grid justify-items-center gap-2 px-7 py-6 mw-620:px-4">
              <input
                aria-label="초대 버튼 문구"
                className="max-w-[220px] rounded-lg border border-transparent px-8 py-3 text-center text-[12px] font-semibold text-white outline-none hover:border-white/70 focus:border-white"
                maxLength={40}
                style={{ backgroundColor: draft.brandColor }}
                value={draft.ctaLabel}
                onChange={(event) => update("ctaLabel", event.target.value)}
              />
              <small className="text-[8px] text-subtle">
                버튼 문구도 클릭해서 수정할 수 있습니다.
              </small>
            </div>

            <div className="grid gap-2 px-7 pb-6 mw-620:px-4">
              <textarea
                aria-label="초대 메일 맺음말"
                className={`${EDITABLE} -mx-2 min-h-[58px] resize-y text-[11px] leading-5 text-ink-secondary`}
                maxLength={1000}
                value={draft.outro}
                onChange={(event) => update("outro", event.target.value)}
              />
            </div>

            <div className="bg-surface-muted px-7 py-4 mw-620:px-4">
              <input
                aria-label="초대 메일 푸터"
                className={`${EDITABLE} -mx-2 text-[9px] text-subtle`}
                maxLength={300}
                value={draft.footer}
                onChange={(event) => update("footer", event.target.value)}
              />
            </div>
          </article>
        </div>
      )}
    </section>
  );
}

function toTemplate(
  state: InvitationEmailTemplateState,
): InvitationEmailTemplate {
  return {
    subject: state.subject,
    headline: state.headline,
    intro: state.intro,
    guides: state.guides,
    ctaLabel: state.ctaLabel,
    outro: state.outro,
    footer: state.footer,
    brandColor: state.brandColor,
    useApplicantName: state.useApplicantName,
    emphasizeDeadline: state.emphasizeDeadline,
    showSecurityNotice: state.showSecurityNotice,
  };
}

function toTemplateState(
  template: InvitationEmailTemplate,
): InvitationEmailTemplateState {
  return {
    ...template,
    logoUrl: null,
    isPositionOverride: true,
  };
}
