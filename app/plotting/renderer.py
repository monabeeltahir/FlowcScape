from __future__ import annotations

import numpy as np
from matplotlib.colors import is_color_like
from matplotlib.figure import Figure

from app.models import AxisScale, PlotConfig, PlotType, SampleData
from app.theme import PLOT_CELL_HEIGHT, PLOT_CELL_WIDTH


def render_plot(sample: SampleData, config: PlotConfig) -> Figure:
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

    x_values = sample.events[config.x_param].to_numpy(dtype=float, copy=False)
    y_values = None
    if config.y_param and config.y_param in sample.events.columns:
        y_values = sample.events[config.y_param].to_numpy(dtype=float, copy=False)

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
        cmap=config.density_color_map,
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
