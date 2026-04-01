from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
from matplotlib.path import Path

from app.models import (
    DataSourceKind,
    GateDefinition,
    GateType,
    PlotConfig,
    PopulationStatistics,
    SampleData,
)


def resolve_plot_events(
    sample: SampleData,
    plot_config: PlotConfig,
    gates: dict[str, GateDefinition],
) -> pd.DataFrame:
    return resolve_source_events(
        sample,
        plot_config.source_kind,
        plot_config.source_gate_id,
        gates,
    )


def resolve_gate_events(
    sample: SampleData,
    gate: GateDefinition,
    gates: dict[str, GateDefinition],
) -> pd.DataFrame:
    base_frame = resolve_source_events(
        sample,
        gate.source_kind,
        gate.source_gate_id,
        gates,
    )
    return apply_gate(base_frame, gate)


def resolve_source_events(
    sample: SampleData,
    source_kind: DataSourceKind,
    source_gate_id: str | None,
    gates: dict[str, GateDefinition],
    _seen: set[str] | None = None,
) -> pd.DataFrame:
    if source_kind == DataSourceKind.ALL_EVENTS or not source_gate_id:
        return sample.events

    gate = gates.get(source_gate_id)
    if gate is None:
        return sample.events

    seen = _seen or set()
    if gate.id in seen:
        raise ValueError("Circular gate source dependency detected.")
    seen.add(gate.id)

    base_frame = resolve_source_events(
        sample,
        gate.source_kind,
        gate.source_gate_id,
        gates,
        _seen=seen,
    )
    return apply_gate(base_frame, gate)


def apply_gate(frame: pd.DataFrame, gate: GateDefinition) -> pd.DataFrame:
    if frame.empty:
        return frame

    if gate.gate_type == GateType.HISTOGRAM:
        return _apply_histogram_gate(frame, gate)
    if gate.gate_type == GateType.RECTANGLE:
        return _apply_rectangle_gate(frame, gate)
    if gate.gate_type == GateType.ELLIPSE:
        return _apply_ellipse_gate(frame, gate)
    if gate.gate_type == GateType.POLYGON:
        return _apply_polygon_gate(frame, gate)
    if gate.gate_type == GateType.QUADRANT:
        return _apply_quadrant_gate(frame, gate)

    return frame


def gates_for_plot(
    gates: Iterable[GateDefinition],
    plot_cell_id: int,
    experiment_id: str,
    sample_id: str,
) -> list[GateDefinition]:
    return [
        gate
        for gate in gates
        if gate.plot_cell_id == plot_cell_id
        and gate.experiment_id == experiment_id
        and gate.sample_id == sample_id
    ]


def gates_for_sample(
    gates: Iterable[GateDefinition],
    experiment_id: str,
    sample_id: str,
) -> list[GateDefinition]:
    return [
        gate
        for gate in gates
        if gate.experiment_id == experiment_id and gate.sample_id == sample_id
    ]


def gate_source_label(gate: GateDefinition) -> str:
    return gate.name


def build_population_statistics(
    frame: pd.DataFrame,
    x_param: str,
    y_param: str | None,
    total_population: int,
    label: str,
) -> PopulationStatistics:
    count = int(len(frame))
    percentage = (count / total_population * 100.0) if total_population else 0.0
    mean_x = _safe_stat(frame, x_param, "mean")
    median_x = _safe_stat(frame, x_param, "median")
    mean_y = _safe_stat(frame, y_param, "mean") if y_param else None
    median_y = _safe_stat(frame, y_param, "median") if y_param else None
    return PopulationStatistics(
        label=label,
        count=count,
        percentage_of_total=percentage,
        mean_x=mean_x,
        median_x=median_x,
        mean_y=mean_y,
        median_y=median_y,
    )


def format_gate_label(gate: GateDefinition, stats: PopulationStatistics | None, label_mode) -> str:
    if stats is None:
        return gate.name

    if getattr(label_mode, "value", str(label_mode)) == "Count":
        return f"{gate.name}: {stats.count}"
    if getattr(label_mode, "value", str(label_mode)) == "Percentage":
        return f"{gate.name}: {stats.percentage_of_total:.2f}%"
    return gate.name


def _apply_histogram_gate(frame: pd.DataFrame, gate: GateDefinition) -> pd.DataFrame:
    x_values = frame[gate.x_param]
    lower = min(gate.x1 or 0.0, gate.x2 or 0.0)
    upper = max(gate.x1 or 0.0, gate.x2 or 0.0)
    mask = x_values.between(lower, upper, inclusive="both")
    return frame.loc[mask]


def _apply_rectangle_gate(frame: pd.DataFrame, gate: GateDefinition) -> pd.DataFrame:
    x_values = frame[gate.x_param]
    y_values = frame[gate.y_param] if gate.y_param else pd.Series([], dtype=float)
    x_lower = min(gate.x1 or 0.0, gate.x2 or 0.0)
    x_upper = max(gate.x1 or 0.0, gate.x2 or 0.0)
    y_lower = min(gate.y1 or 0.0, gate.y2 or 0.0)
    y_upper = max(gate.y1 or 0.0, gate.y2 or 0.0)
    mask = (
        x_values.between(x_lower, x_upper, inclusive="both")
        & y_values.between(y_lower, y_upper, inclusive="both")
    )
    return frame.loc[mask]


def _apply_ellipse_gate(frame: pd.DataFrame, gate: GateDefinition) -> pd.DataFrame:
    x_values = frame[gate.x_param].to_numpy(dtype=float, copy=False)
    y_values = frame[gate.y_param].to_numpy(dtype=float, copy=False)

    x_center = ((gate.x1 or 0.0) + (gate.x2 or 0.0)) / 2.0
    y_center = ((gate.y1 or 0.0) + (gate.y2 or 0.0)) / 2.0
    x_radius = max(abs((gate.x2 or 0.0) - (gate.x1 or 0.0)) / 2.0, 1e-12)
    y_radius = max(abs((gate.y2 or 0.0) - (gate.y1 or 0.0)) / 2.0, 1e-12)
    mask = (((x_values - x_center) / x_radius) ** 2 + ((y_values - y_center) / y_radius) ** 2) <= 1.0
    return frame.loc[mask]


def _apply_polygon_gate(frame: pd.DataFrame, gate: GateDefinition) -> pd.DataFrame:
    if len(gate.points) < 3 or gate.y_param is None:
        return frame

    polygon_path = Path(gate.points)
    points = np.column_stack(
        [
            frame[gate.x_param].to_numpy(dtype=float, copy=False),
            frame[gate.y_param].to_numpy(dtype=float, copy=False),
        ]
    )
    mask = polygon_path.contains_points(points)
    return frame.loc[mask]


def _apply_quadrant_gate(frame: pd.DataFrame, gate: GateDefinition) -> pd.DataFrame:
    if gate.y_param is None:
        return frame

    x_values = frame[gate.x_param]
    y_values = frame[gate.y_param]
    x_center = gate.x1 or 0.0
    y_center = gate.y1 or 0.0
    quadrant = gate.metadata.get("quadrant", "Q1")

    if quadrant == "Q1":
        mask = (x_values >= x_center) & (y_values >= y_center)
    elif quadrant == "Q2":
        mask = (x_values < x_center) & (y_values >= y_center)
    elif quadrant == "Q3":
        mask = (x_values < x_center) & (y_values < y_center)
    else:
        mask = (x_values >= x_center) & (y_values < y_center)

    return frame.loc[mask]


def _safe_stat(frame: pd.DataFrame, parameter: str | None, mode: str) -> float | None:
    if not parameter or parameter not in frame.columns or frame.empty:
        return None

    series = pd.to_numeric(frame[parameter], errors="coerce").dropna()
    if series.empty:
        return None

    if mode == "mean":
        return float(series.mean())
    return float(series.median())
