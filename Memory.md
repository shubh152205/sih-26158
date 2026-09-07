# Project State & Execution Memory (Memory.md)

## System: SIH26158 — Tactical 3D Reconstruction Engine
**Last Updated:** 2026-09-07  
**Current Status:** Architecture & Specification Baseline Established; Ready for Phase 1 Coding  
**Active Phase:** Phase 1 — Ingestion, Telemetry Parsing & Geodetic Synchronization

---

## 1. Project Context & Objectives

- **Mission:** High-speed, defense-grade 3D spatial reconstruction from single-pass monocular UAV video without Ground Control Points (GCPs) or loop closures.
- **Sponsor & Challenge:** National Technical Research Organisation (NTRO) / Smart India Hackathon 2026 (Software Track: Robotics & Drones).
- **Core Strategy:** Foundation feed-forward vision transformers (Fast3R/MASt3R) for pointmap regression + closed-form Kabsch SVD relative camera poses + closed-form weighted Umeyama $\mathrm{Sim}(3)$ georeferencing with DOP weights + surface-aligned 3D Gaussian Splatting (SuGaR) with SDF Marching Tetrahedra + anti-hallucination confidence gating.
- **Hardware Target:** Single NVIDIA RTX 4090 / 3090 GPU (24GB VRAM), turnaround time $< 15$ minutes for 3-minute 4K video.

---

## 2. Active Specification Files

| Document | Purpose | File Link |
| :--- | :--- | :--- |
| **Requirements** | Project Requirements Document (PRD) | [PRD.md](file:///run/media/askshubh/New%20Volume/Downloads/Projects/sih2026/PRD.md) |
| **Architecture** | System flow, repo structure & tech stack | [Architecture.md](file:///run/media/askshubh/New%20Volume/Downloads/Projects/sih2026/Architecture.md) |
| **Rules & Standards** | Operational constraints, error handling & dos/don'ts | [Rules.md](file:///run/media/askshubh/New%20Volume/Downloads/Projects/sih2026/Rules.md) |
| **Phased Roadmap** | 9 structured, progressive engineering phases | [Phases.md](file:///run/media/askshubh/New%20Volume/Downloads/Projects/sih2026/Phases.md) |
| **Design System** | UI/UX visual specs, military HUD theme & tokens | [Design.md](file:///run/media/askshubh/New%20Volume/Downloads/Projects/sih2026/Design.md) |
| **Literature Plan** | Mathematical formulations & scientific proofs | [SIH26158_Literature_Synthesis_and_Implementation_Plan.md](file:///run/media/askshubh/New%20Volume/Downloads/Projects/sih2026/SIH26158_Literature_Synthesis_and_Implementation_Plan.md) |
| **Technical Dossier** | Operational context & geometric degeneracy breakdown | [SIH26158_Operational_and_Technical_Architecture.md](file:///run/media/askshubh/New%20Volume/Downloads/Projects/sih2026/SIH26158_Operational_and_Technical_Architecture.md) |

---

## 3. Phase Tracking & Progress

| Phase | Description | Status | Next Milestone |
| :--- | :--- | :---: | :--- |
| **Phase 1** | Ingestion, Telemetry Parsing & Geodetic Sync | **READY TO COMMENCE** | Video demuxer, `.srt`/KLV parser, B-spline sync, UTM converter |
| **Phase 2** | Adaptive Keyframing & Quality Gating | Pending | GPU Laplacian blur filter & DIS flow covisibility |
| **Phase 3** | Foundation Vision Pose & Pointmap Estimation | Pending | Fast3R/MASt3R wrapper & Kabsch SVD solver |
| **Phase 4** | Telemetry-Anchored Sim(3) Georeferencing | Pending | Weighted Umeyama SVD algorithm with DOP weights |
| **Phase 5** | Surface 3DGS & Watertight Mesh (SuGaR) | Pending | Planar Gaussian optimizer & SDF Marching Tetrahedra |
| **Phase 6** | Anti-Hallucination Audit & Exporters | Pending | Multi-ray density auditor, LAS pointcloud, GeoTIFF DSM |
| **Phase 7** | FastAPI Gateway & Real-Time Orchestrator | Pending | Async API, Celery/Redis, WebSocket progress stream |
| **Phase 8** | Tactical Web Command Center (React/Three.js) | Pending | Full-stack UI, 3D WebGL viewer & measurement tools |
| **Phase 9** | Benchmarking & Defense Jury Hardening | Pending | Test suite, sub-15m benchmark, jury demo mode |

---

## 4. Key Architectural Decisions & Invariants

1. **No GCPs:** All scale and orientation must be resolved in closed form via Umeyama $\mathrm{Sim}(3)$ from synchronous UAV telemetry.
2. **No Classical SfM in Core Loop:** Avoid COLMAP bundle adjustment drift and $b/H \to 0$ epipolar collapse.
3. **Watertight Output Only:** No naked 3DGS point clouds as deliverables; extracted meshes must be verified watertight with continuous topology via SDF Marching Tetrahedra.
4. **Air-Gapped Execution:** Zero external network or proprietary cloud API dependencies.
5. **No Hallucinated Surface Infilling:** Unobserved terrain must be masked as voids with low-confidence flags rather than synthesized.

---

## 5. Immediate Next Steps for Next Session / Chat

1. Build `backend/app/pipeline/stage1_ingestion/telemetry_parser.py` supporting `.srt`, KLV, and CSV telemetry formats.
2. Build `backend/app/pipeline/stage1_ingestion/spline_interpolator.py` implementing cubic B-spline interpolation over flight timestamps.
3. Build `backend/app/pipeline/stage1_ingestion/geodetic.py` for WGS84 to local UTM Cartesian coordinates.
4. Add unit test suite in `tests/unit/test_stage1_ingestion.py` to verify sub-millimeter precision.
