from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class StepperSpinBox(QWidget):
    valueChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("gridStepper")

        self.spinbox = QSpinBox(self)
        self.spinbox.setObjectName("gridStepperSpin")
        self.spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)

        self.up_button = QToolButton(self)
        self.up_button.setObjectName("gridStepperButton")
        self.up_button.setText("▲")
        self.up_button.setAutoRepeat(True)

        self.down_button = QToolButton(self)
        self.down_button.setObjectName("gridStepperButton")
        self.down_button.setText("▼")
        self.down_button.setAutoRepeat(True)

        buttons_layout = QVBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(0)
        buttons_layout.addWidget(self.up_button)
        buttons_layout.addWidget(self.down_button)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.spinbox)
        layout.addLayout(buttons_layout)

        self.up_button.clicked.connect(self.spinbox.stepUp)
        self.down_button.clicked.connect(self.spinbox.stepDown)
        self.spinbox.valueChanged.connect(self.valueChanged.emit)

    def setRange(self, minimum: int, maximum: int) -> None:
        self.spinbox.setRange(minimum, maximum)

    def setValue(self, value: int) -> None:
        self.spinbox.setValue(value)

    def value(self) -> int:
        return self.spinbox.value()
