from typing import Any

from pydantic import BaseModel

from agent.tools.graph_tools import (
    ComposeWorkflowGraphArgs,
    GetWorkflowPlanArgs,
    SetWorkflowPlanArgs,
    SetWorkflowProgressArgs,
    UpdateWorkflowPlanArgs,
    compose_workflow_graph_func,
    get_workflow_plan_func,
    set_workflow_plan_func,
    set_workflow_progress_func,
    update_workflow_plan_func,
)
from agent.tools.viktor_tools import (
    CptPileBearingParams,
    WindTurbineCostAnalysisParams,
    WindTurbineFoundationAnalysisParams,
    WindTurbineReinforcementParams,
    WindTurbineSelectorParams,
    run_cpt_pile_bearing_func,
    run_wind_turbine_cost_analysis_func,
    run_wind_turbine_foundation_analysis_func,
    run_wind_turbine_reinforcement_func,
    run_wind_turbine_selector_func,
)


TOOL_DISPLAY_NAMES = {
    "compose_workflow_graph": "Compose Workflow Graph",
    "get_workflow_plan": "Get Workflow Plan",
    "set_workflow_plan": "Set Workflow Plan",
    "update_workflow_plan": "Update Workflow Plan",
    "set_workflow_progress": "Set Workflow Progress",
    "run_wind_turbine_selector": "Run Wind Turbine Selector",
    "run_cpt_pile_bearing": "Run CPT Pile Bearing",
    "run_wind_turbine_foundation_analysis": "Run Foundation Analysis",
    "run_wind_turbine_reinforcement": "Run Reinforcement",
    "run_wind_turbine_cost_analysis": "Run Cost Analysis",
}


def function_tool(name: str, description: str, schema: type[BaseModel], func: Any) -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name=name,
        description=description,
        params_json_schema=schema.model_json_schema(),
        on_invoke_tool=func,
    )


def get_tools() -> list[Any]:
    return [
        function_tool(
            "compose_workflow_graph",
            "Compose a dependency graph and render it in the workflow WebView.",
            ComposeWorkflowGraphArgs,
            compose_workflow_graph_func,
        ),
        function_tool(
            "get_workflow_plan",
            "Read current plan ids and statuses. Call before update_workflow_plan.",
            GetWorkflowPlanArgs,
            get_workflow_plan_func,
        ),
        function_tool(
            "set_workflow_plan",
            "Set or replace the workflow plan shown in the graph overlay.",
            SetWorkflowPlanArgs,
            set_workflow_plan_func,
        ),
        function_tool(
            "update_workflow_plan",
            "Update existing workflow plan items by stable id.",
            UpdateWorkflowPlanArgs,
            update_workflow_plan_func,
        ),
        function_tool(
            "set_workflow_progress",
            "Set, replace, or clear execution progress below the plan.",
            SetWorkflowProgressArgs,
            set_workflow_progress_func,
        ),
        function_tool(
            "run_wind_turbine_selector",
            (
                "Run the wind turbine selector VIKTOR app. Stores turbine capacity, "
                "mast diameter, and base loads for foundation analysis."
            ),
            WindTurbineSelectorParams,
            run_wind_turbine_selector_func,
        ),
        function_tool(
            "run_cpt_pile_bearing",
            (
                "Run the CPT pile bearing VIKTOR app. Stores pile capacity, pile length, "
                "and pile diameter for foundation analysis."
            ),
            CptPileBearingParams,
            run_cpt_pile_bearing_func,
        ),
        function_tool(
            "run_wind_turbine_foundation_analysis",
            (
                "Run the wind turbine foundation SCIA Results Summary. Reads turbine "
                "loads from run_wind_turbine_selector and pile geometry from "
                "run_cpt_pile_bearing. Stores foundation params and result data."
            ),
            WindTurbineFoundationAnalysisParams,
            run_wind_turbine_foundation_analysis_func,
        ),
        function_tool(
            "run_wind_turbine_reinforcement",
            (
                "Run the reinforcement app using foundation plate thickness and "
                "governing m_xD/m_yD moments from the foundation Results Summary."
            ),
            WindTurbineReinforcementParams,
            run_wind_turbine_reinforcement_func,
        ),
        function_tool(
            "run_wind_turbine_cost_analysis",
            (
                "Run the wind turbine cost analysis app using foundation geometry and "
                "reinforcement output stored by upstream tools."
            ),
            WindTurbineCostAnalysisParams,
            run_wind_turbine_cost_analysis_func,
        ),
    ]
