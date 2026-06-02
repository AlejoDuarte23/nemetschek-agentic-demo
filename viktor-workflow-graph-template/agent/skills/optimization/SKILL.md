# Cost Optimization Workflow

Use this skill when the user asks to optimize, minimize cost, compare design alternatives, run a design sweep, or find the best wind turbine foundation configuration.

## Goal

Find the lowest-cost feasible configuration by varying selected foundation design variables while keeping user-defined and upstream parameters fixed.

## Fixed Inputs

Keep these fixed unless the user explicitly asks to vary them:

- Turbine selection output: mast diameter, vertical load, horizontal load, overturning moment.
- Soil/CPT setup: selected CPT location and pile type/shape assumptions.
- Foundation setup: initial/default pile length and pile diameter for the first SCIA run. The final pile length is patched after CPT required-depth sizing with `set_params_in_node`.
- Cost rates: concrete, reinforcement, pile install, and pile material rates.
- User constraints: minimum pile count, maximum pile count, available pile diameters, geometric limits, SCIA template availability.

## Common Variables

Good first-pass variables are:

- `step_geo.sec_plate.slab_diameter`
- optionally `step_geo.sec_piles.pile_diameter` when the user allows changing pile diameter

This foundation app is a round concrete plate with piles in a circular layout. Do not use rectangular grid fields such as `pile_layout.rows`, `pile_layout.cols`, `plate.length`, `plate.width`, `spacing_x`, or `spacing_y`.

Do not vary `step_geo.sec_piles.num_piles` by default when the starting pile count is already high. Increasing slab diameter increases the pile ring radius and generally reduces axial pile reactions from overturning for the same pile count.

Do not treat pile length as an upstream variable by default. For each candidate, run foundation first with the current/default pile length to get reactions, then run `run_cpt_pile_bearing` with `view_required_depth`. The CPT tool uses the candidate's maximum pile reaction and pile diameter and returns the required pile length; the agent must call `set_params_in_node` to patch that length back into the foundation params for cost without rerunning SCIA.

Secondary variables can be added after the first sweep if needed:

- `step_geo.sec_plate.slab_thickness`
- `step_geo.sec_plate.plate_edge_thickness`
- `step_geo.sec_piles.pile_edge_distance`
- `step_geo_tech.sec_tip.tip_stiffness`
- `step_geo_tech.sec_lateral.lateral_stiffness`

## Loop

1. Create a fresh entity-backed workflow graph immediately with `create_workflow_entity_directory`.
   - Include `cost_analysis`; dependencies will add `wind_turbine_selector`, `foundation_analysis`, `cpt_pile_bearing`, and `reinforcement`.
   - Use `replace_existing=true` so the graph uses newly created sibling entities for this optimization run.
   - Do this before asking for turbine model, CPT coordinates, budget, or variable ranges.
2. Show the workflow graph/node URLs and tell the user to go through the workflow. Offer two input paths:
   - Chat setup: ask for turbine model, foundation geometry/stiffness, exact CPT coordinates if known, and CPT pile type/shape assumptions, then run the typed tools in sequence.
   - Manual setup: show the generated VIKTOR app URLs and ask the user to save inputs there, then call `get_params_in_node` before running user-edited nodes.
3. Run `run_wind_turbine_selector`.
   - Call `set_params_in_node` for `foundation_analysis` with the selector mast diameter and base loads.
4. For CPT setup, prefer chat coordinates only when the user knows the exact location. If the user needs to see the map, ask them to pick or confirm the CPT point in the CPT app and save it. Do not run `run_cpt_pile_bearing` until after the candidate foundation analysis has produced maximum pile reaction.
5. Start a cost optimization study with `start_cost_optimization_study`.
6. For each candidate:
   - Build the candidate foundation params, including slab geometry and any allowed pile diameter change.
   - Call `set_params_in_node` for `foundation_analysis`.
   - Run `run_wind_turbine_foundation_analysis`.
   - Call `set_params_in_node` for `cpt_pile_bearing` with maximum pile reaction and pile diameter.
   - Call `set_params_in_node` for `reinforcement` with the two governing `m_xD` load combinations, including labels `Min m_xD+` and `Max m_xD-`.
   - Run `run_cpt_pile_bearing`; it calculates required pile depth from max pile reaction.
   - Call `set_params_in_node` for `foundation_analysis` with the required pile length returned by CPT. Do not rerun SCIA.
   - Run `run_wind_turbine_reinforcement`.
   - Run `run_wind_turbine_cost_analysis`.
   - Call `record_cost_optimization_candidate` with variables, result metrics, feasibility, and total cost.
7. Read the study with `get_cost_optimization_study`.
8. Call `show_hide_optimization_results` with `action="show"` so the Optimization Results WebView displays the candidate table and parallel-coordinate plot.
9. Report the best feasible candidate and mention the number of failed or infeasible candidates.

## Candidate Isolation

Run candidates sequentially on the same workflow entities. Do not create a new foundation, reinforcement, or cost entity for every candidate.

The latest saved params and latest storage outputs are overwritten as each candidate runs. That is expected and is not a problem for this sequential sweep. `record_cost_optimization_candidate` stores the candidate snapshot used for comparison, so record each candidate immediately after its cost result is available, before moving to the next candidate.

Do not warn that the same downstream entity makes the cost outputs unreliable. That warning does not apply to this workflow because there is no parallel candidate execution.

## Candidate Budget

Keep early optimization loops small. Prefer 3 to 8 candidates unless the user asks for a larger sweep.

Use coarse sweeps first, then refine around the best region. For example:

- Plate diameter: 18, 20, 22 m
- Pile diameter, only when allowed: 400, 500, 600 mm

For every candidate, CPT required-depth sizing runs after foundation analysis because it needs the candidate's maximum pile reaction. The resulting pile length is used downstream for cost and saved back into the foundation app through `set_params_in_node`, but the same candidate does not rerun SCIA after that patch unless the user explicitly requests a second SCIA pass.

Avoid combinatorial explosions. Ask for a candidate budget when the requested ranges create too many combinations.

## Feasibility

Mark a candidate infeasible if:

- Foundation analysis fails.
- SCIA template or worker output is missing.
- Pile reactions exceed available pile capacity.
- Reinforcement design fails or has unacceptable utilization.
- Cost output is missing.

Failed candidates should still be recorded with status `failed` or `infeasible` and a short note.

## Parallel Coordinates

The optimization storage keeps one flattened row per candidate. Each row should contain:

- candidate id
- status and feasibility
- varied design variables
- foundation metrics
- reinforcement metrics
- cost metrics
- objective value
- required pile length and reinforcement mass per m3 when available

Use `get_cost_optimization_study` to retrieve `parallel_coordinates_rows` and `parallel_coordinates_dimensions`.

`record_cost_optimization_candidate` accepts flat or nested variables and outputs. Prefer flat keys that match the actual app, for example `num_piles`, `slab_diameter_m`, and `slab_thickness_m`.

Use `show_hide_optimization_results` with `action="show"` after candidates are recorded. Use `action="hide"` only when the user asks to close the optimization results view.
