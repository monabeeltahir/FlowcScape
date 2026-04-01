from __future__ import annotations

SIDE_PANEL_BACKGROUND = "#000000"
SIDE_PANEL_TEXT = "#ffffff"
SIDE_PANEL_INPUT_BACKGROUND = "#111111"
SIDE_PANEL_BORDER = "#4a4a4a"
SIDE_PANEL_GROUP_BORDER = "#3f3f3f"
SIDE_PANEL_TREE_SELECTED = "#1e78ff"
SIDE_PANEL_BUTTON_BACKGROUND = "#295f9f"
SIDE_PANEL_BUTTON_BORDER = "#4478b6"

GROUP_BOX_TITLE_FONT_SIZE = 18
GROUP_BOX_TITLE_FONT_WEIGHT = 700
GROUP_BOX_TITLE_BACKGROUND = "#000000"

LEFT_PANEL_WIDTH = 320
RIGHT_PANEL_WIDTH = 320
PLOT_CELL_WIDTH = 320
PLOT_CELL_HEIGHT = 300

SELECTED_PLOT_BOX_MIN_HEIGHT = 116
AXES_BOX_MIN_HEIGHT = 192
RANGES_BOX_MIN_HEIGHT = 206
STYLE_BOX_MIN_HEIGHT = 224


def build_main_stylesheet() -> str:
    return f"""
        QMainWindow {{
            background: #d7d9dc;
        }}
        QToolBar {{
            background: #b7bcc2;
            border-bottom: 1px solid #8f959b;
            spacing: 6px;
            padding: 4px;
        }}
        QToolButton {{
            background: #eceeef;
            border: 1px solid #a4aab1;
            padding: 6px 10px;
            min-width: 90px;
        }}
        QWidget#sidePanel {{
            background: {SIDE_PANEL_BACKGROUND};
            color: {SIDE_PANEL_TEXT};
        }}
        QWidget#sidePanel QLabel,
        QWidget#sidePanel QCheckBox,
        QWidget#sidePanel QGroupBox,
        QWidget#sidePanel QTreeWidget,
        QWidget#sidePanel QHeaderView::section {{
            color: {SIDE_PANEL_TEXT};
        }}
        QWidget#sidePanel QGroupBox {{
            background: {SIDE_PANEL_BACKGROUND};
            border: 1px solid {SIDE_PANEL_GROUP_BORDER};
            margin-top: 14px;
            padding-top: 10px;
        }}
        QWidget#sidePanel QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            top: -2px;
            color: {SIDE_PANEL_TEXT};
            background: {GROUP_BOX_TITLE_BACKGROUND};
            font-size: {GROUP_BOX_TITLE_FONT_SIZE}px;
            font-weight: {GROUP_BOX_TITLE_FONT_WEIGHT};
            padding: 0 6px;
        }}
        QWidget#sidePanel QTreeWidget,
        QWidget#sidePanel QLineEdit,
        QWidget#sidePanel QComboBox,
        QWidget#sidePanel QSpinBox {{
            background: {SIDE_PANEL_INPUT_BACKGROUND};
            color: {SIDE_PANEL_TEXT};
            border: 1px solid {SIDE_PANEL_BORDER};
            padding: 3px;
            min-width: 170px;
        }}
        QWidget#sidePanel QComboBox {{
            combobox-popup: 1;
        }}
        QWidget#sidePanel QComboBox::drop-down {{
            border-left: 1px solid {SIDE_PANEL_BORDER};
            background: {SIDE_PANEL_INPUT_BACKGROUND};
            width: 24px;
        }}
        QWidget#sidePanel QComboBox QAbstractItemView {{
            background: {SIDE_PANEL_INPUT_BACKGROUND};
            color: {SIDE_PANEL_TEXT};
            border: 1px solid {SIDE_PANEL_BORDER};
            selection-background-color: {SIDE_PANEL_TREE_SELECTED};
            selection-color: {SIDE_PANEL_TEXT};
            outline: 0;
        }}
        QWidget#sidePanel QTreeWidget {{
            background: {SIDE_PANEL_BACKGROUND};
            alternate-background-color: {SIDE_PANEL_BACKGROUND};
        }}
        QWidget#sidePanel QTreeWidget::item {{
            background: {SIDE_PANEL_BACKGROUND};
            color: {SIDE_PANEL_TEXT};
        }}
        QWidget#sidePanel QTreeWidget::item:selected {{
            background: {SIDE_PANEL_TREE_SELECTED};
            color: {SIDE_PANEL_TEXT};
        }}
        QWidget#sidePanel QHeaderView::section {{
            background: {SIDE_PANEL_INPUT_BACKGROUND};
            border: 1px solid #333333;
            padding: 4px;
        }}
        QWidget#sidePanel QPushButton {{
            background: {SIDE_PANEL_BUTTON_BACKGROUND};
            color: {SIDE_PANEL_TEXT};
            border: 1px solid {SIDE_PANEL_BUTTON_BORDER};
            padding: 7px 10px;
        }}
        QWidget#gridControls {{
            background: #d7d9dc;
        }}
        QWidget#gridControls QLabel {{
            color: #1e2328;
            font-size: 12px;
        }}
        QWidget#gridControls QWidget#gridStepper {{
            background: transparent;
        }}
        QWidget#gridControls QSpinBox#gridStepperSpin {{
            background: #fcfcfc;
            color: #111315;
            border: 1px solid #7f8791;
            padding: 3px;
            min-width: 70px;
        }}
        QWidget#gridControls QToolButton#gridStepperButton {{
            width: 18px;
            min-width: 18px;
            min-height: 14px;
            color: #1e2328;
            background: #ffffff;
            border: 1px solid #7f8791;
            font-size: 10px;
            font-weight: 700;
            padding: 0px;
        }}
        QWidget#gridControls QToolButton#gridStepperButton:hover {{
            background: #eef3f9;
        }}
        QWidget#gridControls QToolButton#gridStepperButton:pressed {{
            background: #d7e5f7;
        }}
        QScrollArea {{
            background: #d7d9dc;
            border: none;
        }}
    """
