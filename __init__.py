# -*- coding: utf-8 -*-
"""QGIS plugin entry point for Visible Obstacles Count."""


def classFactory(iface):
    """Load VisibleObstaclesCountPlugin class from file.

    Parameters
    ----------
    iface : qgis.gui.QgisInterface
        QGIS interface instance.
    """
    from .visible_obstacles_count import VisibleObstaclesCountPlugin

    return VisibleObstaclesCountPlugin(iface)
