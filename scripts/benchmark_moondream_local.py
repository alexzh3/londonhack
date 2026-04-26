#!/usr/bin/env python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "moondream>=1.1.0",
#   "opencv-python-headless>=4.9.0",
#   "pillow>=10.0.0",
#   "pydantic>=2.7.0",
# ]
# ///
"""Preflight and benchmark local Moondream object detection."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DETECT_SCRIPT = ROOT_DIR / "scripts" / "review_layout_objects_moondream.py"


def main() -> int:
    args = _parse_args()
    session_dir = ROOT_DIR / "demo_data" / "sessions" / args.session
    output_path = Path(args.output) if args.output else (
        session_dir / "moondream_local_benchmark.json"
    )
    detection_output = Path(args.detection_output) if args.detection_output else (
        session_dir / "object_detections.moondream.local.cached.json"
    )
    gpu = _gpu_info()
    started_at = datetime.now(timezone.utc)
    report = {
        "schema_version": "cafetwin.moondream_local_benchmark.v1",
        "session_id": args.session,
        "backend": "photon",
        "model": args.model,
        "device": args.device,
        "classes": [part.strip() for part in args.classes.split(",") if part.strip()],
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "gpu": gpu,
        "status": "pending",
        "reason": None,
        "elapsed_s": None,
        "output_path": _display_path(detection_output),
        "summary": None,
        "notes": [
            "Installed moondream 1.1.0 local Photon/Kestrel exposes model names "
            "'moondream2' and 'moondream3-preview'; it does not expose a literal "
            "'0.5B-4bit' model string.",
            "Official 2025-04-14 4-bit Moondream docs cite about 2450 MB VRAM on RTX 3090; "
            "Kestrel moondream2 weights are larger than the old experimental 0.5B edge ports.",
        ],
    }

    if _insufficient_vram(args, gpu) and not args.force:
        report["status"] = "skipped_insufficient_vram"
        report["reason"] = (
            f"free VRAM {gpu.get('memory_free_mb')} MB < required "
            f"{args.min_free_vram_mb} MB; pass --force to attempt anyway"
        )
        _write_report(output_path, report)
        print(f"[moondream-local] {report['reason']}")
        print(f"[moondream-local] wrote {_display_path(output_path)}")
        return 0

    command = [
        sys.executable,
        str(DETECT_SCRIPT),
        "--session",
        args.session,
        "--local",
        "--model",
        args.model,
        "--device",
        args.device,
        "--max-batch-size",
        str(args.max_batch_size),
        "--kv-cache-pages",
        str(args.kv_cache_pages),
        "--classes",
        args.classes,
        "--output",
        str(detection_output),
        "--no-annotated",
    ]
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=ROOT_DIR, text=True, capture_output=True, check=False)
    elapsed = time.perf_counter() - started
    report["elapsed_s"] = elapsed
    report["stdout_tail"] = proc.stdout[-4000:]
    report["stderr_tail"] = proc.stderr[-4000:]
    if proc.returncode != 0:
        report["status"] = "failed"
        report["reason"] = f"local Moondream command exited {proc.returncode}"
    else:
        report["status"] = "completed"
        try:
            cache = json.loads(detection_output.read_text(encoding="utf-8"))
            report["summary"] = cache.get("summary")
        except Exception as exc:
            report["status"] = "completed_without_summary"
            report["reason"] = str(exc)

    _write_report(output_path, report)
    print(f"[moondream-local] status={report['status']} elapsed={elapsed:.2f}s")
    if report["reason"]:
        print(f"[moondream-local] reason={report['reason']}")
    print(f"[moondream-local] wrote {_display_path(output_path)}")
    return 0 if proc.returncode == 0 else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="ai_cafe_a")
    parser.add_argument("--model", default="moondream2")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--classes", default="chair,dining table,couch,potted plant")
    parser.add_argument("--output", default=None)
    parser.add_argument("--detection-output", default=None)
    parser.add_argument("--min-free-vram-mb", type=int, default=2600)
    parser.add_argument("--max-batch-size", type=int, default=1)
    parser.add_argument("--kv-cache-pages", type=int, default=2048)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def _gpu_info() -> dict:
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,compute_cap",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return {"available": False}
    first = proc.stdout.strip().splitlines()[0]
    parts = [part.strip() for part in first.split(",")]
    if len(parts) < 4:
        return {"available": False, "raw": first}
    return {
        "available": True,
        "name": parts[0],
        "memory_total_mb": int(float(parts[1])),
        "memory_free_mb": int(float(parts[2])),
        "compute_capability": parts[3],
    }


def _insufficient_vram(args: argparse.Namespace, gpu: dict) -> bool:
    if not args.device.startswith("cuda"):
        return False
    return (not gpu.get("available")) or int(gpu.get("memory_free_mb") or 0) < args.min_free_vram_mb


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
