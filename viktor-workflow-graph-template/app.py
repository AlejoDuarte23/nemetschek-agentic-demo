import json

import viktor as vkt
from dotenv import load_dotenv

from agent.runner import AgentContext, workflow_agent_sync_stream
from agent.tools.viktor_tools.foundation_moment_contours import (
    FOUNDATION_MOMENT_CONTOURS_STORAGE_KEY,
    SHOW_FOUNDATION_MOMENT_CONTOURS_KEY,
)
from agent.tools.optimization_tools import SHOW_OPTIMIZATION_RESULTS_KEY
from agent.tools.optimization_tools.cost_optimization import (
    COST_OPTIMIZATION_STORAGE_KEY,
    CostOptimizationStudy,
    best_candidate,
    parallel_dimensions,
    parallel_rows,
    study_summary,
)
from workflow_graph.optimization_results_viewer import OptimizationResultsViewer
from workflow_graph.plotly_figure_viewer import PlotlyFigureViewer
from workflow_graph.state import delete_canvas_state, load_canvas_state
from workflow_graph.viewer import WorkflowViewer


load_dotenv()


def get_optimization_results_visibility(params, **kwargs) -> bool:
    if not params.chat:
        try:
            vkt.Storage().delete(SHOW_OPTIMIZATION_RESULTS_KEY, scope="entity")
        except Exception:
            pass
        return False

    try:
        return vkt.Storage().get(
            SHOW_OPTIMIZATION_RESULTS_KEY,
            scope="entity",
        ).getvalue() == "show"
    except Exception:
        return False


def get_foundation_moment_contours_visibility(params, **kwargs) -> bool:
    if not params.chat:
        try:
            vkt.Storage().delete(SHOW_FOUNDATION_MOMENT_CONTOURS_KEY, scope="entity")
        except Exception:
            pass
        return False

    try:
        visible = (
            vkt.Storage()
            .get(SHOW_FOUNDATION_MOMENT_CONTOURS_KEY, scope="entity")
            .getvalue()
            == "show"
        )
        vkt.Storage().get(FOUNDATION_MOMENT_CONTOURS_STORAGE_KEY, scope="entity")
        return visible
    except Exception:
        return False


def _empty_html(message: str = "") -> str:
    body = ""
    if message:
        body = (
            "<div style='display:grid;place-items:center;min-height:100vh;"
            "font-family:system-ui,sans-serif;color:#64748b;background:#f8fafc;'>"
            f"{message}</div>"
        )
    return (
        "<!doctype html><html><head><style>"
        "body{margin:0;background:#fff;}"
        "</style></head><body>"
        f"{body}"
        "</body></html>"
    )


class Parametrization(vkt.Parametrization):
    title = vkt.Text(""" # Workflow Graph Agent
Build a workflow graph, run VIKTOR-backed tools, and keep intermediate results in entity storage."""
    )
    chat = vkt.Chat("", method="call_llm")


class Controller(vkt.Controller):
    parametrization = Parametrization

    def call_llm(self, params, entity_id=None, workspace_id=None, **kwargs):
        if not params.chat:
            return None

        messages = params.chat.get_messages()
        chat_history = [
            {"role": message["role"], "content": message["content"]}
            for message in messages
        ]
        stream = workflow_agent_sync_stream(
            chat_history,
            context=AgentContext(entity_id=entity_id, workspace_id=workspace_id),
            show_tool_progress=True,
        )
        return vkt.ChatResult(params.chat, stream)

    @vkt.WebView("Workflow Graph", width=100)
    def workflow_view(self, params, **kwargs):
        if not params.chat:
            delete_canvas_state()

        canvas_state = load_canvas_state()
        if canvas_state:
            return vkt.WebResult(html=WorkflowViewer(lambda: canvas_state).write())

        return vkt.WebResult(html=_empty_html())

    @vkt.WebView(
        "Optimization Results",
        width=100,
        visible=get_optimization_results_visibility,
    )
    def optimization_results_view(self, params, **kwargs):
        try:
            stored_file = vkt.Storage().get(
                COST_OPTIMIZATION_STORAGE_KEY,
                scope="entity",
            )
            raw = json.loads(stored_file.getvalue_binary().decode("utf-8"))
            study = CostOptimizationStudy.model_validate(raw)
            rows = parallel_rows(study)
            dimensions = parallel_dimensions(rows)
            best = best_candidate(study)
            html = OptimizationResultsViewer(
                summary=study_summary(study),
                rows=rows,
                dimensions=dimensions,
                best_candidate_id=best.candidate_id if best else None,
            ).write()
            return vkt.WebResult(html=html)
        except Exception:
            return vkt.WebResult(
                html=_empty_html("No optimization results are available yet.")
            )

    @vkt.WebView(
        "2D Moment Contour Plots",
        width=100,
        visible=get_foundation_moment_contours_visibility,
    )
    def foundation_moment_contours_view(self, params, **kwargs):
        try:
            stored_file = vkt.Storage().get(
                FOUNDATION_MOMENT_CONTOURS_STORAGE_KEY,
                scope="entity",
            )
            raw = json.loads(stored_file.getvalue_binary().decode("utf-8"))
            return vkt.WebResult(
                html=PlotlyFigureViewer(
                    figure=raw["figure"],
                    title="2D Moment Contour Plots",
                ).write()
            )
        except Exception:
            return vkt.WebResult(
                html=_empty_html("No moment contour plot is available yet.")
            )
