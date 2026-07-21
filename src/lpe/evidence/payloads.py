"""Typed FindingPayload discriminated union (CLOSURE-010 / spec §10.1).

Bare ``dict`` payloads remain accepted for backward compatibility and are
treated as opaque bags. Prefer typed variants for new providers.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

FINDING_PAYLOAD_DISCRIMINATOR = "payload_type"


class _PayloadModel(BaseModel):
    """Local strict base to avoid circular import with ``lpe.models``."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class OpaqueFindingPayload(_PayloadModel):
    """Catch-all for legacy or provider-specific bags."""

    payload_type: Literal["OpaqueFindingPayload"] = "OpaqueFindingPayload"
    data: dict[str, Any] = Field(default_factory=dict)


class SynthesisFindingPayload(_PayloadModel):
    """Evidence synthesis rule output (CLOSURE-011)."""

    payload_type: Literal["SynthesisFindingPayload"] = "SynthesisFindingPayload"
    synthesis_rule: str
    source_check_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class StructuralDiffFindingPayload(_PayloadModel):
    """Declaration / structural comparison findings."""

    payload_type: Literal["StructuralDiffFindingPayload"] = "StructuralDiffFindingPayload"
    changed_names: list[str] = Field(default_factory=list)
    base_refs: list[str] = Field(default_factory=list)
    head_refs: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutedCheckFindingPayload(_PayloadModel):
    """Findings backed by an executed sandboxed command."""

    payload_type: Literal["ExecutedCheckFindingPayload"] = "ExecutedCheckFindingPayload"
    check_id: str
    exit_code: int | None = None
    timed_out: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("check_id")
    @classmethod
    def require_check_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("check_id must be non-empty")
        return cleaned


FindingPayload = Annotated[
    OpaqueFindingPayload
    | SynthesisFindingPayload
    | StructuralDiffFindingPayload
    | ExecutedCheckFindingPayload,
    Field(discriminator=FINDING_PAYLOAD_DISCRIMINATOR),
]

_FINDING_PAYLOAD_ADAPTER: TypeAdapter[FindingPayload] = TypeAdapter(FindingPayload)


def parse_finding_payload(raw: Any) -> FindingPayload | dict[str, Any] | None:
    """Parse a finding payload, preserving bare dicts without ``payload_type``.

    Typed variants validate fail-closed. Legacy bags without a discriminator
    remain ``dict`` so golden packets and provider dumps stay shape-compatible.
    """
    if raw is None:
        return None
    if isinstance(
        raw,
        (
            OpaqueFindingPayload,
            SynthesisFindingPayload,
            StructuralDiffFindingPayload,
            ExecutedCheckFindingPayload,
        ),
    ):
        return raw
    if isinstance(raw, dict):
        if FINDING_PAYLOAD_DISCRIMINATOR in raw:
            return _FINDING_PAYLOAD_ADAPTER.validate_python(raw)
        return dict(raw)
    raise TypeError(f"unsupported finding payload type: {type(raw)!r}")


def finding_payload_as_dict(
    payload: FindingPayload | dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Normalize payload to a JSON-compatible dict for logging / details merge."""
    if payload is None:
        return None
    if isinstance(payload, dict):
        return dict(payload)
    return payload.model_dump(mode="json")


def opaque_finding_payload(details: dict[str, Any]) -> OpaqueFindingPayload:
    """Wrap a provider details bag as an opaque typed payload."""
    return OpaqueFindingPayload(data=dict(details))


def _infer_changed_names(details: dict[str, Any]) -> list[str]:
    if isinstance(details.get("changed_names"), list):
        return [str(x) for x in details["changed_names"]]
    compared = details.get("compared")
    if isinstance(compared, list):
        names: list[str] = []
        for item in compared:
            if isinstance(item, dict) and item.get("name") is not None:
                names.append(str(item["name"]))
        if names:
            return names
    changed = details.get("changed")
    if isinstance(changed, list):
        return [str(x) for x in changed]
    decls = details.get("candidate_declarations")
    if isinstance(decls, list):
        return [str(x) for x in decls]
    return []


def structural_diff_payload(
    details: dict[str, Any],
    *,
    changed_names: list[str] | None = None,
    base_refs: list[str] | None = None,
    head_refs: list[str] | None = None,
) -> StructuralDiffFindingPayload:
    """Build a structural/declaration-diff payload from provider details."""
    return StructuralDiffFindingPayload(
        changed_names=list(
            changed_names if changed_names is not None else _infer_changed_names(details)
        ),
        base_refs=list(base_refs or []),
        head_refs=list(head_refs or []),
        details=dict(details),
    )


def executed_check_payload(
    check_id: str,
    details: dict[str, Any],
    *,
    exit_code: int | None = None,
    timed_out: bool | None = None,
) -> ExecutedCheckFindingPayload:
    """Build an executed-check payload, pulling exit metadata from details when present."""
    code = exit_code
    timed = timed_out
    if code is None and "exit_code" in details:
        raw = details.get("exit_code")
        code = int(raw) if isinstance(raw, int) else None
    if timed is None and "timed_out" in details:
        raw_t = details.get("timed_out")
        timed = bool(raw_t) if isinstance(raw_t, bool) else None
    # Nested lake / successor reports often carry exit metadata one level down.
    if code is None:
        for key in ("lake_dependent_check", "lake_result", "run"):
            nested = details.get(key)
            if isinstance(nested, dict) and isinstance(nested.get("exit_code"), int):
                code = nested["exit_code"]
                break
    return ExecutedCheckFindingPayload(
        check_id=check_id,
        exit_code=code,
        timed_out=timed,
        details=dict(details),
    )
