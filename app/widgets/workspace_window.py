from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models import GateType, PlotType


class WorkspaceWindow(QWidget):
    plot_requested = Signal(object)
    gate_requested = Signal(object)
    export_requested = Signal()
    clear_requested = Signal()
    cancel_gate_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Tool)
        self.setWindowTitle("Workspace")
        self.setMinimumWidth(280)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        plot_group = QGroupBox("Plots")
        plot_layout = QGridLayout(plot_group)
        for index, plot_type in enumerate((PlotType.HISTOGRAM, PlotType.DOT, PlotType.DENSITY)):
            button = QPushButton(plot_type.value)
            button.clicked.connect(
                lambda _checked=False, selected_plot=plot_type: self.plot_requested.emit(selected_plot)
            )
            plot_layout.addWidget(button, index // 2, index % 2)

        gate_group = QGroupBox("Gating Tools")
        gate_layout = QGridLayout(gate_group)
        gate_actions = [
            (GateType.HISTOGRAM, "Histogram Gate"),
            (GateType.RECTANGLE, "Rectangle Gate"),
            (GateType.ELLIPSE, "Oval Gate"),
            (GateType.POLYGON, "Polygon Gate"),
            (GateType.QUADRANT, "Quadrant Gate"),
        ]
        for index, (gate_type, label) in enumerate(gate_actions):
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, selected_gate=gate_type: self.gate_requested.emit(selected_gate)
            )
            gate_layout.addWidget(button, index // 2, index % 2)

        actions_group = QGroupBox("Workspace Actions")
        actions_layout = QVBoxLayout(actions_group)
        export_button = QPushButton("Export Selected Plot")
        export_button.clicked.connect(self.export_requested.emit)
        clear_button = QPushButton("Clear Selected Plot")
        clear_button.clicked.connect(self.clear_requested.emit)
        cancel_gate_button = QPushButton("Cancel Active Gate Tool")
        cancel_gate_button.clicked.connect(self.cancel_gate_requested.emit)
        actions_layout.addWidget(export_button)
        actions_layout.addWidget(clear_button)
        actions_layout.addWidget(cancel_gate_button)

        root_layout.addWidget(plot_group)
        root_layout.addWidget(gate_group)
        root_layout.addWidget(actions_group)
        root_layout.addStretch(1)
