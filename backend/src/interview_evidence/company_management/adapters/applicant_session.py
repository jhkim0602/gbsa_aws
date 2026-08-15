from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.ids import Clock, SystemClock, new_uuid7
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    PrincipalNotFoundError,
)


class InvitationTokenNotFoundError(PermissionError):
    """Raised without revealing whether an invitation existed."""


class InvitationTokenExpiredError(PermissionError):
    """Raised when an invitation token is outside its finite validity period."""


class InvitationTokenAlreadyUsedError(PermissionError):
    """Raised when a one-time invitation token is replayed."""


@dataclass(frozen=True, slots=True)
class IssuedInvitationToken:
    invitation_id: UUID
    token_hash: str
    expires_at: datetime
    raw_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ApplicantSessionCookie:
    expires_at: datetime
    raw_value: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ApplicantTokenRecord:
    invitation_id: UUID
    company_id: UUID
    applicant_id: UUID
    token_hash: str
    expires_at: datetime
    consumed_at: datetime | None = None


class ApplicantSessionStore(Protocol):
    def save_token(
        self,
        *,
        token_hash: str,
        company_id: UUID,
        invitation_id: UUID,
        applicant_id: UUID,
        expires_at: datetime,
    ) -> None: ...

    def get_token(self, token_hash: str) -> ApplicantTokenRecord | None: ...

    def consume_token(self, token_hash: str, *, consumed_at: datetime) -> None: ...

    def save_session(
        self,
        *,
        session_hash: str,
        principal: ApplicantPrincipal,
        expires_at: datetime,
    ) -> None: ...

    def get_session(self, session_hash: str, *, now: datetime) -> ApplicantPrincipal | None: ...

    def revoke_session(self, session_hash: str) -> None: ...


class InMemoryApplicantSessionStore:
    def __init__(self) -> None:
        self.tokens: dict[str, ApplicantTokenRecord] = {}
        self.sessions: dict[str, tuple[ApplicantPrincipal, datetime]] = {}

    def save_token(
        self,
        *,
        token_hash: str,
        company_id: UUID,
        invitation_id: UUID,
        applicant_id: UUID,
        expires_at: datetime,
    ) -> None:
        self.tokens[token_hash] = ApplicantTokenRecord(
            invitation_id=invitation_id,
            company_id=company_id,
            applicant_id=applicant_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

    def get_token(self, token_hash: str) -> ApplicantTokenRecord | None:
        return self.tokens.get(token_hash)

    def consume_token(self, token_hash: str, *, consumed_at: datetime) -> None:
        current = self.tokens[token_hash]
        self.tokens[token_hash] = ApplicantTokenRecord(
            invitation_id=current.invitation_id,
            company_id=current.company_id,
            applicant_id=current.applicant_id,
            token_hash=current.token_hash,
            expires_at=current.expires_at,
            consumed_at=consumed_at,
        )

    def save_session(
        self,
        *,
        session_hash: str,
        principal: ApplicantPrincipal,
        expires_at: datetime,
    ) -> None:
        self.sessions[session_hash] = (principal, expires_at)

    def get_session(self, session_hash: str, *, now: datetime) -> ApplicantPrincipal | None:
        stored = self.sessions.get(session_hash)
        if stored is None:
            return None
        principal, expires_at = stored
        return None if now >= expires_at else principal

    def revoke_session(self, session_hash: str) -> None:
        self.sessions.pop(session_hash, None)


class ApplicantSessionAdapter:
    def __init__(
        self,
        *,
        clock: Clock | None = None,
        session_ttl: timedelta = timedelta(hours=12),
        token_pepper: bytes = b"local-development-pepper",
        store: ApplicantSessionStore | None = None,
    ) -> None:
        self._clock = clock or SystemClock()
        self._session_ttl = session_ttl
        self._token_pepper = token_pepper
        self._store = store or InMemoryApplicantSessionStore()

    @property
    def persisted_token_hashes(self) -> tuple[str, ...]:
        if isinstance(self._store, InMemoryApplicantSessionStore):
            return tuple(record.token_hash for record in self._store.tokens.values())
        return ()

    def hash_token(self, raw_token: str) -> str:
        return hmac.new(
            self._token_pepper,
            raw_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def issue_token(
        self,
        *,
        invitation_id: UUID,
        company_id: UUID,
        applicant_id: UUID,
        expires_at: datetime,
    ) -> IssuedInvitationToken:
        raw_token = secrets.token_urlsafe(48)
        token_hash = self.hash_token(raw_token)
        self._store.save_token(
            token_hash=token_hash,
            company_id=company_id,
            invitation_id=invitation_id,
            applicant_id=applicant_id,
            expires_at=expires_at,
        )
        return IssuedInvitationToken(
            invitation_id=invitation_id,
            token_hash=token_hash,
            expires_at=expires_at,
            raw_token=raw_token,
        )

    def exchange(
        self,
        raw_token: str,
    ) -> tuple[ApplicantPrincipal, ApplicantSessionCookie]:
        token_hash = self.hash_token(raw_token)
        record = self._store.get_token(token_hash)
        if record is None:
            raise InvitationTokenNotFoundError("invitation token is invalid")
        now = self._clock.now()
        if record.consumed_at is not None:
            raise InvitationTokenAlreadyUsedError("invitation token has already been used")
        if now >= record.expires_at:
            raise InvitationTokenExpiredError("invitation token has expired")

        self._store.consume_token(token_hash, consumed_at=now)
        session_id = new_uuid7(now)
        principal = ApplicantPrincipal(
            company_id=record.company_id,
            invitation_id=record.invitation_id,
            applicant_id=record.applicant_id,
            session_id=session_id,
        )
        raw_session = secrets.token_urlsafe(48)
        session_hash = self.hash_token(raw_session)
        expires_at = min(record.expires_at, now + self._session_ttl)
        self._store.save_session(
            session_hash=session_hash,
            principal=principal,
            expires_at=expires_at,
        )
        return principal, ApplicantSessionCookie(
            raw_value=raw_session,
            expires_at=expires_at,
        )

    def get_applicant_principal(self, credential: str) -> ApplicantPrincipal:
        session_hash = self.hash_token(credential)
        principal = self._store.get_session(session_hash, now=self._clock.now())
        if principal is None:
            raise PrincipalNotFoundError("applicant principal not found")
        return principal

    def revoke(self, credential: str) -> None:
        self._store.revoke_session(self.hash_token(credential))
