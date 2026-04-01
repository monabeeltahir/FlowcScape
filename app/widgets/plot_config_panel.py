from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models import AxisScale, PlotConfig, PlotType, SampleData
from app.theme import (
    AXES_BOX_MIN_HEIGHT,
    RANGES_BOX_MIN_HEIGHT,
    SELECTED_PLOT_BOX_MIN_HEIGHT,
    STYLE_BOX_MIN_HEIGHT,
)


class PlotConfigPanel(QWidget):
    config_changed = Signal(object)
    export_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._config: PlotConfig | None = None
        self._sample: SampleData | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        info_group = QGroupBox("Selected Plot")
        info_group.setMinimumHeight(SELECTED_PLOT_BOX_MIN_HEIGHT)
        info_layout = QFormLayout(info_group)
        self.plot_label = QLabel("No plot selected")
        self.sample_label = QLabel("No sample")
        info_layout.addRow("Plot:", self.plot_label)
        info_layout.addRow("Sample:", self.sample_label)

        axis_group = QGroupBox("Axes")
        axis_group.setMinimumHeight(AXES_BOX_MIN_HEIGHT)
        axis_layout = QFormLayout(axis_group)

        self.plot_type_combo = QComboBox()
        self.plot_type_combo.addItems([plot_type.value for plot_type in PlotType])

        self.x_param_combo = QComboBox()
        self.y_param_combo = QComboBox()
        self.x_scale_combo = QComboBox()
        self.x_scale_combo.addItems([AxisScale.LINEAR.value, AxisScale.LOG.value])
        self.y_scale_combo = QComboBox()
        self.y_scale_combo.addItems([AxisScale.LINEAR.value, AxisScale.LOG.value])

        axis_layout.addRow("Type:", self.plot_type_combo)
        axis_layout.addRow("X parameter:", self.x_param_combo)
        axis_layout.addRow("Y parameter:", self.y_param_combo)
        axis_layout.addRow("X scale:", self.x_scale_combo)
        axis_layout.addRow("Y scale:", self.y_scale_combo)

        range_group = QGroupBox("Ranges")
        range_group.setMinimumHeight(RANGES_BOX_MIN_HEIGHT)
        range_layout = QFormLayout(range_group)
        self.x_auto_checkbox = QCheckBox("Automatic X range")
        self.y_auto_checkbox = QCheckBox("Automatic Y range")
        self.x_min_edit = QLineEdit()
        self.x_max_edit = QLineEdit()
        self.y_min_edit = QLineEdit()
        self.y_max_edit = QLineEdit()
        range_layout.addRow(self.x_auto_checkbox)
        range_layout.addRow("X min:", self.x_min_edit)
        range_layout.addRow("X max:", self.x_max_edit)
        range_layout.addRow(self.y_auto_checkbox)
        range_layout.addRow("Y min:", self.y_min_edit)
        range_layout.addRow("Y max:", self.y_max_edit)

        style_group = QGroupBox("Style")
        style_group.setMinimumHeight(STYLE_BOX_MIN_HEIGHT)
        style_layout = QFormLayout(style_group)
        self.title_edit = QLineEdit()
        self.bins_spin = QSpinBox()
        self.bins_spin.setRange(10, 1000)
        self.histogram_style_combo = QComboBox()
        self.histogram_style_combo.addItems(["Line", "Bar"])
        self.histogram_color_combo = QComboBox()
        self.histogram_color_combo.setEditable(True)
        self.histogram_color_combo.addItems(
            ["black", "#d63b2d", "red", "blue", "green", "orange", "purple"]
        )
        self.density_gridsize_spin = QSpinBox()
        self.density_gridsize_spin.setRange(10, 250)
        self.density_min_count_spin = QSpinBox()
        self.density_min_count_spin.setRange(1, 100)
        self.density_cmap_combo = QComboBox()
        self.density_cmap_combo.addItems(
            ["turbo", "viridis", "plasma", "inferno", "magma", "cividis", "jet"]
        )
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 32)
        self.export_dpi_spin = QSpinBox()
        self.export_dpi_spin.setRange(150, 2400)
        self.export_dpi_spin.setSingleStep(50)
        self.export_button = QPushButton("Export Selected Plot")

        style_layout.addRow("Title:", self.title_edit)
        style_layout.addRow("Histogram bins:", self.bins_spin)
        style_layout.addRow("Histogram style:", self.histogram_style_combo)
        style_layout.addRow("Histogram color:", self.histogram_color_combo)
        style_layout.addRow("Density gridsize:", self.density_gridsize_spin)
        style_layout.addRow("Density min count:", self.density_min_count_spin)
        style_layout.addRow("Density colormap:", self.density_cmap_combo)
        style_layout.addRow("Font size:", self.font_size_spin)
        style_layout.addRow("Export DPI:", self.export_dpi_spin)

        button_row = QHBoxLayout()
        button_row.addWidget(self.export_button)

        root_layout.addWidget(info_group)
        root_layout.addWidget(axis_group)
        root_layout.addWidget(range_group)
        root_layout.addWidget(style_group)
        root_layout.addLayout(button_row)
        root_layout.addStretch(1)

        self._connect_signals()
        self._set_enabled(False)

    def set_plot_context(self, config: PlotConfig | None, sample: SampleData | None) -> None:
        self._config = config.clone() if config else None
        self._sample = sample
        has_context = self._config is not None and self._sample is not None
        self._set_enabled(has_context)

        if not has_context:
            self.plot_label.setText("No plot selected")
            self.sample_label.setText("No sample")
            self.x_param_combo.clear()
            self.y_param_combo.clear()
            return

        self.plot_label.setText(f"Cell {self._config.cell_id + 1}")
        self.sample_label.setText(self._sample.name)

        blockers = [
            QSignalBlocker(self.plot_type_combo),
            QSignalBlocker(self.x_param_combo),
            QSignalBlocker(self.y_param_combo),
            QSignalBlocker(self.x_scale_combo),
            QSignalBlocker(self.y_scale_combo),
            QSignalBlocker(self.x_auto_checkbox),
            QSignalBlocker(self.y_auto_checkbox),
            QSignalBlocker(self.title_edit),
            QSignalBlocker(self.bins_spin),
            QSignalBlocker(self.histogram_style_combo),
            QSignalBlocker(self.histogram_color_combo),
            QSignalBlocker(self.density_gridsize_spin),
            QSignalBlocker(self.density_min_count_spin),
            QSignalBlocker(self.density_cmap_combo),
            QSignalBlocker(self.font_size_spin),
            QSignalBlocker(self.export_dpi_spin),
            QSignalBlocker(self.x_min_edit),
            QSignalBlocker(self.x_max_edit),
            QSignalBlocker(self.y_min_edit),
            QSignalBlocker(self.y_max_edit),
        ]
        _ = blockers

        self.plot_type_combo.setCurrentText(self._config.plot_type.value)
        self.x_param_combo.clear()
        self.y_param_combo.clear()
        self.x_param_combo.addItems(self._sample.parameters)
        self.y_param_combo.addItems([""] + self._sample.parameters)
        self.x_param_combo.setCurrentText(self._config.x_param)
        self.y_param_combo.setCurrentText(self._config.y_param or "")
        self.x_scale_combo.setCurrentText(self._config.x_scale.value)
        self.y_scale_combo.setCurrentText(self._config.y_scale.value)
        self.x_auto_checkbox.setChecked(self._config.x_auto_range)
        self.y_auto_checkbox.setChecked(self._config.y_auto_range)
        self.title_edit.setText(self._config.title)
        self.bins_spin.setValue(self._config.bins)
        self.histogram_style_combo.setCurrentText(self._config.histogram_style)
        self.histogram_color_combo.setCurrentText(self._config.histogram_color)
        self.density_gridsize_spin.setValue(self._config.density_gridsize)
        self.density_min_count_spin.setValue(self._config.density_min_count)
        self.density_cmap_combo.setCurrentText(self._config.density_color_map)
        self.font_size_spin.setValue(self._config.font_size)
        self.export_dpi_spin.setValue(self._config.export_dpi)
        self.x_min_edit.setText("" if self._config.x_min is None else str(self._config.x_min))
        self.x_max_edit.setText("" if self._config.x_max is None else str(self._config.x_max))
        self.y_min_edit.setText("" if self._config.y_min is None else str(self._config.y_min))
        self.y_max_edit.setText("" if self._config.y_max is None else str(self._config.y_max))
        self._update_axis_visibility()

    def _connect_signals(self) -> None:
        self.plot_type_combo.currentTextChanged.connect(self._emit_updated_config)
        self.x_param_combo.currentTextChanged.connect(self._emit_updated_config)
        self.y_param_combo.currentTextChanged.connect(self._emit_updated_config)
        self.x_scale_combo.currentTextChanged.connect(self._emit_updated_config)
        self.y_scale_combo.currentTextChanged.connect(self._emit_updated_config)
        self.x_auto_checkbox.toggled.connect(self._emit_updated_config)
        self.y_auto_checkbox.toggled.connect(self._emit_updated_config)
        self.title_edit.editingFinished.connect(self._emit_updated_config)
        self.bins_spin.valueChanged.connect(self._emit_updated_config)
        self.histogram_style_combo.currentTextChanged.connect(self._emit_updated_config)
        self.histogram_color_combo.currentTextChanged.connect(self._emit_updated_config)
        self.density_gridsize_spin.valueChanged.connect(self._emit_updated_config)
        self.density_min_count_spin.valueChanged.connect(self._emit_updated_config)
        self.density_cmap_combo.currentTextChanged.connect(self._emit_updated_config)
        self.font_size_spin.valueChanged.connect(self._emit_updated_config)
        self.export_dpi_spin.valueChanged.connect(self._emit_updated_config)
        self.x_min_edit.editingFinished.connect(self._emit_updated_config)
        self.x_max_edit.editingFinished.connect(self._emit_updated_config)
        self.y_min_edit.editingFinished.connect(self._emit_updated_config)
        self.y_max_edit.editingFinished.connect(self._emit_updated_config)
        self.export_button.clicked.connect(self.export_requested.emit)

    def _set_enabled(self, enabled: bool) -> None:
        for widget in [
            self.plot_type_combo,
            self.x_param_combo,
            self.y_param_combo,
            self.x_scale_combo,
            self.y_scale_combo,
            self.x_auto_checkbox,
            self.y_auto_checkbox,
            self.x_min_edit,
            self.x_max_edit,
            self.y_min_edit,
            self.y_max_edit,
            self.title_edit,
            self.bins_spin,
            self.histogram_style_combo,
            self.histogram_color_combo,
            self.density_gridsize_spin,
            self.density_min_count_spin,
            self.density_cmap_combo,
            self.font_size_spin,
            self.export_dpi_spin,
            self.export_button,
        ]:
            widget.setEnabled(enabled)

    def _emit_updated_config(self) -> None:
        if self._config is None:
            return

        self._config.plot_type = PlotType(self.plot_type_combo.currentText())
        self._config.x_param = self.x_param_combo.currentText()
        self._config.y_param = self.y_param_combo.currentText() or None
        self._config.x_scale = AxisScale(self.x_scale_combo.currentText())
        self._config.y_scale = AxisScale(self.y_scale_combo.currentText())
        self._config.x_auto_range = self.x_auto_checkbox.isChecked()
        self._config.y_auto_range = self.y_auto_checkbox.isChecked()
        self._config.title = self.title_edit.text().strip()
        self._config.bins = self.bins_spin.value()
        self._config.histogram_style = self.histogram_style_combo.currentText()
        self._config.histogram_color = self.histogram_color_combo.currentText().strip() or "black"
        self._config.density_gridsize = self.density_gridsize_spin.value()
        self._config.density_min_count = self.density_min_count_spin.value()
        self._config.density_color_map = self.density_cmap_combo.currentText()
        self._config.font_size = self.font_size_spin.value()
        self._config.export_dpi = self.export_dpi_spin.value()
        self._config.x_min = _to_float(self.x_min_edit.text())
        self._config.x_max = _to_float(self.x_max_edit.text())
        self._config.y_min = _to_float(self.y_min_edit.text())
        self._config.y_max = _to_float(self.y_max_edit.text())
        self._update_axis_visibility()
        self.config_changed.emit(self._config.clone())

    def _update_axis_visibility(self) -> None:
        is_histogram = (
            self.plot_type_combo.currentText() == PlotType.HISTOGRAM.value
            if self._config is not None
            else True
        )
        self.y_param_combo.setEnabled(not is_histogram)
        self.y_scale_combo.setEnabled(not is_histogram)
        self.y_auto_checkbox.setEnabled(not is_histogram)
        self.y_min_edit.setEnabled(not is_histogram and not self.y_auto_checkbox.isChecked())
        self.y_max_edit.setEnabled(not is_histogram and not self.y_auto_checkbox.isChecked())
        self.x_min_edit.setEnabled(not self.x_auto_checkbox.isChecked())
        self.x_max_edit.setEnabled(not self.x_auto_checkbox.isChecked())
        is_density = self.plot_type_combo.currentText() == PlotType.DENSITY.value
        self.density_gridsize_spin.setEnabled(is_density)
        self.density_min_count_spin.setEnabled(is_density)
        self.density_cmap_combo.setEnabled(is_density)
        self.bins_spin.setEnabled(self._config is not None and is_histogram)
        self.histogram_style_combo.setEnabled(self._config is not None and is_histogram)
        self.histogram_color_combo.setEnabled(self._config is not None and is_histogram)


def _to_float(value: str) -> float | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None
