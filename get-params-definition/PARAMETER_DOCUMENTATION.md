# VIKTOR Parameter Structure & Visibility Documentation

**Entity**: simple (ID: 11967)
**Workspace**: 2494
**Type**: Controller
**Editor URL**: https://demo.viktor.ai/workspaces/2494/app/editor/11967

---

## Table of Contents
- [Overview](#overview)
- [Parameter Hierarchy](#parameter-hierarchy)
- [Section 1: General Information (inputs_section)](#section-1-general-information-inputs_section)
- [Section 2: User Preferences and Inputs (user_input)](#section-2-user-preferences-and-inputs-user_input)
- [Section 3: Excel File Input (excel_section)](#section-3-excel-file-input-excel_section)
- [Section 4: Material Properties (material_section)](#section-4-material-properties-material_section)
- [Section 5: Visualization Options (data_analytics)](#section-5-visualization-options-data_analytics)
- [Visibility Logic Summary](#visibility-logic-summary)
- [View Methods Affected](#view-methods-affected)

---

## Overview

This VIKTOR app is a **geotechnical parameter determination tool** that processes CPT (Cone Penetration Test) and SPT (Standard Penetration Test) data to calculate soil material properties across multiple profiles. The parametrization uses sophisticated visibility logic to create a progressive disclosure UX where users only see relevant fields based on their workflow choices.

### Key Workflow Patterns:
1. **Data Upload vs Bypass**: Users can bypass data upload for manual entry or go through the full analytics workflow
2. **Progressive Configuration**: Fields appear as users enable specific features (CPT, SPT, profiles, plots)
3. **Conditional Analytics**: Visualization options only appear after data processing is complete
4. **Multi-Profile Support**: Up to 5 soil profiles with dynamic field visibility

---

## Parameter Hierarchy

```
graph_solver/
├── inputs_section/          # General Information (10 fields)
├── user_input/              # User Preferences (9 fields)
├── excel_section/           # Excel File Input (7 fields)
├── material_section/        # Material Properties (11 fields)
└── data_analytics/          # Visualization Options (29 fields)
```

**Total Fields**: 66
**Boolean**: 13 | **Number**: 20 | **String**: 13 | **Array**: 14 | **File**: 6

---

## Section 1: General Information (inputs_section)

**Section Visibility**: Always visible, initially expanded
**Purpose**: Configure project details and data upload workflow

### 1.1 Project Identification

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `project_number` | TextField | `""` | Always | Project identifier for tracking and reporting |
| `selected_office` | OptionField | `null` | Always | Office location (Denver, Minneapolis, Phoenix, Seattle, Springfield) |

**User Intent**: Track project origin and responsible office for data organization and report generation.

---

### 1.2 Workflow Control

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `bypass_data_upload` | BooleanField | `false` | Always | Master toggle for data upload workflow |

**Visibility Impact**: When `true`:
- ✅ Hides: All upload fields, analytics, user preferences
- ✅ Shows: Only material properties section for manual entry
- 🎯 **Why**: Users with pre-existing data or doing quick estimates can skip the full workflow

**Affected Fields** (hidden when `true`):
- All `inputs_section` upload toggles (CPT, SPT, geophysics)
- All `excel_section` file uploads
- All `user_input` preferences
- All `data_analytics` visualizations

---

### 1.3 CPT (Cone Penetration Test) Configuration

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `upload_cpt` | BooleanField | `false` | `bypass_data_upload == false` | Enable CPT data upload |
| `nkt_value` | NumberField | `14.0` | `upload_cpt == true` AND `bypass_data_upload == false` | Cone factor for undrained shear strength |

**Range**: 5.0 - 30.0
**User Intent**:
- CPT provides high-resolution continuous subsurface data
- `nkt_value` varies by soil type (14 is typical for clays)
- Users adjust based on local calibration or soil conditions
- **Why Hide**: Advanced parameter only relevant when CPT data is uploaded

**Related Views**:
- `view_qtn_fr`, `view_fr_qt`, `view_bq_qt`, `view_cone_rf` (CPT classification plots)

---

### 1.4 SPT (Standard Penetration Test) Configuration

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `upload_spt` | BooleanField | `false` | `bypass_data_upload == false` | Enable SPT data upload |
| `use_assumed_hammer_efficiency` | BooleanField | `false` | `upload_spt == true` AND `bypass_data_upload == false` | Use standard 60% efficiency |
| `reject_hammer_efficiency` | BooleanField | `false` | `upload_spt == true` AND `bypass_data_upload == false` | Disable hammer efficiency correction |
| `hammer_efficiency` | NumberField | `60.0` | Complex (see below) | Custom hammer efficiency % |

**`hammer_efficiency` Visibility Logic**:
```
SHOW IF:
  upload_spt == true
  AND bypass_data_upload == false
  AND use_assumed_hammer_efficiency == false
  AND reject_hammer_efficiency == false
```

**Range**: 30.0 - 100.0%
**User Intent**:
- SPT N-values need correction for hammer efficiency to get N60 (standardized value)
- **Standard workflow**: Check `use_assumed_hammer_efficiency` → uses 60% (most common)
- **Custom workflow**: Uncheck → enter actual measured/estimated efficiency
- **Skip correction**: Check `reject_hammer_efficiency` → no N60 calculation (when efficiency unknown)
- **Why Hide**: Avoid confusion—only show custom field when user explicitly rejects both standard and skip options

**Related Views**:
- `view_spt_uscs_analytics` (SPT vs USCS soil classification)
- `view_phi_pi` (SPT-based friction angle correlations)

---

### 1.5 Geophysics Configuration

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `upload_geophysics` | BooleanField | `false` | `bypass_data_upload == false` | Enable geophysics data (coming soon) |

**User Intent**: Future feature for seismic/geophysical survey integration
**Related Views**: `view_shearwave`, `view_modulus`, `view_stateparam`

---

## Section 2: User Preferences and Inputs (user_input)

**Section Visibility**:
```
SHOW IF: bypass_data_upload == false
```
**Purpose**: Configure global settings for all analyses and visualizations
**Initially Expanded**: false

---

### 2.1 Standard Deviation Plotting

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `plot_std_dev_selection` | BooleanField | `false` | Always (when section visible) | Enable std deviation bands |
| `plot_std_dev_value` | NumberField | `0.5` | `plot_std_dev_selection == true` | Std deviation multiplier |

**Range**: 0.1 - 5.0
**User Intent**:
- Add uncertainty bands (±σ) to material property plots
- Helps visualize data variability and reliability
- **Why Hide Value**: Only show multiplier when user enables the feature
- Common values: 0.5σ (67%), 1.0σ (68%), 2.0σ (95%)

**Affected Views**: All profile analytics views (`view_layer_analytics_web_*`)

---

### 2.2 Groundwater Table (GWT) Configuration

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `gwt_selection` | OptionField | `"Whole Site"` | Always | GWT assignment mode |
| `gwt_wholesite` | NumberField | `0.0` | `gwt_selection == "Whole Site"` | Site-wide GWT depth (ft) |
| `gwt_profile1` | NumberField | `0.0` | Complex (see below) | Profile 1 GWT depth (ft) |
| `gwt_profile2` | NumberField | `0.0` | Complex | Profile 2 GWT depth (ft) |
| `gwt_profile3` | NumberField | `0.0` | Complex | Profile 3 GWT depth (ft) |
| `gwt_profile4` | NumberField | `0.0` | Complex | Profile 4 GWT depth (ft) |
| `gwt_profile5` | NumberField | `0.0` | Complex | Profile 5 GWT depth (ft) |

**`gwt_selection` Options**:
- `"Whole Site"`: Single GWT for entire project
- `"Individual Profiles"`: Separate GWT per profile
- `"Per Exploration"`: GWT defined per boring (handled in data file)

**Profile GWT Visibility Logic** (e.g., `gwt_profile1`):
```python
SHOW IF:
  bypass_data_upload == false
  AND gwt_selection == "Individual Profiles"
  AND number_of_profiles >= profile_number
```

**User Intent**:
- GWT affects effective stress calculations (critical for bearing capacity, settlement)
- **Flat site**: Use "Whole Site" → one field
- **Sloped/variable site**: Use "Individual Profiles" → separate field per profile
- **Per-boring GWT**: Use "Per Exploration" → upload in Excel
- **Why Hide**: Progressive disclosure—only show profile fields when user selects that mode AND has created that many profiles

**Impact on Calculations**:
- Affects unit weight (submerged vs total)
- Changes effective stress in shear strength and settlement calculations
- Critical for liquefaction analysis

---

## Section 3: Excel File Input (excel_section)

**Section Visibility**:
```
SHOW IF: bypass_data_upload == false
```
**Purpose**: Upload and process geotechnical test data
**Initially Expanded**: true

---

### 3.1 File Upload Fields

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `cpt_file` | FileField | `null` | `upload_cpt == true` | CPT Excel file (.xlsx, .xls) |
| `spt_file` | FileField | `null` | `upload_spt == true` | SPT Excel file (.xlsx, .xls) |

**User Intent**:
- Only show file upload for enabled data types
- **Why Hide**: Avoid confusion—users shouldn't see SPT upload if they haven't enabled SPT
- Reduces visual clutter in the UI

---

### 3.2 Data Processing Control

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `data_processed` | BooleanField | `false` | Hidden | Internal flag for processing state |
| `process_files_btn` | SetParamsButton | - | Always | Triggers `process_excel_files_and_populate_table` method |

**User Intent**:
- `data_processed` is a **state flag** that unlocks downstream sections
- Set to `true` by the `process_excel_files_and_populate_table` method
- **Why Hidden**: Internal state, not user-editable

**Method**: `process_excel_files_and_populate_table`
- Parses uploaded Excel files
- Calculates material properties using geotechnical correlations
- Populates layer property tables
- Generates cached JSON data for visualizations
- Sets `data_processed = true`

---

### 3.3 Cached Data (Hidden Fields)

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `cached_model_points` | HiddenField | `null` | Hidden | Spatial coordinates of explorations |
| `cached_explorations` | HiddenField | `null` | Hidden | Exploration metadata (IDs, names, types) |
| `cached_model_data` | HiddenField | `null` | Hidden | Processed test data with calculated properties |
| `cached_all_model_data` | HiddenField | `null` | Hidden | Complete dataset for analytics |

**User Intent**:
- Store processed data in parametrization to avoid re-processing
- Enables fast view rendering without re-reading files
- **Why Hidden**: Internal cache, no user interaction needed
- Stored in entity storage as `graph_solver/app_data.json`

---

## Section 4: Material Properties (material_section)

**Section Visibility**:
```
SHOW IF:
  bypass_data_upload == true
  OR data_processed == true
```
**Purpose**: Define soil layer properties for each profile
**Initially Expanded**: true

**User Intent**: This section becomes available in two scenarios:
1. **After data processing**: Review/edit auto-calculated properties
2. **Bypass mode**: Manually enter all properties from scratch

---

### 4.1 Profile Configuration

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `number_of_profiles` | IntegerField | `1` | Always (when section visible) | Number of distinct soil profiles |

**Range**: 1 - 5
**User Intent**:
- Define how many distinct soil profiles exist on site
- **Single profile**: Uniform conditions across site
- **Multiple profiles**: Varied conditions (e.g., cut vs fill, different geology)
- Drives visibility of profile-specific tables below

---

### 4.2 Profile 1 Configuration

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `layer_properties1_explorations` | MultiSelectField | `[]` | `number_of_profiles >= 1` AND NOT `bypass_data_upload` | Select borings for this profile |
| `layer_properties1` | Table | `[]` | `number_of_profiles >= 1` | Layer properties table |

**Table Columns**:
- `layer_id` (TextField): Layer identifier (e.g., "Fill", "SM-1", "Clay")
- `layer_type` (OptionField): `Cohesive` | `Frictional` | `c-φ material`
- `layer_depth` (NumberField, ft): Bottom depth of layer
- `friction_angle` (NumberField, °): φ (internal friction angle)
- `cohesion` (NumberField, ksf): c (undrained shear strength)
- `unit_weight` (NumberField, pcf): γ (total unit weight)
- `elastic_modulus` (NumberField, ksf): E (Young's modulus)
- `poisson_ratio` (NumberField): ν (0-0.5)

**User Intent**:
- **Exploration selector**: Group nearby borings with similar stratigraphy
  - Only visible when data was uploaded (not in bypass mode)
  - Options populated from `return_exploration_options` → reads from cached data
- **Layer table**: Define soil properties by depth
  - Auto-populated by processing button
  - User can edit/refine values
- **Why Hide Explorations in Bypass**: No uploaded data to select from

**Related Views**:
- `view_profile1_full`: Full profile visualization
- `view_layer_analytics_web_11` through `view_layer_analytics_web_15`: Layer-specific analytics for Profile 1

---

### 4.3 Profiles 2-5 Configuration

**Same structure** as Profile 1, with visibility tied to `number_of_profiles`:

| Profile | Exploration Field | Table Field | Visibility |
|---------|------------------|-------------|------------|
| Profile 2 | `layer_properties2_explorations` | `layer_properties2` | `number_of_profiles >= 2` |
| Profile 3 | `layer_properties3_explorations` | `layer_properties3` | `number_of_profiles >= 3` |
| Profile 4 | `layer_properties4_explorations` | `layer_properties4` | `number_of_profiles >= 4` |
| Profile 5 | `layer_properties5_explorations` | `layer_properties5` | `number_of_profiles == 5` |

**User Intent**:
- Progressive disclosure: Only show profile inputs that user has enabled
- Avoids overwhelming UI with 5 profiles when only 1-2 are needed
- **Why Conditional**: Each profile adds significant UI complexity (multi-select + 8-column table)

**Related Views** (per profile):
- `view_profile2_full` through `view_profile5_full`
- `view_layer_analytics_web_21` through `view_layer_analytics_web_55`

---

## Section 5: Visualization Options (data_analytics)

**Section Visibility**:
```
SHOW IF: data_processed == true
```
**Purpose**: Configure advanced data analytics and custom plots
**Initially Expanded**: false

**User Intent**:
- This is an **optional analytics layer** that appears after data processing
- Users can skip this section if they only need material properties
- **Why Hide Until Processing**: No data to visualize until files are processed

---

### 5.1 Plot Category Toggles

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `profile_plots` | BooleanField | `false` | Always (when section visible) | Show profile data analytics |
| `cpt_plots` | BooleanField | `false` | `upload_cpt == true` | Show CPT analytics |
| `spt_plots` | BooleanField | `false` | `upload_spt == true` | Show SPT analytics |

**User Intent**:
- Master toggles for entire categories of visualizations
- **Profile plots**: Layer-by-layer analytics for each profile
- **CPT plots**: Specialized CPT classification plots (Robertson, Qtn-Fr, Bq-Qt, etc.)
- **SPT plots**: SPT-specific analytics (USCS correlation, phi-PI relationships)
- **Why Hide CPT/SPT toggles**: Only show if user uploaded that data type

**Affected Views**:
- `profile_plots = true` → Shows `view_layer_analytics_web_*` views (25 total)
- `cpt_plots = true` → Shows `view_qtn_fr`, `view_fr_qt`, `view_bq_qt`, `view_cone_rf`
- `spt_plots = true` → Shows `view_spt_uscs_analytics`, `view_phi_pi`

---

### 5.2 Custom Plot Selection

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `selected_plots` | MultiSelectField | `[]` | Always (when section visible) | Choose which additional plots to display |
| `profiles_to_include` | MultiSelectField | `[]` | Always (when section visible) | Filter plots by profile |

**`selected_plots` Options** (max 10):
- **Pre-configured plots** (6):
  - `friction_angle_histogram`
  - `cohesion_histogram`
  - `unit_weight_histogram`
  - `depth_vs_friction_angle`
  - `depth_vs_cohesion`
  - `depth_vs_unit_weight`
- **Custom configurable plots** (7):
  - `custom_scatter_1`, `custom_scatter_2`, `custom_scatter_3`
  - `custom_depth_1`, `custom_depth_2`
  - `custom_histogram_1`, `custom_histogram_2`

**User Intent**:
- **Multi-select pattern**: Users can enable 0-10 additional plots
- **Configuration cascade**: Selecting a custom plot reveals its configuration fields below
- **Profile filter**: Limit analytics to specific profiles (useful for comparing 2 profiles)
- **Why Multi-select**: Users often want to compare 2-3 similar plots side-by-side

**Related Views**: Each selected plot option maps directly to a view method (e.g., `friction_angle_histogram` → `view_friction_angle_histogram`)

---

### 5.3 Custom Scatter Plot 1 Configuration

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `custom_scatter_1_x` | TextField | `"longitude"` | Hidden | X-axis parameter (always longitude) |
| `custom_scatter_1_y` | TextField | `"latitude"` | Hidden | Y-axis parameter (always latitude) |
| `custom_scatter_1_heat_param` | OptionField | `"unit_weight"` | `"custom_scatter_1" in selected_plots` | Z/color parameter |
| `custom_scatter_1_method` | OptionField | `"All"` | `"custom_scatter_1" in selected_plots` | Filter by calculation method |
| `custom_scatter_1_min_depth` | NumberField | `0.0` | `"custom_scatter_1" in selected_plots` | Minimum depth filter (ft) |
| `custom_scatter_1_max_depth` | NumberField | `100.0` | `"custom_scatter_1" in selected_plots` | Maximum depth filter (ft) |

**`heat_param` Options**: `friction_angle`, `cohesion`, `unit_weight`, `Es`, `nu`

**`method` Options**:
- `All`: Show all data points
- Specific correlations: `Robertson_2010`, `Terzaghi_1996`, `Mayne_Peuchen_2018`, `Robertson_2012`, `Robertson_2022`, `Bowles_1977`, `Terzaghi_Peck_1967`, `Bowles_1997`

**User Intent**:
- **Spatial visualization**: Plot material properties on site map (lat/lon)
- **Depth filtering**: Focus on specific depth range (e.g., foundation depth)
- **Method comparison**: See how different empirical correlations compare
- **Why Hide Config**: Only show configuration when user selects this plot
- **Why Hide X/Y**: Always spatial (lat/lon), no need to show these options

**Visibility Function**: `show_if_custom_scatter_1_selected`
```python
return 'custom_scatter_1' in params.graph_solver.data_analytics.selected_plots
```

**Related View**: `view_custom_scatter_1`

---

### 5.4 Custom Scatter Plot 2 & 3 Configuration

**Same structure** as Custom Scatter 1:

| Plot | Heat Param | Method | Min Depth | Max Depth | Visibility Function |
|------|-----------|--------|-----------|-----------|-------------------|
| Scatter 2 | `custom_scatter_2_z_param` | `custom_scatter_2_method` | `custom_scatter_2_min_depth` | `custom_scatter_2_max_depth` | `show_if_custom_scatter_2_selected` |
| Scatter 3 | `custom_scatter_3_z_param` | `custom_scatter_3_method` | `custom_scatter_3_min_depth` | `custom_scatter_3_max_depth` | `show_if_custom_scatter_3_selected` |

**User Intent**:
- Compare multiple parameters side-by-side (e.g., friction angle, cohesion, unit weight on 3 maps)
- Compare same parameter with different filters (e.g., 0-20ft vs 20-50ft)
- **Why 3 Plots**: Balances flexibility with UI complexity

**Related Views**: `view_custom_scatter_2`, `view_custom_scatter_3`

---

### 5.5 Custom Depth Plot 1 & 2 Configuration

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `custom_depth_1_param` | OptionField | `"Es"` | `"custom_depth_1" in selected_plots` | Parameter for depth plot 1 |
| `custom_depth_2_param` | OptionField | `"nu"` | `"custom_depth_2" in selected_plots` | Parameter for depth plot 2 |

**Options**: `friction_angle`, `cohesion`, `unit_weight`, `Es`, `nu`

**User Intent**:
- **Depth vs property plots**: Classic geotechnical visualization (depth on Y-axis, property on X-axis)
- **Profile comparison**: Show how property varies with depth across profiles
- **Why Only 2**: Most common use case is comparing 2 properties (e.g., strength vs stiffness)
- **Why Hide Config**: Only show when user selects these plots

**Visibility Functions**:
- `show_if_custom_depth_1_selected`
- `show_if_custom_depth_2_selected`

**Related Views**: `view_custom_depth_1`, `view_custom_depth_2`

---

### 5.6 Custom Histogram 1 & 2 Configuration

| Field | Type | Default | Visibility | Purpose |
|-------|------|---------|------------|---------|
| `custom_histogram_1_param` | OptionField | `"Es"` | `"custom_histogram_1" in selected_plots` | Parameter for histogram 1 |
| `custom_histogram_1_method` | OptionField | `"All"` | `"custom_histogram_1" in selected_plots` | Method filter for histogram 1 |
| `custom_histogram_2_param` | OptionField | `"nu"` | `"custom_histogram_2" in selected_plots` | Parameter for histogram 2 |
| `custom_histogram_2_method` | OptionField | `"All"` | `"custom_histogram_2" in selected_plots` | Method filter for histogram 2 |

**Options**:
- `param`: `friction_angle`, `cohesion`, `unit_weight`, `Es`, `nu`
- `method`: `All`, `Robertson_2010`, `Terzaghi_1996`, etc. (same as scatter plots)

**User Intent**:
- **Distribution analysis**: Understand range, mean, std dev of properties
- **Method validation**: Compare distributions from different correlations
- **Outlier detection**: Identify unusual values that need review
- **Why 2 Plots**: Common to compare 2 property distributions
- **Why Hide Config**: Reduce clutter until user enables these plots

**Visibility Functions**:
- `show_if_custom_histogram_1_selected`
- `show_if_custom_histogram_2_selected`

**Related Views**: `view_custom_histogram_1`, `view_custom_histogram_2`

---

## Visibility Logic Summary

### Master Toggles (Cascading Visibility)

| Toggle Field | When TRUE → Hides | When FALSE → Hides |
|--------------|-------------------|-------------------|
| `bypass_data_upload` | All upload fields, user preferences, analytics | Material properties section |
| `upload_cpt` | - | CPT file upload, nkt_value, CPT plots toggle |
| `upload_spt` | - | SPT file upload, hammer efficiency fields, SPT plots toggle |
| `data_processed` | - | Material properties section, analytics section |

### Conditional Visibility Patterns

#### Pattern 1: Progressive Workflow
```
User enables feature → Config fields appear → Data uploaded → Results visible
```
Example:
1. Check `upload_cpt`
2. → `nkt_value` appears
3. → `cpt_file` upload appears
4. → Press "Process Files"
5. → `data_processed = true`
6. → `cpt_plots` toggle appears
7. → Check `cpt_plots`
8. → CPT views render

#### Pattern 2: Multi-level Cascades
```
Section unlocked → Category enabled → Specific plot selected → Config fields appear
```
Example:
1. `data_processed = true` → `data_analytics` section unlocked
2. Check `"custom_scatter_1"` in `selected_plots`
3. → Configuration fields appear: `heat_param`, `method`, `min_depth`, `max_depth`
4. → `view_custom_scatter_1` renders with user settings

#### Pattern 3: Quantity-Driven Visibility
```
User sets quantity → That number of sub-forms appear
```
Example:
1. Set `number_of_profiles = 3`
2. → Profile 1, 2, 3 tables appear
3. → Profile 4, 5 tables remain hidden
4. Also affects: `gwt_profile1-3` fields (if "Individual Profiles" selected)

---

## View Methods Affected

### Always Visible Views
- `create_plan_view`: Site plan with exploration locations
- `create_3d_fence_diagram_graph`: 3D stratigraphy visualization

### Profile-Dependent Views (number_of_profiles)

| Profiles | Views Shown |
|----------|------------|
| ≥ 1 | `view_profile1_full`, `view_layer_analytics_web_11-15` |
| ≥ 2 | + `view_profile2_full`, `view_layer_analytics_web_21-25` |
| ≥ 3 | + `view_profile3_full`, `view_layer_analytics_web_31-35` |
| ≥ 4 | + `view_profile4_full`, `view_layer_analytics_web_41-45` |
| = 5 | + `view_profile5_full`, `view_layer_analytics_web_51-55` |

### Data Type-Dependent Views

**CPT Views** (requires `upload_cpt = true` AND `cpt_plots = true`):
- `view_qtn_fr`: Qtn vs Friction Ratio classification
- `view_fr_qt`: Friction Ratio vs Qt classification
- `view_bq_qt`: Bq vs Qt pore pressure classification
- `view_cone_rf`: Cone resistance vs friction ratio

**SPT Views** (requires `upload_spt = true` AND `spt_plots = true`):
- `view_spt_uscs_analytics`: SPT N-value vs USCS soil type
- `view_phi_pi`: Friction angle vs Plasticity Index correlation

**Geophysics Views** (requires `upload_geophysics = true`):
- `view_shearwave`: Shear wave velocity profiles
- `view_modulus`: Modulus reduction curves
- `view_stateparam`: State parameter calculations
- `view_unitweight`: Unit weight from geophysics

### Plot Selection-Driven Views

| Plot Selection | View Method |
|----------------|-------------|
| `friction_angle_histogram` | `view_friction_angle_histogram` |
| `cohesion_histogram` | `view_cohesion_histogram` |
| `unit_weight_histogram` | `view_unit_weight_histogram` |
| `depth_vs_friction_angle` | `view_depth_vs_friction_angle` |
| `depth_vs_cohesion` | `view_depth_vs_cohesion` |
| `depth_vs_unit_weight` | `view_depth_vs_unit_weight` |
| `custom_scatter_1` | `view_custom_scatter_1` |
| `custom_scatter_2` | `view_custom_scatter_2` |
| `custom_scatter_3` | `view_custom_scatter_3` |
| `custom_depth_1` | `view_custom_depth_1` |
| `custom_depth_2` | `view_custom_depth_2` |
| `custom_histogram_1` | `view_custom_histogram_1` |
| `custom_histogram_2` | `view_custom_histogram_2` |

### Generic Analytics Views (requires `data_processed = true`)
- `view_profile`: Detailed profile visualization
- `view_lab_analytics`: Laboratory test data analytics
- `view_location_map`: Project location map
- `view_depth_colored`: Depth-colored property visualization

---

## Design Principles & User Intent

### 1. Progressive Disclosure
**Intent**: Don't overwhelm users with all 66 fields at once
**Implementation**:
- Start with 2 fields (project_number, selected_office)
- Show 10 more after workflow choice (upload vs bypass)
- Reveal analytics only after data processing
- Configuration fields appear only when plot is selected

**Why**: Geotechnical engineers need flexibility but want guided workflow for common cases

---

### 2. Context-Aware Field Visibility
**Intent**: Only show fields that are relevant to current context
**Examples**:
- Don't show `nkt_value` if no CPT data uploaded
- Don't show `hammer_efficiency` if using assumed or rejected
- Don't show Profile 4 table if only 2 profiles defined
- Don't show CPT plots toggle if no CPT data exists

**Why**: Prevents errors (editing irrelevant parameters) and reduces cognitive load

---

### 3. Workflow Branching
**Intent**: Support two distinct workflows without mode confusion
**Branches**:
1. **Full Analytics Workflow**: `bypass_data_upload = false`
   - Upload → Process → Review → Customize → Visualize
   - All features available
2. **Quick Manual Entry**: `bypass_data_upload = true`
   - Skip directly to material properties
   - No file uploads, no analytics
   - For users with existing calculated values

**Why**: Different users have different data sources and time constraints

---

### 4. Safety Through Hiding
**Intent**: Prevent invalid configurations
**Examples**:
- Can't set `hammer_efficiency` when using assumed (would be ignored)
- Can't configure custom plot that isn't selected (wasted effort)
- Can't set individual profile GWT when using whole-site GWT (conflict)

**Why**: Hiding prevents users from setting parameters that won't be used

---

### 5. Visual Hierarchy Through Expansion
**Intent**: Guide users through natural workflow sequence
**Initially Expanded Sections**:
1. ✅ `inputs_section`: Always expanded (start here)
2. ✅ `excel_section`: Expanded (next step is upload)
3. ✅ `material_section`: Expanded (key outputs to review)
4. ❌ `user_input`: Collapsed (optional advanced settings)
5. ❌ `data_analytics`: Collapsed (optional deep dive)

**Why**: Optimizes for 80% use case while allowing 20% power users to find advanced features

---

## Key Takeaways for Developers

### When to Hide a Field
1. **Dependency**: Field only applies when parent feature is enabled
2. **Workflow**: Field belongs to alternate workflow path
3. **State**: Field requires data/state that doesn't exist yet
4. **Redundancy**: Field conflicts with another active setting

### When to Use `visible` vs `initially_expanded`
- **`visible`**: Binary show/hide based on conditions (field doesn't exist in DOM when hidden)
- **`initially_expanded`**: UI hint for sections (field exists but collapsed)

### Dynamic Options Pattern
Functions like `return_exploration_options` and `return_profile_options`:
- Read entity storage or params to generate option lists
- Return empty list when dependencies not met
- Paired with visibility conditions to hide field when list would be empty

### Visibility Function Patterns
```python
# Simple check
lambda params: params.section.field == value

# Complex AND logic
vkt.And(
    vkt.IsTrue(vkt.Lookup("path.to.field1")),
    vkt.IsFalse(vkt.Lookup("path.to.field2"))
)

# Custom function (for complex logic)
lambda params, **kwargs: custom_function(params, profile_num=1)
```

---

## Appendix: Complete Field Reference

| Field Path | Type | Default | Always Visible? | Primary Visibility Condition |
|------------|------|---------|----------------|----------------------------|
| `graph_solver.inputs_section.project_number` | TextField | `""` | ✅ | - |
| `graph_solver.inputs_section.selected_office` | OptionField | `null` | ✅ | - |
| `graph_solver.inputs_section.bypass_data_upload` | BooleanField | `false` | ✅ | - |
| `graph_solver.inputs_section.upload_cpt` | BooleanField | `false` | ❌ | `NOT bypass_data_upload` |
| `graph_solver.inputs_section.nkt_value` | NumberField | `14.0` | ❌ | `upload_cpt AND NOT bypass_data_upload` |
| `graph_solver.inputs_section.upload_spt` | BooleanField | `false` | ❌ | `NOT bypass_data_upload` |
| `graph_solver.inputs_section.use_assumed_hammer_efficiency` | BooleanField | `false` | ❌ | `upload_spt AND NOT bypass_data_upload` |
| `graph_solver.inputs_section.reject_hammer_efficiency` | BooleanField | `false` | ❌ | `upload_spt AND NOT bypass_data_upload` |
| `graph_solver.inputs_section.hammer_efficiency` | NumberField | `60.0` | ❌ | `upload_spt AND NOT assumed AND NOT rejected AND NOT bypass` |
| `graph_solver.inputs_section.upload_geophysics` | BooleanField | `false` | ❌ | `NOT bypass_data_upload` |
| `graph_solver.user_input.plot_std_dev_selection` | BooleanField | `false` | ❌ | `NOT bypass_data_upload` |
| `graph_solver.user_input.plot_std_dev_value` | NumberField | `0.5` | ❌ | `plot_std_dev_selection` |
| `graph_solver.user_input.gwt_selection` | OptionField | `"Whole Site"` | ❌ | `NOT bypass_data_upload` |
| `graph_solver.user_input.gwt_wholesite` | NumberField | `0.0` | ❌ | `gwt_selection == "Whole Site"` |
| `graph_solver.user_input.gwt_profile1-5` | NumberField | `0.0` | ❌ | `gwt_selection == "Individual Profiles" AND number_of_profiles >= N` |
| `graph_solver.excel_section.data_processed` | BooleanField | `false` | ❌ | Hidden (internal state) |
| `graph_solver.excel_section.cpt_file` | FileField | `null` | ❌ | `upload_cpt` |
| `graph_solver.excel_section.spt_file` | FileField | `null` | ❌ | `upload_spt` |
| `graph_solver.excel_section.cached_*` | HiddenField | `null` | ❌ | Hidden (internal cache) |
| `graph_solver.material_section.number_of_profiles` | IntegerField | `1` | ❌ | `bypass_data_upload OR data_processed` |
| `graph_solver.material_section.layer_properties1-5_explorations` | MultiSelectField | `[]` | ❌ | `number_of_profiles >= N AND NOT bypass` |
| `graph_solver.material_section.layer_properties1-5` | Table | `[]` | ❌ | `number_of_profiles >= N` |
| `graph_solver.data_analytics.profile_plots` | BooleanField | `false` | ❌ | `data_processed` |
| `graph_solver.data_analytics.cpt_plots` | BooleanField | `false` | ❌ | `data_processed AND upload_cpt` |
| `graph_solver.data_analytics.spt_plots` | BooleanField | `false` | ❌ | `data_processed AND upload_spt` |
| `graph_solver.data_analytics.selected_plots` | MultiSelectField | `[]` | ❌ | `data_processed` |
| `graph_solver.data_analytics.profiles_to_include` | MultiSelectField | `[]` | ❌ | `data_processed` |
| `graph_solver.data_analytics.custom_scatter_1-3_*` | Various | Various | ❌ | `"custom_scatter_N" in selected_plots` |
| `graph_solver.data_analytics.custom_depth_1-2_param` | OptionField | `"Es"`/`"nu"` | ❌ | `"custom_depth_N" in selected_plots` |
| `graph_solver.data_analytics.custom_histogram_1-2_*` | OptionField | Various | ❌ | `"custom_histogram_N" in selected_plots` |

---

**Document Version**: 1.0
**Generated**: 2025-05-14
**Source**: Entity 11967, Workspace 2494 (demo.viktor.ai)
