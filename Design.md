# UI/UX & Visual Design System (Design.md)

## System: SIH26158 — Tactical Defense Geospatial Command Center
**Design Philosophy:** Modern Military HUD (Heads-Up Display) / Advanced Aerospace Tactical Interface  
**Aesthetic Core:** High-contrast tactical dark theme, clean geometric typography, subtle glassmorphism, micro-animations, and military telemetry readouts optimized for rapid operational comprehension under field conditions.

---

## 1. Color Palette & Visual Design Tokens

The interface uses a tailored dark military slate foundation paired with vibrant situational indicators (Tactical Cyan, Radar Green, Alert Amber, Hazard Red) to ensure immediate visual hierarchy.

### 1.1 Color Tokens

```css
:root {
  /* Surface & Background Hierarchy */
  --bg-abyss: #07090E;          /* Deepest background (app root canvas) */
  --bg-base: #0D1117;           /* Main panel and container background */
  --bg-surface: #161B22;        /* Card, dock, and modal surface */
  --bg-surface-elevated: #21262D; /* Dropdowns, hover states, elevated popovers */
  --bg-glass: rgba(22, 27, 34, 0.75); /* Frosted HUD glass with backdrop-blur */

  /* Border & Grid Lines */
  --border-subtle: #30363D;     /* Standard panel dividers */
  --border-tactical: #484F58;   /* Active frame borders */
  --border-cyan-glow: rgba(6, 182, 212, 0.4); /* Focused element glow */

  /* Primary Accent: Tactical Cyan (Targeting, Selection, Primary Actions) */
  --accent-cyan-500: #06B6D4;
  --accent-cyan-400: #22D3EE;
  --accent-cyan-glow: rgba(6, 182, 212, 0.25);

  /* Status Colors */
  --status-green: #10B981;      /* Telemetry Lock, GPS Valid, Model Watertight */
  --status-green-glow: rgba(16, 185, 129, 0.2);
  --status-amber: #F59E0B;      /* Warning, Low Covisibility, Telemetry Interpolated */
  --status-red: #EF4444;        /* Critical Error, Epipolar Degeneracy, VRAM Alert */
  --status-purple: #8B5CF6;     /* 3D Gaussian Splatting Layer */

  /* Typography Colors */
  --text-primary: #F0F6FC;      /* Main headings, critical telemetry numbers */
  --text-secondary: #8B949E;    /* Labels, descriptions, secondary telemetry */
  --text-muted: #6E7681;        /* Inactive states, placeholder watermarks */
  --text-cyan: #38BDF8;         /* Active readout coordinates */
}
```

---

## 2. Typography & Font Specifications

Clear legibility under dynamic lighting conditions is critical for defense intelligence:

- **Primary UI & Headings:** `Inter` or `Outfit` (sans-serif) — Modern, ultra-clean geometric proportions for menus, dialogs, and labels.
- **Telemetry & Geospatial Readouts:** `JetBrains Mono` or `Roboto Mono` (monospace) — Strictly tabular, monospace font for GPS coordinates, elevation, distance meters, frame rates, and timecodes ($00:00:00.000$).

### 2.1 Type Scale
| Element | Font Family | Size | Weight | Line Height | Tracking |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **HUD Header Title** | Inter / Outfit | 18px / 1.125rem | 700 | 1.2 | +0.05em (Uppercase) |
| **Section Headings** | Inter | 14px / 0.875rem | 600 | 1.3 | +0.03em |
| **Telemetry Readouts** | JetBrains Mono | 13px / 0.8125rem | 500 | 1.4 | 0.0em |
| **Status Badges** | JetBrains Mono | 11px / 0.6875rem | 700 | 1.0 | +0.08em (Uppercase) |
| **Body / Explanations** | Inter | 13px / 0.8125rem | 400 | 1.5 | normal |

---

## 3. Spatial Layout & HUD Grid

The Tactical Command Center is structured into an intuitive **4-Zone High-Density Layout**:

```
+-------------------------------------------------------------------------------+
| TOP HUD BAR: Mission Code [SIH26158] | Status: ACTIVE | GPU: RTX 4090 [42°C, 3.2GB]  |
+-------------------+---------------------------------------+-------------------+
| LEFT DOCK         | CENTRAL 3D VIEWPORT                   | RIGHT DOCK        |
| - Ingestion Feed  | - Interactive WebGL Engine            | - Mensuration Hub |
| - Raw Video Play  |   (Textured Mesh / Splat / DSM)       |   (Distance, Area)|
| - Telemetry Sync  | - Floating Viewport Controls          | - Elevation Prof  |
| - GPS Spline Map  |   (Wireframe, Normals, Audit Heatmap) | - Line of Sight   |
| - Keyframe Strip  | - 3D Camera Trajectory & Cones        | - Export Actions  |
+-------------------+---------------------------------------+-------------------+
| BOTTOM BAR: 6-Stage Pipeline Stepper & Progress Monitor | Timecode: 00:02:14.250 |
+-------------------------------------------------------------------------------+
```

### 3.1 Zone Responsibilities
1. **Top HUD Bar:** Mission identifier, security classification tag (`RESTRICTED / NTRO TACTICAL EVALUATION`), live NVML GPU metrics (VRAM usage, temperature, compute load), and system settings.
2. **Left Flight & Telemetry Dock:**
   - Synchronized UAV video feed preview.
   - Live telemetry gauges: Speed ($m/s$), Altitude AGL/MSL ($m$), Gimbal Pitch ($^\circ$).
   - Dynamic 2D GPS flight path map with keyframe markers.
3. **Central 3D Viewport (The Tactical Core):**
   - High-fidelity Three.js WebGL canvas and Gaussian Splat viewer.
   - Layer toggles: **[Textured Mesh]**, **[Surface Gaussians]**, **[Dense Point Cloud]**, **[Digital Surface Model]**, **[Confidence Heatmap]**.
   - Flight trajectory rendering: Interactive 3D spline showing camera positions and viewing frustum pyramids.
   - Interactive crosshairs and 3D coordinate tooltips showing local UTM $(E, N, Z)$.
4. **Right Tactical Mensuration & Export Dock:**
   - Active measurement toolkit: 3D point-to-point Euclidean ruler with slope angle.
   - Volumetric excavation/pile bounding box.
   - Real-time Line-of-Sight (LOS) visibility ray between two operator-selected points (Green = Visible, Red = Obstructed by terrain).
   - Export center for one-click download of `.glb`, `.las`, and GeoTIFF DSM.
5. **Bottom Timeline & Pipeline Stepper:**
   - 6-Stage reconstruction progression tracker with real-time percentage and millisecond timers.
   - Video scrubber synchronizing the 2D video frame with the 3D camera pose on the flight trajectory.

---

## 4. UI Components & Visual Accents

### 4.1 Tactical HUD Cards & Panels
- **Backdrop Blur:** `backdrop-filter: blur(12px)` over semi-transparent slate backgrounds (`rgba(22, 27, 34, 0.85)`).
- **Corner Brackets:** Subtle military corner brackets (`border-top`, `border-left` in cyan accent) to emphasize tactical targeting aesthetics.
- **Glassmorphic Shadows:** Deep soft shadows (`0 8px 32px 0 rgba(0, 0, 0, 0.4)`) to separate floating toolbars from the 3D scene.

### 4.2 Status Indicators & Badges
- **Active / Operational:** Glowing pulsating radar green dot (`box-shadow: 0 0 8px #10B981`).
- **Processing / In-Flight:** Stepper bar with cyan animated gradient scanline.
- **Warning / Degraded:** Amber warning pill with exclamation icon.

### 4.3 Micro-Animations & Transitions
- **Hover Transitions:** 150ms smooth ease-out on buttons and tool toggles (`transition: all 0.15s ease-out`).
- **3D Gizmo & Crosshairs:** Reticle styling with thin dashed cyan lines when mensuration tools are active.
- **Elevation Profiling:** Dynamic SVG spline chart with animated cross-section marker synced to cursor position along the measurement line.

---

## 5. Responsive Behavior & Performance Standards

- **Framerate Target:** Client-side 3D viewport must sustain **$\ge 60$ FPS** during orbital rotation, panning, and zooming.
- **Memory Efficiency:** Three.js geometries and textures must be disposed of cleanly upon loading a new reconstruction run to prevent browser tab memory leaks.
- **Field Display Support:** Optimized for typical 1920x1080 tactical laptop displays, scaling up gracefully to 4K defense operations command screens.
