from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.models import (
    DataSourceKind,
    GateDefinition,
    GateType,
    PlotConfig,
    PlotType,
    PopulationStatistics,
    SampleData,
    make_gate_id,
)
from app.plotting.config import build_default_plot_config, build_plot_title
from app.plotting.renderer import render_plot
from app.services.atx_loader import ATXLoadError
from app.services.experiment_loader import load_atx_files, load_fcs_files_as_experiment
from app.services.fcs_loader import FCSLoadError
from app.services.gating import (
    build_population_statistics,
    gate_source_label,
    resolve_gate_events,
    resolve_plot_events,
)
from app.state import AppState
from app.theme import LEFT_PANEL_WIDTH, RIGHT_PANEL_WIDTH, build_main_stylesheet
from app.widgets.experiment_tree import ExperimentTree
from app.widgets.gate_editor_dialog import GateEditorDialog
from app.widgets.plot_config_panel import PlotConfigPanel
from app.widgets.plot_grid import PlotGridWidget
from app.widgets.stepper_spinbox import StepperSpinBox


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.state = AppState()
        self._selected_gate_id: str | None = None
        self._selected_gate_cell_id: int | None = None
        self.setWindowTitle("Attune-Style Flow Cytometry Dashboard")
        self.resize(1660, 940)

        self.left_panel = PlotConfigPanel()
        self.left_panel.setObjectName("sidePanel")
        self.left_panel.setMinimumWidth(LEFT_PANEL_WIDTH)

        self.plot_grid = PlotGridWidget()
        self.grid_scroll_area = QScrollArea()
        self.grid_scroll_area.setWidget(self.plot_grid)
        self.grid_scroll_area.setWidgetResizable(False)
        self.grid_scroll_area.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.experiment_tree = ExperimentTree()

        self.rows_spin = StepperSpinBox()
        self.rows_spin.setRange(1, 12)
        self.rows_spin.setValue(self.state.grid_rows)
        self.columns_spin = StepperSpinBox()
        self.columns_spin.setRange(1, 12)
        self.columns_spin.setValue(self.state.grid_columns)

        self._build_toolbar()
        self._build_layout()
        self._connect_signals()
        self.state.set_grid_dimensions(self.state.grid_rows, self.state.grid_columns)
        self.statusBar().showMessage("Load FCS files or an ATX container to start.")

    def _build_toolbar(self) -> None:
        self.top_toolbar = QToolBar("Main")
        self.top_toolbar.setMovable(False)
        self.addToolBar(self.top_toolbar)
        self.delete_gate_action = QAction("Delete Selected Gate", self)
        self.delete_gate_action.setShortcut(QKeySequence.StandardKey.Delete)
        self.delete_gate_action.triggered.connect(self._delete_selected_gate)
        self.addAction(self.delete_gate_action)
        self._show_landing_toolbar()

    def _build_layout(self) -> None:
        experiment_panel = QWidget()
        experiment_panel.setObjectName("sidePanel")
        experiment_panel.setMinimumWidth(RIGHT_PANEL_WIDTH)
        experiment_layout = QVBoxLayout(experiment_panel)
        experiment_layout.setContentsMargins(10, 10, 10, 10)
        experiment_layout.setSpacing(8)
        experiment_layout.addWidget(QLabel("Experiments"))
        experiment_layout.addWidget(self.experiment_tree)

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

        splitter = QSplitter()
        splitter.addWidget(self.left_panel)
        splitter.addWidget(center_container)
        splitter.addWidget(experiment_panel)
        splitter.setSizes([LEFT_PANEL_WIDTH, 980, RIGHT_PANEL_WIDTH])

        self.setCentralWidget(splitter)
        self._apply_styles()

    def _connect_signals(self) -> None:
        self.experiment_tree.sample_selected.connect(self.state.set_selected_sample)
        self.experiment_tree.sample_activated.connect(self._apply_sample_to_workspace)
        self.plot_grid.cell_selected.connect(self._select_plot_cell)
        self.plot_grid.insert_requested.connect(self._insert_plot)
        self.plot_grid.gate_created.connect(self._handle_gate_created)
        self.plot_grid.gate_selected.connect(self._select_gate)
        self.plot_grid.gate_edit_requested.connect(self._edit_gate)
        self.plot_grid.gate_geometry_changed.connect(self._update_gate_geometry)
        self.plot_grid.statistics_requested.connect(self._show_statistics_for_target)
        self.plot_grid.export_requested.connect(self._export_plot_by_cell)
        self.plot_grid.clear_requested.connect(self._clear_plot_by_cell)
        self.left_panel.config_changed.connect(self._update_plot_config)
        self.left_panel.export_requested.connect(self._export_selected_plot)
        self.rows_spin.valueChanged.connect(self._on_grid_spin_changed)
        self.columns_spin.valueChanged.connect(self._on_grid_spin_changed)

        self.state.experiments_changed.connect(self._refresh_experiment_tree)
        self.state.selected_plot_changed.connect(self._sync_plot_panel)
        self.state.layout_changed.connect(self._apply_grid_dimensions)
        self.state.gates_changed.connect(self._on_gates_changed)

    def _apply_styles(self) -> None:
        self.setStyleSheet(build_main_stylesheet())

    def _open_fcs_files(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select FCS Files",
            "",
            "FCS Files (*.fcs);;All Files (*.*)",
        )
        if not file_paths:
            return

        default_name = Path(file_paths[0]).parent.name or "Imported Experiment"
        experiment_name, accepted = QInputDialog.getText(
            self,
            "Experiment Name",
            "Name this experiment:",
            text=default_name,
        )
        if not accepted:
            return

        try:
            experiment = load_fcs_files_as_experiment(file_paths, experiment_name=experiment_name)
        except FCSLoadError as exc:
            self._show_error("FCS Import Failed", str(exc))
            return

        self.state.add_experiment(experiment)
        if experiment.samples:
            self.state.set_selected_sample(experiment.id, experiment.samples[0].id)
        self.statusBar().showMessage(f"Loaded experiment '{experiment.name}'.")

    def _open_atx_files(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select ATX Files",
            "",
            "ATX Files (*.atx);;All Files (*.*)",
        )
        if not file_paths:
            return

        try:
            experiments = load_atx_files(file_paths)
        except ATXLoadError as exc:
            self._show_error(
                "ATX Import Failed",
                f"{exc}\n\nIf needed, import the experiment as multiple FCS files instead.",
            )
            return

        for experiment in experiments:
            self.state.add_experiment(experiment)
        if experiments and experiments[0].samples:
            self.state.set_selected_sample(experiments[0].id, experiments[0].samples[0].id)
        self.statusBar().showMessage("ATX import completed.")

    def _refresh_experiment_tree(self) -> None:
        self.experiment_tree.set_experiments(self.state.experiments)

    def _set_grid_preset(self, rows: int, columns: int) -> None:
        self.rows_spin.setValue(rows)
        self.columns_spin.setValue(columns)

    def _on_grid_spin_changed(self) -> None:
        self.state.set_grid_dimensions(self.rows_spin.value(), self.columns_spin.value())

    def _apply_grid_dimensions(self, rows: int, columns: int) -> None:
        self.plot_grid.set_grid_dimensions(rows, columns)

        active_ids = set(self.plot_grid.active_cell_ids())
        if self.state.current_plot_cell_id not in active_ids:
            self.state.set_selected_plot(None)
        if self._selected_gate_cell_id not in active_ids:
            self._clear_selected_gate()

        for cell_id in sorted(active_ids):
            self._render_plot(cell_id)

        self.plot_grid.set_selected_cell(self.state.current_plot_cell_id)
        self.plot_grid.set_selected_gate(self._selected_gate_cell_id, self._selected_gate_id)

    def _show_landing_toolbar(self) -> None:
        self.top_toolbar.clear()

        open_fcs_action = QAction("Open FCS Files", self)
        open_fcs_action.triggered.connect(self._open_fcs_files)
        self.top_toolbar.addAction(open_fcs_action)

        open_atx_action = QAction("Open ATX File", self)
        open_atx_action.triggered.connect(self._open_atx_files)
        self.top_toolbar.addAction(open_atx_action)

        self.top_toolbar.addSeparator()

        for label, rows, columns in (("4 Panels", 2, 2), ("6 Panels", 2, 3), ("9 Panels", 3, 3)):
            action = QAction(label, self)
            action.triggered.connect(
                lambda _checked=False, r=rows, c=columns: self._set_grid_preset(r, c)
            )
            self.top_toolbar.addAction(action)

        self.top_toolbar.addSeparator()
        workspace_action = QAction("Workspace", self)
        workspace_action.triggered.connect(self._show_workspace_toolbar)
        self.top_toolbar.addAction(workspace_action)

    def _show_workspace_toolbar(self) -> None:
        self.top_toolbar.clear()

        home_action = QAction("Back To Home", self)
        home_action.triggered.connect(self._show_landing_toolbar)
        self.top_toolbar.addAction(home_action)

        self.top_toolbar.addSeparator()

        for plot_type in (PlotType.HISTOGRAM, PlotType.DOT, PlotType.DENSITY):
            action = QAction(plot_type.value, self)
            action.triggered.connect(
                lambda _checked=False, selected_type=plot_type: self._insert_plot_into_selected_cell(selected_type)
            )
            self.top_toolbar.addAction(action)

        self.top_toolbar.addSeparator()

        for gate_type, label in (
            (GateType.HISTOGRAM, "Histogram Gate"),
            (GateType.RECTANGLE, "Rectangle Gate"),
            (GateType.ELLIPSE, "Oval Gate"),
            (GateType.POLYGON, "Polygon Gate"),
            (GateType.QUADRANT, "Quadrant Gate"),
        ):
            action = QAction(label, self)
            action.triggered.connect(
                lambda _checked=False, selected_gate=gate_type: self._begin_gate_tool(selected_gate)
            )
            self.top_toolbar.addAction(action)

        gate_color_action = QAction("Gate Color", self)
        gate_color_action.triggered.connect(self._change_selected_gate_color)
        self.top_toolbar.addAction(gate_color_action)

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

    def _select_plot_cell(self, cell_id: int) -> None:
        self.state.set_selected_plot(cell_id)
        self.plot_grid.set_selected_cell(cell_id)
        if self._selected_gate_cell_id != cell_id:
            self._clear_selected_gate()

    def _insert_plot(self, cell_id: int, plot_type: PlotType) -> None:
        sample = self.state.get_selected_sample()
        if sample is None or self.state.current_sample_ref is None:
            self._show_error("No Sample Selected", "Select a sample on the right before inserting a plot.")
            return

        experiment_id, _sample_id = self.state.current_sample_ref
        config = build_default_plot_config(cell_id, experiment_id, sample, plot_type)
        if plot_type != PlotType.HISTOGRAM and len(sample.parameters) < 2:
            self._show_error(
                "Not Enough Parameters",
                "This sample does not have enough parameters for a 2D plot.",
            )
            return

        self.state.remove_gates_for_plot(cell_id)
        self.state.upsert_plot_config(config)
        self._render_plot(cell_id)
        self._select_plot_cell(cell_id)

    def _update_plot_config(self, config: PlotConfig) -> None:
        sample = self.state.find_sample(config.experiment_id, config.sample_id)
        if sample is None:
            return

        existing = self.state.plot_configs.get(config.cell_id)

        if config.plot_type != PlotType.HISTOGRAM and not config.y_param:
            if len(sample.parameters) < 2:
                return
            config.y_param = sample.parameters[1]
        if config.plot_type == PlotType.HISTOGRAM:
            config.y_param = None

        if (
            config.source_kind == DataSourceKind.GATE
            and (
                not self.state.has_gate(config.source_gate_id)
                or self.state.gates[config.source_gate_id].plot_cell_id == config.cell_id
            )
        ):
            config.source_kind = DataSourceKind.ALL_EVENTS
            config.source_gate_id = None

        if existing is not None and self._plot_structure_changed(existing, config):
            self.state.remove_gates_for_plot(config.cell_id)

        self.state.upsert_plot_config(config)
        self._render_plot(config.cell_id)
        if self.state.current_plot_cell_id == config.cell_id:
            self._sync_plot_panel(config)

    def _apply_sample_to_workspace(self, experiment_id: str, sample_id: str) -> None:
        sample = self.state.find_sample(experiment_id, sample_id)
        if sample is None:
            return

        self.state.set_selected_sample(experiment_id, sample_id)
        active_ids = set(self.plot_grid.active_cell_ids())
        rebound_gate_map: dict[int, list[GateDefinition]] = {}
        for cell_id in sorted(active_ids):
            config = self.state.plot_configs.get(cell_id)
            if config is None:
                continue
            existing_gates = [
                gate
                for gate in self.state.gates.values()
                if gate.plot_cell_id == cell_id
            ]
            self.state.upsert_plot_config(
                self._rebind_plot_config_to_sample(config, experiment_id, sample)
            )
            rebound_gate_map[cell_id] = self._rebind_gates_to_sample(existing_gates, experiment_id, sample)

        for cell_id, rebound_gates in rebound_gate_map.items():
            self.state.replace_gates_for_plot(cell_id, rebound_gates)

        for cell_id in sorted(active_ids):
            self._render_plot(cell_id)

        if self.state.current_plot_cell_id is not None:
            self._sync_plot_panel(self.state.get_selected_plot_config())
        self.statusBar().showMessage(f"Applied sample '{sample.name}' to the visible workspace.")

    def _rebind_plot_config_to_sample(
        self,
        config: PlotConfig,
        experiment_id: str,
        sample: SampleData,
    ) -> PlotConfig:
        rebound = config.clone()
        rebound.experiment_id = experiment_id
        rebound.sample_id = sample.id
        rebound.source_kind = DataSourceKind.ALL_EVENTS
        rebound.source_gate_id = None

        if rebound.x_param not in sample.parameters:
            rebound.x_param = sample.parameters[0]

        if rebound.plot_type == PlotType.HISTOGRAM:
            rebound.y_param = None
        else:
            if len(sample.parameters) < 2:
                rebound.plot_type = PlotType.HISTOGRAM
                rebound.y_param = None
            elif rebound.y_param not in sample.parameters or rebound.y_param == rebound.x_param:
                fallback_y = next(
                    (parameter for parameter in sample.parameters if parameter != rebound.x_param),
                    sample.parameters[1],
                )
                rebound.y_param = fallback_y

        rebound.title = build_plot_title(
            sample.name,
            rebound.plot_type,
            rebound.x_param,
            rebound.y_param,
        )
        return rebound

    def _sync_plot_panel(self, config: PlotConfig | None) -> None:
        if config is None:
            self.left_panel.set_plot_context(None, None)
            return
        sample = self.state.find_sample(config.experiment_id, config.sample_id)
        source_options = self._build_source_options(
            config.experiment_id,
            config.sample_id,
            exclude_plot_cell_id=config.cell_id,
        )
        self.left_panel.set_plot_context(config, sample, source_options)

    def _render_plot(self, cell_id: int) -> None:
        config = self.state.plot_configs.get(cell_id)
        if config is None:
            self.plot_grid.set_cell_figure(cell_id, None)
            self.plot_grid.set_cell_gate_entries(cell_id, [])
            self.plot_grid.set_cell_gates(cell_id, [])
            return

        if cell_id not in self.plot_grid.cells:
            return

        sample = self.state.find_sample(config.experiment_id, config.sample_id)
        if sample is None:
            self.plot_grid.set_cell_figure(cell_id, None)
            self.plot_grid.set_cell_gate_entries(cell_id, [])
            self.plot_grid.set_cell_gates(cell_id, [])
            return

        try:
            events_frame = resolve_plot_events(sample, config, self.state.gates)
            plot_gates = self.state.gates_for_plot(cell_id)
            gate_statistics = self._build_gate_statistics(sample, config, plot_gates)
            figure = render_plot(
                sample,
                config,
                events_frame=events_frame,
                gates=plot_gates,
                gate_statistics=gate_statistics,
                selected_gate_id=self._selected_gate_id if self._selected_gate_cell_id == cell_id else None,
            )
        except Exception as exc:
            self._show_error("Plot Error", str(exc))
            return

        self.plot_grid.set_cell_figure(cell_id, figure)
        self.plot_grid.set_cell_gate_entries(cell_id, self._build_plot_gate_entries(plot_gates))
        self.plot_grid.set_cell_gates(cell_id, plot_gates)
        self.plot_grid.set_selected_gate(self._selected_gate_cell_id, self._selected_gate_id)

    def _export_plot_by_cell(self, cell_id: int) -> None:
        self._select_plot_cell(cell_id)
        self._export_selected_plot()

    def _export_selected_plot(self) -> None:
        config = self.state.get_selected_plot_config()
        if config is None:
            self._show_error("No Plot Selected", "Select a plot before exporting.")
            return

        sample = self.state.find_sample(config.experiment_id, config.sample_id)
        if sample is None:
            self._show_error("Missing Sample", "The selected plot is no longer linked to a sample.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Plot",
            f"{sample.name}_{config.cell_id + 1}.png",
            "PNG Files (*.png);;TIFF Files (*.tiff);;PDF Files (*.pdf)",
        )
        if not file_path:
            return

        events_frame = resolve_plot_events(sample, config, self.state.gates)
        plot_gates = self.state.gates_for_plot(config.cell_id)
        figure = render_plot(
            sample,
            config,
            events_frame=events_frame,
            gates=plot_gates,
            gate_statistics=self._build_gate_statistics(sample, config, plot_gates),
        )
        figure.savefig(file_path, dpi=config.export_dpi, bbox_inches="tight")
        self.statusBar().showMessage(
            f"Exported plot at {config.export_dpi} DPI to {Path(file_path).name}."
        )

    def _clear_plot_by_cell(self, cell_id: int) -> None:
        self.plot_grid.cancel_gate_interactions()
        self.state.remove_gates_for_plot(cell_id)
        self.state.remove_plot_config(cell_id)
        if self._selected_gate_cell_id == cell_id:
            self._clear_selected_gate()
        self.plot_grid.set_cell_figure(cell_id, None)
        self.plot_grid.set_cell_gate_entries(cell_id, [])
        self.plot_grid.set_cell_gates(cell_id, [])
        self.plot_grid.set_selected_cell(self.state.current_plot_cell_id)

    def _clear_selected_plot(self) -> None:
        if self.state.current_plot_cell_id is None:
            return
        self._clear_plot_by_cell(self.state.current_plot_cell_id)

    def _insert_plot_into_selected_cell(self, plot_type: PlotType) -> None:
        cell_id = self.state.current_plot_cell_id
        if cell_id is None:
            active_ids = self.plot_grid.active_cell_ids()
            if not active_ids:
                return
            cell_id = active_ids[0]
        self._insert_plot(cell_id, plot_type)

    def _begin_gate_tool(self, gate_type: GateType) -> None:
        cell_id = self.state.current_plot_cell_id
        if cell_id is None:
            self._show_error("No Plot Selected", "Select a plot before starting a gate tool.")
            return

        config = self.state.plot_configs.get(cell_id)
        if config is None:
            self._show_error("No Plot Selected", "Insert a plot into the selected cell before gating.")
            return

        if not self._is_gate_tool_valid_for_plot(gate_type, config):
            if gate_type == GateType.HISTOGRAM:
                self._show_error("Histogram Gate Unavailable", "Histogram gates can only be applied to histogram plots.")
            else:
                self._show_error("2D Gate Unavailable", "This gate requires a dot plot or density plot.")
            return

        self.plot_grid.cancel_gate_interactions()
        self._clear_selected_gate()
        self.plot_grid.set_selected_cell(cell_id)
        if not self.plot_grid.begin_gate_interaction(cell_id, gate_type):
            self._show_error("Gate Tool Unavailable", "The selected plot is not ready for gating yet.")
            return

        instruction = {
            GateType.HISTOGRAM: "Drag across the histogram to create a range gate.",
            GateType.RECTANGLE: "Drag across the plot to create a rectangular gate.",
            GateType.ELLIPSE: "Drag across the plot to create an oval gate.",
            GateType.POLYGON: "Click to place polygon points, then double-click to finish the gate.",
            GateType.QUADRANT: "Click once on the plot to place the quadrant center.",
        }[gate_type]
        self.statusBar().showMessage(instruction)

    def _handle_gate_created(self, cell_id: int, gate_type: GateType, payload: dict[str, object]) -> None:
        config = self.state.plot_configs.get(cell_id)
        if config is None:
            return

        gates = self._build_gate_definitions(config, gate_type, payload)
        if not gates:
            return

        self.state.add_gates(gates)
        created_gate = gates[0]
        self._selected_gate_id = created_gate.id
        self._selected_gate_cell_id = cell_id
        self._render_plot(cell_id)
        if self.state.current_plot_cell_id == cell_id:
            self._sync_plot_panel(config)
        self.statusBar().showMessage(
            f"Created gate source{'s' if len(gates) > 1 else ''}: {', '.join(gate.name for gate in gates)}."
        )

    def _build_gate_definitions(
        self,
        config: PlotConfig,
        gate_type: GateType,
        payload: dict[str, object],
    ) -> list[GateDefinition]:
        base_fields = {
            "experiment_id": config.experiment_id,
            "sample_id": config.sample_id,
            "plot_cell_id": config.cell_id,
            "source_kind": config.source_kind,
            "source_gate_id": config.source_gate_id,
            "x_param": config.x_param,
            "y_param": config.y_param,
        }

        if gate_type == GateType.HISTOGRAM:
            return [
                GateDefinition(
                    id=make_gate_id(),
                    name=self.state.next_gate_name("H"),
                    gate_type=gate_type,
                    x1=float(payload["x1"]),
                    x2=float(payload["x2"]),
                    **base_fields,
                )
            ]

        if gate_type in (GateType.RECTANGLE, GateType.ELLIPSE):
            prefix = "R" if gate_type == GateType.RECTANGLE else "O"
            return [
                GateDefinition(
                    id=make_gate_id(),
                    name=self.state.next_gate_name(prefix),
                    gate_type=gate_type,
                    x1=float(payload["x1"]),
                    x2=float(payload["x2"]),
                    y1=float(payload["y1"]),
                    y2=float(payload["y2"]),
                    **base_fields,
                )
            ]

        if gate_type == GateType.POLYGON:
            points = [(float(x), float(y)) for x, y in payload.get("points", [])]
            if len(points) < 3:
                return []
            return [
                GateDefinition(
                    id=make_gate_id(),
                    name=self.state.next_gate_name("P"),
                    gate_type=gate_type,
                    points=points,
                    **base_fields,
                )
            ]

        if gate_type == GateType.QUADRANT:
            x_center = float(payload["x1"])
            y_center = float(payload["y1"])
            set_name = self.state.next_gate_name("Q")
            return [
                GateDefinition(
                    id=make_gate_id(),
                    name=f"{set_name}-{quadrant_name}",
                    gate_type=gate_type,
                    x1=x_center,
                    y1=y_center,
                    metadata={"quadrant": quadrant_name, "quadrant_set": set_name},
                    **base_fields,
                )
                for quadrant_name in ("Q1", "Q2", "Q3", "Q4")
            ]

        return []

    def _build_source_options(
        self,
        experiment_id: str,
        sample_id: str,
        exclude_plot_cell_id: int | None = None,
    ) -> list[tuple[DataSourceKind, str | None, str]]:
        options: list[tuple[DataSourceKind, str | None, str]] = [
            (DataSourceKind.ALL_EVENTS, None, "All Events")
        ]
        for gate in self.state.gates_for_sample(experiment_id, sample_id):
            if exclude_plot_cell_id is not None and gate.plot_cell_id == exclude_plot_cell_id:
                continue
            options.append((DataSourceKind.GATE, gate.id, gate_source_label(gate)))
        return options

    def _plot_structure_changed(self, previous: PlotConfig, current: PlotConfig) -> bool:
        return any(
            [
                previous.plot_type != current.plot_type,
                previous.experiment_id != current.experiment_id,
                previous.sample_id != current.sample_id,
                previous.x_param != current.x_param,
                previous.y_param != current.y_param,
                previous.source_kind != current.source_kind,
                previous.source_gate_id != current.source_gate_id,
            ]
        )

    def _is_gate_tool_valid_for_plot(self, gate_type: GateType, config: PlotConfig) -> bool:
        if gate_type == GateType.HISTOGRAM:
            return config.plot_type == PlotType.HISTOGRAM
        return config.plot_type in {PlotType.DOT, PlotType.DENSITY}

    def _on_gates_changed(self) -> None:
        for config in list(self.state.plot_configs.values()):
            if (
                config.source_kind == DataSourceKind.GATE
                and (
                    not self.state.has_gate(config.source_gate_id)
                    or self.state.gates[config.source_gate_id].plot_cell_id == config.cell_id
                )
            ):
                rebound = config.clone()
                rebound.source_kind = DataSourceKind.ALL_EVENTS
                rebound.source_gate_id = None
                self.state.upsert_plot_config(rebound)

        if self._selected_gate_id and self._selected_gate_id not in self.state.gates:
            self._clear_selected_gate()

        for cell_id in self.plot_grid.active_cell_ids():
            self._render_plot(cell_id)

        self._sync_plot_panel(self.state.get_selected_plot_config())

    def _build_gate_statistics(
        self,
        sample: SampleData,
        config: PlotConfig,
        gates: list[GateDefinition],
    ) -> dict[str, PopulationStatistics]:
        statistics: dict[str, PopulationStatistics] = {}
        total_population = len(sample.events)
        for gate in gates:
            gate_frame = resolve_gate_events(sample, gate, self.state.gates)
            statistics[gate.id] = build_population_statistics(
                gate_frame,
                gate.x_param,
                gate.y_param,
                total_population,
                gate.name,
            )
        return statistics

    def _build_plot_gate_entries(self, gates: list[GateDefinition]) -> list[tuple[str, str]]:
        return [(gate.id, gate.name) for gate in sorted(gates, key=lambda item: item.name)]

    def _edit_gate(self, cell_id: int, gate_id: str) -> None:
        _ = cell_id
        gate = self.state.gates.get(gate_id)
        if gate is None:
            return

        self._selected_gate_id = gate.id
        self._selected_gate_cell_id = gate.plot_cell_id

        dialog = GateEditorDialog(gate, self)
        if not dialog.exec():
            return

        payload = dialog.gate_payload()
        if gate.gate_type == GateType.QUADRANT:
            quadrant_set = str(gate.metadata.get("quadrant_set", gate.name))
            updated_gates: list[GateDefinition] = []
            for existing_gate in self.state.gates.values():
                if (
                    existing_gate.gate_type == GateType.QUADRANT
                    and str(existing_gate.metadata.get("quadrant_set", existing_gate.name)) == quadrant_set
                ):
                    updated_gates.append(
                        GateDefinition(
                            id=existing_gate.id,
                            name=existing_gate.name,
                            gate_type=existing_gate.gate_type,
                            experiment_id=existing_gate.experiment_id,
                            sample_id=existing_gate.sample_id,
                            plot_cell_id=existing_gate.plot_cell_id,
                            source_kind=existing_gate.source_kind,
                            source_gate_id=existing_gate.source_gate_id,
                            x_param=existing_gate.x_param,
                            y_param=existing_gate.y_param,
                            x1=float(payload["x1"]),
                            y1=float(payload["y1"]),
                            metadata=dict(existing_gate.metadata),
                        )
                    )
            self.state.update_gates(updated_gates)
            return

        updated_gate = GateDefinition(
            id=gate.id,
            name=str(payload.get("name", gate.name)),
            gate_type=gate.gate_type,
            experiment_id=gate.experiment_id,
            sample_id=gate.sample_id,
            plot_cell_id=gate.plot_cell_id,
            source_kind=gate.source_kind,
            source_gate_id=gate.source_gate_id,
            x_param=gate.x_param,
            y_param=gate.y_param,
            x1=float(payload["x1"]) if "x1" in payload else gate.x1,
            x2=float(payload["x2"]) if "x2" in payload else gate.x2,
            y1=float(payload["y1"]) if "y1" in payload else gate.y1,
            y2=float(payload["y2"]) if "y2" in payload else gate.y2,
            color=gate.color,
            points=payload.get("points", gate.points),
            metadata=dict(gate.metadata),
        )
        self.state.update_gate(updated_gate)

    def _select_gate(self, cell_id: int, gate_id: str | None) -> None:
        self._selected_gate_cell_id = cell_id if gate_id else None
        self._selected_gate_id = gate_id
        self.plot_grid.set_selected_gate(self._selected_gate_cell_id, self._selected_gate_id)
        self._render_plot(cell_id)

    def _update_gate_geometry(self, cell_id: int, gate_id: str, payload: dict[str, object]) -> None:
        gate = self.state.gates.get(gate_id)
        if gate is None:
            return

        if gate.gate_type == GateType.QUADRANT:
            quadrant_set = str(gate.metadata.get("quadrant_set", gate.name))
            updated_gates: list[GateDefinition] = []
            for existing_gate in self.state.gates.values():
                if (
                    existing_gate.gate_type == GateType.QUADRANT
                    and str(existing_gate.metadata.get("quadrant_set", existing_gate.name)) == quadrant_set
                ):
                    updated_gates.append(
                        GateDefinition(
                            id=existing_gate.id,
                            name=existing_gate.name,
                            gate_type=existing_gate.gate_type,
                            experiment_id=existing_gate.experiment_id,
                            sample_id=existing_gate.sample_id,
                            plot_cell_id=existing_gate.plot_cell_id,
                            source_kind=existing_gate.source_kind,
                            source_gate_id=existing_gate.source_gate_id,
                            x_param=existing_gate.x_param,
                            y_param=existing_gate.y_param,
                            x1=float(payload.get("x1", existing_gate.x1 or 0.0)),
                            y1=float(payload.get("y1", existing_gate.y1 or 0.0)),
                            color=existing_gate.color,
                            metadata=dict(existing_gate.metadata),
                        )
                    )
            self.state.update_gates(updated_gates)
            self._selected_gate_cell_id = cell_id
            return

        updated_gate = GateDefinition(
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
            x1=float(payload.get("x1", gate.x1 or 0.0)) if gate.x1 is not None or "x1" in payload else None,
            x2=float(payload.get("x2", gate.x2 or 0.0)) if gate.x2 is not None or "x2" in payload else None,
            y1=float(payload.get("y1", gate.y1 or 0.0)) if gate.y1 is not None or "y1" in payload else None,
            y2=float(payload.get("y2", gate.y2 or 0.0)) if gate.y2 is not None or "y2" in payload else None,
            color=gate.color,
            points=list(payload.get("points", gate.points)),
            metadata=dict(gate.metadata),
        )
        self.state.update_gate(updated_gate)
        self._selected_gate_cell_id = cell_id

    def _change_selected_gate_color(self) -> None:
        cell_id = self.state.current_plot_cell_id
        if cell_id is None:
            self._show_error("No Plot Selected", "Select a plot before changing a gate color.")
            return

        plot_gates = self.state.gates_for_plot(cell_id)
        if not plot_gates:
            self._show_error("No Gates Available", "Create a gate on the selected plot first.")
            return

        selected_gate = None
        if len(plot_gates) == 1:
            selected_gate = plot_gates[0]
        else:
            gate_names = [gate.name for gate in sorted(plot_gates, key=lambda item: item.name)]
            gate_name, accepted = QInputDialog.getItem(
                self,
                "Select Gate",
                "Choose a gate to recolor:",
                gate_names,
                editable=False,
            )
            if not accepted:
                return
            selected_gate = next((gate for gate in plot_gates if gate.name == gate_name), None)

        if selected_gate is None:
            return

        self._selected_gate_id = selected_gate.id
        self._selected_gate_cell_id = selected_gate.plot_cell_id

        color = QColorDialog.getColor(parent=self, title=f"Gate Color - {selected_gate.name}")
        if not color.isValid():
            return

        color_name = color.name()
        if selected_gate.gate_type == GateType.QUADRANT:
            quadrant_set = str(selected_gate.metadata.get("quadrant_set", selected_gate.name))
            updated = []
            for gate in self.state.gates.values():
                if (
                    gate.gate_type == GateType.QUADRANT
                    and str(gate.metadata.get("quadrant_set", gate.name)) == quadrant_set
                ):
                    updated.append(self._copy_gate_with_color(gate, color_name))
            self.state.update_gates(updated)
        else:
            self.state.update_gate(self._copy_gate_with_color(selected_gate, color_name))

        self.statusBar().showMessage(f"Updated gate color for {selected_gate.name}.")

    def _copy_gate_with_color(self, gate: GateDefinition, color: str) -> GateDefinition:
        return GateDefinition(
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
            x1=gate.x1,
            x2=gate.x2,
            y1=gate.y1,
            y2=gate.y2,
            color=color,
            points=list(gate.points),
            metadata=dict(gate.metadata),
        )

    def _rebind_gates_to_sample(
        self,
        gates: list[GateDefinition],
        experiment_id: str,
        sample: SampleData,
    ) -> list[GateDefinition]:
        rebound: list[GateDefinition] = []
        for gate in gates:
            if gate.x_param not in sample.parameters:
                continue
            if gate.gate_type != GateType.HISTOGRAM and gate.y_param and gate.y_param not in sample.parameters:
                continue
            rebound.append(
                GateDefinition(
                    id=gate.id,
                    name=gate.name,
                    gate_type=gate.gate_type,
                    experiment_id=experiment_id,
                    sample_id=sample.id,
                    plot_cell_id=gate.plot_cell_id,
                    source_kind=gate.source_kind,
                    source_gate_id=gate.source_gate_id,
                    x_param=gate.x_param,
                    y_param=gate.y_param,
                    x1=gate.x1,
                    x2=gate.x2,
                    y1=gate.y1,
                    y2=gate.y2,
                    color=gate.color,
                    points=list(gate.points),
                    metadata=dict(gate.metadata),
                )
            )
        return rebound

    def _clear_selected_gate(self) -> None:
        self._selected_gate_id = None
        self._selected_gate_cell_id = None
        self.plot_grid.set_selected_gate(None, None)

    def _delete_selected_gate(self) -> None:
        if not self._selected_gate_id:
            return
        gate = self.state.gates.get(self._selected_gate_id)
        if gate is None:
            self._clear_selected_gate()
            return

        if gate.gate_type == GateType.QUADRANT:
            quadrant_set = str(gate.metadata.get("quadrant_set", gate.name))
            gate_ids = [
                item.id
                for item in self.state.gates.values()
                if item.gate_type == GateType.QUADRANT
                and str(item.metadata.get("quadrant_set", item.name)) == quadrant_set
            ]
            self.state.remove_gates(gate_ids)
        else:
            self.state.remove_gate(gate.id)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete and self._selected_gate_id:
            self._delete_selected_gate()
            event.accept()
            return
        super().keyPressEvent(event)

    def _show_statistics_for_target(self, cell_id: int, gate_id: str | None) -> None:
        config = self.state.plot_configs.get(cell_id)
        if config is None:
            return

        sample = self.state.find_sample(config.experiment_id, config.sample_id)
        if sample is None:
            return

        total_population = len(sample.events)
        if gate_id is None:
            frame = resolve_plot_events(sample, config, self.state.gates)
            stats = build_population_statistics(
                frame,
                config.x_param,
                config.y_param,
                total_population,
                "Current Population",
            )
            title = "Population Statistics"
        else:
            gate = self.state.gates.get(gate_id)
            if gate is None:
                return
            frame = resolve_gate_events(sample, gate, self.state.gates)
            stats = build_population_statistics(
                frame,
                gate.x_param,
                gate.y_param,
                total_population,
                gate.name,
            )
            title = f"Gate Statistics - {gate.name}"

        x_param = config.x_param if gate_id is None else gate.x_param
        y_param = config.y_param if gate_id is None else gate.y_param
        self._show_statistics_message(title, stats, x_param, y_param)

    def _show_statistics_message(
        self,
        title: str,
        stats: PopulationStatistics,
        x_param: str,
        y_param: str | None,
    ) -> None:
        lines = [
            f"Population: {stats.label}",
            f"Count: {stats.count}",
            f"Percentage of total: {stats.percentage_of_total:.2f}%",
            f"Mean {x_param}: {self._format_stat(stats.mean_x)}",
            f"Median {x_param}: {self._format_stat(stats.median_x)}",
        ]
        if y_param:
            lines.extend(
                [
                    f"Mean {y_param}: {self._format_stat(stats.mean_y)}",
                    f"Median {y_param}: {self._format_stat(stats.median_y)}",
                ]
            )
        QMessageBox.information(self, title, "\n".join(lines))

    def _format_stat(self, value: float | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:.4f}"

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)


def run() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
