from datetime import datetime
from typing import Any, Literal

import viktor as vkt
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.tools.viktor_tools.responses import (
    execution_error_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.wind_turbine_common import (
    read_json_from_storage,
    write_json_to_storage,
)


COST_OPTIMIZATION_STORAGE_KEY = "wind_turbine_cost_optimization_study"

CandidateStatus = Literal["pending", "completed", "failed", "infeasible"]
OptimizationObjective = Literal["minimize_total_cost"]
ScalarValue = str | float | int | bool | None


class OptimizationScalar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Short stable scalar name.")
    value: ScalarValue = Field(default=None, description="Scalar value.")
    unit: str | None = Field(default=None, description="Optional display unit.")
    path: str | None = Field(default=None, description="Optional source or parameter path.")


class OptimizationVariableRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Short variable name.")
    path: str = Field(..., description="VIKTOR params path for the varied value.")
    unit: str | None = Field(default=None)
    values: list[float | int | str] = Field(default_factory=list)
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None


class StartCostOptimizationStudyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_name: str | None = Field(default=None)
    objective: OptimizationObjective = "minimize_total_cost"
    candidate_budget: int = Field(default=8, ge=1)
    variables: list[OptimizationVariableRange] = Field(default_factory=list)
    fixed_inputs: list[OptimizationScalar] = Field(default_factory=list)
    notes: str | None = None
    replace_existing: bool = Field(default=False)


class CandidateDesignVariables(BaseModel):
    model_config = ConfigDict(extra="forbid")

    num_piles: int | None = None
    pile_diameter_mm: float | None = None
    pile_length_m: float | None = None
    pile_edge_distance_mm: float | None = None
    slab_diameter_m: float | None = None
    slab_thickness_m: float | None = None
    plate_edge_thickness_m: float | None = None
    pedestal_height_m: float | None = None
    tip_stiffness_kn_per_m: float | None = None
    lateral_stiffness_kn_per_m2: float | None = None
    extra_variables: list[OptimizationScalar] = Field(default_factory=list)


class CandidateOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_cost: float | None = None
    concrete_cost: float | None = None
    rebar_cost: float | None = None
    pile_cost: float | None = None
    plate_volume_m3: float | None = None
    pedestal_volume_m3: float | None = None
    rebar_mass_kg: float | None = None
    total_pile_length_m: float | None = None
    max_pile_reaction_kn: float | None = None
    min_pile_reaction_kn: float | None = None
    reinforcement_utilization: float | None = None
    extra_outputs: list[OptimizationScalar] = Field(default_factory=list)


class RecordCostOptimizationCandidateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(..., description="Stable candidate id, for example cand-001.")
    status: CandidateStatus = "completed"
    feasible: bool = True
    variables: CandidateDesignVariables = Field(default_factory=CandidateDesignVariables)
    outputs: CandidateOutputs = Field(default_factory=CandidateOutputs)
    cost: float | None = Field(default=None, description="Objective cost. Uses outputs.total_cost if omitted.")
    notes: str | None = None
    input_storage_keys: list[str] = Field(default_factory=list)
    output_storage_keys: list[str] = Field(default_factory=list)


class GetCostOptimizationStudyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_candidates: bool = True
    max_candidates: int = Field(default=50, ge=1)


class ResetCostOptimizationStudyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = Field(default=False)


class CostOptimizationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    status: CandidateStatus
    feasible: bool
    variables: CandidateDesignVariables
    outputs: CandidateOutputs
    objective_value: float | None
    notes: str | None = None
    input_storage_keys: list[str] = Field(default_factory=list)
    output_storage_keys: list[str] = Field(default_factory=list)
    recorded_at: str


class CostOptimizationStudy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage_key: str = COST_OPTIMIZATION_STORAGE_KEY
    study_name: str
    objective: OptimizationObjective
    candidate_budget: int
    variables: list[OptimizationVariableRange] = Field(default_factory=list)
    fixed_inputs: list[OptimizationScalar] = Field(default_factory=list)
    notes: str | None = None
    created_at: str
    updated_at: str
    candidates: list[CostOptimizationCandidate] = Field(default_factory=list)


def default_study_name() -> str:
    return f"Cost Optimization - {datetime.now().strftime('%Y-%m-%d %H:%M')}"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_study() -> CostOptimizationStudy:
    raw = read_json_from_storage(COST_OPTIMIZATION_STORAGE_KEY)
    return CostOptimizationStudy.model_validate(raw)


def save_study(study: CostOptimizationStudy) -> None:
    study.updated_at = now_iso()
    write_json_to_storage(COST_OPTIMIZATION_STORAGE_KEY, study.model_dump())


def try_load_study() -> CostOptimizationStudy | None:
    try:
        return load_study()
    except Exception:
        return None


def scalar_to_row(row: dict[str, Any], scalar: OptimizationScalar) -> None:
    if scalar.value is not None:
        row[scalar.name] = scalar.value


def candidate_row(candidate: CostOptimizationCandidate) -> dict[str, Any]:
    variables = candidate.variables.model_dump(exclude={"extra_variables"})
    outputs = candidate.outputs.model_dump(exclude={"extra_outputs"})
    row: dict[str, Any] = {
        "candidate_id": candidate.candidate_id,
        "status": candidate.status,
        "feasible": candidate.feasible,
        "objective_value": candidate.objective_value,
    }
    row.update({key: value for key, value in variables.items() if value is not None})
    row.update({key: value for key, value in outputs.items() if value is not None})
    for scalar in candidate.variables.extra_variables:
        scalar_to_row(row, scalar)
    for scalar in candidate.outputs.extra_outputs:
        scalar_to_row(row, scalar)
    return row


def parallel_rows(study: CostOptimizationStudy) -> list[dict[str, Any]]:
    return [candidate_row(candidate) for candidate in study.candidates]


def parallel_dimensions(rows: list[dict[str, Any]]) -> list[str]:
    dimensions: list[str] = []
    for row in rows:
        for key, value in row.items():
            if key in {"candidate_id", "status"}:
                continue
            if isinstance(value, (int, float, bool)) and key not in dimensions:
                dimensions.append(key)
    return dimensions


def best_candidate(study: CostOptimizationStudy) -> CostOptimizationCandidate | None:
    feasible = [
        candidate
        for candidate in study.candidates
        if candidate.status == "completed"
        and candidate.feasible
        and candidate.objective_value is not None
    ]
    if not feasible:
        return None
    return min(feasible, key=lambda candidate: candidate.objective_value or float("inf"))


def study_summary(study: CostOptimizationStudy) -> dict[str, Any]:
    best = best_candidate(study)
    failed_count = sum(1 for candidate in study.candidates if candidate.status == "failed")
    infeasible_count = sum(
        1
        for candidate in study.candidates
        if candidate.status == "infeasible" or not candidate.feasible
    )
    return {
        "study_name": study.study_name,
        "objective": study.objective,
        "candidate_budget": study.candidate_budget,
        "candidate_count": len(study.candidates),
        "failed_count": failed_count,
        "infeasible_count": infeasible_count,
        "best_candidate_id": best.candidate_id if best else None,
        "best_objective_value": best.objective_value if best else None,
    }


async def start_cost_optimization_study_func(context: Any, args: str) -> str:
    try:
        payload = StartCostOptimizationStudyArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="start_cost_optimization_study",
            message="Invalid cost optimization study arguments.",
            error=exc,
            retry_tool="start_cost_optimization_study",
        )

    existing = try_load_study()
    if existing and not payload.replace_existing:
        return tool_response(
            "study_exists",
            message="A cost optimization study already exists.",
            storage_key=COST_OPTIMIZATION_STORAGE_KEY,
            summary=study_summary(existing),
            retry_action={
                "tool": "start_cost_optimization_study",
                "reason": "Retry with replace_existing=true to overwrite the active study.",
            },
        )

    timestamp = now_iso()
    study = CostOptimizationStudy(
        study_name=(payload.study_name or default_study_name()).strip() or default_study_name(),
        objective=payload.objective,
        candidate_budget=payload.candidate_budget,
        variables=payload.variables,
        fixed_inputs=payload.fixed_inputs,
        notes=payload.notes,
        created_at=timestamp,
        updated_at=timestamp,
    )
    try:
        save_study(study)
    except Exception as exc:
        return execution_error_response(
            tool="start_cost_optimization_study",
            message="Could not create cost optimization study storage.",
            error=exc,
        )

    return tool_response(
        "completed",
        message="Started cost optimization study.",
        storage_key=COST_OPTIMIZATION_STORAGE_KEY,
        summary=study_summary(study),
        variable_count=len(study.variables),
        fixed_input_count=len(study.fixed_inputs),
    )


async def record_cost_optimization_candidate_func(context: Any, args: str) -> str:
    try:
        payload = RecordCostOptimizationCandidateArgs.model_validate_json(args or "{}")
        study = load_study()
    except FileNotFoundError:
        return tool_response(
            "needs_prerequisite",
            tool="record_cost_optimization_candidate",
            message="No active cost optimization study exists.",
            missing_storage_key=COST_OPTIMIZATION_STORAGE_KEY,
            retry_action={
                "tool": "start_cost_optimization_study",
                "reason": "Start the study before recording candidates.",
            },
        )
    except ValidationError as exc:
        return validation_error_response(
            tool="record_cost_optimization_candidate",
            message="Invalid optimization candidate arguments.",
            error=exc,
            retry_tool="record_cost_optimization_candidate",
        )
    except Exception as exc:
        return execution_error_response(
            tool="record_cost_optimization_candidate",
            message="Could not read cost optimization study storage.",
            error=exc,
        )

    objective_value = payload.cost
    if objective_value is None:
        objective_value = payload.outputs.total_cost

    candidate = CostOptimizationCandidate(
        candidate_id=payload.candidate_id,
        status=payload.status,
        feasible=payload.feasible,
        variables=payload.variables,
        outputs=payload.outputs,
        objective_value=objective_value,
        notes=payload.notes,
        input_storage_keys=payload.input_storage_keys,
        output_storage_keys=payload.output_storage_keys,
        recorded_at=now_iso(),
    )

    existing_ids = {item.candidate_id for item in study.candidates}
    if candidate.candidate_id in existing_ids:
        study.candidates = [
            candidate if item.candidate_id == candidate.candidate_id else item
            for item in study.candidates
        ]
    else:
        study.candidates.append(candidate)

    try:
        save_study(study)
    except Exception as exc:
        return execution_error_response(
            tool="record_cost_optimization_candidate",
            message="Could not save optimization candidate.",
            error=exc,
        )

    rows = parallel_rows(study)
    return tool_response(
        "completed",
        message="Recorded optimization candidate.",
        storage_key=COST_OPTIMIZATION_STORAGE_KEY,
        candidate_id=candidate.candidate_id,
        objective_value=candidate.objective_value,
        summary=study_summary(study),
        parallel_coordinates_row=candidate_row(candidate),
        parallel_coordinates_dimensions=parallel_dimensions(rows),
    )


async def get_cost_optimization_study_func(context: Any, args: str) -> str:
    try:
        payload = GetCostOptimizationStudyArgs.model_validate_json(args or "{}")
        study = load_study()
    except FileNotFoundError:
        return tool_response(
            "needs_prerequisite",
            tool="get_cost_optimization_study",
            message="No active cost optimization study exists.",
            missing_storage_key=COST_OPTIMIZATION_STORAGE_KEY,
            retry_action={
                "tool": "start_cost_optimization_study",
                "reason": "Start the study before reading optimization results.",
            },
        )
    except ValidationError as exc:
        return validation_error_response(
            tool="get_cost_optimization_study",
            message="Invalid get optimization study arguments.",
            error=exc,
            retry_tool="get_cost_optimization_study",
        )
    except Exception as exc:
        return execution_error_response(
            tool="get_cost_optimization_study",
            message="Could not read cost optimization study.",
            error=exc,
        )

    rows = parallel_rows(study)
    candidates = study.candidates[: payload.max_candidates] if payload.include_candidates else []
    best = best_candidate(study)
    return tool_response(
        "completed",
        storage_key=COST_OPTIMIZATION_STORAGE_KEY,
        summary=study_summary(study),
        variables=[variable.model_dump() for variable in study.variables],
        fixed_inputs=[item.model_dump() for item in study.fixed_inputs],
        best_candidate=best.model_dump() if best else None,
        candidates=[candidate.model_dump() for candidate in candidates],
        parallel_coordinates_rows=rows[: payload.max_candidates],
        parallel_coordinates_dimensions=parallel_dimensions(rows),
    )


async def reset_cost_optimization_study_func(context: Any, args: str) -> str:
    try:
        payload = ResetCostOptimizationStudyArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="reset_cost_optimization_study",
            message="Invalid reset optimization study arguments.",
            error=exc,
            retry_tool="reset_cost_optimization_study",
        )

    if not payload.confirm:
        return tool_response(
            "confirmation_required",
            message="Set confirm=true to clear the active cost optimization study.",
        )

    try:
        vkt.Storage().delete(COST_OPTIMIZATION_STORAGE_KEY, scope="entity")
    except Exception:
        pass

    return tool_response(
        "completed",
        message="Cost optimization study cleared.",
        cleared_storage_key=COST_OPTIMIZATION_STORAGE_KEY,
    )
