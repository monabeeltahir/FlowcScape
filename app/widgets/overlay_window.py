from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.models import (
    AxisScale,
    DataSourceKind,
    GateDefinition,
    GateType,
    OverlayPlot,
    OverlaySeries,
    PlotConfig,
    PlotType,
    SampleData,
    make_gate_id,
    make_overlay_plot_id,
    make_overlay_series_id,
)
from app.plotting.renderer import render_overlay_plot
from app.services.gating import (
    apply_gate,
    build_population_statistics,
    resolve_source_events,
)
from app.theme import build_main_stylesheet
from app.widgets.plot_grid import PlotGridWidget
from app.widgets.stepper_spinbox import StepperSpinBox


class OverlayWindow(QMainWindow):
    def __init__(
        self,
        sample_resolver: Callable[[str, str], SampleData | None],
        main_gates_provider: Callable[[], dict[str, GateDefinition]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sample_resolver = sample_resolver
        self._main_gates_provider = main_gates_provider
        self.overlay_plots: dict[int, OverlayPlot] = {}
        self.overlay_gates: dict[str, GateDefinition] = {}
        self._selected_cell_id: int | None = None
        self._selected_gate_id: str | None = None
        self._selected_gate_cell_id: int | None = None
        self._overlay_counter = 0
        self._overlay_gate_counter = 0
        self._grid_rows = 2
        self._grid_columns = 2

        self.setWindowTitle("Overlay Workspace")
        self.resize(1280, 860)

        self.plot_grid = PlotGridWidget(allowed_plot_types=())
        self.grid_scroll_area = QScrollArea()
        self.grid_scroll_area.setWidget(self.plot_grid)
        self.grid_scroll_area.setWidgetResizable(False)
        self.grid_scroll_area.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.rows_spin = StepperSpinBox()
        self.rows_spin.setRange(1, 12)
        self.rows_spin.setValue(self._grid_rows)
        self.columns_spin = StepperSpinBox()
        self.columns_spin.setRange(1, 12)
        self.columns_spin.setValue(self._grid_columns)

        self._build_toolbar()
        self._build_layout()
        self._connect_signals()
        self._apply_grid_dimensions(self._grid_rows, self._grid_columns)
        self.statusBar().showMessage("Send a histogram from the main workspace to start an overlay plot.")

    def _build_toolbar(self) -> None:
        self.top_toolbar = QToolBar("Overlay")
        self.top_toolbar.setMovable(False)
        self.addToolBar(self.top_toolbar)

        for label, rows, columns in (("4 Panels", 2, 2), ("6 Panels", 2, 3), ("9 Panels", 3, 3)):
            action = QAction(label, self)
            action.triggered.connect(
                lambda _checked=False, r=rows, c=columns: self._set_grid_preset(r, c)
            )
            self.top_toolbar.addAction(action)

        self.top_toolbar.addSeparator()

        histogram_gate_action = QAction("Histogram Gate", self)
        histogram_gate_action.triggered.connect(self._begin_histogram_gate)
        self.top_toolbar.addAction(histogram_gate_action)

        series_color_action = QAction("Series Color", self)
        series_color_action.triggered.connect(self._change_selected_series_color)
        self.top_toolbar.addAction(series_color_action)

        series_alpha_action = QAction("Series Transparency", self)
        series_alpha_action.triggered.connect(self._change_selected_series_alpha)
        self.top_toolbar.addAction(series_alpha_action)

        self.top_toolbar.addSeparator()

        export_action = QAction("Export Selected Plot", self)
        export_action.triggered.connect(self._export_selected_plot)
        self.top_toolbar.addAction(export_action)

        clear_action = QAction("Clear Selected Plot", self)
        clear_action.triggered.connect(self._clear_selected_plot)
        self.top_toolbar.addAction(clear_action)

        delete_gate_action = QAction("Delete Selected Gate", self)
        delete_gate_action.triggered.connect(self._delete_selected_gate)
        self.top_toolbar.addAction(delete_gate_action)

        cancel_gate_action = QAction("Cancel Gate Tool", self)
        cancel_gate_action.triggered.connect(self.plot_grid.cancel_gate_interactions)
        self.top_toolbar.addAction(cancel_gate_action)

        self.delete_gate_shortcut = QAction("Delete Selected Gate Shortcut", self)
        self.delete_gate_shortcut.setShortcut(QKeySequence.StandardKey.Delete)
        self.delete_gate_shortcut.triggered.connect(self._delete_selected_gate)
        self.addAction(self.delete_gate_shortcut)

    def _build_layout(self) -> None:
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)

        grid_controls = QWidget()
        grid_controls.setObjectName("gridControls")
        grid_controls_layout = QHBoxLayout(grid_controls)
        grid_controls_layout.setContentsMargins(8, 8, 8, 0)
        grid_controls_layout.addWidget(QLabel("Grid Rows"))
        grid_controls_layout.addWidget(self.rows_spin)
        grid_controls_layout.addSpacing(12)
        grid_controls_layout.addWidget(QLabel("Grid Columns"))
        grid_controls_layout.addWidget(self.columns_spin)
        grid_controls_layout.addStretch(1)

        center_layout.addWidget(grid_controls)
        center_layout.addWidget(self.grid_scroll_area, 1)
        self.setCentralWidget(center_container)
        self.setStyleSheet(build_main_stylesheet())

    def _connect_signals(self) -> None:
        self.plot_grid.cell_selected.connect(self._select_plot_cell)
        self.plot_grid.gate_created.connect(self._handle_gate_created)
        self.plot_grid.gate_selected.connect(self._select_gate)
        self.plot_grid.gate_geometry_changed.connect(self._update_gate_geometry)
        self.plot_grid.statistics_requested.connect(self._show_statistics_for_target)
        self.plot_grid.export_requested.connect(self._export_plot_by_cell)
        self.plot_grid.clear_requested.connect(self._clear_plot_by_cell)
        self.rows_spin.valueChanged.connect(self._on_grid_spin_changed)
        self.columns_spin.valueChanged.connect(self._on_grid_spin_changed)

    def overlay_target_choices(self) -> list[str]:
        choices = [plot.title for _, plot in self._ordered_plots()]
        choices.append("New Overlay Plot")
        return choices

    def send_histogram_plot(self, source_config: PlotConfig, sample_name: str) -> bool:
        if source_config.plot_type != PlotType.HISTOGRAM:
            self._show_error(
                "Histogram Required",
                "Only histogram plots can be sent to the overlay workspace.",
            )
            return False

        choices = self.overlay_target_choices()
        target_label = "Choose an existing overlay plot or create a new one:"
        target_choice, accepted = QInputDialog.getItem(
            self,
            "Send To Overlay",
            target_label,
            choices,
            editable=False,
        )
        if not accepted:
            return False

        if target_choice == "New Overlay Plot":
            try:
                cell_id = self._next_available_cell_id()
            except RuntimeError:
                return False
            overlay_plot = self._create_overlay_plot(cell_id, source_config)
            self.overlay_plots[cell_id] = overlay_plot
        else:
            cell_id, overlay_plot = self._find_overlay_plot_by_title(target_choice)
            if overlay_plot is None:
                self._show_error("Overlay Not Found", "The selected overlay plot is no longer available.")
                return False
            if overlay_plot.x_param != source_config.x_param:
                self._show_error(
                    "Parameter Mismatch",
                    (
                        f"{overlay_plot.title} is built on {overlay_plot.x_param}. "
                        f"Send a histogram using the same X parameter or create a new overlay plot."
                    ),
                )
                return False

        overlay_plot.series.append(
            OverlaySeries(
                id=make_overlay_series_id(),
                label=source_config.title or sample_name,
                experiment_id=source_config.experiment_id,
                sample_id=source_config.sample_id,
                x_param=source_config.x_param,
                source_kind=source_config.source_kind,
                source_gate_id=source_config.source_gate_id,
                color=source_config.histogram_color,
                alpha=0.85,
                histogram_style=source_config.histogram_style,
            )
        )
        self.overlay_plots[cell_id] = overlay_plot
        self._select_plot_cell(cell_id)
        self._render_plot(cell_id)
        self.show()
        self.raise_()
        self.activateWindow()
        self.statusBar().showMessage(
            f"Added histogram to {overlay_plot.title}.",
        )
        return True

    def refresh_all(self) -> None:
        for cell_id in self.plot_grid.active_cell_ids():
            self._render_plot(cell_id)

    def _set_grid_preset(self, rows: int, columns: int) -> None:
        self.rows_spin.setValue(rows)
        self.columns_spin.setValue(columns)

    def _on_grid_spin_changed(self) -> None:
        self._apply_grid_dimensions(self.rows_spin.value(), self.columns_spin.value())

    def _apply_grid_dimensions(self, rows: int, columns: int) -> None:
        self._grid_rows = max(1, rows)
        self._grid_columns = max(1, columns)
        self.plot_grid.set_grid_dimensions(self._grid_rows, self._grid_columns)

        active_ids = set(self.plot_grid.active_cell_ids())
        if self._selected_cell_id not in active_ids:
            self._selected_cell_id = None
        if self._selected_gate_cell_id not in active_ids:
            self._clear_selected_gate()

        for cell_id in sorted(active_ids):
            self._render_plot(cell_id)
        self.plot_grid.set_selected_cell(self._selected_cell_id)
        self.plot_grid.set_selected_gate(self._selected_gate_cell_id, self._selected_gate_id)

    def _select_plot_cell(self, cell_id: int) -> None:
        self._selected_cell_id = cell_id
        self.plot_grid.set_selected_cell(cell_id)
        if self._selected_gate_cell_id != cell_id:
            self._clear_selected_gate()

    def _render_plot(self, cell_id: int) -> None:
        overlay_plot = self.overlay_plots.get(cell_id)
        if overlay_plot is None:
            self.plot_grid.set_cell_figure(cell_id, None)
            self.plot_grid.set_cell_gate_entries(cell_id, [])
            self.plot_grid.set_cell_gates(cell_id, [])
            return

        try:
            series_frames = [
                (series, self._resolve_series_values(series))
                for series in overlay_plot.series
            ]
            plot_gates = self._gates_for_plot(cell_id)
            figure = render_overlay_plot(
                overlay_plot,
                series_frames,
                gates=plot_gates,
                selected_gate_id=self._selected_gate_id if self._selected_gate_cell_id == cell_id else None,
            )
        except Exception as exc:
            self._show_error("Overlay Plot Error", str(exc))
            return

        self.plot_grid.set_cell_figure(cell_id, figure)
        self.plot_grid.set_cell_gate_entries(cell_id, [(gate.id, gate.name) for gate in plot_gates])
        self.plot_grid.set_cell_gates(cell_id, plot_gates)
        self.plot_grid.set_selected_gate(self._selected_gate_cell_id, self._selected_gate_id)

    def _begin_histogram_gate(self) -> None:
        if self._selected_cell_id is None or self._selected_cell_id not in self.overlay_plots:
            self._show_error("No Overlay Selected", "Select an overlay plot before starting a histogram gate.")
            return

        self.plot_grid.cancel_gate_interactions()
        self._clear_selected_gate()
        if not self.plot_grid.begin_gate_interaction(self._selected_cell_id, GateType.HISTOGRAM):
            self._show_error("Gate Tool Unavailable", "The selected overlay plot is not ready yet.")
            return

        self.statusBar().showMessage("Drag across the overlay histogram to create a range gate.")

    def _handle_gate_created(self, cell_id: int, gate_type: GateType, payload: dict[str, object]) -> None:
        if gate_type != GateType.HISTOGRAM:
            return

        overlay_plot = self.overlay_plots.get(cell_id)
        if overlay_plot is None:
            return

        self._overlay_gate_counter += 1
        gate = GateDefinition(
            id=make_gate_id(),
            name=f"H{self._overlay_gate_counter}",
            gate_type=GateType.HISTOGRAM,
            experiment_id="overlay",
            sample_id=overlay_plot.id,
            plot_cell_id=cell_id,
            source_kind=DataSourceKind.ALL_EVENTS,
            source_gate_id=None,
            x_param=overlay_plot.x_param,
            x1=float(payload["x1"]),
            x2=float(payload["x2"]),
            color="#ff2d20",
        )
        self.overlay_gates[gate.id] = gate
        self._selected_gate_id = gate.id
        self._selected_gate_cell_id = cell_id
        self._render_plot(cell_id)
        self.statusBar().showMessage(f"Created overlay gate {gate.name}.")

    def _select_gate(self, cell_id: int, gate_id: str | None) -> None:
        self._selected_gate_cell_id = cell_id if gate_id else None
        self._selected_gate_id = gate_id
        self.plot_grid.set_selected_gate(self._selected_gate_cell_id, self._selected_gate_id)
        self._render_plot(cell_id)

    def _update_gate_geometry(self, cell_id: int, gate_id: str, payload: dict[str, object]) -> None:
        gate = self.overlay_gates.get(gate_id)
        if gate is None:
            return

        self.overlay_gates[gate_id] = GateDefinition(
            id=gate.id,
            name=gate.name,
            gate_type=gate.gate_type,
            experiment_id=gate.experiment_id,
            sample_id=gate.sample_id,
            plot_cell_id=gate.plot_cell_id,
            source_kind=gate.source_kind,
            source_gate_id=gate.source_gate_id,
            x_param=gate.x_param,
            y_param=gate.y_param,
            x1=float(payload.get("x1", gate.x1 or 0.0)),
            x2=float(payload.get("x2", gate.x2 or 0.0)),
            y1=gate.y1,
            y2=gate.y2,
            color=gate.color,
            points=list(gate.points),
            metadata=dict(gate.metadata),
        )
        self._selected_gate_cell_id = cell_id
        self._render_plot(cell_id)

    def _change_selected_series_color(self) -> None:
        cell_id, overlay_plot, series = self._choose_overlay_series()
        if overlay_plot is None or series is None or cell_id is None:
            return

        color = QColorDialog.getColor(parent=self, title=f"Series Color - {series.label}")
        if not color.isValid():
            return

        self._replace_series(
            cell_id,
            series.id,
            replace(series, color=color.name()),
        )
        self.statusBar().showMessage(f"Updated overlay color for {series.label}.")

    def _change_selected_series_alpha(self) -> None:
        cell_id, overlay_plot, series = self._choose_overlay_series()
        if overlay_plot is None or series is None or cell_id is None:
            return

        alpha, accepted = QInputDialog.getDouble(
            self,
            "Series Transparency",
            f"Transparency for {series.label} (0-1):",
            series.alpha,
            0.0,
            1.0,
            2,
        )
        if not accepted:
            return

        self._replace_series(
            cell_id,
            series.id,
            replace(series, alpha=float(alpha)),
        )
        self.statusBar().showMessage(f"Updated transparency for {series.label}.")

    def _replace_series(self, cell_id: int, series_id: str, updated_series: OverlaySeries) -> None:
        overlay_plot = self.overlay_plots.get(cell_id)
        if overlay_plot is None:
            return

        overlay_plot.series = [
            updated_series if series.id == series_id else series
            for series in overlay_plot.series
        ]
        self.overlay_plots[cell_id] = overlay_plot
        self._render_plot(cell_id)

    def _show_statistics_for_target(self, cell_id: int, gate_id: str | None) -> None:
        overlay_plot = self.overlay_plots.get(cell_id)
        if overlay_plot is None:
            return

        gate = self.overlay_gates.get(gate_id) if gate_id else None
        title = f"Overlay Statistics - {overlay_plot.title}"
        if gate is not None:
            title = f"Overlay Gate Statistics - {gate.name}"

        sections: list[str] = []
        for series in overlay_plot.series:
            source_frame = self._resolve_series_frame(series)
            if gate is None:
                population_frame = source_frame
                label = "Current Population"
            else:
                population_frame = source_frame
                if not source_frame.empty:
                    histogram_gate = GateDefinition(
                        id=gate.id,
                        name=gate.name,
                        gate_type=GateType.HISTOGRAM,
                        experiment_id=gate.experiment_id,
                        sample_id=gate.sample_id,
                        plot_cell_id=gate.plot_cell_id,
                        source_kind=DataSourceKind.ALL_EVENTS,
                        source_gate_id=None,
                        x_param=gate.x_param,
                        x1=gate.x1,
                        x2=gate.x2,
                        color=gate.color,
                    )
                    population_frame = apply_gate(source_frame, histogram_gate)
                label = gate.name

            stats = build_population_statistics(
                population_frame,
                overlay_plot.x_param,
                None,
                len(source_frame),
                label,
            )
            sections.append(
                "\n".join(
                    [
                        f"Series: {series.label}",
                        f"Count: {stats.count}",
                        f"Percentage of source: {stats.percentage_of_total:.2f}%",
                        f"Mean {overlay_plot.x_param}: {self._format_stat(stats.mean_x)}",
                        f"Median {overlay_plot.x_param}: {self._format_stat(stats.median_x)}",
                    ]
                )
            )

        if not sections:
            sections = ["No series available."]
        QMessageBox.information(self, title, "\n\n".join(sections))

    def _export_plot_by_cell(self, cell_id: int) -> None:
        self._select_plot_cell(cell_id)
        self._export_selected_plot()

    def _export_selected_plot(self) -> None:
        if self._selected_cell_id is None:
            self._show_error("No Overlay Selected", "Select an overlay plot before exporting.")
            return

        overlay_plot = self.overlay_plots.get(self._selected_cell_id)
        if overlay_plot is None:
            self._show_error("No Overlay Selected", "Select an overlay plot before exporting.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Overlay Plot",
            f"{overlay_plot.title}.png",
            "PNG Files (*.png);;TIFF Files (*.tiff);;PDF Files (*.pdf)",
        )
        if not file_path:
            return

        figure = render_overlay_plot(
            overlay_plot,
            [(series, self._resolve_series_values(series)) for series in overlay_plot.series],
            gates=self._gates_for_plot(self._selected_cell_id),
            selected_gate_id=self._selected_gate_id if self._selected_gate_cell_id == self._selected_cell_id else None,
        )
        figure.savefig(file_path, dpi=overlay_plot.export_dpi, bbox_inches="tight")
        self.statusBar().showMessage(
            f"Exported {overlay_plot.title} to {Path(file_path).name}.",
        )

    def _clear_plot_by_cell(self, cell_id: int) -> None:
        if cell_id in self.overlay_plots:
            del self.overlay_plots[cell_id]
        gate_ids = [gate.id for gate in self._gates_for_plot(cell_id)]
        for gate_id in gate_ids:
            self.overlay_gates.pop(gate_id, None)
        if self._selected_cell_id == cell_id:
            self._selected_cell_id = None
        if self._selected_gate_cell_id == cell_id:
            self._clear_selected_gate()
        self.plot_grid.set_cell_figure(cell_id, None)
        self.plot_grid.set_cell_gate_entries(cell_id, [])
        self.plot_grid.set_cell_gates(cell_id, [])
        self.plot_grid.set_selected_cell(self._selected_cell_id)

    def _clear_selected_plot(self) -> None:
        if self._selected_cell_id is None:
            return
        self._clear_plot_by_cell(self._selected_cell_id)

    def _delete_selected_gate(self) -> None:
        if not self._selected_gate_id:
            return
        gate = self.overlay_gates.pop(self._selected_gate_id, None)
        if gate is None:
            self._clear_selected_gate()
            return
        self._clear_selected_gate()
        self._render_plot(gate.plot_cell_id)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete and self._selected_gate_id:
            self._delete_selected_gate()
            event.accept()
            return
        super().keyPressEvent(event)

    def _clear_selected_gate(self) -> None:
        self._selected_gate_id = None
        self._selected_gate_cell_id = None
        self.plot_grid.set_selected_gate(None, None)

    def _resolve_series_frame(self, series: OverlaySeries):
        sample = self._sample_resolver(series.experiment_id, series.sample_id)
        if sample is None:
            return pd.DataFrame(columns=[series.x_param])

        frame = resolve_source_events(
            sample,
            series.source_kind,
            series.source_gate_id,
            self._main_gates_provider(),
        )
        if series.x_param not in frame.columns:
            return frame.iloc[0:0]
        return frame

    def _resolve_series_values(self, series: OverlaySeries) -> np.ndarray:
        frame = self._resolve_series_frame(series)
        if getattr(frame, "empty", True):
            return np.asarray([], dtype=float)
        return frame[series.x_param].to_numpy(dtype=float, copy=False)

    def _ordered_plots(self) -> list[tuple[int, OverlayPlot]]:
        return sorted(self.overlay_plots.items(), key=lambda item: item[0])

    def _find_overlay_plot_by_title(self, title: str) -> tuple[int | None, OverlayPlot | None]:
        for cell_id, overlay_plot in self._ordered_plots():
            if overlay_plot.title == title:
                return cell_id, overlay_plot
        return None, None

    def _next_available_cell_id(self) -> int:
        active_ids = self.plot_grid.active_cell_ids()
        for cell_id in active_ids:
            if cell_id not in self.overlay_plots:
                return cell_id

        next_rows = min(self.rows_spin.value() + 1, 12)
        if next_rows == self.rows_spin.value():
            self._show_error("Overlay Grid Full", "Expand the overlay grid to add another overlay plot.")
            raise RuntimeError("Overlay grid is full.")

        self.rows_spin.setValue(next_rows)
        for cell_id in self.plot_grid.active_cell_ids():
            if cell_id not in self.overlay_plots:
                return cell_id
        raise RuntimeError("No empty overlay cell available after expanding the grid.")

    def _create_overlay_plot(self, cell_id: int, source_config: PlotConfig) -> OverlayPlot:
        self._overlay_counter += 1
        return OverlayPlot(
            id=make_overlay_plot_id(),
            cell_id=cell_id,
            title=f"Overlay {self._overlay_counter}",
            x_param=source_config.x_param,
            x_scale=source_config.x_scale,
            x_auto_range=source_config.x_auto_range,
            x_min=source_config.x_min,
            x_max=source_config.x_max,
            bins=source_config.bins,
            font_size=source_config.font_size,
            export_dpi=source_config.export_dpi,
            series=[],
        )

    def _gates_for_plot(self, cell_id: int) -> list[GateDefinition]:
        return sorted(
            [
                gate
                for gate in self.overlay_gates.values()
                if gate.plot_cell_id == cell_id
            ],
            key=lambda gate: gate.name,
        )

    def _choose_overlay_series(
        self,
    ) -> tuple[int | None, OverlayPlot | None, OverlaySeries | None]:
        if self._selected_cell_id is None:
            self._show_error("No Overlay Selected", "Select an overlay plot first.")
            return None, None, None

        overlay_plot = self.overlay_plots.get(self._selected_cell_id)
        if overlay_plot is None or not overlay_plot.series:
            self._show_error("No Overlay Series", "Send at least one histogram to this overlay plot first.")
            return self._selected_cell_id, overlay_plot, None

        if len(overlay_plot.series) == 1:
            return self._selected_cell_id, overlay_plot, overlay_plot.series[0]

        labels = [f"{index + 1}. {series.label}" for index, series in enumerate(overlay_plot.series)]
        choice, accepted = QInputDialog.getItem(
            self,
            "Select Overlay Series",
            "Choose the overlaid histogram to update:",
            labels,
            editable=False,
        )
        if not accepted:
            return self._selected_cell_id, overlay_plot, None

        series_index = labels.index(choice)
        return self._selected_cell_id, overlay_plot, overlay_plot.series[series_index]

    def _format_stat(self, value: float | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:.4f}"

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
