from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
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

from app.models import PlotConfig, PlotType, SampleData
from app.plotting.config import build_default_plot_config, build_plot_title
from app.plotting.renderer import render_plot
from app.services.atx_loader import ATXLoadError
from app.services.experiment_loader import load_atx_files, load_fcs_files_as_experiment
from app.services.fcs_loader import FCSLoadError
from app.state import AppState
from app.theme import LEFT_PANEL_WIDTH, RIGHT_PANEL_WIDTH, build_main_stylesheet
from app.widgets.experiment_tree import ExperimentTree
from app.widgets.plot_config_panel import PlotConfigPanel
from app.widgets.plot_grid import PlotGridWidget
from app.widgets.stepper_spinbox import StepperSpinBox


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.state = AppState()
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
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_fcs_action = QAction("Open FCS Files", self)
        open_fcs_action.triggered.connect(self._open_fcs_files)
        toolbar.addAction(open_fcs_action)

        open_atx_action = QAction("Open ATX File", self)
        open_atx_action.triggered.connect(self._open_atx_files)
        toolbar.addAction(open_atx_action)

        toolbar.addSeparator()

        preset_actions = [
            ("4 Panels", 2, 2),
            ("6 Panels", 2, 3),
            ("9 Panels", 3, 3),
        ]
        for label, rows, columns in preset_actions:
            action = QAction(label, self)
            action.triggered.connect(
                lambda _checked=False, r=rows, c=columns: self._set_grid_preset(r, c)
            )
            toolbar.addAction(action)

        toolbar.addSeparator()

        export_action = QAction("Export Selected Plot", self)
        export_action.triggered.connect(self._export_selected_plot)
        toolbar.addAction(export_action)

        clear_action = QAction("Clear Selected Plot", self)
        clear_action.triggered.connect(self._clear_selected_plot)
        toolbar.addAction(clear_action)

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
        self.plot_grid.export_requested.connect(self._export_plot_by_cell)
        self.plot_grid.clear_requested.connect(self._clear_plot_by_cell)
        self.left_panel.config_changed.connect(self._update_plot_config)
        self.left_panel.export_requested.connect(self._export_selected_plot)
        self.rows_spin.valueChanged.connect(self._on_grid_spin_changed)
        self.columns_spin.valueChanged.connect(self._on_grid_spin_changed)

        self.state.experiments_changed.connect(self._refresh_experiment_tree)
        self.state.selected_plot_changed.connect(self._sync_plot_panel)
        self.state.layout_changed.connect(self._apply_grid_dimensions)

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

        for cell_id in sorted(active_ids):
            self._render_plot(cell_id)

        self.plot_grid.set_selected_cell(self.state.current_plot_cell_id)

    def _select_plot_cell(self, cell_id: int) -> None:
        self.state.set_selected_plot(cell_id)
        self.plot_grid.set_selected_cell(cell_id)

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

        self.state.upsert_plot_config(config)
        self._render_plot(cell_id)
        self._select_plot_cell(cell_id)

    def _update_plot_config(self, config: PlotConfig) -> None:
        sample = self.state.find_sample(config.experiment_id, config.sample_id)
        if sample is None:
            return
        if config.plot_type != PlotType.HISTOGRAM and not config.y_param:
            if len(sample.parameters) < 2:
                return
            config.y_param = sample.parameters[1]
        self.state.upsert_plot_config(config)
        self._render_plot(config.cell_id)

    def _apply_sample_to_workspace(self, experiment_id: str, sample_id: str) -> None:
        sample = self.state.find_sample(experiment_id, sample_id)
        if sample is None:
            return

        self.state.set_selected_sample(experiment_id, sample_id)
        active_ids = set(self.plot_grid.active_cell_ids())
        for cell_id in sorted(active_ids):
            config = self.state.plot_configs.get(cell_id)
            if config is None:
                continue
            self.state.upsert_plot_config(
                self._rebind_plot_config_to_sample(config, experiment_id, sample)
            )
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
        self.left_panel.set_plot_context(config, sample)

    def _render_plot(self, cell_id: int) -> None:
        config = self.state.plot_configs.get(cell_id)
        if config is None:
            self.plot_grid.set_cell_figure(cell_id, None)
            return

        if cell_id not in self.plot_grid.cells:
            return

        sample = self.state.find_sample(config.experiment_id, config.sample_id)
        if sample is None:
            self.plot_grid.set_cell_figure(cell_id, None)
            return

        try:
            figure = render_plot(sample, config)
        except Exception as exc:
            self._show_error("Plot Error", str(exc))
            return

        self.plot_grid.set_cell_figure(cell_id, figure)

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

        figure = render_plot(sample, config)
        figure.savefig(file_path, dpi=config.export_dpi, bbox_inches="tight")
        self.statusBar().showMessage(
            f"Exported plot at {config.export_dpi} DPI to {Path(file_path).name}."
        )

    def _clear_plot_by_cell(self, cell_id: int) -> None:
        self.state.remove_plot_config(cell_id)
        self.plot_grid.set_cell_figure(cell_id, None)
        self.plot_grid.set_selected_cell(self.state.current_plot_cell_id)

    def _clear_selected_plot(self) -> None:
        if self.state.current_plot_cell_id is None:
            return
        self._clear_plot_by_cell(self.state.current_plot_cell_id)

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)


def run() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
