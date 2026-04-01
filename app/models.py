from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd


class PlotType(str, Enum):
    HISTOGRAM = "Histogram Plot"
    DOT = "Dot Plot"
    DENSITY = "Density Plot"


class GateType(str, Enum):
    HISTOGRAM = "Histogram Gate"
    RECTANGLE = "Rectangle Gate"
    ELLIPSE = "Oval Gate"
    POLYGON = "Polygon Gate"
    QUADRANT = "Quadrant Gate"


class AxisScale(str, Enum):
    LINEAR = "Linear"
    LOG = "Log"


class DataSourceKind(str, Enum):
    ALL_EVENTS = "all_events"
    GATE = "gate"


class GateLabelMode(str, Enum):
    NAME = "Name"
    COUNT = "Count"
    PERCENTAGE = "Percentage"


@dataclass(slots=True)
class SampleData:
    id: str
    name: str
    source_path: Path | None
    parameters: list[str]
    events: pd.DataFrame
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExperimentData:
    id: str
    name: str
    samples: list[SampleData]
    source_paths: list[Path] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PlotConfig:
    cell_id: int
    experiment_id: str
    sample_id: str
    plot_type: PlotType
    x_param: str
    y_param: str | None = None
    title: str = ""
    source_kind: DataSourceKind = DataSourceKind.ALL_EVENTS
    source_gate_id: str | None = None
    x_scale: AxisScale = AxisScale.LINEAR
    y_scale: AxisScale = AxisScale.LINEAR
    x_auto_range: bool = True
    y_auto_range: bool = True
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    bins: int = 120
    histogram_style: str = "Line"
    histogram_color: str = "black"
    density_gridsize: int = 70
    density_min_count: int = 1
    density_color_map: str = "turbo"
    gate_label_mode: GateLabelMode = GateLabelMode.NAME
    font_size: int = 10
    export_dpi: int = 600

    def clone(self) -> "PlotConfig":
        return replace(self)


@dataclass(slots=True)
class GateDefinition:
    id: str
    name: str
    gate_type: GateType
    experiment_id: str
    sample_id: str
    plot_cell_id: int
    source_kind: DataSourceKind
    source_gate_id: str | None
    x_param: str
    y_param: str | None = None
    x1: float | None = None
    x2: float | None = None
    y1: float | None = None
    y2: float | None = None
    color: str = "#2a9d8f"
    points: list[tuple[float, float]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PopulationStatistics:
    label: str
    count: int
    percentage_of_total: float
    mean_x: float | None = None
    median_x: float | None = None
    mean_y: float | None = None
    median_y: float | None = None


def make_experiment_id() -> str:
    return f"exp-{uuid4().hex[:10]}"


def make_sample_id() -> str:
    return f"sample-{uuid4().hex[:10]}"


def make_gate_id() -> str:
    return f"gate-{uuid4().hex[:10]}"
