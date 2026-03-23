# -*- coding: utf-8 -*-
"""Dialog and orchestration logic for the plugin."""

import os
import traceback

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qgis.core import Qgis, QgsProject, QgsRasterLayer, QgsVectorLayer, QgsWkbTypes
from qgis.utils import iface as global_iface

from .validation import InputValidator, ValidationError
from .visibility_engine import VisibilityEngine, VisibilityEngineConfig

class VisibleObstaclesCountDialog(QDialog):
    """Main user interface for the plugin."""

    def __init__(self, iface, project=None, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.project = project or QgsProject.instance()
        self.validator = InputValidator()
        self._build_ui()
        self.refresh_layers()

    def _build_ui(self):
        self.setWindowTitle("Visible Obstacles Count")
        self.setMinimumWidth(620)
        self.setWindowModality(Qt.NonModal)

        main_layout = QVBoxLayout()

        input_group = QGroupBox("Input")
        form = QFormLayout()

        self.dtm_combo = QComboBox()
        form.addRow("DTM raster:", self.dtm_combo)

        self.obstacle_combo = QComboBox()
        self.obstacle_combo.currentIndexChanged.connect(self._refresh_height_fields)
        form.addRow("Obstacle point layer:", self.obstacle_combo)

        self.height_field_combo = QComboBox()
        form.addRow("Obstacle height field:", self.height_field_combo)

        self.observer_height_spin = QDoubleSpinBox()
        self.observer_height_spin.setDecimals(3)
        self.observer_height_spin.setRange(0.001, 1000000.0)
        self.observer_height_spin.setValue(1.7)
        self.observer_height_spin.setSuffix(" m")
        form.addRow("Observer height:", self.observer_height_spin)

        self.max_distance_spin = QDoubleSpinBox()
        self.max_distance_spin.setDecimals(3)
        self.max_distance_spin.setRange(0.001, 100000000.0)
        self.max_distance_spin.setValue(5000.0)
        self.max_distance_spin.setSuffix(" m")
        form.addRow("Maximum analysis distance:", self.max_distance_spin)

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.output_path_edit = QLineEdit()
        self.output_browse_button = QPushButton("Browse…")
        self.output_browse_button.clicked.connect(self._browse_output)
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(self.output_browse_button)
        form.addRow("Output GeoTIFF:", output_row)

        input_group.setLayout(form)
        main_layout.addWidget(input_group)

        self.message_label = QLabel("Select the inputs and run the analysis.")
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("color: #444;")
        main_layout.addWidget(self.message_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch(1)
        self.run_button = QPushButton("Run")
        self.close_button = QPushButton("Close")
        self.run_button.clicked.connect(self._run)
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.close_button)
        main_layout.addWidget(button_row)

        self.setLayout(main_layout)

    def refresh_layers(self):
        """Reload available raster and vector layers from the project."""
        current_raster = self.dtm_combo.currentData()
        current_vector = self.obstacle_combo.currentData()

        self.dtm_combo.blockSignals(True)
        self.obstacle_combo.blockSignals(True)
        self.dtm_combo.clear()
        self.obstacle_combo.clear()

        for layer in self.project.mapLayers().values():
            if isinstance(layer, QgsRasterLayer):
                self.dtm_combo.addItem(layer.name(), layer.id())
            elif isinstance(layer, QgsVectorLayer) and QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.PointGeometry:
                self.obstacle_combo.addItem(layer.name(), layer.id())

        self._restore_selection(self.dtm_combo, current_raster)
        self._restore_selection(self.obstacle_combo, current_vector)
        self.dtm_combo.blockSignals(False)
        self.obstacle_combo.blockSignals(False)
        self._refresh_height_fields()

    def _restore_selection(self, combo, layer_id):
        if not layer_id:
            return
        index = combo.findData(layer_id)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _refresh_height_fields(self):
        self.height_field_combo.clear()
        layer = self._selected_obstacle_layer()
        if layer is None:
            return
        for field in layer.fields():
            if field.isNumeric():
                self.height_field_combo.addItem(field.name())

    def _selected_dtm_layer(self):
        layer_id = self.dtm_combo.currentData()
        return self.project.mapLayer(layer_id) if layer_id else None

    def _selected_obstacle_layer(self):
        layer_id = self.obstacle_combo.currentData()
        return self.project.mapLayer(layer_id) if layer_id else None

    def _browse_output(self):
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save output GeoTIFF",
            self.output_path_edit.text().strip(),
            "GeoTIFF (*.tif *.tiff)",
        )
        if output_path:
            if not output_path.lower().endswith((".tif", ".tiff")):
                output_path += ".tif"
            self.output_path_edit.setText(output_path)

    def _set_busy(self, busy):
        self.run_button.setEnabled(not busy)
        self.close_button.setEnabled(not busy)
        self.output_browse_button.setEnabled(not busy)
        self.dtm_combo.setEnabled(not busy)
        self.obstacle_combo.setEnabled(not busy)
        self.height_field_combo.setEnabled(not busy)
        self.observer_height_spin.setEnabled(not busy)
        self.max_distance_spin.setEnabled(not busy)
        self.output_path_edit.setEnabled(not busy)

    def _push_message(self, message, level=Qgis.Info):
        self.message_label.setText(message)
        if self.iface is not None:
            self.iface.messageBar().pushMessage("Visible Obstacles Count", message, level=level, duration=8)

    def _progress_callback(self, value, message):
        self.progress_bar.setValue(max(0, min(100, int(value))))
        self.message_label.setText(message)
        try:
            if global_iface is not None:
                global_iface.mainWindow().statusBar().showMessage(message)
        except Exception:
            pass
        from qgis.PyQt.QtWidgets import QApplication

        QApplication.processEvents()

    def _run(self):
        try:
            dtm_layer = self._selected_dtm_layer()
            obstacle_layer = self._selected_obstacle_layer()
            height_field = self.height_field_combo.currentText().strip()
            observer_height = float(self.observer_height_spin.value())
            max_distance = float(self.max_distance_spin.value())
            output_path = self.output_path_edit.text().strip()

            validated = self.validator.validate(
                dtm_layer=dtm_layer,
                obstacle_layer=obstacle_layer,
                height_field=height_field,
                observer_height=observer_height,
                max_distance=max_distance,
                output_path=output_path,
            )
        except ValidationError as exc:
            self._push_message(str(exc), level=Qgis.Warning)
            QMessageBox.warning(self, "Validation error", str(exc))
            return

        self._set_busy(True)
        self.progress_bar.setValue(0)
        self._push_message("Starting analysis…", level=Qgis.Info)

        config = VisibilityEngineConfig(
            dtm_layer=validated["dtm_layer"],
            obstacle_layer=validated["obstacle_layer"],
            height_field=validated["height_field"],
            observer_height=validated["observer_height"],
            max_distance=validated["max_distance"],
            output_path=validated["output_path"],
        )

        try:
            engine = VisibilityEngine(config)
            result_path = engine.run(progress_callback=self._progress_callback)
        except Exception as exc:  # pylint: disable=broad-except
            details = traceback.format_exc()
            self._push_message(f"Analysis failed: {exc}", level=Qgis.Critical)
            QMessageBox.critical(self, "Analysis failed", f"{exc}\n\n{details}")
            self._set_busy(False)
            return

        self._set_busy(False)
        self.progress_bar.setValue(100)
        self._push_message(f"Analysis completed. Output saved to {result_path}", level=Qgis.Success)
        self.iface.addRasterLayer(result_path, os.path.basename(result_path))
        QMessageBox.information(self, "Completed", f"Output raster created:\n{result_path}")
