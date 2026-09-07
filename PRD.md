# Project Requirements Document (PRD)

## Project Title: SIH26158 — Single-Pass Drone Video to Accurate 3D Model Generation System
**Sponsoring Agency:** National Technical Research Organisation (NTRO)  
**Hackathon Track:** Smart India Hackathon 2026 (Software Track — Robotics & Drones)  
**Domain:** Tactical Defense Intelligence, Geospatial Reconnaissance, Autonomous Photogrammetry

---

## 1. Executive Summary & Problem Statement

### 1.1 Problem Statement
Tactical unmanned aerial vehicles (UAVs) deployed in reconnaissance, border surveillance, and target acquisition missions capture monocular high-definition video during rapid, single-pass flight trajectories. Defense intelligence operators require accurate, georeferenced 3D models (dense point clouds, watertight textured meshes, and digital surface models) to assess terrain, evaluate targets, and plan tactical incursions.

Current photogrammetric pipelines (e.g., classical Structure-from-Motion such as COLMAP or standard photogrammetry software) fail catastrophically under tactical field realities:
1. **Epipolar Collapse:** Straight-line, single-pass trajectories result in near-zero baseline-to-depth ratios ($b/H < 0.05$) between consecutive frames, causing classical feature triangulation to degenerate.
2. **Open-Loop Scale Drift & Gauge Freedom:** Without loop closures (impossible in forward-recon passes) and without Ground Control Points (GCPs in hostile territory), bundle adjustment drifts exponentially, inducing the photogrammetric "bowl effect" or runaway metric scale distortion.
3. **Vanilla 3DGS Artifacts:** While standard 3D Gaussian Splatting offers rapid rendering, it produces millions of unconstrained semi-transparent "needles" and "floaters," lacking continuous surface topology, rendering the model useless for engineering measurements or ballistic simulation.
4. **Processing Latency:** Classical SfM pipelines take 3 to 12 hours for multi-gigabyte video streams, rendering intelligence obsolete before tactical operations can commence.

### 1.2 The Solution
**SIH26158** is a defense-grade, sub-15-minute 3D spatial reconstruction platform engineered specifically for single-pass UAV video. The system fuses deep feed-forward geometric vision transformers (Fast3R/MASt3R) with synchronous embedded telemetry (`.srt` / KLV / GPS-IMU) to solve relative and absolute scale in closed form without GCPs or loop closures. It leverages surface-aligned 3D Gaussian Splatting (SuGaR) with Signed Distance Field (SDF) Marching Tetrahedra to extract watertight, metric-accurate meshes, supplemented by an anti-hallucination confidence audit engine.

---

## 2. Target Users & Stakeholders

| User Persona | Operational Role | Primary Requirements |
| :--- | :--- | :--- |
| **Defense Intelligence Analyst (NTRO / Armed Forces)** | Geospatial Intelligence (GEOINT) & Target Mensuration | Sub-meter metric accuracy, WGS84 UTM coordinates, watertight meshes, line-of-sight & elevation profiles. |
| **Tactical UAV Operator / Field Commander** | Forward Reconnaissance & Mission Briefing | Sub-15 min processing turnaround on field workstation GPU (RTX 4090), zero GCP setup, automated telemetry extraction. |
| **Disaster & Emergency Response Commander** | Post-disaster damage assessment & hazard mapping | Rapid Digital Surface Model (DSM/DTM) generation, volumetric landslide/flood estimation, high reliability under adverse lighting. |
| **SIH Evaluation Jury & Technical Inspectors** | System Audit & Verification | Algorithmic transparency, reproducible benchmarks, anti-hallucination verification, defense-ready software architecture. |

---

## 3. Core Features & Functional Requirements

### 3.1 Ingestion & Telemetry Parser
- **FR-1.1 Video Ingestion:** Support 4K/1080p drone video at 30/60 FPS in `.mp4`, `.mov`, and `.mkv` with NVDEC hardware decoding.
- **FR-1.2 Synchronous Telemetry Parsing:** Ingest and parse subtitle streams (`.srt`), KLV metadata, EXIF headers, and separate CSV/JSON flight logs.
- **FR-1.3 Cubic Spline Telemetry Interpolator:** Interpolate UAV position (latitude, longitude, altitude), camera gimbal (pitch, roll, yaw), and sensor velocity at exact video frame timestamps with millisecond accuracy.
- **FR-1.4 Geodetic Projection:** Real-time conversion of WGS84 geodetic coordinates to local UTM Cartesian coordinates $(X, Y, Z)$ in meters.

### 3.2 Adaptive Keyframe Selection & Quality Gating
- **FR-2.1 Motion Blur & Degeneracy Filter:** Compute modified Laplacian variance $\sigma_L^2$ on GPU to discard frames degraded by rolling shutter flutter, prop wash, or high angular acceleration.
- **FR-2.2 Covisibility & Parallax Gating:** Fast DIS optical flow estimation between candidate frames to maintain an optimal baseline-to-depth ratio ($b/H \in [0.10, 0.25]$) and $60\%\text{--}80\%$ visual covisibility.
- **FR-2.3 Frame Reduction:** Intelligently reduce 5,400 raw frames (3-minute 30 FPS video) down to $120\text{--}250$ optimal, highly informative keyframes.

### 3.3 Deep Feed-Forward Foundation Geometric Pose Estimation
- **FR-3.1 Feed-Forward ViT Architecture:** Integration of MASt3R / Fast3R foundation models to directly regress local 3D pointmaps $X_{A \to B}, X_{B \to A}$ and pixelwise confidence maps $C$ in a single forward pass without iterative bundle adjustment.
- **FR-3.2 Closed-Form Kabsch SVD Solver:** Solve relative rotation $\mathbf{R} \in \mathrm{SO}(3)$ and translation direction $\mathbf{t}$ in closed form using singular value decomposition on confidence-weighted 3D correspondence vectors.
- **FR-3.3 Linear View-Graph Optimization:** Global camera trajectory stitching via sparse pose-graph optimization, maintaining linear time complexity $\mathcal{O}(N)$ rather than cubic $\mathcal{O}(N^3)$.

### 3.4 Telemetry-Anchored $\mathrm{Sim}(3)$ Georeferencing
- **FR-4.1 Closed-Form Weighted Umeyama Alignment:** Estimate global scale $s$, rotation $\mathbf{R}_{\text{world}}$, and translation $\mathbf{t}_{\text{world}}$ by aligning the unscaled visual camera centers to the metric UTM GPS trajectory.
- **FR-4.2 DOP Confidence Weighting:** Weight each GPS fix inversely by Dilution of Precision ($\sigma_{\text{DOP}}^2$) to reject GPS drift or multipath errors.
- **FR-4.3 True Metric Scale Enforcement:** Scale the reconstruction to metric units ($1.0 \text{ unit} = 1.0 \text{ meter}$) with zero manual ground interventions or physical markers.

### 3.5 Surface-Aligned 3DGS & Watertight Mesh Extraction (SuGaR)
- **FR-5.1 Planar-Constrained Gaussians:** Constrain 3D Gaussians to flat disks aligned with actual physical scene surfaces using regularized scale flattening ($s_3 \ll s_1, s_2$).
- **FR-5.2 Density Field Regularization:** Density loss encouraging Gaussian centroids to adhere tightly to the zero-level set of a true surface Signed Distance Function (SDF).
- **FR-5.3 SDF Marching Tetrahedra:** Extract topologically consistent, watertight triangular meshes directly from the regularized Gaussian density field.
- **FR-5.4 Seamless Texture Baking:** Project view-dependent radiometric colors into UV texture atlases ($4096 \times 4096$) mapped to the generated mesh.

### 3.6 Defense Anti-Hallucination & Confidence Audit Engine
- **FR-6.1 Multi-Ray Density Gating:** Intersect surface geometry with camera observation rays; mask geometry lacking multi-view covisibility ($< 3$ convergent views) or foundation confidence ($C < \tau_c$).
- **FR-6.2 Cartographic Void Masking:** Output explicit void/unobserved labels in unverified areas, preventing generative AI hallucinations in tactical intelligence.
- **FR-6.3 Confidence Heatmap Layer:** Produce per-vertex and per-pixel color-coded metric confidence maps (Green = High Confidence, Amber = Marginal, Red/Hole = Unobserved Void).

### 3.7 Tactical Command Center Web UI
- **FR-7.1 3D Multi-Modal Interactive Viewport:** Real-time WebGL rendering of 3D Gaussian Splats, textured meshes, point clouds, and orthophotos with 60 FPS client navigation.
- **FR-7.2 Geospatial Mensuration Toolkit:** Metric distance calculation, 3D polygon area, volumetric excavation/pile estimation, elevation profiling, and line-of-sight (LOS) intervisibility analysis.
- **FR-7.3 Mission Timeline & Telemetry HUD:** Synchronous playback of original UAV video linked with the 3D trajectory camera cone and telemetry graphs (Altitude, Speed, Gimbal Pitch).
- **FR-7.4 Standard Defense Exports:** One-click download of `.obj` / `.glb` meshes, `.las` georeferenced point clouds, GeoTIFF DSM/DTM, and PDF/JSON intelligence audit reports.

---

## 4. Non-Functional Requirements (NFR)

| Metric / Dimension | Requirement | Defense Justification |
| :--- | :--- | :--- |
| **Turnaround Latency** | $< 15$ minutes for 3-minute 4K video (180s flight) on RTX 4090 (24GB). | Real-time tactical operational cycle and quick incursion planning. |
| **Metric Scale Error** | $\le 3.0\%$ absolute scale error across target terrain. | Reliable spatial mensuration for tactical clearance and target classification. |
| **VRAM Footprint** | Peak consumption $\le 22\text{ GB}$ VRAM. | Runs reliably on standalone consumer-grade defense workstations without OOM crashes. |
| **Surface Continuity** | Zero needle/floater artifacts in extracted `.glb` mesh; watertight topology. | Usable in defense simulation engines (Unreal Engine 5, VBS4, Unity) and physical collision checkers. |
| **Security & Privacy** | $100\%$ air-gapped execution capability; zero external cloud API dependencies. | Defense data confidentiality under strict NTRO / Indian Military guidelines. |
| **Reliability & Resilience** | Graceful degradation on missing telemetry; telemetry loss alerts. | System continues running relative reconstruction if GPS dropouts occur. |

---

## 5. Deliverables & Acceptance Checklist

- [ ] **Data Parser Module:** Python module parsing `.mp4` + `.srt` / KLV and outputting synchronized telemetry dataframe.
- [ ] **Adaptive Keyframe Selector:** GPU-accelerated blur and covisibility selector downsampling video to optimal frames.
- [ ] **Fast3R / MASt3R Pose Engine:** Python/PyTorch module predicting metric pointmaps and relative camera poses.
- [ ] **Umeyama Georeferencer:** Geodetic conversion and Sim(3) solver outputting georeferenced cameras and scale factor.
- [ ] **SuGaR Mesh Reconstruction:** Surface-regularized splatting and SDF Marching Tetrahedra producing watertight `.obj`/`.glb`.
- [ ] **Audit & Exporter Service:** Exporter creating `.las`, GeoTIFF DSM, and confidence audit masks.
- [ ] **Tactical Web Dashboard:** Full-stack dashboard (FastAPI backend + Vite/React frontend) with 3D WebGL viewer and tactical measuring tools.
- [ ] **Automated Test Suite:** Benchmarks verifying execution time, memory stability, and scale accuracy.
