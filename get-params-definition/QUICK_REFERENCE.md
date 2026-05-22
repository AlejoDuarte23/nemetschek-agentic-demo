# VIKTOR Parameter Visibility - Quick Reference

## Master Visibility Switches

| Field | Controls Visibility Of | User Intent |
|-------|----------------------|-------------|
| `bypass_data_upload` | **Hides when TRUE**: All uploads, analytics, user prefs<br>**Shows when TRUE**: Direct material property entry | Skip data workflow for manual entry |
| `upload_cpt` | CPT file upload, `nkt_value`, CPT plots toggle | Enable CPT data analysis |
| `upload_spt` | SPT file upload, hammer efficiency fields, SPT plots toggle | Enable SPT data analysis |
| `data_processed` | Material properties section, analytics section | Unlock results after processing |
| `number_of_profiles` | Profile 1-5 tables and exploration selectors | Show only needed profile forms |

---

## 5 Key Visibility Patterns

### 1️⃣ Simple Boolean Toggle
```python
Field: nkt_value
Visibility: upload_cpt == true
Why: CPT cone factor only needed when CPT data uploaded
```

### 2️⃣ Multi-Condition AND Logic
```python
Field: hammer_efficiency
Visibility: upload_spt AND NOT use_assumed AND NOT reject AND NOT bypass
Why: Custom value only when user rejects both standard and skip options
```

### 3️⃣ Option-Driven Visibility
```python
Field: gwt_wholesite
Visibility: gwt_selection == "Whole Site"

Field: gwt_profile1-5
Visibility: gwt_selection == "Individual Profiles" AND number_of_profiles >= N
Why: Different input patterns for different GWT assignment modes
```

### 4️⃣ State-Gated Sections
```python
Section: material_section
Visibility: bypass_data_upload OR data_processed
Why: Available after processing OR when bypassing workflow
```

### 5️⃣ Selection-Triggered Config
```python
Field: custom_scatter_1_heat_param
Visibility: "custom_scatter_1" in selected_plots
Why: Configuration options only appear when plot is selected
```

---

## Workflow Decision Tree

```
START
│
├─ bypass_data_upload = false (Full Workflow)
│  │
│  ├─ Upload toggles visible
│  │  ├─ upload_cpt → nkt_value, cpt_file visible
│  │  └─ upload_spt → hammer fields, spt_file visible
│  │
│  ├─ User preferences visible
│  │  └─ gwt_selection controls which GWT fields show
│  │
│  ├─ Excel section visible
│  │  └─ Press "Process Files" → data_processed = true
│  │
│  ├─ Material properties unlocked
│  │  └─ number_of_profiles controls profile table visibility
│  │
│  └─ Analytics section unlocked
│     ├─ Category toggles (profile_plots, cpt_plots, spt_plots)
│     └─ selected_plots controls custom plot configs
│
└─ bypass_data_upload = true (Quick Entry)
   │
   └─ Material properties section visible immediately
      └─ All other sections hidden
```

---

## View Methods by Trigger

| Trigger | Views Shown | Count |
|---------|------------|-------|
| Always | `create_plan_view`, `create_3d_fence_diagram_graph` | 2 |
| `number_of_profiles >= 1` | `view_profile1_full`, `view_layer_analytics_web_11-15` | 6 |
| `number_of_profiles >= 2` | + Profile 2 views | +6 |
| `number_of_profiles >= 3` | + Profile 3 views | +6 |
| `number_of_profiles >= 4` | + Profile 4 views | +6 |
| `number_of_profiles == 5` | + Profile 5 views | +6 |
| `cpt_plots == true` | `view_qtn_fr`, `view_fr_qt`, `view_bq_qt`, `view_cone_rf` | 4 |
| `spt_plots == true` | `view_spt_uscs_analytics`, `view_phi_pi` | 2 |
| Plot in `selected_plots` | Corresponding `view_*` method | 13 |

**Total Possible Views**: 51+

---

## Common Visibility Issues & Solutions

### Issue: "Why can't I see the material properties section?"
**Solution**: Either:
- Upload files and press "Process Files" to set `data_processed = true`, OR
- Check "Bypass Data Upload and Analytics"

---

### Issue: "Why did my hammer efficiency field disappear?"
**Solution**: You likely checked one of:
- `use_assumed_hammer_efficiency` → Uses fixed 60%
- `reject_hammer_efficiency` → Skips N60 calculation
Uncheck both to show custom field.

---

### Issue: "I selected 3 profiles but only see 1 GWT field"
**Solution**: Check `gwt_selection`:
- If "Whole Site" → Only `gwt_wholesite` visible
- If "Individual Profiles" → `gwt_profile1-3` visible
- If "Per Exploration" → GWT in uploaded data file

---

### Issue: "I selected custom_scatter_1 but don't see configuration"
**Solution**: Check that:
1. `data_processed == true` (analytics section must be unlocked)
2. "custom_scatter_1" is checked in `selected_plots` multi-select
3. Scroll down—config appears below the multi-select

---

## Hidden Fields (Why They're Hidden)

| Field | Visibility | Purpose |
|-------|-----------|---------|
| `data_processed` | Hidden | Internal state flag - set by processing button |
| `cached_model_points` | Hidden | JSON cache - prevents re-processing |
| `cached_explorations` | Hidden | JSON cache - stores exploration metadata |
| `cached_model_data` | Hidden | JSON cache - stores calculated properties |
| `cached_all_model_data` | Hidden | JSON cache - complete dataset for views |
| `custom_scatter_*_x` | Hidden | Always "longitude" - no need to show |
| `custom_scatter_*_y` | Hidden | Always "latitude" - no need to show |

**Why Hidden**: These are either:
- **State flags**: Set by methods, not user input
- **Cache**: Performance optimization
- **Fixed values**: No user choice needed

---

## Best Practices for Editing Visibility Logic

### ✅ DO
- Use simple boolean checks when possible: `vkt.IsTrue(vkt.Lookup("path"))`
- Chain conditions with `vkt.And()` and `vkt.Or()` for readability
- Create visibility functions for complex logic (see `show_if_gwt_profile`)
- Add descriptive comments explaining *why* a field is hidden
- Test all branches (true/false for each condition)

### ❌ DON'T
- Create circular dependencies (A visible if B, B visible if A)
- Hide critical fields users need for the next step
- Use visibility as business logic (use validators instead)
- Forget to update views when adding new selection-driven plots

---

## Quick Visibility Testing Checklist

When adding a new field with visibility conditions:

- [ ] Does field appear when condition is TRUE?
- [ ] Does field hide when condition is FALSE?
- [ ] Does field show/hide immediately (reactive)?
- [ ] Are related view methods also conditional on same trigger?
- [ ] Is visibility explained in field description or section text?
- [ ] Does hiding field prevent access to needed functionality?
- [ ] Are default values appropriate when field first appears?

---

## Files Reference

| File | Purpose |
|------|---------|
| `PARAMETER_DOCUMENTATION.md` | Full documentation with intent and context |
| `parameter_structure_summary.json` | Field counts and statistics |
| `parameter_schema.json` | JSON Schema for validation |
| `parameters_only.json` | Clean parameter values |
| `entity_11967_params.json` | Full API response |
| `QUICK_REFERENCE.md` | This file - fast lookup |

---

**For Full Details**: See `PARAMETER_DOCUMENTATION.md`
