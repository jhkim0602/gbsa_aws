from urllib.parse import urlparse

from interview_evidence.company_management.api.company_routes import (
    _invitation_access_url,
)


def test_invitation_access_url_places_token_in_path() -> None:
    invitation_url = _invitation_access_url(
        "https://applicant.example/access/",
        "url-safe-invitation-token",
    )

    parsed = urlparse(invitation_url)
    assert parsed.query == ""
    assert parsed.path == "/access/url-safe-invitation-token"
