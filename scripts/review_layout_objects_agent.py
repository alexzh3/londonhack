#!/usr/bin/env python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pydantic-ai>=1.16.0",
#   "pydantic>=2.7.0",
# ]
# ///
"""Review static layout detections with a Pydantic AI agent."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.agents.object_review_agent import run_object_review  # noqa: E402
from app.vision.objects import (  # noqa: E402
    ObjectReviewBundle,
    load_object_detections_cache,
    reviewed_object_cache,
    write_object_detections_cache,
    write_object_review_result,
)


def main() -> int:
    args = _parse_args()
    session_dir = ROOT_DIR / "demo_data" / "sessions" / args.session
    detector_path = Path(args.detector_cache) if args.detector_cache else (
        session_dir / "object_detections.cached.json"
    )
    vlm_path = Path(args.vlm_cache) if args.vlm_cache else (
        session_dir / "object_detections.moondream.cached.json"
    )
    review_path = Path(args.review_output) if args.review_output else (
        session_dir / "object_review.cached.json"
    )
    reviewed_path = Path(args.reviewed_output) if args.reviewed_output else (
        session_dir / "object_detections.reviewed.cached.json"
    )

    detector_cache = load_object_detections_cache(detector_path)
    vlm_cache = load_object_detections_cache(vlm_path) if vlm_path.exists() else None
    bundle = ObjectReviewBundle(
        session_id=args.session,
        detector_cache=detector_cache,
        vlm_cache=vlm_cache,
    )

    review, used_fallback = asyncio.run(run_object_review(bundle))
    write_object_review_result(review_path, review)

    reviewed = reviewed_object_cache(
        detector_cache,
        review,
        model=_reviewed_model_name(detector_cache.model, vlm_cache.model if vlm_cache else None, used_fallback),
        generated_at=datetime.now(timezone.utc),
    )
    write_object_detections_cache(reviewed_path, reviewed)

    kept = sum(1 for decision in review.decisions if decision.action == "keep")
    dropped = len(review.decisions) - kept
    print(f"[object-review] wrote {_display_path(review_path)}")
    print(f"[object-review] wrote {_display_path(reviewed_path)}")
    print(
        "[object-review] "
        f"used_fallback={used_fallback} · kept={kept} · dropped={dropped} · "
        f"vlm={'yes' if vlm_cache else 'no'}"
    )
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="ai_cafe_a")
    parser.add_argument("--detector-cache", default=None)
    parser.add_argument("--vlm-cache", default=None)
    parser.add_argument("--review-output", default=None)
    parser.add_argument("--reviewed-output", default=None)
    return parser.parse_args()


def _reviewed_model_name(detector_model: str, vlm_model: str | None, used_fallback: bool) -> str:
    parts = [detector_model]
    if vlm_model:
        parts.append(vlm_model)
    parts.append("heuristic_object_review" if used_fallback else "object_review_agent")
    return "+".join(parts)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
