from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from app.models import ExperimentData


class ExperimentTree(QTreeWidget):
    sample_selected = Signal(str, str)
    sample_activated = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.setHeaderLabels(["Experiments and Samples"])
        self.setAlternatingRowColors(False)
        self.setUniformRowHeights(True)
        self.itemSelectionChanged.connect(self._emit_selection)
        self.itemDoubleClicked.connect(self._emit_activation)

    def set_experiments(self, experiments: list[ExperimentData]) -> None:
        self.clear()

        for experiment in experiments:
            experiment_item = QTreeWidgetItem([experiment.name])
            experiment_item.setData(0, Qt.ItemDataRole.UserRole, ("experiment", experiment.id))
            experiment_item.setExpanded(True)
            self.addTopLevelItem(experiment_item)

            group_nodes: dict[tuple[str, ...], QTreeWidgetItem] = {}
            for sample in experiment.samples:
                parent_item = experiment_item
                tree_path = sample.metadata.get("tree_path", [])
                normalized_tree_path = [str(part) for part in tree_path if str(part).strip()]
                current_path: list[str] = []
                for group_name in normalized_tree_path:
                    current_path.append(group_name)
                    path_key = tuple(current_path)
                    group_item = group_nodes.get(path_key)
                    if group_item is None:
                        group_item = QTreeWidgetItem([group_name])
                        group_item.setData(
                            0,
                            Qt.ItemDataRole.UserRole,
                            ("group", experiment.id, tuple(current_path)),
                        )
                        parent_item.addChild(group_item)
                        group_item.setExpanded(True)
                        group_nodes[path_key] = group_item
                    parent_item = group_item

                sample_item = QTreeWidgetItem([sample.name])
                sample_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    ("sample", experiment.id, sample.id),
                )
                parent_item.addChild(sample_item)

    def _emit_selection(self) -> None:
        item = self.currentItem()
        if item is None:
            return

        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not payload or payload[0] != "sample":
            return

        _, experiment_id, sample_id = payload
        self.sample_selected.emit(experiment_id, sample_id)

    def _emit_activation(self, item: QTreeWidgetItem, _column: int) -> None:
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not payload or payload[0] != "sample":
            return

        _, experiment_id, sample_id = payload
        self.sample_activated.emit(experiment_id, sample_id)
