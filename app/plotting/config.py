from __future__ import annotations

from app.models import AxisScale, PlotConfig, PlotType, SampleData


def build_default_plot_config(
    cell_id: int,
    experiment_id: str,
    sample: SampleData,
    plot_type: PlotType,
) -> PlotConfig:
    x_param = sample.parameters[0]
    y_param = sample.parameters[1] if len(sample.parameters) > 1 else None

    return PlotConfig(
        cell_id=cell_id,
        experiment_id=experiment_id,
        sample_id=sample.id,
        plot_type=plot_type,
        x_param=x_param,
        y_param=y_param,
        title=build_plot_title(sample.name, plot_type, x_param, y_param),
        x_scale=AxisScale.LINEAR,
        y_scale=AxisScale.LINEAR,
    )


def build_plot_title(
    sample_name: str,
    plot_type: PlotType,
    x_param: str,
    y_param: str | None = None,
) -> str:
    if plot_type == PlotType.HISTOGRAM:
        return f"{sample_name} - {x_param}"
    if y_param:
        return f"{sample_name} - {x_param} vs {y_param}"
    return f"{sample_name} - {x_param}"
