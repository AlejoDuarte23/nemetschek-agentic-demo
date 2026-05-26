# Cost Optimization Workflow

Use this skill when the user asks to optimize, minimize cost, compare design alternatives, run a design sweep, or find the best wind turbine foundation configuration.

## Goal

Find the lowest-cost feasible configuration by varying selected foundation design variables while keeping user-defined and upstream parameters fixed.

## Fixed Inputs

Keep these fixed unless the user explicitly asks to vary them:

- Turbine selection output: mast diameter, vertical load, horizontal load, overturning moment.
- Soil/CPT output: selected CPT location, pile length, pile diameter, and bearing capacity.
- Cost rates: concrete, reinforcement, pile install, and pile material rates.
- User constraints: minimum pile count, maximum pile count, available pile diameters, geometric limits, SCIA template availability.

## Common Variables

Good first-pass variables are:

- `step_geo.sec_piles.num_piles`
- `step_geo.sec_piles.pile_edge_distance`
- `step_geo.sec_plate.slab_diameter`
- `step_geo.sec_plate.slab_thickness`
- `step_geo.sec_plate.plate_edge_thickness`
- `step_geo.sec_plate.pedestal_height`
- `step_geo_tech.sec_tip.tip_stiffness`
- `step_geo_tech.sec_lateral.lateral_stiffness`

This foundation app is a round concrete plate with piles in a circular layout. Do not use rectangular grid fields such as `pile_layout.rows`, `pile_layout.cols`, `plate.length`, `plate.width`, `spacing_x`, or `spacing_y`.

Only vary `pile_length` or `pile_diameter` when the user allows changing the CPT/pile design assumptions. Otherwise treat them as soil-output values from the CPT app.

## Loop

1. Make sure a workflow entity directory exists for the needed nodes.
2. Ask the user to save upstream inputs in the VIKTOR apps.
3. Run `run_wind_turbine_selector`.
4. Ask the user to confirm the CPT coordinates/location in the CPT app, then run `run_cpt_pile_bearing`.
5. Start a cost optimization study with `start_cost_optimization_study`.
6. For each candidate:
   - Build the candidate foundation params.
   - Call `set_params_in_node` for `foundation_analysis`.
   - Run `run_wind_turbine_foundation_analysis`.
   - Run `run_wind_turbine_reinforcement`.
   - Run `run_wind_turbine_cost_analysis`.
   - Call `record_cost_optimization_candidate` with variables, result metrics, feasibility, and total cost.
7. Read the study with `get_cost_optimization_study`.
8. Report the best feasible candidate and mention the number of failed or infeasible candidates.

## Candidate Budget

Keep early optimization loops small. Prefer 3 to 8 candidates unless the user asks for a larger sweep.

Use coarse sweeps first, then refine around the best region. For example:

- Piles: 24, 30, 36
- Plate diameter: 18, 20, 22 m
- Centre thickness: 2.5, 3.0, 3.5 m

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

Use `get_cost_optimization_study` to retrieve `parallel_coordinates_rows` and `parallel_coordinates_dimensions`.

`record_cost_optimization_candidate` accepts flat or nested variables and outputs. Prefer flat keys that match the actual app, for example `num_piles`, `slab_diameter_m`, and `slab_thickness_m`.
