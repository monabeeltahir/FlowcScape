from __future__ import annotations

from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
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

        experiment_name = source_path.stem
        sample_metadata_by_id: dict[str, dict[str, object]] = {}
        if "experiment.xml" in archive.namelist():
            try:
                experiment_name, sample_metadata_by_id = _parse_experiment_manifest(
                    archive.read("experiment.xml"),
                    fallback_experiment_name=source_path.stem,
                )
            except Exception:
                experiment_name = source_path.stem

        for member_name in embedded_fcs_files:
            try:
                sample = load_fcs_bytes(member_name, archive.read(member_name))
            except FCSLoadError as exc:
                raise ATXLoadError(
                    f"Embedded FCS file '{member_name}' could not be parsed: {exc}"
                ) from exc
            member_path = PurePosixPath(member_name)
            member_id = member_path.parts[0] if member_path.parts else ""
            manifest_info = sample_metadata_by_id.get(member_id, {})
            relative_parts = [
                str(part)
                for part in manifest_info.get("tree_path", [])
                if str(part).strip()
            ]
            if not relative_parts:
                relative_parts = []
            sample.metadata["archive_member_name"] = member_name
            sample.metadata["tree_path"] = relative_parts
            sample.metadata["attune_sample_id"] = member_id
            manifest_name = str(manifest_info.get("name", "")).strip()
            if manifest_name:
                sample.name = manifest_name
            samples.append(sample)

    return ExperimentData(
        id=make_experiment_id(),
        name=experiment_name,
        samples=samples,
        source_paths=[source_path],
        metadata={"source_type": "ATX"},
    )


def _parse_experiment_manifest(
    xml_bytes: bytes,
    fallback_experiment_name: str,
) -> tuple[str, dict[str, dict[str, object]]]:
    root = ET.fromstring(xml_bytes.decode("utf-8", errors="ignore"))
    experiment_name = root.attrib.get("Name", fallback_experiment_name).strip() or fallback_experiment_name
    sample_map: dict[str, dict[str, object]] = {}

    def walk(node: ET.Element, path: list[str]) -> None:
        node_tag = _strip_namespace(node.tag)

        if node_tag == "Sample":
            sample_id = node.attrib.get("Id", "").strip()
            sample_name = node.attrib.get("Name", "").strip()
            if sample_id:
                sample_map[sample_id] = {
                    "name": sample_name,
                    "tree_path": list(path),
                }
            return

        next_path = list(path)
        if node_tag in {"Compensation", "Group"}:
            node_name = node.attrib.get("Name", "").strip()
            if node_name:
                next_path.append(node_name)

        for child in list(node):
            walk(child, next_path)

    for child in list(root):
        walk(child, [])

    return experiment_name, sample_map


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
