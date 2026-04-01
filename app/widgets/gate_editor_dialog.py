from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from app.models import GateDefinition, GateType


class GateEditorDialog(QDialog):
    def __init__(self, gate: GateDefinition, parent=None) -> None:
        super().__init__(parent)
        self._gate = gate
        self.setWindowTitle(f"Edit Gate - {gate.name}")
        self.setMinimumWidth(420)

        root_layout = QVBoxLayout(self)

        details_group = QGroupBox("Gate Details")
        details_layout = QFormLayout(details_group)
        self.name_edit = QLineEdit(gate.name)
        details_layout.addRow("Name:", self.name_edit)

        self.x1_spin = _build_coordinate_spinbox(gate.x1)
        self.x2_spin = _build_coordinate_spinbox(gate.x2)
        self.y1_spin = _build_coordinate_spinbox(gate.y1)
        self.y2_spin = _build_coordinate_spinbox(gate.y2)
        self.points_edit = QPlainTextEdit(_format_points(gate.points))
        self.points_edit.setPlaceholderText("One x,y pair per line")

        if gate.gate_type == GateType.HISTOGRAM:
            details_layout.addRow("X min:", self.x1_spin)
            details_layout.addRow("X max:", self.x2_spin)
        elif gate.gate_type in (GateType.RECTANGLE, GateType.ELLIPSE):
            details_layout.addRow("X1:", self.x1_spin)
            details_layout.addRow("X2:", self.x2_spin)
            details_layout.addRow("Y1:", self.y1_spin)
            details_layout.addRow("Y2:", self.y2_spin)
        elif gate.gate_type == GateType.POLYGON:
            details_layout.addRow("Points:", self.points_edit)
        elif gate.gate_type == GateType.QUADRANT:
            details_layout.addRow("Center X:", self.x1_spin)
            details_layout.addRow("Center Y:", self.y1_spin)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        root_layout.addWidget(details_group)
        root_layout.addWidget(button_box)

    def gate_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"name": self.name_edit.text().strip() or self._gate.name}
        if self._gate.gate_type == GateType.HISTOGRAM:
            payload["x1"] = self.x1_spin.value()
            payload["x2"] = self.x2_spin.value()
        elif self._gate.gate_type in (GateType.RECTANGLE, GateType.ELLIPSE):
            payload["x1"] = self.x1_spin.value()
            payload["x2"] = self.x2_spin.value()
            payload["y1"] = self.y1_spin.value()
            payload["y2"] = self.y2_spin.value()
        elif self._gate.gate_type == GateType.POLYGON:
            payload["points"] = _parse_points(self.points_edit.toPlainText())
        elif self._gate.gate_type == GateType.QUADRANT:
            payload["x1"] = self.x1_spin.value()
            payload["y1"] = self.y1_spin.value()
        return payload

    def accept(self) -> None:
        if self._gate.gate_type == GateType.POLYGON:
            try:
                points = _parse_points(self.points_edit.toPlainText())
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Polygon", str(exc))
                return
            if len(points) < 3:
                QMessageBox.warning(self, "Invalid Polygon", "A polygon gate needs at least three points.")
                return
        super().accept()


def _build_coordinate_spinbox(value: float | None) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(-1_000_000_000.0, 1_000_000_000.0)
    spin.setDecimals(6)
    spin.setSingleStep(1.0)
    spin.setValue(value or 0.0)
    return spin


def _format_points(points: list[tuple[float, float]]) -> str:
    return "\n".join(f"{x}, {y}" for x, y in points)


def _parse_points(text: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "," not in line:
            raise ValueError("Use one point per line in the format x, y.")
        x_text, y_text = [item.strip() for item in line.split(",", 1)]
        points.append((float(x_text), float(y_text)))
    return points
