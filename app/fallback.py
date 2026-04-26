"""Fallback loaders for cached recommendations and demo-safe responses."""

from __future__ import annotations

import json

from app.schemas import CafeEvidencePack, LayoutChange
from app.sessions import session_dir


def load_cached_recommendation(session_id: str) -> LayoutChange:
    path = session_dir(session_id) / "recommendation.cached.json"
    return LayoutChange.model_validate(json.loads(path.read_text(encoding="utf-8")))


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

    return errors
