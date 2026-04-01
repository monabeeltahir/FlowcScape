from __future__ import annotations

from matplotlib.path import Path
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.widgets import EllipseSelector, PolygonSelector, RectangleSelector, SpanSelector
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFrame, QLabel, QMenu, QVBoxLayout

from app.models import GateDefinition, GateType, PlotType
from app.theme import PLOT_CELL_HEIGHT, PLOT_CELL_WIDTH

LIVE_GATE_EDGE_COLOR = "#ff2d20"
LIVE_GATE_FILL_COLOR = "#fbff00"
LIVE_GATE_LINE_COLOR = "#ff2d20"


class PlotCell(QFrame):
    selected = Signal(int)
    insert_requested = Signal(int, object)
    export_requested = Signal(int)
    clear_requested = Signal(int)
    gate_created = Signal(int, object, object)
    gate_selected = Signal(int, object)
    gate_edit_requested = Signal(int, str)
    gate_geometry_changed = Signal(int, str, object)
    statistics_requested = Signal(int, object)

    def __init__(self, cell_id: int) -> None:
        super().__init__()
        self.cell_id = cell_id
        self._canvas: FigureCanvasQTAgg | None = None
        self._active_selector = None
        self._quadrant_connection_id: int | None = None
        self._gate_entries: list[tuple[str, str]] = []
        self._gates: list[GateDefinition] = []
        self._selected_gate_id: str | None = None
        self._dragging_gate_id: str | None = None
        self._drag_handle: object | None = None
        self._drag_origin: tuple[float, float] | None = None
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
        self.cancel_gate_interaction()
        self._clear_canvas()
        if figure is None:
            self._placeholder.show()
            return

        self._placeholder.hide()
        self._canvas = FigureCanvasQTAgg(figure)
        self._canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._canvas.customContextMenuRequested.connect(self._show_context_menu)
        self._canvas.mpl_connect("button_press_event", self._on_canvas_pressed)
        self._canvas.mpl_connect("button_release_event", self._on_canvas_released)
        self._layout.addWidget(self._canvas)

    def set_gate_entries(self, gate_entries: list[tuple[str, str]]) -> None:
        self._gate_entries = gate_entries

    def set_gates(self, gates: list[GateDefinition]) -> None:
        self._gates = gates

    def set_selected_gate_id(self, gate_id: str | None) -> None:
        self._selected_gate_id = gate_id

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
        self._show_context_menu(event.pos(), global_pos=event.globalPos())

    def _show_context_menu(self, pos, global_pos=None) -> None:
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

        if self._gate_entries:
            edit_menu = menu.addMenu("Edit Gate")
            for gate_id, gate_label in self._gate_entries:
                action = QAction(gate_label, self)
                action.triggered.connect(
                    lambda _checked=False, selected_gate_id=gate_id: self.gate_edit_requested.emit(
                        self.cell_id,
                        selected_gate_id,
                    )
                )
                edit_menu.addAction(action)

        statistics_menu = menu.addMenu("Statistics")
        current_population_action = QAction("Current Population", self)
        current_population_action.triggered.connect(
            lambda: self.statistics_requested.emit(self.cell_id, None)
        )
        statistics_menu.addAction(current_population_action)
        if self._gate_entries:
            statistics_menu.addSeparator()
            for gate_id, gate_label in self._gate_entries:
                action = QAction(gate_label, self)
                action.triggered.connect(
                    lambda _checked=False, selected_gate_id=gate_id: self.statistics_requested.emit(
                        self.cell_id,
                        selected_gate_id,
                    )
                )
                statistics_menu.addAction(action)

        export_action = QAction("Export Plot", self)
        export_action.triggered.connect(lambda: self.export_requested.emit(self.cell_id))
        menu.addAction(export_action)

        clear_action = QAction("Clear Plot", self)
        clear_action.triggered.connect(lambda: self.clear_requested.emit(self.cell_id))
        menu.addAction(clear_action)

        menu.exec(global_pos or self.mapToGlobal(pos))

    def _on_canvas_pressed(self, event) -> None:
        self.selected.emit(self.cell_id)
        button_value = getattr(event.button, "value", event.button)
        if (
            event.inaxes is None
            or button_value != 1
            or event.xdata is None
            or event.ydata is None
            or self._active_selector is not None
        ):
            return

        selected_gate = self._find_gate(self._selected_gate_id)
        if selected_gate is not None:
            handle = self._handle_at_event(event, selected_gate)
            if handle is not None:
                self._dragging_gate_id = selected_gate.id
                self._drag_handle = handle
                self._drag_origin = (float(event.xdata), float(event.ydata))
                return

            if self._gate_matches_event(event, selected_gate):
                self._dragging_gate_id = selected_gate.id
                self._drag_handle = {"kind": "move"}
                self._drag_origin = (float(event.xdata), float(event.ydata))
                return

        gate = self._gate_at_event(event)
        if gate is not None:
            self._selected_gate_id = gate.id
            self.gate_selected.emit(self.cell_id, gate.id)
            return

        self._selected_gate_id = None
        self.gate_selected.emit(self.cell_id, None)

    def _on_canvas_released(self, event) -> None:
        if self._dragging_gate_id is None or event.inaxes is None:
            self._dragging_gate_id = None
            self._drag_handle = None
            self._drag_origin = None
            return

        if event.xdata is None or event.ydata is None:
            self._dragging_gate_id = None
            self._drag_handle = None
            self._drag_origin = None
            return

        gate = self._find_gate(self._dragging_gate_id)
        if gate is None:
            self._dragging_gate_id = None
            self._drag_handle = None
            self._drag_origin = None
            return

        payload = self._updated_payload_for_drag(gate, self._drag_handle, float(event.xdata), float(event.ydata))
        self._dragging_gate_id = None
        self._drag_handle = None
        self._drag_origin = None
        if payload is not None:
            self.gate_geometry_changed.emit(self.cell_id, gate.id, payload)

    def begin_gate_interaction(self, gate_type: GateType) -> bool:
        if self._canvas is None or not self._canvas.figure.axes:
            return False

        self.cancel_gate_interaction()
        axis = self._canvas.figure.axes[0]

        if gate_type == GateType.HISTOGRAM:
            self._active_selector = SpanSelector(
                axis,
                lambda xmin, xmax: self._finish_gate(
                    gate_type,
                    {"x1": float(xmin), "x2": float(xmax)},
                ),
                "horizontal",
                useblit=False,
                props={"facecolor": LIVE_GATE_FILL_COLOR, "edgecolor": LIVE_GATE_EDGE_COLOR, "alpha": 0.32},
                interactive=False,
            )
        elif gate_type == GateType.RECTANGLE:
            self._active_selector = RectangleSelector(
                axis,
                lambda eclick, erelease: self._finish_gate(
                    gate_type,
                    {
                        "x1": float(eclick.xdata),
                        "x2": float(erelease.xdata),
                        "y1": float(eclick.ydata),
                        "y2": float(erelease.ydata),
                    },
                ),
                useblit=False,
                props={
                    "edgecolor": LIVE_GATE_EDGE_COLOR,
                    "facecolor": LIVE_GATE_FILL_COLOR,
                    "alpha": 0.24,
                    "linewidth": 2.0,
                },
                interactive=False,
            )
        elif gate_type == GateType.ELLIPSE:
            self._active_selector = EllipseSelector(
                axis,
                lambda eclick, erelease: self._finish_gate(
                    gate_type,
                    {
                        "x1": float(eclick.xdata),
                        "x2": float(erelease.xdata),
                        "y1": float(eclick.ydata),
                        "y2": float(erelease.ydata),
                    },
                ),
                useblit=False,
                props={
                    "edgecolor": LIVE_GATE_EDGE_COLOR,
                    "facecolor": LIVE_GATE_FILL_COLOR,
                    "alpha": 0.24,
                    "linewidth": 2.0,
                },
                interactive=False,
            )
        elif gate_type == GateType.POLYGON:
            self._active_selector = PolygonSelector(
                axis,
                lambda verts: self._finish_gate(
                    gate_type,
                    {"points": [(float(x), float(y)) for x, y in verts]},
                ),
                useblit=False,
                props={"color": LIVE_GATE_LINE_COLOR, "alpha": 1.0, "linewidth": 2.4},
            )
        elif gate_type == GateType.QUADRANT:
            self._quadrant_connection_id = self._canvas.mpl_connect(
                "button_press_event",
                lambda event: self._handle_quadrant_click(event, gate_type),
            )
        else:
            return False

        self._canvas.draw_idle()
        return True

    def cancel_gate_interaction(self) -> None:
        if self._active_selector is not None:
            self._active_selector.set_active(False)
            self._active_selector = None
        if self._canvas is not None and self._quadrant_connection_id is not None:
            self._canvas.mpl_disconnect(self._quadrant_connection_id)
        self._quadrant_connection_id = None
        self._dragging_gate_id = None
        self._drag_handle = None
        self._drag_origin = None

    def _handle_quadrant_click(self, event, gate_type: GateType) -> None:
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return
        self._finish_gate(
            gate_type,
            {"x1": float(event.xdata), "y1": float(event.ydata)},
        )

    def _finish_gate(self, gate_type: GateType, payload: dict[str, object]) -> None:
        self.cancel_gate_interaction()
        self.gate_created.emit(self.cell_id, gate_type, payload)

    def _gate_at_event(self, event) -> GateDefinition | None:
        if event.inaxes is None or event.x is None or event.y is None:
            return None

        for gate in sorted(self._gates, key=lambda item: item.name):
            if gate.gate_type == GateType.HISTOGRAM and self._hit_histogram_gate(event, gate):
                return gate
            if gate.gate_type == GateType.RECTANGLE and self._hit_rectangle_gate(event, gate):
                return gate
            if gate.gate_type == GateType.ELLIPSE and self._hit_ellipse_gate(event, gate):
                return gate
            if gate.gate_type == GateType.POLYGON and self._hit_polygon_gate(event, gate):
                return gate
            if gate.gate_type == GateType.QUADRANT and self._hit_quadrant_gate(event, gate):
                return gate
        return None

    def _find_gate(self, gate_id: str | None) -> GateDefinition | None:
        if not gate_id:
            return None
        return next((gate for gate in self._gates if gate.id == gate_id), None)

    def _gate_matches_event(self, event, gate: GateDefinition) -> bool:
        if gate.gate_type == GateType.HISTOGRAM:
            return self._hit_histogram_gate(event, gate)
        if gate.gate_type == GateType.RECTANGLE:
            return self._hit_rectangle_gate(event, gate)
        if gate.gate_type == GateType.ELLIPSE:
            return self._hit_ellipse_gate(event, gate)
        if gate.gate_type == GateType.POLYGON:
            return self._hit_polygon_gate(event, gate)
        if gate.gate_type == GateType.QUADRANT:
            return self._hit_quadrant_gate(event, gate)
        return False

    def _handle_at_event(self, event, gate: GateDefinition):
        axis = event.inaxes
        if axis is None or event.x is None or event.y is None:
            return None
        event_x = float(event.x)
        event_y = float(event.y)
        tolerance = 8.0
        for handle in self._gate_handles(gate):
            if handle["kind"] == "histogram":
                handle_px = axis.transData.transform((handle["x"], 0.0))[0]
                if abs(event_x - handle_px) <= tolerance:
                    return handle
                continue
            handle_x, handle_y = axis.transData.transform((handle["x"], handle["y"]))
            if abs(event_x - handle_x) <= tolerance and abs(event_y - handle_y) <= tolerance:
                return handle
        return None

    def _gate_handles(self, gate: GateDefinition) -> list[dict[str, object]]:
        if gate.gate_type == GateType.HISTOGRAM and gate.x1 is not None and gate.x2 is not None:
            return [
                {"kind": "histogram", "field": "x1", "x": gate.x1},
                {"kind": "histogram", "field": "x2", "x": gate.x2},
            ]
        if gate.gate_type in (GateType.RECTANGLE, GateType.ELLIPSE) and None not in (gate.x1, gate.x2, gate.y1, gate.y2):
            return [
                {"kind": "corner", "index": 0, "field_x": "x1", "field_y": "y1", "x": gate.x1, "y": gate.y1},
                {"kind": "corner", "index": 1, "field_x": "x2", "field_y": "y1", "x": gate.x2, "y": gate.y1},
                {"kind": "corner", "index": 2, "field_x": "x2", "field_y": "y2", "x": gate.x2, "y": gate.y2},
                {"kind": "corner", "index": 3, "field_x": "x1", "field_y": "y2", "x": gate.x1, "y": gate.y2},
            ]
        if gate.gate_type == GateType.POLYGON:
            return [
                {"kind": "vertex", "index": index, "x": x, "y": y}
                for index, (x, y) in enumerate(gate.points)
            ]
        if gate.gate_type == GateType.QUADRANT and gate.x1 is not None and gate.y1 is not None:
            return [{"kind": "center", "x": gate.x1, "y": gate.y1}]
        return []

    def _updated_payload_for_drag(
        self,
        gate: GateDefinition,
        handle,
        x_value: float,
        y_value: float,
    ) -> dict[str, object] | None:
        if handle["kind"] == "histogram":
            return {str(handle["field"]): x_value}
        if handle["kind"] == "move":
            if self._drag_origin is None:
                return None
            delta_x = x_value - self._drag_origin[0]
            delta_y = y_value - self._drag_origin[1]
            if abs(delta_x) < 1e-12 and abs(delta_y) < 1e-12:
                return None
            if gate.gate_type == GateType.HISTOGRAM:
                return {
                    "x1": (gate.x1 or 0.0) + delta_x,
                    "x2": (gate.x2 or 0.0) + delta_x,
                }
            if gate.gate_type in (GateType.RECTANGLE, GateType.ELLIPSE):
                return {
                    "x1": (gate.x1 or 0.0) + delta_x,
                    "x2": (gate.x2 or 0.0) + delta_x,
                    "y1": (gate.y1 or 0.0) + delta_y,
                    "y2": (gate.y2 or 0.0) + delta_y,
                }
            if gate.gate_type == GateType.POLYGON:
                return {
                    "points": [(point_x + delta_x, point_y + delta_y) for point_x, point_y in gate.points]
                }
            if gate.gate_type == GateType.QUADRANT:
                return {
                    "x1": (gate.x1 or 0.0) + delta_x,
                    "y1": (gate.y1 or 0.0) + delta_y,
                }
            return None
        if handle["kind"] == "corner":
            return {
                str(handle["field_x"]): x_value,
                str(handle["field_y"]): y_value,
            }
        if handle["kind"] == "vertex":
            points = list(gate.points)
            points[int(handle["index"])] = (x_value, y_value)
            return {"points": points}
        if handle["kind"] == "center":
            return {"x1": x_value, "y1": y_value}
        return None

    def _hit_histogram_gate(self, event, gate: GateDefinition) -> bool:
        if gate.x1 is None or gate.x2 is None:
            return False
        axis = event.inaxes
        lower_px = axis.transData.transform((min(gate.x1, gate.x2), 0))[0]
        upper_px = axis.transData.transform((max(gate.x1, gate.x2), 0))[0]
        event_x = float(event.x)
        left = min(lower_px, upper_px)
        right = max(lower_px, upper_px)
        return left - 6 <= event_x <= right + 6

    def _hit_rectangle_gate(self, event, gate: GateDefinition) -> bool:
        if None in (gate.x1, gate.x2, gate.y1, gate.y2):
            return False
        corners = [
            (min(gate.x1, gate.x2), min(gate.y1, gate.y2)),
            (max(gate.x1, gate.x2), min(gate.y1, gate.y2)),
            (max(gate.x1, gate.x2), max(gate.y1, gate.y2)),
            (min(gate.x1, gate.x2), max(gate.y1, gate.y2)),
        ]
        polygon = Path(corners)
        return polygon.contains_point((event.xdata, event.ydata))

    def _hit_ellipse_gate(self, event, gate: GateDefinition) -> bool:
        if None in (gate.x1, gate.x2, gate.y1, gate.y2):
            return False
        x_center = (gate.x1 + gate.x2) / 2.0
        y_center = (gate.y1 + gate.y2) / 2.0
        x_radius = max(abs(gate.x2 - gate.x1) / 2.0, 1e-12)
        y_radius = max(abs(gate.y2 - gate.y1) / 2.0, 1e-12)
        distance = (((event.xdata - x_center) / x_radius) ** 2) + (((event.ydata - y_center) / y_radius) ** 2)
        return distance <= 1.0

    def _hit_polygon_gate(self, event, gate: GateDefinition) -> bool:
        if len(gate.points) < 3:
            return False
        polygon = Path(gate.points)
        return polygon.contains_point((event.xdata, event.ydata))

    def _hit_quadrant_gate(self, event, gate: GateDefinition) -> bool:
        if gate.x1 is None or gate.y1 is None:
            return False
        axis = event.inaxes
        center_x_px, center_y_px = axis.transData.transform((gate.x1, gate.y1))
        return (
            abs(float(event.x) - center_x_px) <= 8
            or abs(float(event.y) - center_y_px) <= 8
        )
