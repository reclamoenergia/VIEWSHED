# -*- coding: utf-8 -*-
"""Input validation utilities."""

import os

from qgis.core import QgsUnitTypes, QgsWkbTypes


class ValidationError(Exception):
    """Raised when plugin inputs are not valid."""


class InputValidator:
    """Validates the plugin inputs before the computation starts."""

    def validate(self, dtm_layer, obstacle_layer, height_field, observer_height, max_distance, output_path):
        if dtm_layer is None:
            raise ValidationError("Select a DTM raster layer.")
        if not dtm_layer.isValid():
            raise ValidationError("The selected DTM raster is not valid or cannot be read.")

        if obstacle_layer is None:
            raise ValidationError("Select an obstacle point layer.")
        if not obstacle_layer.isValid():
            raise ValidationError("The selected obstacle layer is not valid or cannot be read.")
        if QgsWkbTypes.geometryType(obstacle_layer.wkbType()) != QgsWkbTypes.PointGeometry:
            raise ValidationError("The obstacle layer must contain point geometries.")

        field = obstacle_layer.fields().field(height_field)
        if field.name() == "":
            raise ValidationError("Select a valid numeric obstacle height field.")
        if not field.isNumeric():
            raise ValidationError("The obstacle height field must be numeric.")

        dtm_crs = dtm_layer.crs()
        obstacle_crs = obstacle_layer.crs()
        if not dtm_crs.isValid() or not obstacle_crs.isValid():
            raise ValidationError("Both layers must have a valid CRS.")
        if dtm_crs != obstacle_crs:
            raise ValidationError("DTM raster and obstacle layer must use the same CRS.")
        if not dtm_crs.isProjected():
            raise ValidationError("The CRS must be projected and metric.")
        if dtm_crs.mapUnits() != QgsUnitTypes.DistanceMeters:
            raise ValidationError("The CRS map units must be meters.")

        provider = dtm_layer.dataProvider()
        extent = dtm_layer.extent()
        if provider.xSize() <= 0 or provider.ySize() <= 0 or extent.isEmpty():
            raise ValidationError("The DTM raster has invalid dimensions or extent.")

        if observer_height <= 0:
            raise ValidationError("Observer height must be greater than zero.")
        if max_distance <= 0:
            raise ValidationError("Maximum analysis distance must be greater than zero.")

        if not output_path:
            raise ValidationError("Choose a valid output GeoTIFF path.")
        output_dir = os.path.dirname(output_path) or "."
        if not os.path.isdir(output_dir):
            raise ValidationError("The output directory does not exist.")
        if not output_path.lower().endswith((".tif", ".tiff")):
            raise ValidationError("The output file must use the .tif or .tiff extension.")

        return {
            "dtm_layer": dtm_layer,
            "obstacle_layer": obstacle_layer,
            "height_field": height_field,
            "observer_height": observer_height,
            "max_distance": max_distance,
            "output_path": output_path,
        }
