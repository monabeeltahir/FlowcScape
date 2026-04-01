from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFrame, QLabel, QMenu, QVBoxLayout

from app.models import PlotType
from app.theme import PLOT_CELL_HEIGHT, PLOT_CELL_WIDTH


class PlotCell(QFrame):
    selected = Signal(int)
    insert_requested = Signal(int, object)
    export_requested = Signal(int)
    clear_requested = Signal(int)

    def __init__(self, cell_id: int) -> None:
        super().__init__()
        self.cell_id = cell_id
        self._canvas: FigureCanvasQTAgg | None = None
        self._placeholder = QLabel("Right-click to insert a plot")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.addWidget(self._placeholder)

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
        self.setObjectName("plotCell")
        self.setFixedSize(PLOT_CELL_WIDTH, PLOT_CELL_HEIGHT)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        border = "#4a90e2" if selected else "#cfd6de"
        self.setStyleSheet(
            f"QFrame#plotCell {{ background: white; border: 2px solid {border}; }}"
        )

    def set_figure(self, figure: Figure | None) -> None:
        self._clear_canvas()
        if figure is None:
            self._placeholder.show()
            return

        self._placeholder.hide()
        self._canvas = FigureCanvasQTAgg(figure)
        self._canvas.mpl_connect("button_press_event", self._on_canvas_clicked)
        self._layout.addWidget(self._canvas)

    def _clear_canvas(self) -> None:
        if self._canvas is None:
            return
        self._layout.removeWidget(self._canvas)
        self._canvas.setParent(None)
        self._canvas.deleteLater()
        self._canvas = None

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self.cell_id)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        self.selected.emit(self.cell_id)

        menu = QMenu(self)
        insert_menu = menu.addMenu("Insert")

        histogram_action = QAction(PlotType.HISTOGRAM.value, self)
        histogram_action.triggered.connect(
            lambda: self.insert_requested.emit(self.cell_id, PlotType.HISTOGRAM)
        )
        insert_menu.addAction(histogram_action)

        dot_action = QAction(PlotType.DOT.value, self)
        dot_action.triggered.connect(
            lambda: self.insert_requested.emit(self.cell_id, PlotType.DOT)
        )
        insert_menu.addAction(dot_action)

        density_action = QAction(PlotType.DENSITY.value, self)
        density_action.triggered.connect(
            lambda: self.insert_requested.emit(self.cell_id, PlotType.DENSITY)
        )
        insert_menu.addAction(density_action)

        export_action = QAction("Export Plot", self)
        export_action.triggered.connect(lambda: self.export_requested.emit(self.cell_id))
        menu.addAction(export_action)

        clear_action = QAction("Clear Plot", self)
        clear_action.triggered.connect(lambda: self.clear_requested.emit(self.cell_id))
        menu.addAction(clear_action)

        menu.exec(event.globalPos())

    def _on_canvas_clicked(self, _event) -> None:
        self.selected.emit(self.cell_id)
