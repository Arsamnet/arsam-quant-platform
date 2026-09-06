"""Deterministic separation of contract changes from dynamic observations."""

from dataclasses import dataclass
from typing import Any

from fx_platform.broker_validation.models import BrokerContractSnapshot
from fx_platform.serialization import canonical_json


@dataclass(frozen=True, slots=True, kw_only=True)
class BrokerSnapshotChange:
    """One field-level change with an explicit static/dynamic classification."""

    field: str
    classification: str
    before: Any
    after: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "classification": self.classification,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class BrokerContractDiff:
    """Reproducible comparison that never conflates a quote move with contract drift."""

    before_snapshot_fingerprint: str
    after_snapshot_fingerprint: str
    before_contract_fingerprint: str
    after_contract_fingerprint: str
    contract_changes: tuple[BrokerSnapshotChange, ...]
    dynamic_changes: tuple[BrokerSnapshotChange, ...]

    @classmethod
    def between(
        cls,
        before: BrokerContractSnapshot,
        after: BrokerContractSnapshot,
    ) -> "BrokerContractDiff":
        return cls(
            before_snapshot_fingerprint=before.snapshot_fingerprint,
            after_snapshot_fingerprint=after.snapshot_fingerprint,
            before_contract_fingerprint=before.contract_fingerprint,
            after_contract_fingerprint=after.contract_fingerprint,
            contract_changes=_changes(
                before.contract_payload(), after.contract_payload(), "contract"
            ),
            dynamic_changes=_changes(before.dynamic_payload(), after.dynamic_payload(), "dynamic"),
        )

    @property
    def contract_changed(self) -> bool:
        return bool(self.contract_changes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "before_snapshot_fingerprint": self.before_snapshot_fingerprint,
            "after_snapshot_fingerprint": self.after_snapshot_fingerprint,
            "before_contract_fingerprint": self.before_contract_fingerprint,
            "after_contract_fingerprint": self.after_contract_fingerprint,
            "contract_changed": self.contract_changed,
            "contract_changes": tuple(change.to_dict() for change in self.contract_changes),
            "dynamic_changes": tuple(change.to_dict() for change in self.dynamic_changes),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def _changes(before: Any, after: Any, classification: str) -> tuple[BrokerSnapshotChange, ...]:
    before_flat = _flatten(before)
    after_flat = _flatten(after)
    fields = sorted(before_flat.keys() | after_flat.keys())
    return tuple(
        BrokerSnapshotChange(
            field=field,
            classification=classification,
            before=before_flat.get(field),
            after=after_flat.get(field),
        )
        for field in fields
        if before_flat.get(field) != after_flat.get(field)
    )


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            field = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(item, field))
        return result
    if isinstance(value, (tuple, list)):
        result = {}
        for index, item in enumerate(value):
            field = f"{prefix}[{index}]"
            result.update(_flatten(item, field))
        return result
    return {prefix: value}
