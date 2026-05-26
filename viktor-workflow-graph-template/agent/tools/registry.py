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
from agent.tools.optimization_tools import (
    GetCostOptimizationStudyArgs,
    RecordCostOptimizationCandidateArgs,
    ResetCostOptimizationStudyArgs,
    StartCostOptimizationStudyArgs,
    get_cost_optimization_study_func,
    record_cost_optimization_candidate_func,
    reset_cost_optimization_study_func,
    start_cost_optimization_study_func,
)
from agent.tools.skill_tools import (
    ListSkillFilesArgs,
    ReadSkillFileArgs,
    list_skill_files_func,
    read_skill_file_func,
)
from agent.tools.viktor_tools import (
    CptPileBearingParams,
    CreateWorkflowEntityDirectoryArgs,
    GetWorkflowEntityDirectoryArgs,
    ResetWorkflowEntityDirectoryArgs,
    SetParamsInNodeArgs,
    WindTurbineCostAnalysisParams,
    WindTurbineFoundationAnalysisParams,
    WindTurbineReinforcementParams,
    WindTurbineSelectorParams,
    create_workflow_entity_directory_func,
    get_workflow_entity_directory_func,
    reset_workflow_entity_directory_func,
    run_cpt_pile_bearing_func,
    run_wind_turbine_cost_analysis_func,
    run_wind_turbine_foundation_analysis_func,
    run_wind_turbine_reinforcement_func,
    run_wind_turbine_selector_func,
    set_params_in_node_func,
)


TOOL_DISPLAY_NAMES = {
    "compose_workflow_graph": "Compose Workflow Graph",
    "get_workflow_plan": "Get Workflow Plan",
    "set_workflow_plan": "Set Workflow Plan",
    "update_workflow_plan": "Update Workflow Plan",
    "set_workflow_progress": "Set Workflow Progress",
    "list_skill_files": "List Skill Files",
    "read_skill_file": "Read Skill File",
    "start_cost_optimization_study": "Start Cost Optimization",
    "record_cost_optimization_candidate": "Record Optimization Candidate",
    "get_cost_optimization_study": "Get Cost Optimization",
    "reset_cost_optimization_study": "Reset Cost Optimization",
    "create_workflow_entity_directory": "Create Workflow Entities",
    "get_workflow_entity_directory": "Get Workflow Entities",
    "set_params_in_node": "Set Params in Node",
    "reset_workflow_entity_directory": "Reset Workflow Entities",
    "run_wind_turbine_selector": "Run Wind Turbine Selector",
    "run_cpt_pile_bearing": "Run CPT Pile Bearing",
    "run_wind_turbine_foundation_analysis": "Run Foundation Analysis",
    "run_wind_turbine_reinforcement": "Run Reinforcement",
    "run_wind_turbine_cost_analysis": "Run Cost Analysis",
}


def function_tool(
    name: str,
    description: str,
    schema: type[BaseModel],
    func: Any,
    *,
    strict_json_schema: bool = True,
) -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name=name,
        description=description,
        params_json_schema=schema.model_json_schema(),
        on_invoke_tool=func,
        strict_json_schema=strict_json_schema,
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
            "list_skill_files",
            "List local optimization skill files that can guide workflow and cost optimization requests.",
            ListSkillFilesArgs,
            list_skill_files_func,
        ),
        function_tool(
            "read_skill_file",
            "Read a local optimization skill file before answering or planning optimization workflows.",
            ReadSkillFileArgs,
            read_skill_file_func,
        ),
        function_tool(
            "start_cost_optimization_study",
            "Create or replace append-only storage for a wind turbine foundation cost optimization study.",
            StartCostOptimizationStudyArgs,
            start_cost_optimization_study_func,
        ),
        function_tool(
            "record_cost_optimization_candidate",
            (
                "Append or replace one evaluated optimization candidate with design "
                "variables, result metrics, feasibility, and objective cost."
            ),
            RecordCostOptimizationCandidateArgs,
            record_cost_optimization_candidate_func,
            strict_json_schema=False,
        ),
        function_tool(
            "get_cost_optimization_study",
            "Read the active optimization study, best candidate, and parallel-coordinate rows.",
            GetCostOptimizationStudyArgs,
            get_cost_optimization_study_func,
        ),
        function_tool(
            "reset_cost_optimization_study",
            "Clear the active cost optimization study after explicit confirmation.",
            ResetCostOptimizationStudyArgs,
            reset_cost_optimization_study_func,
        ),
        function_tool(
            "create_workflow_entity_directory",
            (
                "Create fresh sibling VIKTOR entities for selected known workflow "
                "nodes, save the active entity directory, and compose the graph with "
                "the new entity URLs."
            ),
            CreateWorkflowEntityDirectoryArgs,
            create_workflow_entity_directory_func,
        ),
        function_tool(
            "get_workflow_entity_directory",
            "Return the active workflow run entity IDs, URLs, methods, and storage keys.",
            GetWorkflowEntityDirectoryArgs,
            get_workflow_entity_directory_func,
        ),
        function_tool(
            "set_params_in_node",
            (
                "Set or deep-merge a JSON params object into the saved params of an "
                "active workflow node. Use after building the downstream params object."
            ),
            SetParamsInNodeArgs,
            set_params_in_node_func,
            strict_json_schema=False,
        ),
        function_tool(
            "reset_workflow_entity_directory",
            "Clear the active workflow entity directory after explicit confirmation.",
            ResetWorkflowEntityDirectoryArgs,
            reset_workflow_entity_directory_func,
        ),
        function_tool(
            "run_wind_turbine_selector",
            (
                "Read saved params from the active workflow selector entity, run the "
                "wind turbine selector VIKTOR app, and store turbine capacity, mast "
                "diameter, and base loads for foundation analysis."
            ),
            WindTurbineSelectorParams,
            run_wind_turbine_selector_func,
        ),
        function_tool(
            "run_cpt_pile_bearing",
            (
                "Read saved params from the active workflow CPT entity, run the CPT "
                "pile bearing VIKTOR app, and store pile capacity, pile length, and "
                "pile diameter for foundation analysis. Use chat-provided coordinates "
                "when exact, or wait for the user to save a map-selected CPT location "
                "in the VIKTOR app."
            ),
            CptPileBearingParams,
            run_cpt_pile_bearing_func,
        ),
        function_tool(
            "run_wind_turbine_foundation_analysis",
            (
                "Read saved params from the active workflow foundation entity, patch "
                "turbine loads and CPT pile geometry, run the SCIA Results Summary, "
                "and store foundation params and result data."
            ),
            WindTurbineFoundationAnalysisParams,
            run_wind_turbine_foundation_analysis_func,
        ),
        function_tool(
            "run_wind_turbine_reinforcement",
            (
                "Read saved params from the active workflow reinforcement entity, "
                "patch foundation plate thickness and governing m_xD/m_yD moments, "
                "and run the reinforcement app."
            ),
            WindTurbineReinforcementParams,
            run_wind_turbine_reinforcement_func,
        ),
        function_tool(
            "run_wind_turbine_cost_analysis",
            (
                "Read saved params from the active workflow cost entity, patch "
                "foundation geometry and reinforcement output, and run the cost app."
            ),
            WindTurbineCostAnalysisParams,
            run_wind_turbine_cost_analysis_func,
        ),
    ]
