# Optimization Examples

## Start a Small Study

```json
{
  "study_name": "Pile count and plate thickness sweep",
  "candidate_budget": 6,
  "variables": [
    {
      "name": "num_piles",
      "path": "step_geo.sec_piles.num_piles",
      "values": [24, 30, 36]
    },
    {
      "name": "slab_thickness",
      "path": "step_geo.sec_plate.slab_thickness",
      "values": [2.5, 3.0]
    }
  ],
  "fixed_inputs": [
    {
      "name": "turbine_loads",
      "path": "selector output",
      "value": "fixed from run_wind_turbine_selector"
    },
    {
      "name": "cpt_location",
      "path": "step1.location",
      "value": "fixed from user-confirmed CPT app location"
    }
  ],
  "replace_existing": true
}
```

## Set Candidate Foundation Params

```json
{
  "node_id": "foundation_analysis",
  "merge": true,
  "params": {
    "step_geo": {
      "sec_plate": {
        "slab_diameter": 20.0,
        "slab_thickness": 2.5,
        "plate_edge_thickness": 1.0,
        "pedestal_height": 1.0
      },
      "sec_piles": {
        "num_piles": 24,
        "pile_edge_distance": 600
      }
    },
    "step_geo_tech": {
      "sec_tip": {
        "tip_stiffness": 50000.0
      },
      "sec_lateral": {
        "lateral_stiffness": 10000.0
      }
    }
  }
}
```

## Record a Candidate

```json
{
  "candidate_id": "cand-001",
  "status": "completed",
  "feasible": true,
  "variables": {
    "num_piles": 24,
    "slab_diameter_m": 20.0,
    "slab_thickness_m": 2.5,
    "plate_edge_thickness_m": 1.0,
    "pile_edge_distance_mm": 600
  },
  "outputs": {
    "max_pile_reaction_kn": 5120.5,
    "min_pile_reaction_kn": -120.0,
    "required_pile_length_m": 20.0,
    "steel_mass_kg_m3": 72.0,
    "rebar_mass_kg": 62000.0,
    "total_pile_length_m": 480.0,
    "total_cost": 845000.0
  },
  "cost": 845000.0,
  "notes": "SCIA, reinforcement, and cost tools completed."
}
```
