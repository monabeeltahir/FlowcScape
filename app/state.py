from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import QObject, Signal

from app.models import ExperimentData, GateDefinition, PlotConfig, SampleData


class AppState(QObject):
    experiments_changed = Signal()
    selected_sample_changed = Signal(object)
    selected_plot_changed = Signal(object)
    plot_config_changed = Signal(object)
    layout_changed = Signal(int, int)
    gates_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.experiments: list[ExperimentData] = []
        self.current_sample_ref: tuple[str, str] | None = None
        self.current_plot_cell_id: int | None = None
        self.plot_configs: dict[int, PlotConfig] = {}
        self.gates: dict[str, GateDefinition] = {}
        self._gate_name_counters: dict[str, int] = defaultdict(int)
        self.grid_rows: int = 2
        self.grid_columns: int = 3

    def add_experiment(self, experiment: ExperimentData) -> None:
        self.experiments.append(experiment)
        self.experiments_changed.emit()

    def set_experiments(self, experiments: list[ExperimentData]) -> None:
        self.experiments = experiments
        self.experiments_changed.emit()

    def set_selected_sample(self, experiment_id: str, sample_id: str) -> None:
        self.current_sample_ref = (experiment_id, sample_id)
        self.selected_sample_changed.emit(self.get_selected_sample())

    def set_selected_plot(self, cell_id: int | None) -> None:
        self.current_plot_cell_id = cell_id
        config = self.plot_configs.get(cell_id) if cell_id is not None else None
        self.selected_plot_changed.emit(config)

    def upsert_plot_config(self, config: PlotConfig) -> None:
        self.plot_configs[config.cell_id] = config
        self.plot_config_changed.emit(config)

    def remove_plot_config(self, cell_id: int) -> None:
        if cell_id in self.plot_configs:
            del self.plot_configs[cell_id]
        if self.current_plot_cell_id == cell_id:
            self.set_selected_plot(None)

    def set_grid_dimensions(self, rows: int, columns: int) -> None:
        self.grid_rows = max(1, rows)
        self.grid_columns = max(1, columns)
        self.layout_changed.emit(self.grid_rows, self.grid_columns)

    def get_selected_sample(self) -> SampleData | None:
        if not self.current_sample_ref:
            return None
        return self.find_sample(*self.current_sample_ref)

    def get_selected_plot_config(self) -> PlotConfig | None:
        if self.current_plot_cell_id is None:
            return None
        return self.plot_configs.get(self.current_plot_cell_id)

    def add_gate(self, gate: GateDefinition) -> None:
        self.gates[gate.id] = gate
        self.gates_changed.emit()

    def add_gates(self, gates: list[GateDefinition]) -> None:
        for gate in gates:
            self.gates[gate.id] = gate
        self.gates_changed.emit()

    def update_gate(self, gate: GateDefinition) -> None:
        self.gates[gate.id] = gate
        self.gates_changed.emit()

    def update_gates(self, gates: list[GateDefinition]) -> None:
        for gate in gates:
            self.gates[gate.id] = gate
        self.gates_changed.emit()

    def remove_gate(self, gate_id: str) -> None:
        if gate_id not in self.gates:
            return
        del self.gates[gate_id]
        self.gates_changed.emit()

    def remove_gates(self, gate_ids: list[str]) -> None:
        removed = False
        for gate_id in gate_ids:
            if gate_id in self.gates:
                del self.gates[gate_id]
                removed = True
        if removed:
            self.gates_changed.emit()

    def remove_gates_for_plot(self, plot_cell_id: int) -> None:
        gate_ids = [gate_id for gate_id, gate in self.gates.items() if gate.plot_cell_id == plot_cell_id]
        if not gate_ids:
            return
        for gate_id in gate_ids:
            del self.gates[gate_id]
        self.gates_changed.emit()

    def replace_gates_for_plot(self, plot_cell_id: int, gates: list[GateDefinition]) -> None:
        existing_gate_ids = [gate_id for gate_id, gate in self.gates.items() if gate.plot_cell_id == plot_cell_id]
        for gate_id in existing_gate_ids:
            del self.gates[gate_id]
        for gate in gates:
            self.gates[gate.id] = gate
        self.gates_changed.emit()

    def has_gate(self, gate_id: str | None) -> bool:
        return bool(gate_id and gate_id in self.gates)

    def gates_for_sample(self, experiment_id: str, sample_id: str) -> list[GateDefinition]:
        return sorted(
            [
                gate
                for gate in self.gates.values()
                if gate.experiment_id == experiment_id and gate.sample_id == sample_id
            ],
            key=lambda gate: gate.name,
        )

    def gates_for_plot(self, plot_cell_id: int) -> list[GateDefinition]:
        plot_config = self.plot_configs.get(plot_cell_id)
        if plot_config is None:
            return []
        return [
            gate
            for gate in self.gates.values()
            if gate.plot_cell_id == plot_cell_id
            and gate.experiment_id == plot_config.experiment_id
            and gate.sample_id == plot_config.sample_id
        ]

    def next_gate_name(self, prefix: str) -> str:
        self._gate_name_counters[prefix] += 1
        return f"{prefix}{self._gate_name_counters[prefix]}"

    def find_experiment(self, experiment_id: str) -> ExperimentData | None:
        for experiment in self.experiments:
            if experiment.id == experiment_id:
                return experiment
        return None

    def find_sample(self, experiment_id: str, sample_id: str) -> SampleData | None:
        experiment = self.find_experiment(experiment_id)
        if experiment is None:
            return None
        for sample in experiment.samples:
            if sample.id == sample_id:
                return sample
        return None
