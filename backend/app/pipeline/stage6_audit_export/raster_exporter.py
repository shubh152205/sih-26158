"""Orthorectified Digital Surface Model (DSM) and Raster Exporter Subsystem.

Projects georeferenced metric points into 2D terrain elevation grids with
specified Ground Sampling Distance (GSD) and writes georeferenced GeoTIFF images.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import tifffile

from backend.app.core.logger import get_logger
from backend.app.pipeline.stage4_georeferencing.metric_scaler import MetricSceneModel

logger = get_logger(__name__, subsystem="RASTER-EXPORTER")


class RasterExporter:
    """Generates orthorectified elevation models and GeoTIFFs."""

    def __init__(self, gsd_meters: float = 0.10, nodata_value: float = -9999.0):
        self.gsd = gsd_meters
        self.nodata = nodata_value

    def generate_dsm_grid(
        self, model: MetricSceneModel
    ) -> tuple[np.ndarray, tuple[float, float, float, float]]:
        """Rasterize 3D metric UTM points into a 2D elevation grid.

        Returns:
            Tuple of:
                - elevation_grid: (H, W) float32 array in meters
                - bounds: (min_easting, max_easting, min_northing, max_northing)
        """
        pts_utm = model.points_utm
        e = pts_utm[:, 0]
        n = pts_utm[:, 1]
        z = pts_utm[:, 2]

        min_e, max_e = float(np.min(e)), float(np.max(e))
        min_n, max_n = float(np.min(n)), float(np.max(n))

        # Dimensions of output raster
        width = max(16, int(np.ceil((max_e - min_e) / self.gsd)))
        height = max(16, int(np.ceil((max_n - min_n) / self.gsd)))

        # Allocate grid initialized to nodata
        dsm = np.full((height, width), self.nodata, dtype=np.float32)

        # Discretize point coordinates to raster pixel indices (Y inverted: top row is north)
        col_indices = np.clip(((e - min_e) / self.gsd).astype(np.int32), 0, width - 1)
        row_indices = np.clip(((max_n - n) / self.gsd).astype(np.int32), 0, height - 1)

        # Accumulate maximum elevation per raster bin (Digital Surface Model)
        for i in range(len(z)):
            r = row_indices[i]
            c = col_indices[i]
            curr_val = dsm[r, c]
            if curr_val == self.nodata or z[i] > curr_val:
                dsm[r, c] = z[i]

        logger.info(
            "Generated DSM Grid: %dx%d pixels @ %.2fm GSD (Extents: E[%.1f, %.1f], N[%.1f, %.1f])",
            width, height, self.gsd, min_e, max_e, min_n, max_n
        )

        return dsm, (min_e, max_e, min_n, max_n)

    def export_geotiff(
        self,
        model: MetricSceneModel,
        output_path: str | Path,
        epsg_code: int = 32643,
    ) -> Path:
        """Export orthorectified elevation raster to GeoTIFF (.tif) format."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        dsm_grid, (min_e, max_e, min_n, max_n) = self.generate_dsm_grid(model)

        # Standard GeoTIFF tags: ModelTiepoint (0, 0, 0 -> min_e, max_n, 0)
        # ModelPixelScale (gsd, gsd, 0)
        tiepoint = [0.0, 0.0, 0.0, min_e, max_n, 0.0]
        pixel_scale = [self.gsd, self.gsd, 0.0]

        extratags = [
            (33550, "d", 3, pixel_scale, True),     # ModelPixelScaleTag
            (33922, "d", 6, tiepoint, True),        # ModelTiepointTag
            (42113, "s", len(str(self.nodata)), str(self.nodata), True),  # GDAL_NODATA
        ]

        tifffile.imwrite(
            str(out),
            dsm_grid,
            dtype=np.float32,
            extratags=extratags,
        )

        logger.info("Exported GeoTIFF DSM to %s", str(out))
        return out
