from collections import defaultdict
from pathlib import Path
from typing import Any

import viktor as vkt
from viktor.utils import memoize


def file_to_text(file: vkt.File) -> str:
    """Convert a VIKTOR file to text for memoized worker input."""
    value = file.getvalue()
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _first_matching_column(table: dict[str, Any], *candidates: str) -> Any:
    candidate_keys = {
        candidate.lower().replace(" ", "").replace("_", "")
        for candidate in candidates
    }
    for candidate in candidates:
        if candidate in table:
            return table[candidate]
    for key, value in table.items():
        normalized_key = key.lower().replace(" ", "").replace("_", "")
        if normalized_key in candidate_keys:
            return value
    return []


def _parse_reactions(scia_result: vkt.File, parent_label: str) -> dict[str, list[Any]]:
    """Parse grouped nodal reaction min/max values for a SCIA output parent."""
    result = vkt.scia.OutputFileParser.get_result(
        scia_result,
        "Reactions",
        parent=parent_label,
    )
    table = result.get("Nodal reactions", result)
    node_key = next((key for key in table if key.lower() in ("node", "name")), None)
    raw_names = list(table.get(node_key, [])) if node_key else []
    raw_rz = list(_first_matching_column(table, "R_z", "Rz", "FZ", "Fz", "rz"))

    node_rz_map: dict[str, list[float]] = defaultdict(list)
    for name, rz in zip(raw_names, raw_rz):
        try:
            node_rz_map[str(name)].append(float(rz))
        except (TypeError, ValueError):
            continue

    return {
        "node_names": list(node_rz_map.keys()),
        "rz_min": [min(values) for values in node_rz_map.values()],
        "rz_max": [max(values) for values in node_rz_map.values()],
    }


def _parse_internal_forces_2d(scia_result: vkt.File) -> dict[str, list[Any]]:
    """Parse the 2D internal forces table as JSON-safe column lists."""
    result = vkt.scia.OutputFileParser.get_result(
        scia_result,
        "2D internal forces",
        parent="Combinations - C1",
    )
    if isinstance(result, dict):
        sub_key = next(iter(result), None)
        table = result[sub_key] if sub_key else result
    else:
        table = {}

    parsed: dict[str, list[Any]] = {}
    for key, value in table.items():
        try:
            parsed[key] = [
                item if isinstance(item, (int, float, str, bool, type(None))) else str(item)
                for item in value
            ]
        except TypeError:
            parsed[key] = [value]
    return parsed


@memoize
def run_scia_analysis_results(
    *,
    input_xml: str,
    input_def: str,
    esa_template_path: str,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Run SCIA worker analysis and return serializable parsed result data."""
    scia_analysis = vkt.scia.SciaAnalysis(
        vkt.File.from_data(input_xml),
        vkt.File.from_data(input_def),
        vkt.File.from_path(Path(esa_template_path)),
    )
    scia_analysis.execute(timeout_seconds)
    scia_result = scia_analysis.get_xml_output_file()

    try:
        reactions = _parse_reactions(scia_result, "Combinations - C1")
    except Exception:
        reactions = {"node_names": [], "rz_min": [], "rz_max": []}

    try:
        internal_forces_2d = _parse_internal_forces_2d(scia_result)
    except Exception:
        internal_forces_2d = {}

    return {
        "node_names": [str(value) for value in reactions["node_names"]],
        "rz_min": [float(value) for value in reactions["rz_min"]],
        "rz_max": [float(value) for value in reactions["rz_max"]],
        "internal_forces_2d": internal_forces_2d,
    }
