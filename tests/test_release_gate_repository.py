from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.release_gate import ReleaseGateRepository
from app.schemas.release_gate import ReleaseGateCreate, ReleaseGateVersionCreate


def test_repository_versions_release_gate_policies(db_session: Session) -> None:
    repository = ReleaseGateRepository(db_session)
    gate = repository.create(
        ReleaseGateCreate(
            name="Production Gate",
            slug="production-gate",
        )
    )

    version = repository.create_version(
        gate.id,
        ReleaseGateVersionCreate(
            min_pass_rate=Decimal("0.95"),
            max_errored_cases=1,
            change_note="Allow one provider error during the pilot.",
        ),
    )

    assert version.version == 2
    assert repository.get_latest_version_number(gate.id) == 2
    assert repository.get_latest_version(gate.id) is version
    assert [item.version for item in repository.get_by_id(gate.id).versions] == [1, 2]
    assert repository.list_all() == [gate]
