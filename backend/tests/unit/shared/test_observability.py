from interview_evidence.shared.observability import sanitize_log_event


def test_log_sanitizer_redacts_protected_fields_recursively() -> None:
    event = sanitize_log_event(
        {
            "event": "request.failed",
            "token": "raw-token",
            "nested": {
                "answer_text": "protected answer",
                "signed_url": "https://example.invalid/private",
                "code": "TIMEOUT",
            },
        }
    )

    assert event["token"] == "[REDACTED]"
    assert event["nested"]["answer_text"] == "[REDACTED]"
    assert event["nested"]["signed_url"] == "[REDACTED]"
    assert event["nested"]["code"] == "TIMEOUT"
