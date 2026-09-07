# AI & Developer Operational Rules & Guidelines (Rules.md)

## System: SIH26158 — Tactical 3D Reconstruction Engine
**Authority:** Project Engineering Lead / NTRO SIH 2026 Core Architecture  
**Scope:** Universal governing rules for AI assistants and human contributors across all development phases.

---

## 1. Golden Rules (Non-Negotiable Boundaries)

1. **NO PLACEHOLDER IMPLEMENTATIONS (Zero `TODO`, `pass`, or `mock` in Production Code):**
   - Every function, class, and method must be fully and functionally implemented.
   - Do not write `# TODO: implement later` or placeholder stubs for core mathematical formulas, telemetry parsers, or API routes. If a module is being authored, complete its working logic.

2. **DEFENSE-GRADE ANTI-HALLUCINATION & RIGOR:**
   - Never generate synthetic or imagined geometry where camera rays were not observed. Unobserved or low-confidence regions must be explicitly masked or left as topological voids.
   - Never inject generative AI diffusion/inpainting into spatial depth or surface points for defense intelligence models.

3. **ZERO GROUND CONTROL POINT (GCP) DEPENDENCY:**
   - The system is built for non-cooperative, hostile, or inaccessible terrain. The algorithm must never assume or require physical Ground Control Points. Metric scale and world orientation must be resolved strictly through synchronous UAV telemetry and the closed-form Umeyama $\mathrm{Sim}(3)$ solver.

4. **STRICT AIR-GAPPED OPERATION:**
   - No external third-party cloud APIs (e.g., OpenAI, Google Cloud, AWS Rekognition) may be called in the reconstruction or evaluation pipeline.
   - All machine learning inference (Fast3R, MASt3R, SuGaR) must run entirely on the local GPU.

5. **PRODUCTION CODE INTEGRITY:**
   - Preserve existing comments and docstrings.
   - Maintain strict typing throughout the codebase (Python `typing` with Pydantic v2, TypeScript strict mode).

---

## 2. Library & Technology Boundaries

### 2.1 Approved Libraries & Frameworks
| Domain | Approved Technologies |
| :--- | :--- |
| **Compute & Machine Learning** | PyTorch 2.3+ (CUDA 12.1+), TorchVision, `gsplat`, `diff-gaussian-rasterization`, NumPy, SciPy, Einops. |
| **Video & Computer Vision** | OpenCV (cv2 with CUDA/DIS flow), PyAV (ffmpeg bindings), Pillow. |
| **3D Geometry & GIS** | Trimesh, Open3D, PyVista, Rasterio, Shapely, PyProj, PyVista. |
| **Backend & Web API** | FastAPI, Uvicorn, Pydantic v2, Celery, Redis, WebSockets. |
| **Frontend UI** | React 18, TypeScript, Vite, Tailwind CSS, Three.js, `@mkkellogg/gaussian-splats-3d`, Lucide React, Zustand. |
| **Testing & Quality** | Pytest, Pytest-asyncio, Playwright / Vitest, Black, Ruff, MyPy. |

### 2.2 Explicitly Prohibited Libraries & Anti-Patterns
- ❌ **DO NOT use classical COLMAP CLI execution as the primary pipeline:** Classical SfM cannot meet the sub-15 minute turnaround and collapses under single-pass linear trajectories.
- ❌ **DO NOT use vanilla 3DGS without surface constraints:** Standard 3DGS produces millions of free-floating needles; SuGaR or surface-regularized splatting with SDF meshing is mandatory for watertight deliverables.
- ❌ **DO NOT use blocking synchronous calls in FastAPI endpoints:** Long-running reconstruction tasks must be dispatched asynchronously to Celery/background workers with progress pushed over WebSockets.
- ❌ **DO NOT use `eval()` or unvalidated shell execution:** Never pass unsanitized input to subprocesses.

---

## 3. Error Handling & Fail-Safe Protocols

1. **Telemetry Loss / Degraded GPS Protocol:**
   - If `.srt` or KLV telemetry is missing, corrupt, or has high DOP uncertainty ($> 5.0$), the system must **not** crash.
   - **Fallback Action:** Log a high-priority warning (`ALERT: Telemetry degraded or absent`), proceed with relative reconstruction using the Kabsch SVD baseline, and clearly flag the output with `MetricScaleConfirmed: False` in the UI and metadata.

2. **GPU Out-Of-Memory (OOM) Protection:**
   - All pairwise ViT inferences and Gaussian optimizations must query available VRAM before allocating large tensors.
   - If VRAM is constrained ($< 4\text{ GB}$ available), the pipeline must dynamically downscale candidate image patches (e.g., from $512\times512$ to $384\times384$) or reduce batch size rather than throwing an unhandled `torch.cuda.OutOfMemoryError`.

3. **Motion Blur & Low Keyframe Fallback:**
   - If high motion blur eliminates $> 90\%$ of candidate frames, the Laplacian threshold $\sigma_L^2$ must dynamically relax by $20\%$ until at least $60$ keyframes are retained to ensure reconstruction continuity.

4. **Watertight Mesh Topology Fallback:**
   - If Marching Tetrahedra encounters non-manifold zero-crossings, run a Trimesh Laplacian smoothing and topological hole-filling pass to guarantee watertightness before `.glb` packaging.

---

## 4. Coding Standards & Conventions

### 4.1 Python (Backend & Pipeline)
- **Formatting:** Adhere to PEP 8, formatted with Black/Ruff (100 character line limit).
- **Type Annotations:** Every function signature must contain full parameter and return type hints:
  ```python
  def solve_umeyama_sim3(
      source_points: np.ndarray,
      target_points: np.ndarray,
      weights: np.ndarray | None = None
  ) -> tuple[float, np.ndarray, np.ndarray]:
      ...
  ```
- **Logging:** Use structured logging with module-level loggers (`logger = get_logger(__name__)`). Never use naked `print()` statements.
- **Mathematical Clarity:** Document coordinate frames explicitly (e.g., OpenCV camera frame $+X$ Right, $+Y$ Down, $+Z$ Forward vs. OpenGL/Three.js $+X$ Right, $+Y$ Up, $-Z$ Forward vs. UTM $+X$ East, $+Y$ North, $+Z$ Up).

### 4.2 TypeScript & React (Frontend)
- **Strict TypeScript:** No `any` types. Define explicit interfaces for all telemetry points, reconstruction job states, and 3D camera configs.
- **State Separation:** Keep 3D scene graph state (Three.js objects) outside of React's reactive render cycle (use refs or Zustand non-reactive setters) to avoid frame drops.
- **Component Design:** Components must be modular, adhering to the Military HUD aesthetic defined in `Design.md`.

---

## 5. What the AI Should & Shouldn't Do

### 5.1 What the AI MUST Do
- Always write clean, production-ready, self-documenting code.
- Always provide verifiable mathematical solutions (e.g., closed-form SVD, quaternion rotations, geodetic conversions).
- Always ensure frontend and backend are interconnected with accurate data types and error boundaries.
- Update `Memory.md` when completing major phases or changing active architectural decisions.

### 5.2 What the AI MUST NOT Do
- Never fabricate fake accuracy statistics or claim real-time processing without verifying computational complexity.
- Never write monolithic files exceeding 600 lines; split logic into focused, single-responsibility modules.
- Never modify files outside the workspace.
- Never commit secrets, dummy credentials, or machine-specific absolute file paths in code.
