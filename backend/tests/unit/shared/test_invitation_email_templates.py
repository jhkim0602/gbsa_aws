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


def test_position_description_replaces_legacy_guide_rows() -> None:
    rendered = render_invitation_email(
        DEFAULT_INVITATION_EMAIL_TEMPLATE,
        InvitationEmailContent(
            company_name="WhyYou",
            position_title="백엔드 엔지니어",
            position_description=(
                "서버 API와 데이터 처리 기능을 구현합니다.\n작은 팀에서 제품 개선에 참여합니다."
            ),
            deadline_text="2026년 8월 31일 23:59",
            invitation_url="https://example.com/access/token",
        ),
    )

    assert "포지션 상세" in rendered.html_body
    assert "서버 API와 데이터 처리 기능을 구현합니다." in rendered.html_body
    assert "면접 전 확인해 주세요" not in rendered.html_body
    assert "약 30분" not in rendered.text_body
