"""Deterministic layout-shift candidates for OptimizationAgent."""

from __future__ import annotations

import math

from app.schemas import (
    CafeEvidencePack,
    LayoutCandidate,
    LayoutChange,
    LayoutSimulation,
    OptimizationChoice,
    SceneObject,
    SimulationAction,
    Zone,
)

MAX_SHIFT_PX = 180.0
FROM_POSITION_TOLERANCE_PX = 1.0
FIXED_COLLISION_IOU = 0.02

ACTION_BY_KIND: dict[str, SimulationAction] = {
    "table": "move_table",
    "chair": "move_chair",
    "counter": "move_station",
    "pickup_shelf": "move_station",
    "queue_marker": "change_queue_boundary",
    "barrier": "change_queue_boundary",
}

ALLOWED_ZONE_KINDS_BY_OBJECT = {
    "table": {"seating"},
    "chair": {"seating"},
    "counter": {"counter", "pickup", "staff_path"},
    "pickup_shelf": {"pickup", "counter", "staff_path"},
    "queue_marker": {"queue", "pickup", "staff_path", "entrance"},
    "barrier": {"queue", "pickup", "staff_path", "entrance"},
}

SERVICE_ZONE_KINDS = {"counter", "pickup", "queue", "staff_path", "entrance"}
GENERATED_TARGET_KINDS = {"table", "counter", "pickup_shelf", "queue_marker", "barrier"}

CANDIDATE_DELTAS: tuple[tuple[float, float], ...] = (
    (90.0, 60.0),
    (-90.0, 60.0),
    (90.0, -60.0),
    (-90.0, -60.0),
    (80.0, 20.0),
    (-80.0, -20.0),
    (80.0, 0.0),
    (-80.0, 0.0),
    (0.0, 80.0),
    (0.0, -80.0),
    (120.0, 0.0),
    (-120.0, 0.0),
)


def generate_layout_candidates(pack: CafeEvidencePack, limit: int = 12) -> list[LayoutCandidate]:
    candidates = []
    for obj in pack.object_inventory.objects:
        action = ACTION_BY_KIND.get(obj.kind)
        if action is None or not obj.movable or obj.kind not in GENERATED_TARGET_KINDS:
            continue
        for dx, dy in CANDIDATE_DELTAS:
            to_position = (obj.center_xy[0] + dx, obj.center_xy[1] + dy)
            simulation = LayoutSimulation(
                action=action,
                target_id=obj.id,
                from_position=obj.center_xy,
                to_position=to_position,
                rotation_degrees=obj.rotation_degrees,
            )
            if validate_simulation_geometry(simulation, pack, obj):
                continue
            score, reasons = _score_candidate(pack, obj, simulation)
            if score <= 0:
                continue
            candidate_id = _candidate_id(obj, action, dx, dy)
            candidates.append(
                LayoutCandidate(
                    candidate_id=candidate_id,
                    fingerprint=_fingerprint(pack.session_id, candidate_id),
                    action=action,
                    target_id=obj.id,
                    target_kind=obj.kind,
                    from_position=obj.center_xy,
                    to_position=to_position,
                    rotation_degrees=obj.rotation_degrees,
                    expected_kpi_delta=_expected_kpi_delta(pack, score),
                    score=round(score, 3),
                    reasons=reasons,
                )
            )
    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)[:limit]


def validate_optimization_choice(
    choice: OptimizationChoice,
    pack: CafeEvidencePack,
    candidates: list[LayoutCandidate] | None = None,
) -> list[str]:
    errors: list[str] = []
    candidates = candidates if candidates is not None else generate_layout_candidates(pack)
    candidate_ids = {candidate.candidate_id for candidate in candidates}
    if choice.selected_candidate_id not in candidate_ids:
        errors.append(
            "selected_candidate_id must be one of generated candidates: "
            f"{sorted(candidate_ids)}"
        )
    if len(choice.title) > 120:
        errors.append("title must be 120 characters or fewer")
    if len(choice.rationale) > 700:
        errors.append("rationale must be 700 characters or fewer")
    if "score" in choice.rationale.lower():
        errors.append("rationale must not quote candidate scores")
    errors.extend(_validate_evidence_ids(choice.evidence_ids, pack))
    return errors


def materialize_layout_change(
    choice: OptimizationChoice,
    pack: CafeEvidencePack,
    candidates: list[LayoutCandidate] | None = None,
) -> LayoutChange:
    candidates = candidates if candidates is not None else generate_layout_candidates(pack)
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    candidate = candidate_by_id.get(choice.selected_candidate_id)
    if candidate is None:
        raise ValueError(f"unknown layout candidate: {choice.selected_candidate_id}")
    return LayoutChange(
        title=choice.title,
        rationale=choice.rationale,
        target_id=candidate.target_id,
        simulation=LayoutSimulation(
            action=candidate.action,
            target_id=candidate.target_id,
            from_position=candidate.from_position,
            to_position=candidate.to_position,
            rotation_degrees=candidate.rotation_degrees,
        ),
        evidence_ids=choice.evidence_ids,
        expected_kpi_delta=candidate.expected_kpi_delta,
        confidence=choice.confidence,
        risk=choice.risk,
        fingerprint=candidate.fingerprint,
    )


def validate_layout_geometry(change: LayoutChange, pack: CafeEvidencePack) -> list[str]:
    target = _object_by_id(pack).get(change.target_id)
    if target is None:
        return []
    return validate_simulation_geometry(change.simulation, pack, target)


def validate_expected_kpi_delta(change: LayoutChange, pack: CafeEvidencePack) -> list[str]:
    pattern_fields = {ref.kpi_field for ref in pack.pattern.evidence if ref.kpi_field}
    if not pattern_fields:
        return []
    if not (set(change.expected_kpi_delta) & pattern_fields):
        return [
            "expected_kpi_delta must include at least one KPI field cited by "
            f"pattern evidence: {sorted(pattern_fields)}"
        ]
    if not any(
        field in pattern_fields and delta < 0
        for field, delta in change.expected_kpi_delta.items()
    ):
        return ["expected_kpi_delta must improve at least one KPI cited by pattern evidence"]
    return []


def validate_simulation_geometry(
    simulation: LayoutSimulation,
    pack: CafeEvidencePack,
    target: SceneObject,
) -> list[str]:
    errors: list[str] = []
    expected_action = ACTION_BY_KIND.get(target.kind)
    if expected_action is None:
        errors.append(f"target kind {target.kind!r} cannot be moved by the MVP simulator")
    elif simulation.action != expected_action:
        errors.append(
            f"simulation.action must be {expected_action!r} for target kind {target.kind!r}"
        )
    if simulation.target_id != target.id:
        errors.append("simulation.target_id must match target_id")
    if not target.movable:
        errors.append(f"target_id {target.id!r} is not movable")
    if _distance(simulation.from_position, target.center_xy) > FROM_POSITION_TOLERANCE_PX:
        errors.append(
            "simulation.from_position must equal the target object's current center_xy "
            "within 1px"
        )
    shift_distance = _distance(simulation.from_position, simulation.to_position)
    if shift_distance <= 0:
        errors.append("simulation.to_position must differ from from_position")
    if shift_distance > MAX_SHIFT_PX:
        errors.append(f"simulation shift distance must be <= {MAX_SHIFT_PX:.0f}px")
    shifted_bbox = _bbox_at(target, simulation.to_position)
    if not _bbox_inside_frame(shifted_bbox, _frame_bounds(pack)):
        errors.append("shifted target bbox must stay inside the source frame")
    if not _position_allowed(target, simulation.to_position, pack.zones):
        errors.append(
            f"simulation.to_position for {target.kind!r} must stay in an allowed zone"
        )
    collisions = [
        other.id
        for other in pack.object_inventory.objects
        if other.id != target.id
        and not other.movable
        and _bbox_iou(shifted_bbox, other.bbox_xyxy) > FIXED_COLLISION_IOU
    ]
    if collisions:
        errors.append("shifted target bbox collides with fixed object(s): " + ", ".join(collisions))
    return errors


def _validate_evidence_ids(evidence_ids: list[str], pack: CafeEvidencePack) -> list[str]:
    allowed_evidence_ids = {ref.memory_id for ref in pack.pattern.evidence}
    cited_ids = set(evidence_ids)
    if cited_ids <= allowed_evidence_ids:
        return []
    return [
        "evidence_ids must be a subset of pattern evidence IDs: "
        f"{sorted(allowed_evidence_ids)}"
    ]


def _score_candidate(
    pack: CafeEvidencePack,
    target: SceneObject,
    simulation: LayoutSimulation,
) -> tuple[float, list[str]]:
    affected = [zone for zone in pack.zones if zone.id in pack.pattern.affected_zones]
    service_zones = [zone for zone in affected if zone.kind in SERVICE_ZONE_KINDS]
    before_bbox = target.bbox_xyxy
    after_bbox = _bbox_at(target, simulation.to_position)
    before_overlap = _zone_overlap_ratio(before_bbox, service_zones)
    after_overlap = _zone_overlap_ratio(after_bbox, service_zones)
    overlap_gain = max(0.0, before_overlap - after_overlap)
    distance_gain = _service_distance_gain(service_zones, target.center_xy, simulation.to_position)
    kind_base = {
        "table": 0.34,
        "queue_marker": 0.38,
        "barrier": 0.34,
        "pickup_shelf": 0.28,
        "counter": 0.22,
        "chair": 0.12,
    }.get(target.kind, 0.08)
    zone_bonus = 0.12 if target.zone_id in pack.pattern.affected_zones else 0.0
    source_bonus = 0.08 if target.source in {"manual", "fixture"} else -0.03
    confidence_bonus = target.confidence * 0.08
    move_penalty = _distance(simulation.from_position, simulation.to_position) / MAX_SHIFT_PX * 0.08
    score = (
        kind_base
        + zone_bonus
        + source_bonus
        + confidence_bonus
        + overlap_gain * 0.55
        + distance_gain * 0.24
        - move_penalty
    )
    reasons = ["valid geometry", "no fixed-object collision"]
    if overlap_gain > 0.01:
        reasons.append("reduces overlap with affected service zones")
    if distance_gain > 0.01:
        reasons.append("moves pressure away from the bottleneck centroid")
    if target.zone_id in pack.pattern.affected_zones:
        reasons.append(f"target starts in affected zone {target.zone_id}")
    if target.source in {"manual", "fixture"}:
        reasons.append("uses reviewed fixture object")
    return max(0.0, score), reasons


def _expected_kpi_delta(pack: CafeEvidencePack, score: float) -> dict[str, float]:
    fields: list[str] = []
    for ref in pack.pattern.evidence:
        if ref.kpi_field and ref.kpi_field not in fields:
            fields.append(ref.kpi_field)
    if not fields:
        fields = ["congestion_score"]
    impact = min(1.0, max(0.2, score))
    deltas = {}
    for field in fields:
        if field == "staff_walk_distance_px":
            deltas[field] = -round(35.0 + impact * 80.0, 1)
        elif field == "staff_customer_crossings":
            deltas[field] = -round(1.0 + impact * 2.2, 1)
        elif field == "queue_obstruction_seconds":
            deltas[field] = -round(4.0 + impact * 7.5, 1)
        elif field == "congestion_score":
            deltas[field] = -round(0.05 + impact * 0.12, 2)
        elif field == "table_detour_score":
            deltas[field] = -round(0.15 + impact * 0.35, 2)
    return deltas


def _object_by_id(pack: CafeEvidencePack) -> dict[str, SceneObject]:
    return {obj.id: obj for obj in pack.object_inventory.objects}


def _frame_bounds(pack: CafeEvidencePack) -> tuple[float, float, float, float]:
    xs = [0.0]
    ys = [0.0]
    for zone in pack.zones:
        for x, y in zone.polygon:
            xs.append(x)
            ys.append(y)
    for obj in pack.object_inventory.objects:
        x1, y1, x2, y2 = obj.bbox_xyxy
        xs.extend([x1, x2])
        ys.extend([y1, y2])
    return (0.0, 0.0, max(xs), max(ys))


def _bbox_at(obj: SceneObject, center: tuple[float, float]) -> tuple[float, float, float, float]:
    w, h = obj.size_xy
    return (
        center[0] - w / 2.0,
        center[1] - h / 2.0,
        center[0] + w / 2.0,
        center[1] + h / 2.0,
    )


def _bbox_inside_frame(
    bbox: tuple[float, float, float, float],
    frame: tuple[float, float, float, float],
) -> bool:
    x1, y1, x2, y2 = bbox
    fx1, fy1, fx2, fy2 = frame
    return x1 >= fx1 and y1 >= fy1 and x2 <= fx2 and y2 <= fy2


def _position_allowed(
    obj: SceneObject,
    position: tuple[float, float],
    zones: list[Zone],
) -> bool:
    allowed_kinds = ALLOWED_ZONE_KINDS_BY_OBJECT.get(obj.kind)
    if not allowed_kinds:
        return False
    if not zones:
        return True
    for zone in zones:
        if zone.kind in allowed_kinds and _point_in_polygon(position, zone.polygon):
            return True
    return False


def _zone_overlap_ratio(
    bbox: tuple[float, float, float, float],
    zones: list[Zone],
) -> float:
    area = _bbox_area(bbox) or 1.0
    overlap = sum(_bbox_intersection_area(bbox, _zone_bbox(zone)) for zone in zones)
    return min(1.0, overlap / area)


def _service_distance_gain(
    service_zones: list[Zone],
    before: tuple[float, float],
    after: tuple[float, float],
) -> float:
    if not service_zones:
        return 0.0
    cx, cy = _zones_centroid(service_zones)
    before_distance = _distance(before, (cx, cy))
    after_distance = _distance(after, (cx, cy))
    return max(0.0, min(1.0, (after_distance - before_distance) / 250.0))


def _zones_centroid(zones: list[Zone]) -> tuple[float, float]:
    points = [point for zone in zones for point in zone.polygon]
    if not points:
        return (0.0, 0.0)
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _zone_bbox(zone: Zone) -> tuple[float, float, float, float]:
    xs = [point[0] for point in zone.polygon]
    ys = [point[1] for point in zone.polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _bbox_intersection_area(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(
        0.0, min(ay2, by2) - max(ay1, by1)
    )


def _bbox_iou(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    inter = _bbox_intersection_area(a, b)
    if inter <= 0:
        return 0.0
    return inter / ((_bbox_area(a) + _bbox_area(b) - inter) or 1e-9)


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        ):
            inside = not inside
        j = i
    return inside


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _candidate_id(
    obj: SceneObject,
    action: SimulationAction,
    dx: float,
    dy: float,
) -> str:
    return f"{action}_{_slug(obj.id)}_{_signed(dx)}_{_signed(dy)}"


def _fingerprint(session_id: str, candidate_id: str) -> str:
    return _slug(f"{session_id}_{candidate_id}")[:96]


def _signed(value: float) -> str:
    rounded = int(round(value))
    prefix = "p" if rounded >= 0 else "m"
    return f"{prefix}{abs(rounded)}"


def _slug(value: str) -> str:
    chars = []
    for char in value.lower():
        chars.append(char if char.isalnum() else "_")
    return "_".join(part for part in "".join(chars).split("_") if part)
