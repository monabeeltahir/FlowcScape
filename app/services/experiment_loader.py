from __future__ import annotations

from pathlib import Path

from app.models import ExperimentData, make_experiment_id
from app.services.atx_loader import load_atx_file
from app.services.fcs_loader import load_fcs_file


def load_fcs_files_as_experiment(
    file_paths: list[str] | list[Path],
    experiment_name: str | None = None,
) -> ExperimentData:
    paths = [Path(path) for path in file_paths]
    samples = [load_fcs_file(path) for path in paths]

    if experiment_name:
        name = experiment_name.strip()
    elif paths:
        name = paths[0].parent.name or "Imported Experiment"
    else:
        name = "Imported Experiment"

    return ExperimentData(
        id=make_experiment_id(),
        name=name,
        samples=samples,
        source_paths=paths,
        metadata={"source_type": "FCS"},
    )


def load_atx_files(file_paths: list[str] | list[Path]) -> list[ExperimentData]:
    return [load_atx_file(path) for path in file_paths]
