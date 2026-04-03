from __future__ import annotations

from matplotlib.figure import Figure
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QSizePolicy, QWidget

from app.models import GateType
from app.theme import PLOT_CELL_HEIGHT, PLOT_CELL_WIDTH
from app.widgets.plot_cell import PlotCell


class PlotGridWidget(QWidget):
    cell_selected = Signal(int)
    insert_requested = Signal(int, object)
    send_to_overlay_requested = Signal(int)
    export_requested = Signal(int)
    clear_requested = Signal(int)
    gate_created = Signal(int, object, object)
    gate_selected = Signal(int, object)
    gate_edit_requested = Signal(int, str)
    gate_geometry_changed = Signal(int, str, object)
    statistics_requested = Signal(int, object)

    def __init__(
        self,
        allowed_plot_types=None,
        show_send_to_overlay: bool = False,
    ) -> None:
        super().__init__()
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(8)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._allowed_plot_types = allowed_plot_types
        self._show_send_to_overlay = show_send_to_overlay
        self.cells: dict[int, PlotCell] = {}
        self.rows = 2
        self.columns = 3
        self._rebuild_grid()

    def set_grid_dimensions(self, rows: int, columns: int) -> None:
        rows = max(1, rows)
        columns = max(1, columns)
        if rows == self.rows and columns == self.columns:
            return
        self.rows = rows
        self.columns = columns
        self._rebuild_grid()

    def set_selected_cell(self, selected_cell_id: int | None) -> None:
        for cell_id, cell in self.cells.items():
            cell.set_selected(cell_id == selected_cell_id)

    def set_cell_figure(self, cell_id: int, figure: Figure | None) -> None:
        if cell_id in self.cells:
            self.cells[cell_id].set_figure(figure)

    def set_cell_gate_entries(self, cell_id: int, gate_entries: list[tuple[str, str]]) -> None:
        if cell_id in self.cells:
            self.cells[cell_id].set_gate_entries(gate_entries)

    def set_cell_gates(self, cell_id: int, gates) -> None:
        if cell_id in self.cells:
            self.cells[cell_id].set_gates(gates)

    def set_selected_gate(self, cell_id: int | None, gate_id: str | None) -> None:
        for current_cell_id, cell in self.cells.items():
            cell.set_selected_gate_id(gate_id if current_cell_id == cell_id else None)

    def active_cell_ids(self) -> list[int]:
        return sorted(self.cells.keys())

    def _rebuild_grid(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        self.cells.clear()
        total_cells = self.rows * self.columns
        for cell_id in range(total_cells):
            cell = PlotCell(
                cell_id,
                allowed_plot_types=self._allowed_plot_types,
                show_send_to_overlay=self._show_send_to_overlay,
            )
            cell.selected.connect(self.cell_selected.emit)
            cell.insert_requested.connect(self.insert_requested.emit)
            cell.send_to_overlay_requested.connect(self.send_to_overlay_requested.emit)
            cell.export_requested.connect(self.export_requested.emit)
            cell.clear_requested.connect(self.clear_requested.emit)
            cell.gate_created.connect(self.gate_created.emit)
            cell.gate_selected.connect(self.gate_selected.emit)
            cell.gate_edit_requested.connect(self.gate_edit_requested.emit)
            cell.gate_geometry_changed.connect(self.gate_geometry_changed.emit)
            cell.statistics_requested.connect(self.statistics_requested.emit)
            self.cells[cell_id] = cell
            self._layout.addWidget(cell, cell_id // self.columns, cell_id % self.columns)

        total_width = 10 + 10 + (self.columns * PLOT_CELL_WIDTH) + ((self.columns - 1) * 8)
        total_height = 10 + 10 + (self.rows * PLOT_CELL_HEIGHT) + ((self.rows - 1) * 8)
        self.setMinimumSize(total_width, total_height)
        self.resize(total_width, total_height)
        self.adjustSize()
        self.updateGeometry()

    def begin_gate_interaction(self, cell_id: int, gate_type: GateType) -> bool:
        cell = self.cells.get(cell_id)
        if cell is None:
            return False
        return cell.begin_gate_interaction(gate_type)

    def cancel_gate_interactions(self) -> None:
        for cell in self.cells.values():
            cell.cancel_gate_interaction()
