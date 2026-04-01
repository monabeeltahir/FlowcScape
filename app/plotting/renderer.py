from __future__ import annotations

import math

import numpy as np
from matplotlib.colors import LinearSegmentedColormap, is_color_like
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse, Polygon, Rectangle
from matplotlib.ticker import ScalarFormatter

from app.models import (
    AxisScale,
    GateDefinition,
    GateType,
    PlotConfig,
    PlotType,
    PopulationStatistics,
    SampleData,
)
from app.services.gating import format_gate_label
from app.theme import PLOT_CELL_HEIGHT, PLOT_CELL_WIDTH


def render_plot(
    sample: SampleData,
    config: PlotConfig,
    events_frame=None,
    gates: list[GateDefinition] | None = None,
    gate_statistics: dict[str, PopulationStatistics] | None = None,
    selected_gate_id: str | None = None,
) -> Figure:
    inner_width = max(PLOT_CELL_WIDTH - 22, 220)
    inner_height = max(PLOT_CELL_HEIGHT - 22, 200)
    figure = Figure(
        figsize=(inner_width / 100.0, inner_height / 100.0),
        dpi=100,
        facecolor="white",
    )
    axis = figure.add_subplot(111)
    axis.set_facecolor("white")
    effective_font_size = _effective_font_size(config.font_size)

    frame = sample.events if events_frame is None else events_frame
    x_values = frame[config.x_param].to_numpy(dtype=float, copy=False)
    y_values = None
    if config.y_param and config.y_param in frame.columns:
        y_values = frame[config.y_param].to_numpy(dtype=float, copy=False)

    if config.plot_type == PlotType.HISTOGRAM:
        _draw_histogram(axis, x_values, config)
    elif config.plot_type == PlotType.DOT:
        if y_values is None:
            raise ValueError("Dot plots require a Y parameter.")
        _draw_dot_plot(axis, x_values, y_values, config)
    elif config.plot_type == PlotType.DENSITY:
        if y_values is None:
            raise ValueError("Density plots require a Y parameter.")
        _draw_density_plot(axis, x_values, y_values, config)
    else:
        raise ValueError(f"Unsupported plot type: {config.plot_type}")

    axis.set_title(config.title or sample.name, fontsize=effective_font_size + 1)
    axis.set_xlabel(config.x_param, fontsize=effective_font_size)
    if config.plot_type == PlotType.HISTOGRAM:
        axis.set_ylabel("Count", fontsize=effective_font_size)
    else:
        axis.set_ylabel(config.y_param or "", fontsize=effective_font_size)

    axis.tick_params(axis="both", labelsize=max(effective_font_size - 1, 7))
    _apply_scales(axis, config)
    _apply_ranges(axis, config)
    _apply_tick_formatting(axis, config)
    fixed_x_limits = axis.get_xlim()
    fixed_y_limits = axis.get_ylim()
    _draw_gate_overlays(axis, gates or [], config, gate_statistics or {}, selected_gate_id)
    axis.set_xlim(fixed_x_limits)
    axis.set_ylim(fixed_y_limits)
    figure.tight_layout(pad=0.8)
    return figure


def _draw_histogram(axis, x_values: np.ndarray, config: PlotConfig) -> None:
    x_values = _filter_valid(x_values, config.x_scale)
    if x_values.size == 0:
        axis.text(0.5, 0.5, "No valid data", ha="center", va="center")
        return

    if config.x_scale == AxisScale.LOG:
        lower = max(float(np.nanmin(x_values)), 1e-6)
        upper = max(float(np.nanmax(x_values)), lower * 10.0)
        bins = np.logspace(np.log10(lower), np.log10(upper), config.bins)
    else:
        bins = config.bins

    histogram_color = _resolve_histogram_color(config.histogram_color)
    if config.histogram_style == "Bar":
        axis.hist(
            x_values,
            bins=bins,
            histtype="bar",
            color=histogram_color,
            edgecolor=histogram_color,
            linewidth=0.35,
            alpha=0.85,
        )
        return

    counts, bin_edges = np.histogram(x_values, bins=bins)
    axis.stairs(
        counts,
        bin_edges,
        baseline=None,
        fill=False,
        color=histogram_color,
        linewidth=1.35,
    )


def _draw_dot_plot(axis, x_values: np.ndarray, y_values: np.ndarray, config: PlotConfig) -> None:
    x_values, y_values = _paired_values(x_values, y_values, config)
    if x_values.size == 0:
        axis.text(0.5, 0.5, "No valid data", ha="center", va="center")
        return

    x_values, y_values = _limit_points(x_values, y_values, max_points=25000)
    axis.scatter(
        x_values,
        y_values,
        s=2.0,
        c="#1d4f91",
        alpha=0.35,
        linewidths=0,
        rasterized=True,
    )


def _draw_density_plot(axis, x_values: np.ndarray, y_values: np.ndarray, config: PlotConfig) -> None:
    x_values, y_values = _paired_values(x_values, y_values, config)
    if x_values.size == 0:
        axis.text(0.5, 0.5, "No valid data", ha="center", va="center")
        return

    x_values, y_values = _limit_points(x_values, y_values, max_points=50000)
    axis.hexbin(
        x_values,
        y_values,
        gridsize=config.density_gridsize,
        bins="log",
        mincnt=config.density_min_count,
        cmap=_resolve_density_cmap(config.density_color_map),
        linewidths=0,
    )


def _paired_values(
    x_values: np.ndarray,
    y_values: np.ndarray,
    config: PlotConfig,
) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(x_values) & np.isfinite(y_values)
    if config.x_scale == AxisScale.LOG:
        mask &= x_values > 0
    if config.y_scale == AxisScale.LOG:
        mask &= y_values > 0
    return x_values[mask], y_values[mask]


def _filter_valid(values: np.ndarray, scale: AxisScale) -> np.ndarray:
    mask = np.isfinite(values)
    if scale == AxisScale.LOG:
        mask &= values > 0
    return values[mask]


def _apply_scales(axis, config: PlotConfig) -> None:
    axis.set_xscale("log" if config.x_scale == AxisScale.LOG else "linear")
    if config.plot_type != PlotType.HISTOGRAM:
        axis.set_yscale("log" if config.y_scale == AxisScale.LOG else "linear")


def _apply_ranges(axis, config: PlotConfig) -> None:
    if not config.x_auto_range and config.x_min is not None and config.x_max is not None:
        axis.set_xlim(config.x_min, config.x_max)
    if (
        config.plot_type != PlotType.HISTOGRAM
        and not config.y_auto_range
        and config.y_min is not None
        and config.y_max is not None
    ):
        axis.set_ylim(config.y_min, config.y_max)


def _limit_points(
    x_values: np.ndarray,
    y_values: np.ndarray,
    max_points: int,
) -> tuple[np.ndarray, np.ndarray]:
    if x_values.size <= max_points:
        return x_values, y_values
    indices = np.linspace(0, x_values.size - 1, max_points, dtype=int)
    return x_values[indices], y_values[indices]


def _effective_font_size(requested_size: int) -> int:
    max_font_for_cell = max(8, min(16, int(PLOT_CELL_HEIGHT / 18)))
    return max(6, min(requested_size, max_font_for_cell))


def _resolve_histogram_color(value: str) -> str:
    cleaned = value.strip()
    if cleaned and is_color_like(cleaned):
        return cleaned
    return "black"


def _resolve_gate_color(value: str) -> str:
    cleaned = value.strip()
    if cleaned and is_color_like(cleaned):
        return cleaned
    return "#2a9d8f"


def _resolve_density_cmap(value: str):
    custom_maps = {
        "Flow Cytometry": LinearSegmentedColormap.from_list(
            "flow_cytometry",
            [
                "#12356e",
                "#295da8",
                "#4fa0d8",
                "#9bd8cf",
                "#ffe54d",
                "#ffb000",
                "#ff4b20",
            ],
        ),
        "Attune Warm": LinearSegmentedColormap.from_list(
            "attune_warm",
            [
                "#1b3b7a",
                "#2d66bd",
                "#58b0cf",
                "#f2dc46",
                "#ff9f1a",
                "#ef3e2d",
            ],
        ),
        "Blue-Yellow-Red": LinearSegmentedColormap.from_list(
            "blue_yellow_red",
            ["#143d8d", "#2f72d8", "#6fc9ef", "#ffe75a", "#ffb400", "#ff4a22"],
        ),
        "Green Fire": LinearSegmentedColormap.from_list(
    "green_fire",
    ["#0b2e13", "#1f7a1f", "#7fd34e", "#ffe85a", "#ff7b22"],
),

    }
    return custom_maps.get(value, value)


def _apply_tick_formatting(axis, config: PlotConfig) -> None:
    if config.x_scale == AxisScale.LINEAR:
        _apply_scalar_formatter(axis.xaxis, axis.get_xlim())
    if config.plot_type == PlotType.HISTOGRAM:
        _apply_scalar_formatter(axis.yaxis, axis.get_ylim())
    elif config.y_scale == AxisScale.LINEAR:
        _apply_scalar_formatter(axis.yaxis, axis.get_ylim())

def _apply_scalar_formatter(axis_obj, limits: tuple[float, float], threshold: float = 100.0) -> None:
    formatter = ScalarFormatter(useMathText=False)
    formatter.set_useOffset(False)

    max_abs_limit = max(abs(limits[0]), abs(limits[1]))
    if max_abs_limit >= threshold:
        formatter.set_scientific(True)
        formatter.set_powerlimits((0, 0))
    else:
        formatter.set_scientific(False)

    axis_obj.set_major_formatter(formatter)


def _draw_gate_overlays(
    axis,
    gates: list[GateDefinition],
    plot_config: PlotConfig,
    gate_statistics: dict[str, PopulationStatistics],
    selected_gate_id: str | None,
) -> None:
    quadrant_sets_drawn: set[tuple[str, float, float]] = set()
    x_min, x_max = axis.get_xlim()
    y_min, y_max = axis.get_ylim()
    x_span = x_max - x_min
    y_span = y_max - y_min
    for gate in gates:
        gate_label = format_gate_label(gate, gate_statistics.get(gate.id), plot_config.gate_label_mode)
        gate_color = _resolve_gate_color(gate.color)
        is_selected = gate.id == selected_gate_id
        line_width = 2.2 if is_selected else 1.2
        if gate.gate_type == GateType.HISTOGRAM and plot_config.plot_type == PlotType.HISTOGRAM:
            lower = min(gate.x1 or 0.0, gate.x2 or 0.0)
            upper = max(gate.x1 or 0.0, gate.x2 or 0.0)
            axis.axvline(lower, color=gate_color, linestyle="--", linewidth=line_width)
            axis.axvline(upper, color=gate_color, linestyle="--", linewidth=line_width)
            label_x = lower + ((upper - lower) * 0.05)
            label_y = y_max * 0.94 if y_max > 0 else 0.0
            axis.text(label_x, label_y, gate_label, color=gate_color, fontsize=9, clip_on=True)
            if is_selected:
                _draw_point_handles(axis, [(lower, label_y), (upper, label_y)], gate_color)
        elif gate.gate_type == GateType.RECTANGLE and plot_config.plot_type != PlotType.HISTOGRAM:
            rectangle = Rectangle(
                (min(gate.x1 or 0.0, gate.x2 or 0.0), min(gate.y1 or 0.0, gate.y2 or 0.0)),
                abs((gate.x2 or 0.0) - (gate.x1 or 0.0)),
                abs((gate.y2 or 0.0) - (gate.y1 or 0.0)),
                fill=False,
                edgecolor=gate_color,
                linewidth=line_width,
            )
            axis.add_patch(rectangle)
            axis.text(rectangle.get_x(), rectangle.get_y(), gate_label, color=gate_color, fontsize=9, clip_on=True)
            if is_selected:
                _draw_point_handles(
                    axis,
                    [
                        (gate.x1 or 0.0, gate.y1 or 0.0),
                        (gate.x2 or 0.0, gate.y1 or 0.0),
                        (gate.x2 or 0.0, gate.y2 or 0.0),
                        (gate.x1 or 0.0, gate.y2 or 0.0),
                    ],
                    gate_color,
                )
        elif gate.gate_type == GateType.ELLIPSE and plot_config.plot_type != PlotType.HISTOGRAM:
            ellipse = Ellipse(
                (
                    ((gate.x1 or 0.0) + (gate.x2 or 0.0)) / 2.0,
                    ((gate.y1 or 0.0) + (gate.y2 or 0.0)) / 2.0,
                ),
                width=abs((gate.x2 or 0.0) - (gate.x1 or 0.0)),
                height=abs((gate.y2 or 0.0) - (gate.y1 or 0.0)),
                fill=False,
                edgecolor=gate_color,
                linewidth=line_width,
            )
            axis.add_patch(ellipse)
            axis.text(ellipse.center[0], ellipse.center[1], gate_label, color=gate_color, fontsize=9, clip_on=True)
            if is_selected:
                _draw_point_handles(
                    axis,
                    [
                        (gate.x1 or 0.0, gate.y1 or 0.0),
                        (gate.x2 or 0.0, gate.y1 or 0.0),
                        (gate.x2 or 0.0, gate.y2 or 0.0),
                        (gate.x1 or 0.0, gate.y2 or 0.0),
                    ],
                    gate_color,
                )
        elif gate.gate_type == GateType.POLYGON and plot_config.plot_type != PlotType.HISTOGRAM:
            if len(gate.points) >= 3:
                polygon = Polygon(gate.points, closed=True, fill=False, edgecolor=gate_color, linewidth=line_width)
                axis.add_patch(polygon)
                label_x, label_y = gate.points[0]
                axis.text(label_x, label_y, gate_label, color=gate_color, fontsize=9, clip_on=True)
                if is_selected:
                    _draw_point_handles(axis, gate.points, gate_color)
        elif gate.gate_type == GateType.QUADRANT and plot_config.plot_type != PlotType.HISTOGRAM:
            set_name = str(gate.metadata.get("quadrant_set", gate.name))
            key = (set_name, gate.x1 or 0.0, gate.y1 or 0.0)
            if key in quadrant_sets_drawn:
                continue
            quadrant_sets_drawn.add(key)
            x_center = gate.x1 or 0.0
            y_center = gate.y1 or 0.0
            axis.axvline(x_center, color=gate_color, linestyle="--", linewidth=line_width)
            axis.axhline(y_center, color=gate_color, linestyle="--", linewidth=line_width)
            axis.text(x_center, y_center, set_name, color=gate_color, fontsize=9, clip_on=True)
            quadrant_gates = [
                item
                for item in gates
                if item.gate_type == GateType.QUADRANT
                and str(item.metadata.get("quadrant_set", item.name)) == set_name
            ]
            quadrant_positions = {
                "Q1": (x_center + x_span * 0.18, y_center + y_span * 0.18),
                "Q2": (x_center - x_span * 0.18, y_center + y_span * 0.18),
                "Q3": (x_center - x_span * 0.18, y_center - y_span * 0.18),
                "Q4": (x_center + x_span * 0.18, y_center - y_span * 0.18),
            }
            for quadrant_gate in quadrant_gates:
                quadrant_name = str(quadrant_gate.metadata.get("quadrant", quadrant_gate.name))
                label = format_gate_label(
                    quadrant_gate,
                    gate_statistics.get(quadrant_gate.id),
                    plot_config.gate_label_mode,
                )
                pos_x, pos_y = quadrant_positions.get(quadrant_name, (x_center, y_center))
                if plot_config.x_scale == AxisScale.LOG:
                    pos_x = _log_midpoint(x_center, x_max if pos_x >= x_center else x_min)
                if plot_config.y_scale == AxisScale.LOG:
                    pos_y = _log_midpoint(y_center, y_max if pos_y >= y_center else y_min)
                axis.text(pos_x, pos_y, label, color=gate_color, fontsize=9, ha="center", clip_on=True)
            if is_selected:
                _draw_point_handles(axis, [(x_center, y_center)], gate_color)


def _log_midpoint(lower: float, upper: float) -> float:
    safe_lower = max(min(lower, upper), 1e-9)
    safe_upper = max(max(lower, upper), safe_lower * 1.0001)
    return math.sqrt(safe_lower * safe_upper)


def _draw_point_handles(axis, points: list[tuple[float, float]], color: str) -> None:
    if not points:
        return
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    axis.scatter(
        x_values,
        y_values,
        s=28,
        marker="s",
        facecolor="white",
        edgecolor=color,
        linewidths=1.1,
        zorder=6,
        clip_on=True,
    )
