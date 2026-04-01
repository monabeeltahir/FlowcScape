from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile, is_zipfile

from app.models import ExperimentData, make_experiment_id
from app.services.fcs_loader import FCSLoadError, load_fcs_bytes


class ATXLoadError(RuntimeError):
    pass


def load_atx_file(path: str | Path) -> ExperimentData:
    source_path = Path(path)

    if not is_zipfile(source_path):
        raise ATXLoadError(
            ".atx parsing is only implemented for container-style files with embedded FCS data."
        )

    samples = []
    with ZipFile(source_path, "r") as archive:
        embedded_fcs_files = [
            name for name in archive.namelist() if name.lower().endswith(".fcs")
        ]

        if not embedded_fcs_files:
            raise ATXLoadError(
                "No embedded FCS files were found in this .atx file. Use FCS import instead."
            )

        for member_name in embedded_fcs_files:
            try:
                sample = load_fcs_bytes(member_name, archive.read(member_name))
            except FCSLoadError as exc:
                raise ATXLoadError(
                    f"Embedded FCS file '{member_name}' could not be parsed: {exc}"
                ) from exc
            samples.append(sample)

    return ExperimentData(
        id=make_experiment_id(),
        name=source_path.stem,
        samples=samples,
        source_paths=[source_path],
        metadata={"source_type": "ATX"},
    )
