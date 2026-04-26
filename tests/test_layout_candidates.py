from app.evidence_pack import build
from app.fallback import load_cached_recommendation, validate_layout_change
from app.layout_candidates import (
    generate_layout_candidates,
    materialize_layout_change,
    validate_expected_kpi_delta,
    validate_layout_geometry,
    validate_optimization_choice,
)
from app.schemas import OptimizationChoice


def test_generate_candidates_prioritizes_valid_fixture_moves():
    pack = build("ai_cafe_a")

    candidates = generate_layout_candidates(pack)

    assert candidates
    assert any(candidate.target_id == "table_center_1" for candidate in candidates)
    assert all(candidate.score > 0 for candidate in candidates)
    assert all(validate_layout_geometry(_as_change(candidate, pack), pack) == [] for candidate in candidates)


def test_generate_candidates_includes_real_cafe_queue_boundary():
    pack = build("real_cafe")

    candidates = generate_layout_candidates(pack)

    assert candidates
    assert any(candidate.target_id == "service_lane_marker_1" for candidate in candidates)


def test_cached_recommendations_pass_strict_geometry_validation():
    for session_id in ("ai_cafe_a", "real_cafe"):
        pack = build(session_id)
        cached = load_cached_recommendation(session_id)

        assert validate_layout_change(cached, pack) == []


def test_validation_rejects_freeform_bad_shift():
    pack = build("ai_cafe_a")
    cached = load_cached_recommendation("ai_cafe_a")
    bad = cached.model_copy(
        deep=True,
        update={
            "simulation": cached.simulation.model_copy(
                update={
                    "from_position": (0.0, 0.0),
                    "to_position": (2500.0, 2500.0),
                }
            ),
        },
    )

    errors = validate_layout_change(bad, pack)

    assert any("from_position" in error for error in errors)
    assert any("source frame" in error for error in errors)


def test_validation_rejects_non_improving_pattern_delta():
    pack = build("ai_cafe_a")
    cached = load_cached_recommendation("ai_cafe_a")
    bad = cached.model_copy(update={"expected_kpi_delta": {"queue_obstruction_seconds": 2.0}})

    errors = validate_expected_kpi_delta(bad, pack)

    assert errors == ["expected_kpi_delta must improve at least one KPI cited by pattern evidence"]


def test_optimization_choice_materializes_candidate_layout_change():
    pack = build("ai_cafe_a")
    candidate = generate_layout_candidates(pack)[0]
    choice = OptimizationChoice(
        selected_candidate_id=candidate.candidate_id,
        title="Use a vetted candidate",
        rationale="The selected candidate keeps the furniture in-bounds and opens the lane.",
        evidence_ids=["kpi_ai_a_w2"],
        confidence=0.82,
        risk="low",
    )

    assert validate_optimization_choice(choice, pack) == []
    change = materialize_layout_change(choice, pack)

    assert change.target_id == candidate.target_id
    assert change.simulation.to_position == candidate.to_position
    assert change.expected_kpi_delta == candidate.expected_kpi_delta
    assert change.fingerprint == candidate.fingerprint


def _as_change(candidate, pack):
    choice = OptimizationChoice(
        selected_candidate_id=candidate.candidate_id,
        title="candidate",
        rationale="candidate",
        evidence_ids=[pack.pattern.evidence[0].memory_id],
        confidence=0.5,
        risk="low",
    )
    return materialize_layout_change(choice, pack, [candidate])
