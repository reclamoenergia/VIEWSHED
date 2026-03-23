# -*- coding: utf-8 -*-
"""Main QGIS plugin implementation."""

import os

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsProject

from .visible_obstacles_count_dialog import VisibleObstaclesCountDialog


class VisibleObstaclesCountPlugin:
    """QGIS plugin bootstrap class."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.dialog = None

    def tr(self, message):
        """Translate a string using Qt translation services."""
        return QCoreApplication.translate("VisibleObstaclesCount", message)

    def initGui(self):
        """Create plugin action and add it to the QGIS UI."""
        self.action = QAction(
            QIcon(),
            self.tr("Visible Obstacles Count"),
            self.iface.mainWindow(),
        )
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(self.tr("&Visible Obstacles Count"), self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        """Remove plugin action from the QGIS UI."""
        if self.action is not None:
            self.iface.removePluginMenu(self.tr("&Visible Obstacles Count"), self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    def run(self):
        """Open the main dialog."""
        if self.dialog is None:
            self.dialog = VisibleObstaclesCountDialog(self.iface, QgsProject.instance())
        else:
            self.dialog.refresh_layers()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
