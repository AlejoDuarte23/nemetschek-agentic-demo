import json
from typing import Any

import viktor as vkt

from agent.tools.viktor_tools.sdk_compute import select_result_key


WIND_TURBINE_SELECTOR_STORAGE_KEY = "wind_turbine_selector_data"
CPT_PILE_BEARING_STORAGE_KEY = "cpt_pile_bearing_data"
FOUNDATION_STORAGE_KEY = "wind_turbine_foundation_data"
FOUNDATION_PARAMS_STORAGE_KEY = "wind_turbine_foundation_params"
REINFORCEMENT_STORAGE_KEY = "wind_turbine_reinforcement_data"
COST_STORAGE_KEY = "wind_turbine_cost_data"


def write_json_to_storage(key: str, payload: Any) -> None:
    vkt.Storage().set(
        key,
        data=vkt.File.from_data(json.dumps(payload, indent=2)),
        scope="entity",
    )


def read_json_from_storage(key: str) -> Any:
    stored_file = vkt.Storage().get(key, scope="entity")
    if not stored_file:
        raise FileNotFoundError(f"Missing VIKTOR Storage key '{key}'.")
    return json.loads(stored_file.getvalue_binary().decode("utf-8"))


def leaf_value(item: dict[str, Any]) -> Any:
    return item.get("value", item.get("display_value"))


def flatten_data_items(items: Any) -> dict[str, Any]:
    flattened: dict[str, Any] = {}

    def add_alias(alias: Any, value: Any) -> None:
        if alias is None:
            return
        text = str(alias).strip()
        if text:
            flattened[text] = value
            flattened[text.lower()] = value

    def walk(value: Any, path: list[str]) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item, path)
            return
        if not isinstance(value, dict):
            return

        key = value.get("key")
        label = value.get("label")
        next_path = path + [str(key or label)] if key or label else path
        children = value.get("children") or []

        if not children and ("value" in value or "display_value" in value):
            item_value = leaf_value(value)
            add_alias(key, item_value)
            add_alias(label, item_value)
            if next_path:
                add_alias(".".join(next_path), item_value)

        walk(children, next_path)

    walk(items, [])
    return flattened


def get_data_value(data: Any, *keys: str, default: Any = None) -> Any:
    flattened = flatten_data_items(data)
    for key in keys:
        if key in flattened:
            return flattened[key]
        lower_key = key.lower()
        if lower_key in flattened:
            return flattened[lower_key]
    return default


def get_number(data: Any, *keys: str, default: float | None = None) -> float:
    value = get_data_value(data, *keys, default=default)
    if value is None:
        raise ValueError(f"Missing numeric value for any of: {', '.join(keys)}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected a numeric value for {keys[0]} but got {value!r}.") from exc


def get_int(data: Any, *keys: str, default: int | None = None) -> int:
    return int(round(get_number(data, *keys, default=default)))


def rounded_positive_int(value: float, *, default: int) -> int:
    try:
        rounded = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(1, rounded)


def select_and_store_result(
    *,
    result: dict[str, Any],
    result_key: str,
    storage_key: str,
) -> Any:
    payload = select_result_key(result, result_key)
    write_json_to_storage(storage_key, payload)
    return payload
