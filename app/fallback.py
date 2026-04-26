"""Fallback loaders for cached recommendations and demo-safe responses."""

from __future__ import annotations

import json

from app.schemas import (
    CafeEvidencePack,
    LayoutChange,
    OperationalPattern,
    PatternEvidenceBundle,
)
from app.layout_candidates import validate_expected_kpi_delta, validate_layout_geometry
from app.sessions import session_dir


def load_cached_recommendation(session_id: str) -> LayoutChange:
    path = session_dir(session_id) / "recommendation.cached.json"
    return LayoutChange.model_validate(json.loads(path.read_text(encoding="utf-8")))


def load_cached_pattern(session_id: str) -> OperationalPattern:
    """Load the demo-safe pattern fixture used as PatternAgent's fallback."""
    path = session_dir(session_id) / "pattern_fixture.json"
    return OperationalPattern.model_validate(json.loads(path.read_text(encoding="utf-8")))


def validate_layout_change(change: LayoutChange, pack: CafeEvidencePack) -> list[str]:
    """Return validation errors for agent output that drifts from the evidence pack."""
    errors: list[str] = []
    allowed_evidence_ids = {ref.memory_id for ref in pack.pattern.evidence}
    cited_ids = set(change.evidence_ids)
    object_ids = {obj.id for obj in pack.object_inventory.objects}

    if not cited_ids <= allowed_evidence_ids:
        errors.append(
            "evidence_ids must be a subset of pattern evidence IDs: "
            f"{sorted(allowed_evidence_ids)}"
        )
    if change.target_id not in object_ids:
        errors.append(f"target_id {change.target_id!r} is not in object_inventory")
    if change.simulation.target_id != change.target_id:
        errors.append("simulation.target_id must match target_id")
    errors.extend(validate_layout_geometry(change, pack))
    errors.extend(validate_expected_kpi_delta(change, pack))

    return errors


def validate_operational_pattern(
    pattern: OperationalPattern,
    bundle: PatternEvidenceBundle,
) -> list[str]:
    """Return validation errors for PatternAgent output that drifts from the
    evidence bundle. Only checks hard constraints — severity / pattern_type /
    titles are the agent's call."""
    errors: list[str] = []
    allowed_kpi_memory_ids = {window.memory_id for window in bundle.kpi_windows}
    cited_evidence_ids = {ref.memory_id for ref in pattern.evidence}
    allowed_zone_ids = {zone.id for zone in bundle.zones}
    cited_zone_ids = set(pattern.affected_zones)

    if not cited_evidence_ids:
        errors.append("evidence must cite at least one kpi_windows[*].memory_id")
    elif not cited_evidence_ids <= allowed_kpi_memory_ids:
        errors.append(
            "evidence[*].memory_id must be a subset of kpi_windows[*].memory_id: "
            f"{sorted(allowed_kpi_memory_ids)}"
        )

    if not cited_zone_ids:
        errors.append("affected_zones must reference at least one zone")
    elif not cited_zone_ids <= allowed_zone_ids:
        errors.append(
            "affected_zones must be a subset of zones[*].id: "
            f"{sorted(allowed_zone_ids)}"
        )

    return errors
