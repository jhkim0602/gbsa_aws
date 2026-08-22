from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import DateTime, Index, Integer, String, Uuid, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from interview_evidence.capacity_management.domain import (
    CapacityReservation,
    CapacityReservationStatus,
    CapacityServiceRole,
    ScheduledCapacityAction,
)
from interview_evidence.shared.persistence import Base
from interview_evidence.shared.tenant import TenantContext, require_tenant_context


class CapacityReservationRow(Base):
    __tablename__ = "capacity_reservations"
    __table_args__ = (
        Index(
            "ix_capacity_reservations_active_window",
            "status",
            "interview_at",
        ),
    )

    position_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    expected_concurrency: Mapped[int | None] = mapped_column(Integer)
    interview_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    interview_duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScheduledCapacityActionRow(Base):
    __tablename__ = "capacity_scheduled_actions"
    __table_args__ = (
        Index(
            "ix_capacity_scheduled_actions_service_time",
            "service_role",
            "effective_at",
        ),
    )

    action_name: Mapped[str] = mapped_column(String(256), primary_key=True)
    service_role: Mapped[str] = mapped_column(String(30))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    min_capacity: Mapped[int] = mapped_column(Integer)
    max_capacity: Mapped[int] = mapped_column(Integer)
    expected_load: Mapped[int] = mapped_column(Integer)
    plan_hash: Mapped[str] = mapped_column(String(64))
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CapacityPlanStateRow(Base):
    __tablename__ = "capacity_plan_state"

    plan_key: Mapped[str] = mapped_column(String(30), primary_key=True)
    plan_version: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CapacityRepository(Protocol):
    def acquire_plan_lock(self, *, now: datetime) -> None: ...

    def upsert_reservation(
        self,
        context: TenantContext,
        reservation: CapacityReservation,
    ) -> CapacityReservation: ...

    def list_reservations(self) -> tuple[CapacityReservation, ...]: ...

    def list_scheduled_actions(self) -> tuple[ScheduledCapacityAction, ...]: ...

    def replace_scheduled_actions(
        self,
        actions: Sequence[ScheduledCapacityAction],
        *,
        applied_at: datetime,
    ) -> None: ...


class SqlAlchemyCapacityRepository:
    """System-scoped planner store; tenant scope is enforced on every event upsert."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def acquire_plan_lock(self, *, now: datetime) -> None:
        state = self._session.scalar(
            select(CapacityPlanStateRow)
            .where(CapacityPlanStateRow.plan_key == "global")
            .with_for_update()
        )
        if state is None:
            state = CapacityPlanStateRow(
                plan_key="global",
                plan_version=0,
                updated_at=now,
            )
            self._session.add(state)
            self._session.flush()
        state.plan_version += 1
        state.updated_at = now
        self._session.flush()

    def upsert_reservation(
        self,
        context: TenantContext,
        reservation: CapacityReservation,
    ) -> CapacityReservation:
        tenant = require_tenant_context(context)
        tenant.assert_company(reservation.company_id)
        row = self._session.get(CapacityReservationRow, reservation.position_id)
        if row is not None:
            tenant.assert_company(row.company_id)
            if row.source_version >= reservation.source_version:
                return _reservation_from_row(row)
        if row is None:
            row = CapacityReservationRow(
                position_id=reservation.position_id,
                company_id=reservation.company_id,
                source_version=reservation.source_version,
                status=reservation.status.value,
                expected_concurrency=reservation.expected_concurrency,
                interview_at=reservation.interview_at,
                interview_duration_minutes=reservation.interview_duration_minutes,
                updated_at=reservation.updated_at,
            )
            self._session.add(row)
        else:
            row.source_version = reservation.source_version
            row.status = reservation.status.value
            row.expected_concurrency = reservation.expected_concurrency
            row.interview_at = reservation.interview_at
            row.interview_duration_minutes = reservation.interview_duration_minutes
            row.updated_at = reservation.updated_at
        self._session.flush()
        return reservation

    def list_reservations(self) -> tuple[CapacityReservation, ...]:
        rows = self._session.scalars(
            select(CapacityReservationRow).order_by(
                CapacityReservationRow.interview_at,
                CapacityReservationRow.position_id,
            )
        )
        return tuple(_reservation_from_row(row) for row in rows)

    def list_scheduled_actions(self) -> tuple[ScheduledCapacityAction, ...]:
        rows = self._session.scalars(
            select(ScheduledCapacityActionRow).order_by(
                ScheduledCapacityActionRow.effective_at,
                ScheduledCapacityActionRow.action_name,
            )
        )
        return tuple(_action_from_row(row) for row in rows)

    def replace_scheduled_actions(
        self,
        actions: Sequence[ScheduledCapacityAction],
        *,
        applied_at: datetime,
    ) -> None:
        self._session.execute(delete(ScheduledCapacityActionRow))
        self._session.add_all(
            [
                ScheduledCapacityActionRow(
                    action_name=action.action_name,
                    service_role=action.service_role.value,
                    effective_at=action.effective_at,
                    min_capacity=action.min_capacity,
                    max_capacity=action.max_capacity,
                    expected_load=action.expected_load,
                    plan_hash=action.plan_hash,
                    applied_at=applied_at,
                )
                for action in actions
            ]
        )
        self._session.flush()


class InMemoryCapacityRepository:
    def __init__(self) -> None:
        self.reservations: dict[UUID, CapacityReservation] = {}
        self.actions: dict[str, ScheduledCapacityAction] = {}
        self.plan_version = 0

    def acquire_plan_lock(self, *, now: datetime) -> None:
        del now
        self.plan_version += 1

    def upsert_reservation(
        self,
        context: TenantContext,
        reservation: CapacityReservation,
    ) -> CapacityReservation:
        tenant = require_tenant_context(context)
        tenant.assert_company(reservation.company_id)
        existing = self.reservations.get(reservation.position_id)
        if existing is not None:
            tenant.assert_company(existing.company_id)
            if existing.source_version >= reservation.source_version:
                return existing
        self.reservations[reservation.position_id] = reservation
        return reservation

    def list_reservations(self) -> tuple[CapacityReservation, ...]:
        return tuple(self.reservations.values())

    def list_scheduled_actions(self) -> tuple[ScheduledCapacityAction, ...]:
        return tuple(self.actions.values())

    def replace_scheduled_actions(
        self,
        actions: Sequence[ScheduledCapacityAction],
        *,
        applied_at: datetime,
    ) -> None:
        del applied_at
        self.actions = {action.action_name: action for action in actions}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _reservation_from_row(row: CapacityReservationRow) -> CapacityReservation:
    return CapacityReservation(
        position_id=row.position_id,
        company_id=row.company_id,
        source_version=row.source_version,
        status=CapacityReservationStatus(row.status),
        expected_concurrency=row.expected_concurrency,
        interview_at=_aware(row.interview_at) if row.interview_at is not None else None,
        interview_duration_minutes=row.interview_duration_minutes,
        updated_at=_aware(row.updated_at),
    )


def _action_from_row(row: ScheduledCapacityActionRow) -> ScheduledCapacityAction:
    return ScheduledCapacityAction(
        action_name=row.action_name,
        service_role=CapacityServiceRole(row.service_role),
        effective_at=_aware(row.effective_at),
        min_capacity=row.min_capacity,
        max_capacity=row.max_capacity,
        expected_load=row.expected_load,
        plan_hash=row.plan_hash,
    )
