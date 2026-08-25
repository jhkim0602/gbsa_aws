from interview_evidence.shared.email_templates import (
    DEFAULT_INVITATION_EMAIL_TEMPLATE,
    InvitationEmailContent,
    InvitationEmailTemplate,
    render_invitation_email,
)


def test_legacy_duration_guide_is_rendered_as_the_fixed_thirty_minutes() -> None:
    template = InvitationEmailTemplate(
        subject="면접 안내",
        headline="온라인 면접 안내",
        intro="면접에 초대합니다.",
        guides=("소요 시간 | 약 25분", "준비물 | 마이크"),
        cta_label="면접 시작하기",
    )

    rendered = render_invitation_email(
        template,
        InvitationEmailContent(
            company_name="WhyYou",
            position_title="백엔드 엔지니어",
            deadline_text="2026년 8월 31일 23:59",
            invitation_url="https://example.com/access/token",
        ),
    )

    assert template.guides[0] == DEFAULT_INVITATION_EMAIL_TEMPLATE.guides[0]
    assert "약 30분" in rendered.text_body
    assert "약 25분" not in rendered.text_body
