# -*- coding: utf-8 -*-
"""Visibility computation engine."""

from dataclasses import dataclass
import math

import numpy as np
from qgis.core import QgsFeatureRequest

from .raster_utils import RasterGrid, write_int32_geotiff


OUTPUT_NODATA = np.int32(-2147483648)


@dataclass
class VisibilityEngineConfig:
    """Parameters required by the visibility engine."""

    dtm_layer: object
    obstacle_layer: object
    height_field: str
    observer_height: float
    max_distance: float
    output_path: str


@dataclass
class PreparedObstacle:
    """Obstacle projected onto the DTM model."""

    x: float
    y: float
    top_elevation: float


class VisibilityEngine:
    """Computes the number of visible obstacles from each valid DTM pixel."""

    def __init__(self, config):
        self.config = config
        self.grid = RasterGrid.from_path(self.config.dtm_layer.source())
        self.max_distance_sq = self.config.max_distance * self.config.max_distance

    def run(self, progress_callback=None):
        progress = progress_callback or (lambda value, message: None)

        progress(0, "Loading raster and obstacle data…")
        obstacles = self._prepare_obstacles(progress)
        progress(12, f"Prepared {len(obstacles)} valid obstacles.")

        output = np.full(self.grid.array.shape, OUTPUT_NODATA, dtype=np.int32)
        row_centers = np.array([self.grid.pixel_center(row, 0)[1] for row in range(self.grid.rows)], dtype=np.float64)

        if not obstacles:
            valid_mask = np.vectorize(lambda val: not self.grid.is_nodata(val))(self.grid.array)
            output[valid_mask] = 0
            write_int32_geotiff(self.config.output_path, output, self.grid, OUTPUT_NODATA)
            progress(100, "No valid obstacles found. Output raster contains zeros on valid DTM cells.")
            return self.config.output_path

        obstacle_x = np.array([item.x for item in obstacles], dtype=np.float64)
        obstacle_y = np.array([item.y for item in obstacles], dtype=np.float64)
        obstacle_top = np.array([item.top_elevation for item in obstacles], dtype=np.float64)

        total_rows = self.grid.rows
        report_interval = max(1, total_rows // 100)

        for row in range(total_rows):
            observer_y = row_centers[row]
            row_mask = np.abs(obstacle_y - observer_y) <= self.config.max_distance
            row_obstacle_idx = np.where(row_mask)[0]

            for col in range(self.grid.cols):
                terrain_z = self.grid.array[row, col]
                if self.grid.is_nodata(terrain_z):
                    continue

                observer_x, observer_y = self.grid.pixel_center(row, col)
                observer_z = float(terrain_z) + self.config.observer_height
                visible_count = 0

                if row_obstacle_idx.size > 0:
                    dx = obstacle_x[row_obstacle_idx] - observer_x
                    dy = obstacle_y[row_obstacle_idx] - observer_y
                    dist_sq = dx * dx + dy * dy
                    candidate_idx = row_obstacle_idx[(dist_sq <= self.max_distance_sq) & (dist_sq > 0.0)]

                    for obstacle_index in candidate_idx:
                        if self._is_visible(
                            observer_x,
                            observer_y,
                            observer_z,
                            obstacle_x[obstacle_index],
                            obstacle_y[obstacle_index],
                            obstacle_top[obstacle_index],
                        ):
                            visible_count += 1

                output[row, col] = visible_count

            if row == total_rows - 1 or row % report_interval == 0:
                progress_value = 12 + int(84 * ((row + 1) / float(total_rows)))
                progress(progress_value, f"Processing row {row + 1} of {total_rows}…")

        progress(98, "Writing output GeoTIFF…")
        write_int32_geotiff(self.config.output_path, output, self.grid, OUTPUT_NODATA)
        progress(100, "Analysis completed.")
        return self.config.output_path

    def _prepare_obstacles(self, progress):
        request = QgsFeatureRequest()
        request.setSubsetOfAttributes([self.config.height_field], self.config.obstacle_layer.fields())
        obstacles = []

        feature_count = max(1, self.config.obstacle_layer.featureCount())
        for index, feature in enumerate(self.config.obstacle_layer.getFeatures(request)):
            if not feature.hasGeometry():
                continue

            geometry = feature.geometry()
            if geometry.isEmpty():
                continue

            point = geometry.asPoint()
            obstacle_height = feature[self.config.height_field]
            if obstacle_height is None:
                continue

            try:
                obstacle_height = float(obstacle_height)
            except (TypeError, ValueError):
                continue

            if not math.isfinite(obstacle_height) or obstacle_height <= 0:
                continue

            terrain_z = self.grid.sample_bilinear(point.x(), point.y())
            if terrain_z is None:
                continue

            obstacles.append(
                PreparedObstacle(
                    x=float(point.x()),
                    y=float(point.y()),
                    top_elevation=float(terrain_z) + obstacle_height,
                )
            )

            if index == feature_count - 1 or index % max(1, feature_count // 20) == 0:
                progress_value = int(12 * ((index + 1) / float(feature_count)))
                progress(progress_value, f"Preparing obstacles ({index + 1}/{feature_count})…")

        return obstacles

    def _is_visible(self, observer_x, observer_y, observer_z, target_x, target_y, target_z):
        dx = target_x - observer_x
        dy = target_y - observer_y
        horizontal_distance = math.hypot(dx, dy)
        if horizontal_distance <= 0.0:
            return False

        sample_step = self.grid.sample_step
        n_samples = max(1, int(math.ceil(horizontal_distance / sample_step)))

        for sample_idx in range(1, n_samples):
            ratio = sample_idx / float(n_samples)
            x = observer_x + dx * ratio
            y = observer_y + dy * ratio
            line_z = observer_z + (target_z - observer_z) * ratio
            terrain_z = self.grid.sample_bilinear(x, y)
            if terrain_z is None:
                return False
            if terrain_z > line_z:
                return False

        return True
