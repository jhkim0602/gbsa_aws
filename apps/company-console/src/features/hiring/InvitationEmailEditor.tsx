import { Check, ImageUp, Plus, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  BRAND_COLOR_PRESETS,
  describeLogoRejection,
  fromGuideLines,
  isBrandColor,
  LOGO_CONTENT_TYPES,
  MAX_GUIDE_LINES,
  normalizeBrandColor,
  templateEquals,
  toGuideLines,
  type InvitationEmailTemplate,
  type InvitationEmailTemplateApi,
  type InvitationEmailTemplateState,
} from "./invitationEmailTemplate";

type EditorScope =
  | { kind: "company" }
  | { kind: "position"; positionId: string; positionName?: string };

/** Guides are edited as one textarea and split into lines only on submit. */
type Draft = Omit<InvitationEmailTemplate, "guides"> & { guidesText: string };

const PREVIEW_DEBOUNCE_MS = 350;

export function InvitationEmailEditor({
  api,
  scope,
  onSaved,
  onClose,
}: {
  api: InvitationEmailTemplateApi;
  scope: EditorScope;
  onSaved?: (state: InvitationEmailTemplateState) => void;
  onClose?: () => void;
}) {
  const positionScope = scope.kind === "position";
  const [saved, setSaved] = useState<InvitationEmailTemplateState | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewSubject, setPreviewSubject] = useState("");
  const [device, setDevice] = useState<"desktop" | "mobile">("desktop");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [customColors, setCustomColors] = useState<readonly string[]>([]);
  const [colorInput, setColorInput] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useMemo(
    () => () =>
      scope.kind === "position"
        ? api.getPositionTemplate(scope.positionId)
        : api.getCompanyTemplate(),
    [api, scope],
  );

  useEffect(() => {
    let active = true;
    setLoading(true);
    load()
      .then((state) => {
        if (!active) return;
        setSaved(state);
        setDraft(toDraft(state));
      })
      .catch(() => {
        if (active) {
          setError("초대 메일 템플릿을 불러오지 못했습니다.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [load]);

  const template = useMemo(() => (draft ? toTemplate(draft) : null), [draft]);
  const dirty = Boolean(template && saved && !templateEquals(template, saved));

  // The preview is rendered by the same server-side renderer that sends the mail, so
  // what the recruiter approves here is exactly what a recipient receives.
  useEffect(() => {
    if (!template) return;
    let active = true;
    const timer = setTimeout(() => {
      api
        .previewTemplate(template)
        .then((result) => {
          if (!active) return;
          setPreviewHtml(result.htmlBody);
          setPreviewSubject(result.subject);
        })
        .catch(() => {
          if (active) setError("미리보기를 만들 수 없습니다.");
        });
    }, PREVIEW_DEBOUNCE_MS);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [api, template]);

  function update<K extends keyof Draft>(key: K, value: Draft[K]) {
    setNotice("");
    setDraft((current) => (current ? { ...current, [key]: value } : current));
  }

  function appendVariable(key: "subject" | "intro", variable: string) {
    setDraft((current) =>
      current ? { ...current, [key]: `${current[key]}${variable}` } : current,
    );
  }

  function applyColor(value: string) {
    update("brandColor", normalizeBrandColor(value));
  }

  function addCustomColor() {
    const candidate = normalizeBrandColor(colorInput);
    if (!isBrandColor(candidate)) {
      setError("색상은 #RRGGBB 형식으로 입력하세요.");
      return;
    }
    setError("");
    setCustomColors((current) =>
      current.includes(candidate) ? current : [...current, candidate],
    );
    setColorInput("");
    applyColor(candidate);
  }

  async function save() {
    if (!template) return;
    setSaving(true);
    setError("");
    try {
      const next =
        scope.kind === "position"
          ? await api.savePositionTemplate(scope.positionId, template)
          : await api.saveCompanyTemplate(template);
      setSaved(next);
      setDraft(toDraft(next));
      setNotice(
        positionScope
          ? "이 포지션의 초대 메일을 저장했습니다."
          : "전사 기본 초대 메일을 저장했습니다.",
      );
      onSaved?.(next);
      onClose?.();
    } catch {
      setError("저장하지 못했습니다. 입력값을 확인해 주세요.");
    } finally {
      setSaving(false);
    }
  }

  async function revert() {
    setSaving(true);
    setError("");
    try {
      const next =
        scope.kind === "position"
          ? await api.resetPositionTemplate(scope.positionId)
          : await api.resetCompanyTemplate();
      setSaved(next);
      setDraft(toDraft(next));
      setNotice(
        positionScope
          ? "전사 기본값을 다시 따르도록 되돌렸습니다."
          : "플랫폼 기본 문구로 되돌렸습니다.",
      );
      onSaved?.(next);
    } catch {
      setError("되돌리지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setSaving(false);
    }
  }

  async function uploadLogo(file: File | undefined) {
    if (!file) return;
    const rejection = describeLogoRejection(file);
    if (rejection) {
      setError(rejection);
      return;
    }
    setError("");
    try {
      const logo = await api.uploadLogo(file);
      setSaved((current) =>
        current ? { ...current, logoUrl: logo.logoUrl } : current,
      );
      setNotice("로고를 등록했습니다.");
    } catch {
      setError("로고를 올리지 못했습니다.");
    }
  }

  async function removeLogo() {
    setError("");
    try {
      await api.deleteLogo();
      setSaved((current) =>
        current ? { ...current, logoUrl: null } : current,
      );
      setNotice("로고를 삭제했습니다. 회사명이 대신 표시됩니다.");
    } catch {
      setError("로고를 삭제하지 못했습니다.");
    }
  }

  if (loading || !draft || !saved) {
    return (
      <div className="async-state" role={error ? "alert" : "status"}>
        {error || "초대 메일 템플릿을 불러오는 중입니다."}
      </div>
    );
  }

  const scopeTag = positionScope ? (
    <span className="template-scope is-position">이 포지션만</span>
  ) : (
    <span className="template-scope is-global">전사 공통</span>
  );
  const swatches = [...BRAND_COLOR_PRESETS, ...customColors];

  return (
    <div className="template-editor">
      <div className="template-editor__form">
        {notice ? (
          <p className="form-alert is-success" role="status">
            {notice}
          </p>
        ) : null}
        {error ? (
          <p className="form-alert" role="alert">
            {error}
          </p>
        ) : null}

        {positionScope ? (
          <p className="template-editor__scope-note">
            변경한 문구는 <strong>이 포지션에만</strong> 적용됩니다. 전사
            기본값은 설정 › 초대 메일 템플릿에서 바꿉니다.
            {saved.isPositionOverride
              ? " 현재 이 포지션은 자체 문구를 사용합니다."
              : " 현재 이 포지션은 전사 기본값을 따릅니다."}
          </p>
        ) : null}

        <section className="template-group">
          <h3>브랜딩 {scopeTag}</h3>
          <div className="form-field">
            <span className="template-label">
              <strong>기업 로고</strong>
              <small>PNG / SVG / JPG / WebP · 최대 512KB</small>
            </span>
            <div className="template-logo">
              {saved.logoUrl ? (
                <img src={saved.logoUrl} alt="등록된 기업 로고" height={30} />
              ) : (
                <span className="template-logo__empty">로고 없음</span>
              )}
              <div className="template-logo__actions">
                <button
                  className="button-secondary"
                  type="button"
                  onClick={() => fileInput.current?.click()}
                >
                  <ImageUp size={14} aria-hidden="true" />
                  {saved.logoUrl ? "로고 교체" : "로고 업로드"}
                </button>
                {saved.logoUrl ? (
                  <button
                    className="button-quiet"
                    type="button"
                    onClick={() => void removeLogo()}
                  >
                    <Trash2 size={14} aria-hidden="true" />
                    삭제
                  </button>
                ) : null}
              </div>
              <input
                ref={fileInput}
                className="sr-only"
                type="file"
                aria-label="기업 로고 파일"
                accept={LOGO_CONTENT_TYPES.join(",")}
                onChange={(event) => {
                  void uploadLogo(event.currentTarget.files?.[0]);
                  event.currentTarget.value = "";
                }}
              />
            </div>
            <small className="form-field__hint">
              로고는 전사 공통이며, 메일 앱이 인증 없이 불러갈 수 있도록 공개
              주소로 제공됩니다.
            </small>
          </div>

          <div className="form-field">
            <span className="template-label">
              <strong>브랜드 색상</strong>
              <small>상단 바 · 포지션 라벨 · 안내 제목 · CTA 버튼에 적용</small>
            </span>
            <div
              className="template-swatches"
              role="group"
              aria-label="브랜드 색상"
            >
              {swatches.map((color) => (
                <button
                  key={color}
                  className={`template-swatch ${
                    draft.brandColor === color ? "is-active" : ""
                  }`}
                  type="button"
                  style={{ background: color }}
                  aria-label={`브랜드 색상 ${color}`}
                  aria-pressed={draft.brandColor === color}
                  onClick={() => applyColor(color)}
                >
                  {draft.brandColor === color ? (
                    <Check size={13} aria-hidden="true" />
                  ) : null}
                </button>
              ))}
            </div>
            <div className="template-color-add">
              <input
                type="color"
                aria-label="색상 선택기"
                value={isBrandColor(colorInput) ? colorInput : draft.brandColor}
                onChange={(event) => setColorInput(event.target.value)}
              />
              <input
                type="text"
                aria-label="브랜드 색상 직접 입력"
                placeholder="#5966ce"
                maxLength={7}
                value={colorInput}
                onChange={(event) => setColorInput(event.target.value)}
              />
              <button
                className="button-secondary"
                type="button"
                onClick={addCustomColor}
              >
                <Plus size={14} aria-hidden="true" />
                색상 추가
              </button>
            </div>
          </div>
        </section>

        <section className="template-group">
          <h3>문구 {scopeTag}</h3>
          <TemplateField
            label="메일 제목"
            value={draft.subject}
            maxLength={200}
            variables={["{{회사명}}", "{{포지션명}}", "{{지원자명}}"]}
            onInsert={(variable) => appendVariable("subject", variable)}
            onChange={(value) => update("subject", value)}
          />
          <TemplateField
            label="헤드라인"
            note="축하 인사"
            value={draft.headline}
            maxLength={200}
            onChange={(value) => update("headline", value)}
          />
          <TemplateField
            label="본문 인사"
            note="감사 인사"
            rows={4}
            value={draft.intro}
            maxLength={2000}
            variables={["{{지원자명}}", "{{회사명}}", "{{포지션명}}"]}
            onInsert={(variable) => appendVariable("intro", variable)}
            onChange={(value) => update("intro", value)}
          />
          <TemplateField
            label="안내 메시지"
            note="한 줄에 하나씩"
            hint={`"제목 | 내용" 형태로 쓰면 두 칸으로 정렬됩니다. 최대 ${MAX_GUIDE_LINES}줄.`}
            rows={5}
            value={draft.guidesText}
            onChange={(value) => update("guidesText", value)}
          />
          <TemplateField
            label="버튼 텍스트"
            value={draft.ctaLabel}
            maxLength={40}
            onChange={(value) => update("ctaLabel", value)}
          />
          <TemplateField
            label="맺음말"
            rows={2}
            value={draft.outro}
            maxLength={1000}
            onChange={(value) => update("outro", value)}
          />
          <TemplateField
            label="푸터 · 문의처"
            value={draft.footer}
            maxLength={300}
            onChange={(value) => update("footer", value)}
          />
        </section>

        <section className="template-group">
          <h3>옵션 {scopeTag}</h3>
          <TemplateToggle
            label="지원자 실명 사용"
            description="끄면 “지원자님”으로 대체되어, 실명이 메일 본문에 들어가지 않습니다."
            checked={draft.useApplicantName}
            onChange={(value) => update("useApplicantName", value)}
          />
          <TemplateToggle
            label="마감일시 강조"
            description="포지션 정보 카드에서 마감일을 붉게 표시합니다."
            checked={draft.emphasizeDeadline}
            onChange={(value) => update("emphasizeDeadline", value)}
          />
          <TemplateToggle
            label="보안 안내문 표시"
            description="본인 전용·재사용 불가 안내를 넣습니다. 끄지 않는 것을 권합니다."
            checked={draft.showSecurityNotice}
            onChange={(value) => update("showSecurityNotice", value)}
          />
        </section>
      </div>

      <div className="template-editor__preview">
        <header className="template-preview__bar">
          <div>
            <strong>미리보기</strong>
            <small>{previewSubject || "샘플 지원자 데이터로 렌더링"}</small>
          </div>
          <div className="segmented-control template-preview__device">
            {(
              [
                ["desktop", "데스크톱"],
                ["mobile", "모바일"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={device === value ? "is-active" : ""}
                aria-pressed={device === value}
                onClick={() => setDevice(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </header>
        <div className="template-preview__stage">
          <iframe
            className={`template-preview__frame is-${device}`}
            title="초대 메일 미리보기"
            // The preview is company-authored copy rendered by our own server; the
            // sandbox keeps it from running scripts or navigating the console.
            sandbox=""
            srcDoc={previewHtml}
          />
        </div>
        <footer className="template-preview__foot">
          <span aria-live="polite">
            {dirty
              ? "저장하지 않은 변경이 있습니다."
              : "변경 사항은 저장 전까지 발송되지 않습니다."}
          </span>
          <button
            className="button-quiet"
            type="button"
            disabled={saving}
            onClick={() => void revert()}
          >
            <RotateCcw size={14} aria-hidden="true" />
            {positionScope ? "전사 기본값 따르기" : "기본 문구로 되돌리기"}
          </button>
          {onClose ? (
            <button
              className="button-secondary"
              type="button"
              onClick={onClose}
            >
              닫기
            </button>
          ) : null}
          <button
            className="button-primary"
            type="button"
            disabled={saving || !dirty}
            onClick={() => void save()}
          >
            {saving ? "저장 중" : onClose ? "저장하고 닫기" : "저장"}
          </button>
        </footer>
      </div>
    </div>
  );
}

function TemplateField({
  label,
  note,
  hint,
  rows,
  value,
  maxLength,
  variables,
  onChange,
  onInsert,
}: {
  label: string;
  note?: string;
  hint?: string;
  rows?: number;
  value: string;
  maxLength?: number;
  variables?: readonly string[];
  onChange(value: string): void;
  onInsert?(variable: string): void;
}) {
  return (
    <div className="form-field template-field">
      <label className="form-field__control">
        <span className="template-label">
          <strong>{label}</strong>
          {note ? <small>{note}</small> : null}
        </span>
        {rows ? (
          <textarea
            rows={rows}
            value={value}
            maxLength={maxLength}
            onChange={(event) => onChange(event.target.value)}
          />
        ) : (
          <input
            type="text"
            value={value}
            maxLength={maxLength}
            onChange={(event) => onChange(event.target.value)}
          />
        )}
      </label>
      {hint ? <small className="form-field__hint">{hint}</small> : null}
      {variables && onInsert ? (
        <div className="template-variables">
          {variables.map((variable) => (
            <button
              key={variable}
              className="template-variable"
              type="button"
              aria-label={`${label}에 ${variable} 넣기`}
              onClick={() => onInsert(variable)}
            >
              {variable}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function TemplateToggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange(value: boolean): void;
}) {
  return (
    <label className="template-toggle">
      <span>
        <strong>{label}</strong>
        <small>{description}</small>
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
    </label>
  );
}

function toDraft(state: InvitationEmailTemplateState): Draft {
  return {
    subject: state.subject,
    headline: state.headline,
    intro: state.intro,
    guidesText: fromGuideLines(state.guides),
    ctaLabel: state.ctaLabel,
    outro: state.outro,
    footer: state.footer,
    brandColor: state.brandColor,
    useApplicantName: state.useApplicantName,
    emphasizeDeadline: state.emphasizeDeadline,
    showSecurityNotice: state.showSecurityNotice,
  };
}

function toTemplate(draft: Draft): InvitationEmailTemplate {
  return {
    subject: draft.subject,
    headline: draft.headline,
    intro: draft.intro,
    guides: toGuideLines(draft.guidesText),
    ctaLabel: draft.ctaLabel,
    outro: draft.outro,
    footer: draft.footer,
    brandColor: normalizeBrandColor(draft.brandColor),
    useApplicantName: draft.useApplicantName,
    emphasizeDeadline: draft.emphasizeDeadline,
    showSecurityNotice: draft.showSecurityNotice,
  };
}
