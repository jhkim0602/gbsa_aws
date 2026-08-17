"""Render the applicant invitation email from a company-editable template.

Every ``EmailSender`` implementation renders through this module so the message a
developer inspects in mailpit is byte-for-byte the message SES delivers. The markup
is deliberately table-based with inline styles: Outlook discards ``<style>`` blocks
and ignores flex and grid, so a modern layout would collapse into a single column
for a large share of recipients. The call to action is text on a coloured cell
rather than an image so it survives clients that block remote images by default.

Applicant display names never reach this module unless the company opted in through
``use_applicant_name``; see ``InvitationEmailContent.resolved_applicant_name``.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

ANONYMOUS_APPLICANT_NAME: Final = "지원자"

_PLACEHOLDER_COMPANY: Final = "{{회사명}}"
_PLACEHOLDER_APPLICANT: Final = "{{지원자명}}"
_PLACEHOLDER_POSITION: Final = "{{포지션명}}"
_PLACEHOLDER_DEADLINE: Final = "{{마감일시}}"

SUPPORTED_PLACEHOLDERS: Final = (
    _PLACEHOLDER_COMPANY,
    _PLACEHOLDER_APPLICANT,
    _PLACEHOLDER_POSITION,
    _PLACEHOLDER_DEADLINE,
)

MAX_GUIDE_LINES: Final = 12
GUIDE_SEPARATOR: Final = "|"

LOOPBACK_HTTP_PREFIXES: Final = ("http://localhost", "http://127.0.0.1")


class InvitationEmailTemplate(BaseModel):
    """The company-editable parts of the invitation email."""

    model_config = ConfigDict(frozen=True)

    subject: str = Field(min_length=1, max_length=200)
    headline: str = Field(min_length=1, max_length=200)
    intro: str = Field(min_length=1, max_length=2_000)
    guides: tuple[str, ...] = Field(default=(), max_length=MAX_GUIDE_LINES)
    cta_label: str = Field(min_length=1, max_length=40)
    outro: str = Field(default="", max_length=1_000)
    footer: str = Field(default="", max_length=300)
    brand_color: str = Field(default="#5966ce", pattern=r"^#[0-9a-fA-F]{6}$")
    logo_url: str | None = Field(default=None, max_length=2_000)
    use_applicant_name: bool = True
    emphasize_deadline: bool = True
    show_security_notice: bool = True

    @field_validator("brand_color")
    @classmethod
    def normalize_brand_color(cls, value: str) -> str:
        return value.lower()

    @field_validator("logo_url")
    @classmethod
    def require_public_absolute_logo(cls, value: str | None) -> str | None:
        """Reject logos mail clients cannot load.

        Remote images are fetched by the recipient's mail client with no session, so a
        relative path or a presigned URL that expires renders as a broken image. Plain
        http is allowed only on loopback, where mailpit renders developer mail.
        """
        if value is None:
            return None
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.startswith("https://"):
            return candidate
        if candidate.startswith(LOOPBACK_HTTP_PREFIXES):
            return candidate
        raise ValueError("logo_url must be an absolute https URL")

    @field_validator("guides")
    @classmethod
    def drop_blank_guides(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(line.strip() for line in value if line.strip())


DEFAULT_INVITATION_EMAIL_TEMPLATE: Final = InvitationEmailTemplate(
    subject=f"[{_PLACEHOLDER_COMPANY}] {_PLACEHOLDER_POSITION} 온라인 면접 안내",
    headline="서류 전형 합격을 축하드립니다",
    intro=(
        f"{_PLACEHOLDER_APPLICANT}님, {_PLACEHOLDER_COMPANY} {_PLACEHOLDER_POSITION} 포지션에 "
        "지원해주셔서 진심으로 감사합니다.\n"
        "서류 검토 결과 다음 단계인 온라인 구조화 면접에 초대드립니다. "
        "아래 버튼으로 편한 시간에 바로 시작하실 수 있습니다."
    ),
    guides=(
        "소요 시간 | 약 25분 (중간 저장되며 이어서 진행 가능)",
        "준비물 | 웹캠, 마이크 — 헤드셋 사용을 권장합니다",
        "권장 환경 | Chrome 최신 버전, 조용하고 밝은 공간",
        "사전 제출 | 이력서·포트폴리오는 면접 시작 전 화면에서 등록합니다",
    ),
    cta_label="면접 시작하기",
    outro="좋은 결과로 만나뵙기를 기대합니다.\n궁금한 점은 아래 메일로 편하게 문의해 주세요.",
    footer="본 메일은 발신 전용입니다",
)


@dataclass(frozen=True, slots=True)
class InvitationEmailContent:
    """The per-invitation facts substituted into the template."""

    company_name: str
    position_title: str
    deadline_text: str
    invitation_url: str
    applicant_display_name: str | None = None

    def resolved_applicant_name(self, template: InvitationEmailTemplate) -> str:
        """Return the salutation, honouring the company's PII opt-in.

        With ``use_applicant_name`` disabled the display name never enters the
        rendered body, so it cannot be retained in a delivery record either.
        """
        if not template.use_applicant_name:
            return ANONYMOUS_APPLICANT_NAME
        return self.applicant_display_name or ANONYMOUS_APPLICANT_NAME


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    subject: str
    html_body: str
    text_body: str


def _substitute(
    text: str,
    template: InvitationEmailTemplate,
    content: InvitationEmailContent,
) -> str:
    return (
        text.replace(_PLACEHOLDER_COMPANY, content.company_name)
        .replace(_PLACEHOLDER_APPLICANT, content.resolved_applicant_name(template))
        .replace(_PLACEHOLDER_POSITION, content.position_title)
        .replace(_PLACEHOLDER_DEADLINE, content.deadline_text)
    )


def _lines(text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in text.split("\n") if line.strip())


def _paragraphs(text: str, style: str) -> str:
    return "".join(f'<p style="{style}">{escape(line)}</p>' for line in _lines(text))


def _guide_rows(
    template: InvitationEmailTemplate,
    content: InvitationEmailContent,
) -> str:
    rows: list[str] = []
    for line in template.guides:
        label, separator, body = line.partition(GUIDE_SEPARATOR)
        # A line without the separator is a single full-width note, not a pair.
        term = escape(_substitute(label.strip(), template, content))
        detail = escape(_substitute(body.strip(), template, content)) if separator else ""
        if not detail:
            rows.append(
                "<tr>"
                '<td colspan="2" style="padding:0 0 9px;font-size:12.5px;'
                f'line-height:1.6;color:#414051">{term}</td>'
                "</tr>"
            )
            continue
        rows.append(
            "<tr>"
            '<td width="86" valign="top" style="padding:0 0 9px;font-size:12.5px;'
            f"line-height:1.6;color:{template.brand_color};font-weight:600;"
            f'white-space:nowrap">{term}</td>'
            '<td valign="top" style="padding:0 0 9px;font-size:12.5px;'
            f'line-height:1.6;color:#414051">{detail}</td>'
            "</tr>"
        )
    return "".join(rows)


def _brand_block(
    template: InvitationEmailTemplate,
    content: InvitationEmailContent,
) -> str:
    company = escape(content.company_name)
    if template.logo_url is None:
        return (
            '<div style="font-size:15px;font-weight:700;color:#1a1f36;'
            f'letter-spacing:-0.2px">{company}</div>'
        )
    return (
        f'<img src="{escape(template.logo_url)}" alt="{company}" height="30" '
        'style="display:block;border:0;height:30px;max-height:30px;width:auto" />'
    )


def _security_notice(
    template: InvitationEmailTemplate,
    content: InvitationEmailContent,
) -> str:
    if not template.show_security_notice:
        return ""
    holder = escape(content.resolved_applicant_name(template))
    return (
        '<tr><td style="padding:0 40px 26px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'border="0" style="background:#fff8ec;border-radius:8px"><tr>'
        '<td width="3" style="background:#e0ab5a;font-size:0;line-height:0">&nbsp;</td>'
        '<td style="padding:13px 16px;font-size:11.5px;line-height:1.7;color:#8a6420">'
        f'이 링크는 <strong style="color:#6f4f14">{holder}님 본인 전용</strong>입니다. '
        "타인에게 공유하거나 재사용할 수 없으며, 마감일시가 지나면 자동으로 만료됩니다."
        "</td></tr></table></td></tr>"
    )


def render_invitation_email(
    template: InvitationEmailTemplate,
    content: InvitationEmailContent,
) -> RenderedEmail:
    """Render the invitation into a subject line plus HTML and plain-text bodies."""
    color = template.brand_color
    company = escape(content.company_name)
    position = escape(content.position_title)
    deadline = escape(content.deadline_text)
    url = escape(content.invitation_url)
    subject = _substitute(template.subject, template, content)
    headline = escape(_substitute(template.headline, template, content))
    deadline_color = "#d64545" if template.emphasize_deadline else "#1a1f36"

    html_body = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<meta name="color-scheme" content="light only" />
<title>{escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#f5f6f8;-webkit-text-size-adjust:100%">
<div style="display:none;font-size:0;line-height:0;max-height:0;overflow:hidden">\
{headline} · 마감 {deadline}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" \
style="background:#f5f6f8">
<tr><td align="center" style="padding:28px 14px 44px">

<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" \
style="width:600px;max-width:600px;background:#ffffff;border:1px solid #e6e8ee;\
border-radius:12px;overflow:hidden;font-family:Inter,Pretendard,'Noto Sans KR',\
-apple-system,'Segoe UI',sans-serif">

  <tr><td style="background:{color};height:4px;font-size:0;line-height:0">&nbsp;</td></tr>

  <tr><td style="padding:22px 40px 20px;border-bottom:1px solid #eef0f4">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td valign="middle">{_brand_block(template, content)}</td>
      <td valign="middle" align="right" style="font-size:10.5px;font-weight:600;\
letter-spacing:0.5px;color:#9a9db0">ONLINE INTERVIEW</td>
    </tr></table>
  </td></tr>

  <tr><td style="padding:32px 40px 0">
    <div style="font-size:11px;font-weight:600;letter-spacing:0.4px;color:{color};\
margin-bottom:7px">{position}</div>
    <h1 style="margin:0 0 16px;font-size:23px;line-height:1.35;font-weight:700;\
color:#1a1f36;letter-spacing:-0.4px">{headline}</h1>
    {
        _paragraphs(
            _substitute(template.intro, template, content),
            "margin:0 0 11px;font-size:13.5px;line-height:1.75;color:#414051",
        )
    }
  </td></tr>

  <tr><td style="padding:22px 40px 0">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" \
style="background:#f8f9fb;border:1px solid #eef0f4;border-radius:9px">
      <tr><td style="padding:16px 20px">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td width="72" style="padding:0 0 8px;font-size:11.5px;color:#8a8da0">포지션</td>
            <td style="padding:0 0 8px;font-size:12.5px;font-weight:600;color:#1a1f36">\
{position}</td>
          </tr>
          <tr>
            <td width="72" style="font-size:11.5px;color:#8a8da0">응시 마감</td>
            <td style="font-size:12.5px;font-weight:600;color:{deadline_color}">{deadline}</td>
          </tr>
        </table>
      </td></tr>
    </table>
  </td></tr>

  <tr><td style="padding:26px 40px 0">
    <div style="font-size:12.5px;font-weight:600;color:#1a1f36;margin-bottom:12px">\
면접 전 확인해 주세요</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">\
{_guide_rows(template, content)}</table>
  </td></tr>

  <tr><td align="center" style="padding:28px 40px 14px">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
      <td align="center" style="background:{color};border-radius:8px">
        <a href="{url}" style="display:inline-block;padding:13px 34px;font-size:14px;\
font-weight:600;color:#ffffff;text-decoration:none;letter-spacing:-0.1px">\
{escape(_substitute(template.cta_label, template, content))}</a>
      </td>
    </tr></table>
  </td></tr>

  <tr><td align="center" style="padding:0 40px 24px">
    <div style="font-size:10.5px;line-height:1.6;color:#9a9db0">
      버튼이 열리지 않으면 아래 주소를 복사해 브라우저에 붙여 넣으세요<br />
      <span style="color:#75788b;word-break:break-all">{url}</span>
    </div>
  </td></tr>

  {_security_notice(template, content)}

  <tr><td style="padding:0 40px 30px">
    {
        _paragraphs(
            _substitute(template.outro, template, content),
            "margin:0 0 6px;font-size:12.5px;line-height:1.75;color:#414051",
        )
    }
    <p style="margin:14px 0 0;font-size:12.5px;font-weight:600;color:#1a1f36">\
{company} 채용팀</p>
  </td></tr>

  <tr><td style="padding:18px 40px;background:#f8f9fb;border-top:1px solid #eef0f4">
    <div style="font-size:10.5px;line-height:1.7;color:#9a9db0">
      {escape(_substitute(template.footer, template, content))}<br />
      본 메일은 {company}의 채용 절차 안내를 위해 발송되었습니다.
    </div>
  </td></tr>

</table>
</td></tr></table></body></html>"""

    return RenderedEmail(
        subject=subject,
        html_body=html_body,
        text_body=_render_text(template, content),
    )


def _render_text(
    template: InvitationEmailTemplate,
    content: InvitationEmailContent,
) -> str:
    """Build the plain-text alternative for clients that reject HTML."""
    blocks: list[str] = [
        _substitute(template.headline, template, content),
        "",
        *_lines(_substitute(template.intro, template, content)),
        "",
        f"포지션: {content.position_title}",
        f"응시 마감: {content.deadline_text}",
    ]
    if template.guides:
        blocks.extend(("", "면접 전 확인해 주세요"))
        for line in template.guides:
            label, separator, body = line.partition(GUIDE_SEPARATOR)
            term = _substitute(label.strip(), template, content)
            detail = _substitute(body.strip(), template, content) if separator else ""
            blocks.append(f"- {term}: {detail}" if detail else f"- {term}")
    blocks.extend(
        (
            "",
            f"{_substitute(template.cta_label, template, content)}: {content.invitation_url}",
        )
    )
    if template.show_security_notice:
        blocks.extend(
            (
                "",
                f"이 링크는 {content.resolved_applicant_name(template)}님 본인 전용입니다. "
                "타인에게 공유하거나 재사용할 수 없으며, 마감일시가 지나면 자동으로 만료됩니다.",
            )
        )
    if template.outro:
        blocks.extend(("", *_lines(_substitute(template.outro, template, content))))
    blocks.extend(("", f"{content.company_name} 채용팀"))
    if template.footer:
        blocks.extend(("", _substitute(template.footer, template, content)))
    return "\n".join(blocks)
