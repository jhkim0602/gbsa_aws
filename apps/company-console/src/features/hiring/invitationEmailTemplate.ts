export type InvitationEmailTemplate = {
  subject: string;
  headline: string;
  intro: string;
  /** One guide line per entry. "제목 | 내용" renders as two aligned columns. */
  guides: readonly string[];
  ctaLabel: string;
  outro: string;
  footer: string;
  brandColor: string;
  useApplicantName: boolean;
  emphasizeDeadline: boolean;
  showSecurityNotice: boolean;
};

export type InvitationEmailTemplateState = InvitationEmailTemplate & {
  /** Server-derived; a client cannot choose the logo host. */
  logoUrl: string | null;
  isPositionOverride: boolean;
};

export type CompanyLogo = {
  logoUrl: string;
  contentType: string;
  byteSize: number;
};

export type InvitationEmailTemplateApi = Readonly<{
  getCompanyTemplate(): Promise<InvitationEmailTemplateState>;
  saveCompanyTemplate(
    template: InvitationEmailTemplate,
  ): Promise<InvitationEmailTemplateState>;
  resetCompanyTemplate(): Promise<InvitationEmailTemplateState>;
  getPositionTemplate(
    positionId: string,
  ): Promise<InvitationEmailTemplateState>;
  savePositionTemplate(
    positionId: string,
    template: InvitationEmailTemplate,
  ): Promise<InvitationEmailTemplateState>;
  resetPositionTemplate(
    positionId: string,
  ): Promise<InvitationEmailTemplateState>;
  previewTemplate(template: InvitationEmailTemplate): Promise<{
    subject: string;
    htmlBody: string;
  }>;
  uploadLogo(file: File): Promise<CompanyLogo>;
  deleteLogo(): Promise<void>;
}>;

export const MAX_LOGO_BYTES = 512 * 1024;
export const MAX_GUIDE_LINES = 12;
export const LOGO_CONTENT_TYPES = [
  "image/png",
  "image/svg+xml",
  "image/jpeg",
  "image/webp",
] as const;

export const BRAND_COLOR_PRESETS = [
  "#5966ce",
  "#1e9e63",
  "#d64545",
  "#0f172a",
  "#c77d11",
] as const;

const HEX_COLOR = /^#[0-9a-fA-F]{6}$/;

export function isBrandColor(value: string) {
  return HEX_COLOR.test(value.trim());
}

export function normalizeBrandColor(value: string) {
  return value.trim().toLowerCase();
}

/** Split the textarea the recruiter types into the guide lines the API expects. */
export function toGuideLines(text: string): readonly string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .slice(0, MAX_GUIDE_LINES);
}

export function fromGuideLines(guides: readonly string[]) {
  return guides.join("\n");
}

export function describeLogoRejection(file: File): string | null {
  if (!(LOGO_CONTENT_TYPES as readonly string[]).includes(file.type)) {
    return "PNG, SVG, JPG, WebP 형식만 올릴 수 있습니다.";
  }
  if (file.size > MAX_LOGO_BYTES) {
    return "로고 파일은 512KB 이하여야 합니다.";
  }
  if (file.size === 0) {
    return "빈 파일은 올릴 수 없습니다.";
  }
  return null;
}

export function templateEquals(
  left: InvitationEmailTemplate,
  right: InvitationEmailTemplate,
) {
  return (
    left.subject === right.subject &&
    left.headline === right.headline &&
    left.intro === right.intro &&
    left.ctaLabel === right.ctaLabel &&
    left.outro === right.outro &&
    left.footer === right.footer &&
    left.brandColor === right.brandColor &&
    left.useApplicantName === right.useApplicantName &&
    left.emphasizeDeadline === right.emphasizeDeadline &&
    left.showSecurityNotice === right.showSecurityNotice &&
    left.guides.length === right.guides.length &&
    left.guides.every((guide, index) => guide === right.guides[index])
  );
}
