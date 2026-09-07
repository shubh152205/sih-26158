# Project Implementation Roadmap & Phases (Phases.md)

## System: SIH26158 — Tactical 3D Reconstruction Engine
**Roadmap Strategy:** Progressive, test-driven phases designed to build, verify, and harden each layer from low-level mathematical telemetry ingestion up to the interactive tactical command dashboard.

---

## Phase Overview Matrix

| Phase | Core Objective | Primary Deliverables | Estimated Milestone | Status |
| :---: | :--- | :--- | :--- | :---: |
| **Phase 1** | **Ingestion & Telemetry Engine** | Video demuxer, `.srt`/KLV parser, B-spline sync, WGS84-to-UTM geodetic math. | Milestone 1: Telemetry Alignment | Pending |
| **Phase 2** | **Adaptive Keyframing & Gating** | GPU Laplacian blur filter, DIS optical flow covisibility, candidate selector. | Milestone 2: Curated Keyframes | Pending |
| **Phase 3** | **Foundation Vision Pose Solver** | ViT pointmap regressor, confidence gating, closed-form Kabsch SVD solver. | Milestone 3: Relative Sparse Trajectory | Pending |
| **Phase 4** | **Sim(3) Georeferencing Engine** | Weighted Umeyama SVD algorithm, DOP weighting, metric scale enforcement. | Milestone 4: Absolute Metric Poses | Pending |
| **Phase 5** | **Surface 3DGS & SDF Meshing** | Flat Gaussian regularizer, density SDF extraction, Marching Tetrahedra mesh. | Milestone 5: Watertight Textured Mesh | Pending |
| **Phase 6** | **Anti-Hallucination & Exporters** | Multi-ray density auditor, void generator, `.las`, GeoTIFF DSM, `.glb` packaging. | Milestone 6: Multi-Modal Deliverables | Pending |
| **Phase 7** | **FastAPI Gateway & Workers** | Async REST endpoints, Celery/Redis tasks, WebSocket progress stream, GPU monitor. | Milestone 7: Full Backend Service | Pending |
| **Phase 8** | **Tactical Web Command Center** | React/Vite dashboard, Three.js & 3DGS viewer, measurement tools, HUD UI. | Milestone 8: Complete Full-Stack App | Pending |
| **Phase 9** | **Benchmarking & Jury Hardening** | Sub-15 min benchmark, test suite, sample datasets, defense jury demonstration mode. | Milestone 9: Final SIH Production Release | Pending |

---

## Detailed Phase Breakdown

### Phase 1: Ingestion, Telemetry Parsing & Geodetic Synchronization
- **Goal:** Ingest monocular UAV video and extract millisecond-accurate synchronized geospatial camera poses $(X, Y, Z, \text{Roll}, \text{Pitch}, \text{Yaw})$.
- **Key Tasks:**
  1. Author `backend/app/pipeline/stage1_ingestion/telemetry_parser.py`: Robust parser for DJI-style `.srt` subtitle metadata, KLV binary streams, and CSV flight records.
  2. Implement `spline_interpolator.py`: Continuous cubic B-spline interpolation over time stamps to map arbitrary video frame indices to precise GPS coordinates.
  3. Implement `geodetic.py`: Ellipsoidal WGS84 to local UTM Cartesian coordinate converter using PyProj with validation against EPSG codes.
  4. Unit test suite validating timestamp synchronization and metric distance calculations.
- **Verification Gate:** Passing unit tests showing sub-centimeter interpolation accuracy and correct UTM Cartesian projection.

---

### Phase 2: GPU-Accelerated Adaptive Keyframing & Quality Gating
- **Goal:** Filter out motion-blurred or jittery frames and select optimal baseline keyframes ($b/H \in [0.10, 0.25]$) to eliminate epipolar collapse.
- **Key Tasks:**
  1. Author `blur_detector.py`: PyTorch/OpenCV CUDA Laplacian kernel computing variance of the Laplacian $\sigma_L^2$ per frame.
  2. Author `flow_estimator.py`: High-speed DIS optical flow tracker computing mean pixel displacement between frame candidates.
  3. Author `keyframe_selector.py`: Adaptive selection controller that balances forward progress with visual covisibility ($60\%\text{--}80\%$).
- **Verification Gate:** Automatic reduction of 5,400 raw video frames down to $120\text{--}250$ sharp, high-covisibility keyframes in $< 45$ seconds.

---

### Phase 3: Foundation Vision Pose & Dense Pointmap Estimation
- **Goal:** Predict pairwise dense 3D pointmaps and relative camera extrinsics in a single feed-forward pass without iterative bundle adjustment.
- **Key Tasks:**
  1. Implement `vit_model.py`: Optimized wrapper for Fast3R / MASt3R architecture with FP16 precision.
  2. Implement `pointmap_regressor.py`: Inference pipeline predicting local 3D point clouds and per-pixel confidence maps.
  3. Implement `kabsch_svd.py`: Closed-form differentiable Kabsch algorithm computing relative rotation $\mathbf{R} \in \mathrm{SO}(3)$ and translation vector $\mathbf{t}$ from 3D correspondences.
  4. Implement `view_graph.py`: Incremental pose chaining along the sequential UAV flight path with linear time complexity $\mathcal{O}(N)$.
- **Verification Gate:** Relative camera trajectory accurately reconstructed without epipolar failure across challenging collinear drone paths.

---

### Phase 4: Telemetry-Anchored $\mathrm{Sim}(3)$ Georeferencing Engine
- **Goal:** Anchor the unscaled visual camera trajectory to absolute metric WGS84 UTM space using the synchronous drone GPS fixes.
- **Key Tasks:**
  1. Implement `umeyama_solver.py`: Closed-form weighted Umeyama algorithm solving for global scale factor $s$, rotation matrix $\mathbf{R}_{\text{world}}$, and translation $\mathbf{t}_{\text{world}}$.
  2. Incorporate Dilution of Precision (DOP) weighting to suppress erroneous GPS fixes.
  3. Align all camera centers and 3D pointmaps to the metric world coordinate frame ($1 \text{ unit} = 1 \text{ meter}$).
- **Verification Gate:** Absolute metric scale error $\le 3\%$ compared to known flight distances without any manual Ground Control Points.

---

### Phase 5: Surface-Aligned 3DGS & Watertight Mesh Extraction
- **Goal:** Reconstruct scene surfaces using planar-constrained 3D Gaussians and extract continuous, watertight polygonal meshes via SDF Marching Tetrahedra.
- **Key Tasks:**
  1. Implement `gaussian_trainer.py`: Initialize 3D Gaussians from the georeferenced pointmaps and enforce flattening loss ($s_3 \ll s_1, s_2$) aligning Gaussians to local surface normals.
  2. Implement `sdf_extractor.py`: Calculate Signed Distance Function (SDF) values on a tetrahedral grid and apply Marching Tetrahedra to extract triangular topology.
  3. Implement `texture_baker.py`: Project radiometric colors onto UV maps ($4096 \times 4096$) for clean rendering in external engines.
- **Verification Gate:** Extracted `.glb` model is 100% watertight, verified via `trimesh.is_watertight`, with zero floating needle artifacts.

---

### Phase 6: Defense Anti-Hallucination & Multi-Modal Exporters
- **Goal:** Identify and mask unobserved terrain to prevent false intelligence, then package all standard defense geospatial deliverables.
- **Key Tasks:**
  1. Implement `confidence_gate.py`: Multi-ray raycasting to flag terrain patches observed by fewer than 3 views or with model confidence below $\tau_c$.
  2. Generate cartographic void masks and confidence heatmaps.
  3. Implement `pointcloud_exporter.py`: Export metric georeferenced point clouds in `.las` format with UTM projection metadata.
  4. Implement `raster_exporter.py`: Generate orthorectified GeoTIFF Digital Surface Models (DSM/DTM).
  5. Implement `mesh_exporter.py`: Pack watertight `.glb` and `.obj` with materials.
- **Verification Gate:** Defense audit report generated; points lacking observation are accurately masked rather than hallucinated.

---

### Phase 7: FastAPI Backend Gateway & Real-Time Orchestration
- **Goal:** Provide a resilient, high-concurrency API layer with asynchronous job dispatching and real-time WebSocket progress streaming.
- **Key Tasks:**
  1. Implement `main.py`, config settings, and modular routing (`/api/v1/recon`, `/api/v1/telemetry`, `/api/v1/export`).
  2. Implement Celery/Redis worker tasks with fallbacks for standalone local execution.
  3. Implement WebSocket handler streaming stage-by-stage percentage, VRAM usage, and preview thumbnails to clients.
  4. Add NVML GPU monitoring for temperature, memory, and compute load.
- **Verification Gate:** End-to-end API job dispatch with live WebSocket events broadcasting to connected clients.

---

### Phase 8: Tactical Defense Web Command Center
- **Goal:** Build an intuitive, military-grade web dashboard for mission monitoring, 3D visualization, and tactical mensuration.
- **Key Tasks:**
  1. Set up React 18 + TypeScript + Vite + Tailwind CSS frontend with dark tactical HUD aesthetic.
  2. Implement `ThreeMeshViewer.tsx`: WebGL viewer rendering watertight `.glb` with lighting, wireframe, and normal views.
  3. Implement `GaussianSplatViewer.tsx`: Real-time 3D Gaussian Splatting renderer for volumetric exploration.
  4. Implement tactical mensuration tools: 3D point-to-point distance ruler, polygon area, elevation profile, and Line-of-Sight (LOS) visibility raycaster.
  5. Implement Telemetry HUD: Synchronous UAV video player with altitude, speed, and flight path visualization.
- **Verification Gate:** Responsive 60 FPS 3D rendering with live interactive measurements in the browser.

---

### Phase 9: System Integration, Benchmarking & Jury Hardening
- **Goal:** End-to-end performance validation, automated testing, and SIH jury presentation packaging.
- **Key Tasks:**
  1. Run end-to-end reconstruction on reference drone datasets; verify turnaround time $< 15$ minutes on RTX 4090.
  2. Create automated benchmark script testing VRAM peak, metric accuracy, and FPS.
  3. Implement "Demo Flight" pre-cached dataset for instant jury demonstration without waiting for GPU processing.
  4. Polish comprehensive documentation and operational user manual.
- **Verification Gate:** 100% passing tests, automated demonstration ready, and defense jury checklist satisfied.
