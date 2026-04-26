# Vision Benchmark Results

Archived results from the Tier 1 perception experiments. The ad-hoc benchmark
scripts were removed after these numbers were captured; the runtime demo uses
the checked-in/validated cache files under `demo_data/sessions/`.

## Static furniture/object detector comparison

All detector runs used the same representative frame plus sampled video frames
per session and the same target classes: chair, dining table, couch, potted
plant. Counts below are aggregated static objects after duplicate clustering.

| Session | Model | Objects | Raw detections | Chair | Dining table | Couch | Potted plant | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `ai_cafe_a` | YOLOv8x | 31 | 345 | 15 | 7 | 1 | 8 | Chosen base: strongest stable overlay. |
| `ai_cafe_a` | RT-DETR-x | 48 | 610 | 23 | 9 | 2 | 14 | Highest recall, but visibly noisier duplicate/oversized boxes. |
| `ai_cafe_a` | YOLO11x | 37 | 360 | 17 | 10 | 1 | 9 | More boxes than YOLOv8x, but introduced larger false table/counter boxes. |
| `real_cafe` | YOLOv8x | 12 | 84 | 11 | 1 | 0 | 0 | Chosen base for stable cache. |
| `real_cafe` | RT-DETR-x | 28 | 299 | 23 | 4 | 0 | 1 | Higher recall, but too noisy to promote directly. |
| `real_cafe` | YOLO11x | 12 | 83 | 11 | 1 | 0 | 0 | Similar count to YOLOv8x; no reason to switch. |

Decision: keep YOLOv8x as the base static layout detector and use the
ObjectReviewAgent-reviewed cache for the demo (`ai_cafe_a`: 23 kept / 31;
`real_cafe`: 9 kept / 12).

## Local Moondream Photon/Kestrel preflight

The installed Python `moondream` package supports local Photon/Kestrel model
names such as `moondream2` and `moondream3-preview`; it does not load legacy
`.mf` archives.

| Session | GPU | Free VRAM | Threshold | Status |
|---|---|---:|---:|---|
| `ai_cafe_a` | NVIDIA GeForce MX330 | 1993 MB | 2600 MB | skipped_insufficient_vram |
| `real_cafe` | NVIDIA GeForce MX330 | 1993 MB | 2600 MB | skipped_insufficient_vram |

Decision: do not promote local Photon/Kestrel on this laptop; the MX330 has
only about 2 GB free VRAM.

## Legacy Moondream 0.5B `.mf` ONNX artifact

Source branch: `vikhyatk/moondream2` `onnx` branch.

| Artifact | Quantization | Size | Commit / ETag | Local result |
|---|---:|---:|---|---|
| `moondream-0_5b-int8.mf.gz` | int8 | 621,619,051 bytes | commit `9dddae84d54db4ac56fe37817aeaeb502ed083e2`; ETag `2d27a34d92cdff8e7296e03e2290027ab08ba936de7649d79d2dc6ab26a94098` | Runs on ONNX Runtime CPU. |
| `moondream-0_5b-int4.mf.gz` | int4 | 442,376,060 bytes | ETag `ad3b3c3de06c60097c08d93822b93b29f2625168838ec406e5b6db243e2135bb` | Downloads/unpacks, but ONNX Runtime CPU fails `MatMulNBits` with quantized-weight shape mismatch. |

Int8 CPU detection results:

| Session | Objects kept | Raw legacy regions | Class result | Zone | Elapsed |
|---|---:|---:|---|---|---:|
| `ai_cafe_a` | 1 | 3 | 1 dining table | counter | ~28.5 s |
| `real_cafe` | 1 | 13 | 1 chair | staff_path | ~34.9 s |

Decision: the exact supplied 0.5B int8 artifact was verified end-to-end, but its
cafe-furniture boxes were weak/noisy. Keep it as provenance only; do not use it
as the demo detector.
