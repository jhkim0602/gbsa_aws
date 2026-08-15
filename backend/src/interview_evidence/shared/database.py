from __future__ import annotations

from contextvars import ContextVar, Token
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from starlette.middleware.base import RequestResponseEndpoint

_request_scope: ContextVar[str | None] = ContextVar(
    "database_request_scope",
    default=None,
)


class RequestScopedDatabase:
    def __init__(
        self,
        database_url: str,
        *,
        engine: Engine | None = None,
    ) -> None:
        self.engine = engine or create_engine(
            database_url,
            pool_pre_ping=True,
        )
        self._sessions = scoped_session(
            sessionmaker(
                bind=self.engine,
                autoflush=False,
                expire_on_commit=False,
            ),
            scopefunc=self._scope_key,
        )

    @staticmethod
    def _scope_key() -> str:
        scope = _request_scope.get()
        if scope is None:
            raise RuntimeError("database session requested outside a transaction scope")
        return scope

    @property
    def session(self) -> Session:
        return cast(Session, self._sessions)

    def begin_scope(self) -> Token[str | None]:
        return _request_scope.set(str(uuid4()))

    def end_scope(self, token: Token[str | None]) -> None:
        self._sessions.remove()
        _request_scope.reset(token)

    def install_http_transaction_middleware(self, application: FastAPI) -> None:
        @application.middleware("http")
        async def transaction_request(
            request: Request,
            call_next: RequestResponseEndpoint,
        ) -> Response:
            token = self.begin_scope()
            try:
                response = await call_next(request)
                if response.status_code >= 500:
                    self.session.rollback()
                else:
                    self.session.commit()
                return response
            except BaseException:
                self.session.rollback()
                raise
            finally:
                self.end_scope(token)
