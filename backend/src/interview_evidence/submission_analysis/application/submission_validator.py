from __future__ import annotations

import ipaddress
from pathlib import PurePath
from urllib.parse import urlparse

from interview_evidence.submission_analysis.domain.submission import SourceType


class SubmissionValidationError(ValueError):
    """Raised before untrusted material reaches storage or fetch workers."""


class SubmissionValidator:
    def __init__(self, *, max_file_bytes: int = 20 * 1024 * 1024) -> None:
        self._max_file_bytes = max_file_bytes

    def validate_file(
        self,
        *,
        source_type: SourceType,
        filename: str,
        media_type: str,
        byte_size: int,
        content_hash: str,
    ) -> None:
        if source_type not in {
            SourceType.COVER_LETTER,
            SourceType.RESUME,
            SourceType.PDF,
        }:
            raise SubmissionValidationError("source type is not a file")
        if byte_size < 1 or byte_size > self._max_file_bytes:
            raise SubmissionValidationError("file size is outside the configured limit")
        safe_name = PurePath(filename).name
        if safe_name != filename or safe_name.casefold() in {
            ".env",
            "id_rsa",
            "credentials",
        }:
            raise SubmissionValidationError("filename is not allowed")
        if media_type != "application/pdf" or not filename.casefold().endswith(".pdf"):
            raise SubmissionValidationError("only PDF documents are accepted")
        if len(content_hash) != 64 or any(
            character not in "0123456789abcdef" for character in content_hash
        ):
            raise SubmissionValidationError("sha256 is invalid")

    def validate_public_url(
        self,
        *,
        source_type: SourceType,
        public_url: str,
    ) -> str:
        parsed = urlparse(public_url)
        if parsed.scheme != "https" or parsed.hostname is None:
            raise SubmissionValidationError("public URL must use HTTPS")
        if parsed.username or parsed.password:
            raise SubmissionValidationError("URL credentials are prohibited")
        if any(
            key.casefold() in {"token", "key", "secret", "password"}
            for key in (part.split("=", 1)[0] for part in parsed.query.split("&"))
            if key
        ):
            raise SubmissionValidationError("URL contains a secret-like query")
        hostname = parsed.hostname.casefold()
        if hostname in {"localhost", "localhost.localdomain"}:
            raise SubmissionValidationError("local addresses are prohibited")
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise SubmissionValidationError("private addresses are prohibited")
        if source_type is SourceType.PUBLIC_GIT and hostname not in {
            "github.com",
            "gitlab.com",
            "bitbucket.org",
        }:
            raise SubmissionValidationError("unsupported public Git host")
        return parsed.geturl()
