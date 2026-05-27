import json
from typing import Any, Literal

import viktor as vkt
from pydantic import BaseModel, ConfigDict, ValidationError

from agent.tools.viktor_tools.responses import (
    execution_error_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.sdk_compute import ViktorSdkComputeClient
from agent.tools.viktor_tools.wind_turbine_common import (
    FOUNDATION_PARAMS_STORAGE_KEY,
    read_json_from_storage,
    write_json_to_storage,
)
from agent.tools.viktor_tools.workflow_entities import (
    needs_workflow_run_response,
    read_last_saved_params,
    resolve_workflow_entity,
)


FOUNDATION_MOMENT_CONTOURS_STORAGE_KEY = "foundation_moment_contours_plotly"
SHOW_FOUNDATION_MOMENT_CONTOURS_KEY = "show_foundation_moment_contours"
FOUNDATION_MOMENT_CONTOURS_METHOD = "view_mxd_plus_plot"


class FoundationMomentContoursParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShowHideFoundationMomentContoursParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["show", "hide"]


def _decode_figure(figure: str | dict[str, Any]) -> dict[str, Any]:
    decoded = json.loads(figure) if isinstance(figure, str) else figure
    if not isinstance(decoded, dict):
        raise ValueError("Plotly figure payload is not a JSON object.")
    if not isinstance(decoded.get("data"), list):
        raise ValueError("Plotly figure payload does not contain a data list.")
    if not isinstance(decoded.get("layout"), dict):
        raise ValueError("Plotly figure payload does not contain a layout object.")
    return decoded


def summarize_plotly_figure(figure: str | dict[str, Any]) -> dict[str, Any]:
    decoded = _decode_figure(figure)
    data = decoded.get("data", [])
    layout = decoded.get("layout", {})
    title = layout.get("title")
    if isinstance(title, dict):
        title = title.get("text")

    trace_types = sorted(
        {
            str(trace.get("type", "unknown"))
            for trace in data
            if isinstance(trace, dict)
        }
    )
    trace_names = [
        trace.get("name")
        for trace in data
        if isinstance(trace, dict) and trace.get("name")
    ]
    return {
        "title": title,
        "trace_count": len(data),
        "trace_types": trace_types,
        "trace_names": trace_names,
        "figure_json_bytes": len(figure.encode("utf-8")) if isinstance(figure, str) else None,
    }


async def run_foundation_moment_contours_func(context: Any, args: str) -> str:
    try:
        FoundationMomentContoursParams.model_validate_json(args or "{}")
        target = resolve_workflow_entity("foundation_analysis")
    except ValidationError as exc:
        return validation_error_response(
            tool="run_foundation_moment_contours",
            message="Invalid moment contour arguments.",
            error=exc,
            retry_tool="run_foundation_moment_contours",
        )
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="run_foundation_moment_contours",
            node_id="foundation_analysis",
        )

    try:
        try:
            params = read_json_from_storage(FOUNDATION_PARAMS_STORAGE_KEY)
        except FileNotFoundError:
            params = read_last_saved_params(target)

        result = ViktorSdkComputeClient().compute_method(
            workspace_id=target.workspace_id,
            entity_id=target.entity_id,
            method_name=FOUNDATION_MOMENT_CONTOURS_METHOD,
            params=params,
            timeout=300,
        )
        plotly_payload = result.get("plotly")
        if not isinstance(plotly_payload, dict):
            raise ValueError("Moment contour result does not contain a plotly object.")
        figure = plotly_payload.get("figure")
        if not isinstance(figure, (str, dict)):
            raise ValueError("Moment contour plotly result does not contain a figure.")

        summary = summarize_plotly_figure(figure)
        write_json_to_storage(
            FOUNDATION_MOMENT_CONTOURS_STORAGE_KEY,
            {
                "figure": figure if isinstance(figure, str) else json.dumps(figure),
                "summary": summary,
                "entity_id": target.entity_id,
                "entity_url": target.url,
                "method_name": FOUNDATION_MOMENT_CONTOURS_METHOD,
            },
        )
        vkt.Storage().set(
            SHOW_FOUNDATION_MOMENT_CONTOURS_KEY,
            data=vkt.File.from_data("show"),
            scope="entity",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_foundation_moment_contours",
            message="Could not render the foundation moment contour Plotly view.",
            error=exc,
        )

    return tool_response(
        "completed",
        message="Rendered foundation 2D moment contour plots in the WebView.",
        entity_id=target.entity_id,
        entity_url=target.url,
        method_name=FOUNDATION_MOMENT_CONTOURS_METHOD,
        params_storage_key=FOUNDATION_PARAMS_STORAGE_KEY,
        storage_key=FOUNDATION_MOMENT_CONTOURS_STORAGE_KEY,
        visibility_storage_key=SHOW_FOUNDATION_MOMENT_CONTOURS_KEY,
        summary=summary,
    )


async def show_hide_foundation_moment_contours_func(context: Any, args: str) -> str:
    try:
        payload = ShowHideFoundationMomentContoursParams.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="show_hide_foundation_moment_contours",
            message="Invalid foundation moment contour visibility arguments.",
            error=exc,
            retry_tool="show_hide_foundation_moment_contours",
        )

    if payload.action == "show":
        try:
            vkt.Storage().get(FOUNDATION_MOMENT_CONTOURS_STORAGE_KEY, scope="entity")
        except Exception:
            return tool_response(
                "needs_prerequisite",
                tool="show_hide_foundation_moment_contours",
                message="No foundation moment contour plot exists to display.",
                missing_storage_key=FOUNDATION_MOMENT_CONTOURS_STORAGE_KEY,
                retry_action={
                    "tool": "run_foundation_moment_contours",
                    "reason": "Run and store the SCIA moment contour Plotly figure first.",
                },
            )

    try:
        vkt.Storage().set(
            SHOW_FOUNDATION_MOMENT_CONTOURS_KEY,
            data=vkt.File.from_data(payload.action),
            scope="entity",
        )
    except Exception as exc:
        return execution_error_response(
            tool="show_hide_foundation_moment_contours",
            message="Could not update foundation moment contour visibility.",
            error=exc,
        )

    return tool_response(
        "completed",
        message=f"Foundation moment contour view set to {payload.action}.",
        visibility=payload.action,
        storage_key=SHOW_FOUNDATION_MOMENT_CONTOURS_KEY,
    )
