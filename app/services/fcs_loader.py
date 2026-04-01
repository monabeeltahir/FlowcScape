from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.models import SampleData, make_sample_id


class FCSLoadError(RuntimeError):
    pass


def load_fcs_file(path: str | Path) -> SampleData:
    source_path = Path(path)
    raw_bytes = source_path.read_bytes()
    return load_fcs_bytes(source_path.name, raw_bytes, source_path=source_path)


def load_fcs_bytes(
    source_name: str,
    raw_bytes: bytes,
    source_path: Path | None = None,
) -> SampleData:
    if len(raw_bytes) < 58:
        raise FCSLoadError(f"{source_name} is too small to be a valid FCS file.")

    version = raw_bytes[0:6].decode("ascii", errors="ignore").strip()
    text_start = _read_header_int(raw_bytes[10:18])
    text_end = _read_header_int(raw_bytes[18:26])
    data_start = _read_header_int(raw_bytes[26:34])
    data_end = _read_header_int(raw_bytes[34:42])

    if text_start is None or text_end is None:
        raise FCSLoadError(f"{source_name} does not have a readable FCS text segment.")

    text_segment = raw_bytes[text_start : text_end + 1]
    metadata = _parse_text_segment(text_segment)
    metadata["FCS_VERSION"] = version

    if data_start is None or data_end is None or data_start == 0 or data_end == 0:
        data_start = _safe_int(metadata.get("$BEGINDATA"))
        data_end = _safe_int(metadata.get("$ENDDATA"))
        if data_start is None or data_end is None:
            raise FCSLoadError(f"{source_name} is missing a readable FCS data segment.")

    mode = metadata.get("$MODE", "L").upper()
    if mode != "L":
        raise FCSLoadError(f"{source_name} uses unsupported FCS mode '{mode}'.")

    total_events = _required_int(metadata, "$TOT", source_name)
    total_parameters = _required_int(metadata, "$PAR", source_name)
    datatype = metadata.get("$DATATYPE", "").upper()
    byte_order = metadata.get("$BYTEORD", "1,2,3,4")

    parameter_names: list[str] = []
    parameter_bits: list[int] = []
    for index in range(1, total_parameters + 1):
        name = (
            metadata.get(f"$P{index}S")
            or metadata.get(f"$P{index}N")
            or f"Parameter {index}"
        )
        parameter_names.append(name)
        parameter_bits.append(_required_int(metadata, f"$P{index}B", source_name))

    data_segment = raw_bytes[data_start : data_end + 1]
    values = _decode_event_matrix(
        data_segment=data_segment,
        event_count=total_events,
        parameter_count=total_parameters,
        datatype=datatype,
        parameter_bits=parameter_bits,
        byte_order=byte_order,
        source_name=source_name,
    )

    dataframe = pd.DataFrame(values, columns=parameter_names)
    metadata["parameter_names"] = parameter_names

    return SampleData(
        id=make_sample_id(),
        name=Path(source_name).stem,
        source_path=source_path,
        parameters=parameter_names,
        events=dataframe,
        metadata=metadata,
    )


def _read_header_int(value: bytes) -> int | None:
    try:
        text = value.decode("ascii", errors="ignore").strip()
        return int(text) if text else None
    except ValueError:
        return None


def _parse_text_segment(segment: bytes) -> dict[str, str]:
    if not segment:
        return {}

    delimiter = chr(segment[0])
    text = segment[1:].decode("latin-1", errors="ignore")
    tokens = _split_text_tokens(text, delimiter)
    metadata: dict[str, str] = {}

    for index in range(0, len(tokens) - 1, 2):
        key = tokens[index].strip()
        value = tokens[index + 1].replace("\x00", "").strip()
        if key:
            metadata[key] = value

    return metadata


def _split_text_tokens(text: str, delimiter: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    index = 0
    text_length = len(text)

    while index < text_length:
        char = text[index]
        if char == delimiter:
            next_index = index + 1
            if next_index < text_length and text[next_index] == delimiter:
                current.append(delimiter)
                index += 2
                continue
            tokens.append("".join(current))
            current = []
            index += 1
            continue

        current.append(char)
        index += 1

    if current:
        tokens.append("".join(current))

    return tokens


def _decode_event_matrix(
    data_segment: bytes,
    event_count: int,
    parameter_count: int,
    datatype: str,
    parameter_bits: list[int],
    byte_order: str,
    source_name: str,
) -> np.ndarray:
    expected_values = event_count * parameter_count

    if datatype == "F":
        dtype = np.dtype(_endian_prefix(byte_order) + "f4")
    elif datatype == "D":
        dtype = np.dtype(_endian_prefix(byte_order) + "f8")
    elif datatype == "I":
        unique_bits = set(parameter_bits)
        if len(unique_bits) != 1:
            raise FCSLoadError(
                f"{source_name} uses mixed integer parameter widths, which are not yet supported."
            )
        bit_width = unique_bits.pop()
        integer_map = {
            8: "u1",
            16: "u2",
            32: "u4",
            64: "u8",
        }
        dtype_code = integer_map.get(bit_width)
        if dtype_code is None:
            raise FCSLoadError(
                f"{source_name} uses unsupported integer width '{bit_width}'."
            )
        dtype = np.dtype(_endian_prefix(byte_order) + dtype_code)
    else:
        raise FCSLoadError(f"{source_name} uses unsupported FCS datatype '{datatype}'.")

    values = np.frombuffer(data_segment, dtype=dtype, count=expected_values)
    if values.size != expected_values:
        raise FCSLoadError(
            f"{source_name} ended before all expected events could be read."
        )

    return values.reshape((event_count, parameter_count))


def _endian_prefix(byte_order: str) -> str:
    return "<" if byte_order.startswith("1") else ">"


def _required_int(metadata: dict[str, str], key: str, source_name: str) -> int:
    value = _safe_int(metadata.get(key))
    if value is None:
        raise FCSLoadError(f"{source_name} is missing required FCS field '{key}'.")
    return value


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None
