# -*- coding: utf-8 -*-
"""Raster helper classes used by the visibility engine."""

import math
from dataclasses import dataclass

import numpy as np
from osgeo import gdal


@dataclass
class RasterGrid:
    """In-memory representation of a single-band raster grid."""

    path: str
    array: np.ndarray
    geotransform: tuple
    projection_wkt: str
    nodata_value: float

    @classmethod
    def from_path(cls, raster_path):
        dataset = gdal.Open(raster_path, gdal.GA_ReadOnly)
        if dataset is None:
            raise RuntimeError(f"Unable to open raster: {raster_path}")

        band = dataset.GetRasterBand(1)
        array = band.ReadAsArray().astype(np.float64, copy=False)
        nodata_value = band.GetNoDataValue()
        geotransform = dataset.GetGeoTransform(can_return_null=True)
        if geotransform is None:
            raise RuntimeError("The raster has no geotransform.")
        if abs(geotransform[2]) > 1e-12 or abs(geotransform[4]) > 1e-12:
            raise RuntimeError("Rotated rasters are not supported by this plugin.")

        projection_wkt = dataset.GetProjectionRef()
        dataset = None
        return cls(
            path=raster_path,
            array=array,
            geotransform=geotransform,
            projection_wkt=projection_wkt,
            nodata_value=nodata_value,
        )

    @property
    def rows(self):
        return int(self.array.shape[0])

    @property
    def cols(self):
        return int(self.array.shape[1])

    @property
    def pixel_width(self):
        return float(self.geotransform[1])

    @property
    def pixel_height(self):
        return float(abs(self.geotransform[5]))

    @property
    def sample_step(self):
        return min(abs(self.pixel_width), abs(self.pixel_height))

    def is_nodata(self, value):
        if self.nodata_value is None:
            return np.isnan(value)
        if np.isnan(self.nodata_value):
            return np.isnan(value)
        return np.isnan(value) or math.isclose(value, self.nodata_value, rel_tol=0.0, abs_tol=1e-12)

    def contains_pixel(self, row, col):
        return 0 <= row < self.rows and 0 <= col < self.cols

    def pixel_center(self, row, col):
        x = self.geotransform[0] + (col + 0.5) * self.geotransform[1]
        y = self.geotransform[3] + (row + 0.5) * self.geotransform[5]
        return x, y

    def world_to_pixel_float(self, x, y):
        col = (x - self.geotransform[0]) / self.geotransform[1] - 0.5
        row = (y - self.geotransform[3]) / self.geotransform[5] - 0.5
        return row, col

    def world_to_pixel_index(self, x, y):
        row_f, col_f = self.world_to_pixel_float(x, y)
        return int(math.floor(row_f + 0.5)), int(math.floor(col_f + 0.5))

    def sample_bilinear(self, x, y):
        row_f, col_f = self.world_to_pixel_float(x, y)
        if row_f < 0.0 or col_f < 0.0 or row_f > self.rows - 1 or col_f > self.cols - 1:
            return None

        row0 = int(math.floor(row_f))
        col0 = int(math.floor(col_f))
        row1 = min(row0 + 1, self.rows - 1)
        col1 = min(col0 + 1, self.cols - 1)

        frac_r = row_f - row0
        frac_c = col_f - col0

        v00 = self.array[row0, col0]
        v01 = self.array[row0, col1]
        v10 = self.array[row1, col0]
        v11 = self.array[row1, col1]

        if any(self.is_nodata(value) for value in (v00, v01, v10, v11)):
            return None

        top = v00 * (1.0 - frac_c) + v01 * frac_c
        bottom = v10 * (1.0 - frac_c) + v11 * frac_c
        return top * (1.0 - frac_r) + bottom * frac_r


def write_int32_geotiff(output_path, array, grid, nodata_value=-2147483648):
    """Write an Int32 GeoTIFF aligned to the provided RasterGrid."""
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(
        output_path,
        grid.cols,
        grid.rows,
        1,
        gdal.GDT_Int32,
        options=["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"],
    )
    if dataset is None:
        raise RuntimeError(f"Unable to create output raster: {output_path}")

    dataset.SetGeoTransform(grid.geotransform)
    dataset.SetProjection(grid.projection_wkt)
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(int(nodata_value))
    band.WriteArray(array.astype(np.int32, copy=False))
    band.FlushCache()
    dataset.FlushCache()
    dataset = None
