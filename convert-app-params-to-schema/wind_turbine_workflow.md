# Wind Turbine Foundation Workflow

This workflow connects the five live VIKTOR apps extracted by the notebooks in this folder.

```mermaid
flowchart LR
  selector["Wind Turbine Selector"]
  cpt["CPT Required Depth"]
  foundation["Wind Turbine Foundation Analysis"]
  reinforcement["Reinforcement"]
  cost["Wind Turbine Cost Analysis"]

  selector --> foundation
  foundation --> cpt
  cpt --> reinforcement
  foundation --> reinforcement
  cpt --> cost
  foundation --> cost
  reinforcement --> cost
```

## Nodes

| Node | Workspace | Entity | Primary method | Result |
| --- | ---: | ---: | --- | --- |
| Wind Turbine Selector | 2544 | 12164 | `view_turbine_data` | `data` |
| CPT Required Depth | 2564 | 12165 | `view_required_depth` | `data` |
| Wind Turbine Foundation Analysis | 2677 | 12173 | `view_results` | `data` |
| Reinforcement | 2640 | 12166 | `view_optimise` | `data` |
| Wind Turbine Cost Analysis | 2647 | 12169 | `view_data` | `data` |

The foundation analysis result handoff is based on the app's `view_results` DataView. It returns maximum/minimum pile `Rz` plus governing `m_xD` and `m_yD` moment extremes. The SCIA sample app reads `sample_apps/scia/base_model.esa` from disk.

## Main Handoffs

| From | To | Mapping |
| --- | --- | --- |
| Selector | Foundation | `tower.base_diameter` -> `step_geo.sec_mast.mast_diameter` |
| Selector | Foundation | `tower.base_vert_force` -> `step_geo.sec_mast.mast_vertical_load` |
| Selector | Foundation | `tower.base_horiz_force` -> `step_geo.sec_mast.mast_horizontal_load` |
| Selector | Foundation | `tower.base_moment` -> `step_geo.sec_mast.mast_moment` |
| Foundation | CPT | `Maximum pile reaction (Rz)` -> `step2.sec_load.design_load` |
| Foundation | CPT | `params.step_geo.sec_piles.pile_diameter` -> `step2.sec_pile.pile_diameter` |
| CPT | Foundation params | required pile depth/length -> `step_geo.sec_piles.pile_length` via `set_params_in_node` without rerunning SCIA |
| Foundation | Reinforcement | design rule -> `tab_geometry.width = 1000 mm` representative strip |
| Foundation | Reinforcement | `step_geo.sec_plate.slab_thickness` -> `tab_geometry.height` after m-to-mm conversion |
| Foundation | Reinforcement | `Minimum m_xD+`, `Maximum m_xD-` -> two `tab_loading.combinations` with labels `Min m_xD+` and `Max m_xD-` |
| Foundation | Cost | mast, plate, pedestal, and pile geometry -> `step_1` geometry and pile inputs |
| Reinforcement | Cost | `section.kg_m3` -> `step_1.rebar.plate_main_reinforcement` with a project reinforcement-intensity rule |

Use `wind_turbine_workflow.json` for machine-readable node metadata, graph icons, storage keys, and field-level mapping details.
