from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.release_gate import (
    ReleaseGate,
    ReleaseGateCheck,
    ReleaseGateEvaluation,
    ReleaseGateVersion,
)
from app.schemas.release_gate import (
    ReleaseGateCreate,
    ReleaseGateEvaluationCreate,
    ReleaseGateVersionCreate,
)


class ReleaseGateRepository:
    """Persist versioned policies and immutable evidence-backed decisions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: ReleaseGateCreate) -> ReleaseGate:
        gate = ReleaseGate(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
        )
        gate.versions.append(
            ReleaseGateVersion(
                version=1,
                **payload.initial_version.model_dump(),
            )
        )
        self.session.add(gate)
        self._commit()
        return self.get_by_id(gate.id) or gate

    def create_version(
        self,
        gate_id: UUID,
        payload: ReleaseGateVersionCreate,
    ) -> ReleaseGateVersion:
        version = ReleaseGateVersion(
            release_gate_id=gate_id,
            version=self.get_latest_version_number(gate_id) + 1,
            **payload.model_dump(),
        )
        self.session.add(version)
        self._commit()
        self.session.refresh(version)
        return version

    def get_by_id(self, gate_id: UUID) -> ReleaseGate | None:
        statement = (
            select(ReleaseGate)
            .where(ReleaseGate.id == gate_id)
            .options(selectinload(ReleaseGate.versions))
            .execution_options(populate_existing=True)
        )
        return self.session.scalar(statement)

    def get_by_slug(self, slug: str) -> ReleaseGate | None:
        statement = select(ReleaseGate).where(ReleaseGate.slug == slug)
        return self.session.scalar(statement)

    def list_all(self, *, offset: int = 0, limit: int = 100) -> list[ReleaseGate]:
        statement = (
            select(ReleaseGate)
            .order_by(ReleaseGate.created_at, ReleaseGate.id)
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def get_latest_version_number(self, gate_id: UUID) -> int:
        statement = select(func.max(ReleaseGateVersion.version)).where(
            ReleaseGateVersion.release_gate_id == gate_id
        )
        return self.session.scalar(statement) or 0

    def get_latest_version(self, gate_id: UUID) -> ReleaseGateVersion | None:
        statement = (
            select(ReleaseGateVersion)
            .where(ReleaseGateVersion.release_gate_id == gate_id)
            .order_by(ReleaseGateVersion.version.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def create_evaluation(
        self,
        gate_version_id: UUID,
        payload: ReleaseGateEvaluationCreate,
        *,
        evaluation_status: str,
        checks: list[ReleaseGateCheck],
    ) -> ReleaseGateEvaluation:
        evaluation = ReleaseGateEvaluation(
            release_gate_version_id=gate_version_id,
            candidate_run_id=payload.candidate_run_id,
            baseline_run_id=payload.baseline_run_id,
            status=evaluation_status,
            checks=checks,
        )
        self.session.add(evaluation)
        self._commit()
        return self.get_evaluation(evaluation.id) or evaluation

    def get_evaluation(
        self,
        evaluation_id: UUID,
    ) -> ReleaseGateEvaluation | None:
        statement = (
            select(ReleaseGateEvaluation)
            .where(ReleaseGateEvaluation.id == evaluation_id)
            .options(selectinload(ReleaseGateEvaluation.checks))
        )
        return self.session.scalar(statement)

    def list_evaluations(
        self,
        gate_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ReleaseGateEvaluation]:
        statement = (
            select(ReleaseGateEvaluation)
            .join(ReleaseGateVersion)
            .where(ReleaseGateVersion.release_gate_id == gate_id)
            .options(selectinload(ReleaseGateEvaluation.checks))
            .order_by(ReleaseGateEvaluation.created_at, ReleaseGateEvaluation.id)
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
