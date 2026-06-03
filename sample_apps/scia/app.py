"""
Round Concrete Plate with Circular Pile Layout
===============================================
Models a circular concrete foundation plate supported by piles arranged
in a ring pattern. Provides a 3D geometry preview and runs a SCIA
structural analysis via the VIKTOR Worker.

IMPORTANT – ESA template file
------------------------------
Uses the bundled sample_apps/scia/base_model.esa template:
  - Material: 'C30/37' (concrete for piles) and 'concrete_plate' (for plate)
  - An I/O document named exactly "output" with a "Reactions" result table
    configured for Combinations.
"""

import logging
import math

import numpy as np
import viktor as vkt
from worker import (
    file_to_text,
    get_esa_template_path,
    run_scia_analysis_results,
)

logger = logging.getLogger("viktor")


# ---------------------------------------------------------------------------
# Parametrization
# ---------------------------------------------------------------------------

class Parametrization(vkt.Parametrization):
    """Input form for a round concrete plate with a circular pile layout."""

    # ── Step 1: Define Loads & Geometry ─────────────────────────────────────
    step_geo = vkt.Step("Define Loads & Geometry", views=["view_geometry"])
    step_geo.intro = vkt.Text(
        """# Round Plate Foundation
Set the mast loads, tapered circular plate geometry, and circular pile layout used for the SCIA model. The geometry preview shows the plate, pedestal, and pile ring before analysis.
"""
    )

    step_geo.sec_mast = vkt.Section("Mast", initially_expanded=True)
    step_geo.sec_mast.mast_diameter = vkt.NumberField(
        "Mast diameter",
        default=5.0,
        suffix="m",
        description="Outer diameter of the wind turbine mast at the foundation interface.",
    )
    step_geo.sec_mast.mast_vertical_load = vkt.NumberField(
        "Vertical Force",
        default=4000.0,
        suffix="kN",
        description="Vertical force applied at the mast ring (positive = downward).",
    )
    step_geo.sec_mast.mast_horizontal_load = vkt.NumberField(
        "Horizontal Force",
        default=1500.0,
        suffix="kN",
        description="Horizontal force applied at the mast ring.",
    )
    step_geo.sec_mast.mast_moment = vkt.NumberField(
        "Overturning Moment",
        default=150000.0,
        suffix="kN·m",
        description="Overturning moment applied at the mast ring (e.g. from wind on the turbine).",
    )

    step_geo.sec_plate = vkt.Section("Plate", initially_expanded=True)
    step_geo.sec_plate.slab_diameter = vkt.NumberField(
        "Plate diameter",
        default=20.0,
        suffix="m",
        description="Outer diameter of the circular concrete plate.",
    )
    step_geo.sec_plate.slab_thickness = vkt.NumberField(
        "Plate thickness at centre",
        default=4.5,
        suffix="m",
        description="Thickness of the concrete plate at the centre (below the mast).",
    )
    step_geo.sec_plate.plate_edge_thickness = vkt.NumberField(
        "Plate thickness at edge",
        default=1.0,
        suffix="m",
        description="Thickness of the concrete plate at the outer edge. The top surface tapers linearly from centre to edge; the bottom remains flat.",
    )
    step_geo.sec_plate.pedestal_height = vkt.NumberField(
        "Pedestal height",
        default=1.0,
        suffix="m",
        description="Height of the concrete pedestal sitting on top of the plate, below the mast flange. Same diameter as the mast.",
    )

    step_geo.sec_piles = vkt.Section("Piles", initially_expanded=True)
    step_geo.sec_piles.num_piles = vkt.IntegerField(
        "Number of piles",
        default=30,
        min=6,
        description="Number of piles evenly spaced on the pile circle.",
    )
    step_geo.sec_piles.pile_length = vkt.NumberField(
        "Pile length",
        default=20.0,
        suffix="m",
        description="Length of each pile below the plate.",
    )
    step_geo.sec_piles.pile_diameter = vkt.NumberField(
        "Pile diameter",
        default=500,
        suffix="mm",
        description="Diameter of each circular concrete pile.",
    )
    step_geo.sec_piles.pile_edge_distance = vkt.NumberField(
        "Edge distance (plate edge → pile centre)",
        default=600,
        suffix="mm",
        description="Horizontal distance from the plate edge to the centre of the piles.",
    )

    # ── Step 2: Geotechnical Parameters ─────────────────────────────────────
    step_geo_tech = vkt.Step("Geotechnical Parameters")
    step_geo_tech.intro = vkt.Text(
        """# Soil Springs
Define simplified axial tip and lateral shaft springs for the pile supports. These values control the support stiffness used in the SCIA analysis.
"""
    )

    step_geo_tech.sec_tip = vkt.Section("Pile Tip – Axial Spring")
    step_geo_tech.sec_tip.tip_stiffness = vkt.NumberField(
        "Axial spring stiffness at pile tip",
        default=50000.0,
        suffix="kN/m",
        description=(
            "Vertical spring stiffness representing the soil resistance at the pile tip "
            "(end-bearing component). Typical range: 10 000 – 200 000 kN/m depending on "
            "soil type and pile geometry."
        ),
    )

    step_geo_tech.sec_lateral = vkt.Section("Pile Shaft – Horizontal Spring")
    step_geo_tech.sec_lateral.lateral_stiffness = vkt.NumberField(
        "Horizontal spring stiffness (per unit length)",
        default=10000.0,
        suffix="kN/m/m",
        description=(
            "Distributed horizontal (lateral) spring stiffness along the pile shaft, "
            "representing the subgrade reaction of the surrounding soil. "
            "Typical range: 5 000 – 50 000 kN/m/m for medium-dense sand/clay."
        ),
    )

    # ── Step 3: Run SCIA Analysis ────────────────────────────────────────────
    step_analysis = vkt.Step("Run SCIA Analysis", views=["view_results", "view_pile_reactions", "view_2d_internal_forces", "view_mxd_plus_plot"])
    step_analysis.intro = vkt.Text(
        """# SCIA Results
Run the analysis to review pile reactions, 2D internal forces, and m_xD contour plots. Use the download buttons when you need to inspect the generated SCIA input files.
"""
    )

    step_analysis.download_xml = vkt.DownloadButton(
        "Download SCIA input XML",
        method="download_scia_input_xml",
    )
    step_analysis.download_def = vkt.DownloadButton(
        "Download SCIA .def file",
        method="download_scia_input_def",
    )


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _pile_positions(plate_diameter: float, pile_edge_distance: float, num_piles: int) -> list[tuple[float, float]]:
    """
    Return (x, y) centre coordinates for piles arranged in a ring.

    The pile circle radius = plate_radius - pile_edge_distance.
    Piles are evenly spaced by angle, starting at the positive X-axis.
    """
    pile_radius = plate_diameter / 2.0 - pile_edge_distance
    angles = [2 * math.pi * i / num_piles for i in range(num_piles)]
    return [(pile_radius * math.cos(a), pile_radius * math.sin(a)) for a in angles]


def _build_disk(
    centre_x: float,
    centre_y: float,
    centre_z: float,
    radius: float,
    n_segments: int = 64,
    *,
    material: vkt.Material = None,
) -> vkt.Polygon:
    """
    Build a flat circular disk as a Polygon approximated by n_segments vertices.
    The disk lies in the XY-plane at height centre_z.
    """
    points = [
        vkt.Point(
            centre_x + radius * math.cos(2 * math.pi * i / n_segments),
            centre_y + radius * math.sin(2 * math.pi * i / n_segments),
            centre_z,
        )
        for i in range(n_segments)
    ]
    return vkt.Polygon(points, material=material)


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class Controller(vkt.Controller):
    """Builds the round plate + circular pile layout, previews geometry, and runs SCIA."""

    parametrization = Parametrization

    # ------------------------------------------------------------------
    # Helper: extract geometry params from nested tabs
    # ------------------------------------------------------------------

    @staticmethod
    def _geo_params(params):
        """Convenience accessor for geometry parameters. Converts mm inputs to metres."""
        g = params.step_geo
        return (
            g.sec_plate.slab_diameter,
            g.sec_plate.slab_thickness,
            g.sec_plate.plate_edge_thickness,
            g.sec_plate.pedestal_height,
            g.sec_mast.mast_diameter,
            g.sec_piles.num_piles,
            g.sec_piles.pile_length,
            g.sec_piles.pile_diameter / 1000.0,       # mm → m
            g.sec_piles.pile_edge_distance / 1000.0,  # mm → m
        )

    @staticmethod
    def _mast_loads(params):
        """Convenience accessor for mast load parameters (now in Step 1)."""
        m = params.step_geo.sec_mast
        return m.mast_vertical_load, m.mast_horizontal_load, m.mast_moment

    # ------------------------------------------------------------------
    # 3-D Geometry preview
    # ------------------------------------------------------------------

    @vkt.GeometryView("3D Geometry", x_axis_to_right=True, up_axis="Z")
    def view_geometry(self, params, **kwargs) -> vkt.GeometryResult:
        """
        Render the circular plate and piles in 3-D.

        - Plate: a thick cylinder (extruded polygon) sitting at z = 0 … plate_thickness.
        - Piles: circular extrusions hanging below the plate (z = 0 … -pile_length).
        """
        plate_diameter, plate_thickness, plate_edge_thickness, pedestal_height, mast_diameter, num_piles, pile_length, pile_diameter, pile_edge_distance = (
            self._geo_params(params)
        )
        plate_radius = plate_diameter / 2.0
        mast_radius = mast_diameter / 2.0

        logger.info(
            f"🏗️ Geometry preview: plate ⌀{plate_diameter} m, centre thickness={plate_thickness} m, "
            f"edge thickness={plate_edge_thickness} m, mast ⌀{mast_diameter} m, "
            f"{num_piles} piles ⌀{pile_diameter} m × {pile_length} m"
        )

        objects: list[vkt.TransformableObject] = []

        # ── Plate ─────────────────────────────────────────────────────────
        # Flat bottom at z=0.
        # Top surface:
        #   - Flat at plate_thickness from centre out to mast_radius
        #   - Linearly tapered from plate_thickness (at mast_radius) down to
        #     plate_edge_thickness (at plate_radius)
        # Built as a single TriangleAssembly.
        concrete_color = vkt.Material("Concrete plate", color=vkt.Color(180, 170, 155), roughness=0.8)
        n_seg = 64  # angular slices — more = smoother circle
        triangles: list[vkt.Triangle] = []

        centre_bot = vkt.Point(0, 0, 0)
        centre_top = vkt.Point(0, 0, plate_thickness)

        for i in range(n_seg):
            a0 = 2 * math.pi * i / n_seg
            a1 = 2 * math.pi * (i + 1) / n_seg
            cos0, sin0 = math.cos(a0), math.sin(a0)
            cos1, sin1 = math.cos(a1), math.sin(a1)

            # ── Inner ring points (at mast radius) ──
            # Bottom at z=0, top at plate_thickness (flat inner zone)
            ib0 = vkt.Point(mast_radius * cos0, mast_radius * sin0, 0)
            ib1 = vkt.Point(mast_radius * cos1, mast_radius * sin1, 0)
            it0 = vkt.Point(mast_radius * cos0, mast_radius * sin0, plate_thickness)
            it1 = vkt.Point(mast_radius * cos1, mast_radius * sin1, plate_thickness)

            # ── Outer ring points (at plate radius) ──
            # Bottom at z=0, top at plate_edge_thickness (tapered outer zone)
            ob0 = vkt.Point(plate_radius * cos0, plate_radius * sin0, 0)
            ob1 = vkt.Point(plate_radius * cos1, plate_radius * sin1, 0)
            ot0 = vkt.Point(plate_radius * cos0, plate_radius * sin0, plate_edge_thickness)
            ot1 = vkt.Point(plate_radius * cos1, plate_radius * sin1, plate_edge_thickness)

            # ── Bottom face (flat, z=0, normal points DOWN = -Z) ──
            # CCW when viewed from below: centre → ib1 → ib0 (inner disk)
            triangles.append(vkt.Triangle(centre_bot, ib1, ib0))
            # outer annulus quad (CCW from below)
            triangles.append(vkt.Triangle(ib0, ob1, ob0))
            triangles.append(vkt.Triangle(ib0, ib1, ob1))

            # ── Top face: inner flat disk (z=plate_thickness, normal points UP = +Z) ──
            # CCW when viewed from above: centre → it0 → it1
            triangles.append(vkt.Triangle(centre_top, it0, it1))

            # ── Top face: tapered annulus (normal points UP/outward) ──
            # CCW when viewed from above: it0 → ot0 → ot1, it0 → ot1 → it1
            triangles.append(vkt.Triangle(it0, ot0, ot1))
            triangles.append(vkt.Triangle(it0, ot1, it1))

            # ── Outer wall (normal points radially outward) ──
            # CCW when viewed from outside: ob0 → ot1 → ot0, ob0 → ob1 → ot1
            triangles.append(vkt.Triangle(ob0, ot1, ot0))
            triangles.append(vkt.Triangle(ob0, ob1, ot1))

            # ── Inner wall at mast radius (normal points radially inward) ──
            # CCW when viewed from inside: ib0 → it0 → it1, ib0 → it1 → ib1
            triangles.append(vkt.Triangle(ib0, it0, it1))
            triangles.append(vkt.Triangle(ib0, it1, ib1))

        objects.append(vkt.TriangleAssembly(triangles, material=concrete_color))

        # ── Pedestal (visualisation only) ────────────────────────────────
        # Solid concrete cylinder sitting on the flat inner zone of the plate,
        # same diameter as the mast, rising from plate_thickness to
        # plate_thickness + pedestal_height.
        pedestal_top_z = plate_thickness + pedestal_height
        pedestal_material = vkt.Material("Pedestal", color=vkt.Color(180, 170, 155), roughness=0.8)
        pedestal = vkt.CircularExtrusion(
            diameter=mast_diameter,
            line=vkt.Line(
                vkt.Point(0, 0, plate_thickness),
                vkt.Point(0, 0, pedestal_top_z),
            ),
            material=pedestal_material,
        )
        objects.append(pedestal)


        # ── Piles ─────────────────────────────────────────────────────────
        pile_material = vkt.Material("Concrete pile", color=vkt.Color(130, 120, 110), roughness=0.7)
        positions = _pile_positions(plate_diameter, pile_edge_distance, num_piles)
        logger.info(f"📍 Pile positions (first 3): {positions[:3]}")

        for px, py in positions:
            pile = vkt.CircularExtrusion(
                diameter=pile_diameter,
                line=vkt.Line(vkt.Point(px, py, 0), vkt.Point(px, py, -pile_length)),
                material=pile_material,
            )
            objects.append(pile)

        # ── Labels ────────────────────────────────────────────────────────
        labels = [
            vkt.Label(vkt.Point(0, 0, plate_thickness + 0.3), f"⌀ {plate_diameter} m plate"),
        ]

        return vkt.GeometryResult(geometry=vkt.Group(objects), labels=labels)

    # ------------------------------------------------------------------
    # Helper: build the SCIA model
    # ------------------------------------------------------------------

    def _build_scia_model(self, params) -> vkt.scia.Model:
        """
        Construct the SCIA model for the round plate with circular pile layout.

        The plate is approximated as a polygon (16-sided) in SCIA.
        Piles are circular beam elements with point supports at their bases.
        """
        plate_diameter, plate_thickness, plate_edge_thickness, pedestal_height, mast_diameter, num_piles, pile_length, pile_diameter, pile_edge_distance = (
            self._geo_params(params)
        )
        plate_radius = plate_diameter / 2.0
        # Average thickness used for the SCIA shell element
        plate_thickness_avg = (plate_thickness + plate_edge_thickness) / 2.0

        # ── Mast load values ──────────────────────────────────────────────
        # Read from Step 1 (sec_mast) via the _mast_loads helper
        mast_vertical_load, mast_horizontal_load, mast_moment_val = self._mast_loads(params)

        logger.info(
            f"🏗️ Building SCIA model: plate ⌀{plate_diameter} m, centre t={plate_thickness} m, "
            f"edge t={plate_edge_thickness} m, avg t={plate_thickness_avg:.3f} m, "
            f"{num_piles} piles, mast Fz={mast_vertical_load} kN, Mx={mast_moment_val} kN·m"
        )

        model = vkt.scia.Model()

        # ── Plate nodes (16-sided polygon approximation) ──────────────────
        n_plate_segments = 16
        plate_nodes = []
        for i in range(n_plate_segments):
            angle = 2 * math.pi * i / n_plate_segments
            nx = plate_radius * math.cos(angle)
            ny = plate_radius * math.sin(angle)
            node = model.create_node(f"plate_n{i+1}", nx, ny, 0)
            plate_nodes.append(node)
        logger.info(f"📍 {n_plate_segments} plate boundary nodes created")

        # ── Pile nodes ────────────────────────────────────────────────────
        positions = _pile_positions(plate_diameter, pile_edge_distance, num_piles)
        pile_top_nodes = []
        pile_bottom_nodes = []
        for i, (px, py) in enumerate(positions, 1):
            n_top = model.create_node(f"K:p{i}_t", px, py, 0)
            n_bottom = model.create_node(f"K:p{i}_b", px, py, -pile_length)
            pile_top_nodes.append(n_top)
            pile_bottom_nodes.append(n_bottom)
        logger.info(f"📍 {num_piles} pile node pairs created")

        # ── Pile beams ────────────────────────────────────────────────────
        pile_material = vkt.scia.Material(0, "C30/37")
        cross_section = model.create_circular_cross_section("concrete_pile", pile_material, pile_diameter)
        pile_beams = []
        for i, (n_top, n_bottom) in enumerate(zip(pile_top_nodes, pile_bottom_nodes), 1):
            pile_beams.append(model.create_beam(n_top, n_bottom, cross_section))
        logger.info(f"🔩 {len(pile_beams)} pile beams created")

        # ── Foundation plate ──────────────────────────────────────────────
        # Use average of centre and edge thickness for the SCIA shell element.
        plate_material = vkt.scia.Material(0, "concrete_plate")
        plate_plane = model.create_plane(plate_nodes, plate_thickness_avg, name="foundation plate", material=plate_material)
        logger.info(f"🟦 Foundation plate created, avg thickness={plate_thickness_avg:.3f} m")

        # ── Supports ──────────────────────────────────────────────────────
        # Vertical spring at each pile base
        kv = 400 * 1e6
        freedom_v = (
            vkt.scia.PointSupport.Freedom.FREE,
            vkt.scia.PointSupport.Freedom.FREE,
            vkt.scia.PointSupport.Freedom.FLEXIBLE,
            vkt.scia.PointSupport.Freedom.FREE,
            vkt.scia.PointSupport.Freedom.FREE,
            vkt.scia.PointSupport.Freedom.FREE,
        )
        stiffness_v = (0, 0, kv, 0, 0, 0)
        for i, pile_beam in enumerate(pile_beams, 1):
            model.create_point_support(
                f"Sn:p{i}", pile_beam.end_node,
                vkt.scia.PointSupport.Type.STANDARD,
                freedom_v, stiffness_v,
                vkt.scia.PointSupport.CSys.GLOBAL,
            )

        # Horizontal spring along each pile shaft
        kh = 10 * 1e6
        for pile_beam in pile_beams:
            model.create_line_support_on_beam(
                pile_beam,
                x=vkt.scia.LineSupport.Freedom.FLEXIBLE, stiffness_x=kh,
                y=vkt.scia.LineSupport.Freedom.FLEXIBLE, stiffness_y=kh,
                z=vkt.scia.LineSupport.Freedom.FREE,
                rx=vkt.scia.LineSupport.Freedom.FREE,
                ry=vkt.scia.LineSupport.Freedom.FREE,
                rz=vkt.scia.LineSupport.Freedom.FREE,
                c_sys=vkt.scia.LineSupport.CSys.GLOBAL,
            )
        logger.info("🔒 Pile supports created")

        # ── Mast load values ──────────────────────────────────────────────
        # Convert kN → N and kN·m → N·m; downward = negative Z in SCIA
        mast_fz = mast_vertical_load * 1e3 * -1   # N, downward
        mast_mx = mast_moment_val    * 1e3        # N·m, about X-axis

        logger.info(
            f"🌬️ Mast loads: Fz={mast_fz:.0f} N (downward) | Fh={mast_horizontal_load * 1e3:.0f} N | Mx={mast_mx:.0f} N·m"
        )

        # ── Mast ring coordinates ─────────────────────────────────────────
        # Pre-compute the XY coordinates of the 16 nodes around the mast ring.
        # These are used directly as point_1 / point_2 in create_free_line_load —
        # no SCIA nodes or beams are needed for free loads.
        n_mast = 16
        mast_radius = mast_diameter / 2.0
        mast_ring_xy = [
            (mast_radius * math.cos(2 * math.pi * i / n_mast),
             mast_radius * math.sin(2 * math.pi * i / n_mast))
            for i in range(n_mast)
        ]
        logger.info(f"⭕ {n_mast} mast ring coordinates computed at r={mast_radius:.2f} m")

        # ── Load groups & cases ───────────────────────────────────────────
        # LC_SW: permanent self-weight load case.
        # Using PermanentLoadType.SELF_WEIGHT tells SCIA to automatically
        # compute self-weight from material density × volume for all members.
        # No explicit surface/line loads are needed — SCIA handles it internally.
        # Direction defaults to NEG_Z (downward), which is correct.
        lg_perm = model.create_load_group(
            "LG_SW",
            vkt.scia.LoadGroup.LoadOption.PERMANENT,
            vkt.scia.LoadGroup.RelationOption.STANDARD,
        )
        lc_sw = model.create_permanent_load_case(
            "LC_SW", "self weight",
            lg_perm,
            vkt.scia.LoadCase.PermanentLoadType.SELF_WEIGHT,
            direction=vkt.scia.LoadCase.Direction.NEG_Z,
        )
        logger.info("⚖️ Self-weight load case created (SCIA computes density × volume automatically)")

        # LC1: variable load case for mast loads
        lg = model.create_load_group(
            "LG1",
            vkt.scia.LoadGroup.LoadOption.VARIABLE,
            vkt.scia.LoadGroup.RelationOption.STANDARD,
            vkt.scia.LoadGroup.LoadTypeOption.CAT_G,
        )
        lc = model.create_variable_load_case(
            "LC1", "wind turbine loads",
            lg,
            vkt.scia.LoadCase.VariableLoadType.STATIC,
            vkt.scia.LoadCase.Specification.STANDARD,
            vkt.scia.LoadCase.Duration.SHORT,
        )
        # Envelope combination: SW (factor 1) + mast loads (factor 1)
        model.create_load_combination(
            "C1",
            vkt.scia.LoadCombination.Type.ENVELOPE_SERVICEABILITY,
            {lc_sw: 1, lc: 1},
        )

        # ── Total chord length of the mast ring polygon ───────────────────
        # The mast ring is approximated as an n_mast-sided polygon.
        # Free line loads in SCIA use N/m (force per unit actual length),
        # so we must divide the total force by the total chord length of the
        # polygon — NOT the circumference (2πr), since the segments are chords.
        # Chord length per segment: 2·r·sin(π/n_mast)
        # Total chord length: n_mast · 2·r·sin(π/n_mast)
        chord_per_segment = 2 * mast_radius * math.sin(math.pi / n_mast)
        total_chord_length = n_mast * chord_per_segment
        logger.info(
            f"📐 Mast ring polygon: chord/segment={chord_per_segment:.4f} m, "
            f"total chord={total_chord_length:.4f} m, circumference={2*math.pi*mast_radius:.4f} m"
        )

        # ── Mast vertical force → uniform free line load around mast ring ─
        # API signature: create_free_line_load(name, load_case, point_1, point_2, direction, magnitude_1, magnitude_2)
        # magnitude_1 / magnitude_2 are in [N] at each endpoint (NOT N/m).
        # For a uniform load the total force per segment = magnitude (same at both ends).
        # Total applied force = n_segments × magnitude_per_segment = mast_fz  ✓
        magnitude_z = mast_fz / n_mast   # N per segment endpoint, uniform
        for i in range(n_mast):
            x1, y1 = mast_ring_xy[i]
            x2, y2 = mast_ring_xy[(i + 1) % n_mast]
            model.create_free_line_load(
                f"FL:fz_{i+1}", lc,
                (x1, y1), (x2, y2),          # point_1, point_2 come BEFORE direction
                vkt.scia.FreeLoad.Direction.Z,
                magnitude_z, magnitude_z,     # uniform: same magnitude [N] at both endpoints
            )
        logger.info(
            f"⬇️ Mast vertical load: ring line load magnitude_z={magnitude_z:.2f} N/segment, "
            f"total={magnitude_z * n_mast / 1e3:.1f} kN (input={mast_fz / 1e3:.1f} kN)"
        )

        # ── Mast horizontal force → uniform free line load around mast ring ─
        # Same approach as Fz: magnitude_h [N] per segment, total = n_segments × magnitude_h = mast_fh  ✓
        mast_fh = mast_horizontal_load * 1e3   # kN → N
        magnitude_h = mast_fh / n_mast   # N per segment endpoint, uniform
        for i in range(n_mast):
            x1, y1 = mast_ring_xy[i]
            x2, y2 = mast_ring_xy[(i + 1) % n_mast]
            model.create_free_line_load(
                f"FL:fh_{i+1}", lc,
                (x1, y1), (x2, y2),          # point_1, point_2 come BEFORE direction
                vkt.scia.FreeLoad.Direction.X,
                magnitude_h, magnitude_h,     # uniform: same magnitude [N] at both endpoints
            )
        logger.info(
            f"➡️ Mast horizontal force: ring line load magnitude_h={magnitude_h:.2f} N/segment, "
            f"total={magnitude_h * n_mast / 1e3:.1f} kN (input={mast_fh / 1e3:.1f} kN)"
        )

        # ── Mast overturning moment → antisymmetric free point loads on ring
        # The moment Mx (about global X, in N·m) is converted to a cosine-
        # varying set of vertical point loads at each mast ring node:
        #   F_i = (Mx / Σ(r_i² · Δθ/2)) · cos(θ_i)
        # For a uniform ring: F_i = (2·Mx / (n·r²)) · cos(θ_i)  [N per node]
        # Equilibrium check: Σ F_i · y_i = Σ (2Mx/(n·r²))·cos(θ_i)·r·sin(θ_i)
        #   = (2Mx/(n·r)) · Σ sin(θ_i)cos(θ_i) = (Mx/(n·r)) · Σ sin(2θ_i) ≈ 0  ✓
        # Moment check: Σ F_i · x_i = Σ (2Mx/(n·r²))·cos²(θ_i)·r = (2Mx/(n·r))·(n/2) = Mx/r·r = Mx  ✓
        f_moment_amplitude = (2 * mast_mx) / (n_mast * mast_radius)   # N per node at θ=0

        for i in range(n_mast):
            angle = 2 * math.pi * i / n_mast
            f_node = f_moment_amplitude * math.cos(angle)   # N, varies with cos(θ)
            model.create_free_point_load(
                f"FP:mast_mx_{i+1}", lc,
                vkt.scia.FreeLoad.Direction.Z,
                f_node,
                mast_ring_xy[i],
            )
        logger.info(
            f"↩️ Mast moment: {n_mast} point loads, amplitude={f_moment_amplitude:.1f} N at θ=0, "
            f"Mx_check={sum((2*mast_mx/(n_mast*mast_radius))*math.cos(2*math.pi*i/n_mast)*(mast_radius*math.cos(2*math.pi*i/n_mast)) for i in range(n_mast))/1e3:.1f} kN·m (input={mast_mx/1e3:.1f} kN·m)"
        )

        return model

    # ------------------------------------------------------------------
    # Results view – runs SCIA analysis via Worker
    # ------------------------------------------------------------------

    def _run_scia_and_get_reactions(self, params) -> dict:
        """
        Run the memoized SCIA worker analysis and return parsed result data.

        The memoized worker function deliberately receives generated XML/DEF
        content and the bundled ESA template path as keyword-only inputs. It
        does not receive the full params object, because params serialization is
        too broad and causes unreliable memoization keys.
        """
        vkt.progress_message("Building SCIA model…", percentage=10)
        model = self._build_scia_model(params)
        input_xml, input_def = model.generate_xml_input()

        vkt.progress_message("Sending model to SCIA Worker…", percentage=25)
        logger.info("🚀 Sending model to memoized SCIA Worker analysis...")
        result = run_scia_analysis_results(
            input_xml=file_to_text(input_xml),
            input_def=file_to_text(input_def),
            esa_template_path=str(get_esa_template_path()),
            timeout_seconds=300,
        )
        logger.info(f"📊 Node names sample (first 5): {result['node_names'][:5]}")
        logger.info(f"📊 Rz min sample: {result.get('rz_min', [])[:5]}")
        logger.info(f"📊 Rz max sample: {result.get('rz_max', [])[:5]}")
        vkt.progress_message("Done!", percentage=100)

        return result

    @vkt.DataView("Results Summary", duration_guess=60)
    def view_results(self, params, **kwargs) -> vkt.DataResult:
        """Run the SCIA analysis and display a flat summary of pile reactions and governing moments."""
        num_piles = params.step_geo.sec_piles.num_piles
        reactions = self._run_scia_and_get_reactions(params)

        # ── Pile reactions ──────────────────────────────────────────────────
        # rz_min/rz_max are already grouped per unique pile node (one entry per pile),
        # with min/max taken across envelope sub-cases (C1/1, C1/2) during parsing.
        def _is_pile_node(name: str) -> bool:
            n = name.split("/")[-1]
            return (n.startswith("K:p") and n.endswith("_b")) or \
                   (n.startswith("K:p") and n.endswith("_t"))

        node_names = reactions["node_names"]
        rz_min_list = reactions.get("rz_min", [])
        rz_max_list = reactions.get("rz_max", [])

        # Filter to pile nodes only
        pile_rz_min = [
            rz for name, rz in zip(node_names, rz_min_list)
            if _is_pile_node(name)
        ]
        pile_rz_max = [
            rz for name, rz in zip(node_names, rz_max_list)
            if _is_pile_node(name)
        ]

        if not pile_rz_min:
            logger.warning("⚠️ No pile nodes matched by name – using all nodes as fallback")
            pile_rz_min = rz_min_list[:num_piles]
            pile_rz_max = rz_max_list[:num_piles]

        logger.info(f"📊 Pile Rz min (first 5): {pile_rz_min[:5]}")
        logger.info(f"📊 Pile Rz max (first 5): {pile_rz_max[:5]}")

        max_rz = max(pile_rz_max) if pile_rz_max else 0.0
        min_rz = min(pile_rz_min) if pile_rz_min else 0.0

        # ── 2D moment extremes ───────────────────────────────────────────────
        # Pull the raw moment columns from the internal forces result and find
        # the governing (min/max) value for each of the four design moments.
        forces = reactions.get("internal_forces_2d", {})

        def _col_extremes(key: str) -> tuple[float | None, float | None]:
            """Return (min, max) for a moment column; None if data is missing."""
            raw = forces.get(key, [])
            vals = []
            for v in raw:
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    pass
            if not vals:
                return None, None
            return min(vals), max(vals)

        # m_xD+ and m_yD+ are positive-side moments → report the minimum (least favourable)
        # m_xD- and m_yD- are negative-side moments → report the maximum (least favourable)
        mxdp_min, _ = _col_extremes("m_xD+")
        _, mxdm_max = _col_extremes("m_xD-")
        mydp_min, _ = _col_extremes("m_yD+")
        _, mydm_max = _col_extremes("m_yD-")

        def _fmt_moment(v: float | None) -> float | str:
            """Convert Nm/m → kNm/m, rounded to 2 decimals. Returns '-' if None."""
            return round(v / 1e3, 2) if v is not None else "-"

        logger.info(f"📐 Moment extremes – m_xD+ min: {mxdp_min}, m_xD- max: {mxdm_max}, "
                    f"m_yD+ min: {mydp_min}, m_yD- max: {mydm_max}")

        # ── Flat DataGroup (no nesting) ──────────────────────────────────────
        data = vkt.DataGroup(
            vkt.DataItem("Maximum pile reaction (Rz)", round(max_rz / 1e3, 2), suffix="kN"),
            vkt.DataItem("Minimum pile reaction (Rz)", round(min_rz / 1e3, 2), suffix="kN"),
            vkt.DataItem("Minimum m_xD+",              _fmt_moment(mxdp_min),  suffix="kNm/m"),
            vkt.DataItem("Maximum m_xD-",              _fmt_moment(mxdm_max),  suffix="kNm/m"),
            vkt.DataItem("Minimum m_yD+",              _fmt_moment(mydp_min),  suffix="kNm/m"),
            vkt.DataItem("Maximum m_yD-",              _fmt_moment(mydm_max),  suffix="kNm/m"),
        )
        return vkt.DataResult(data)

    @vkt.TableView("Pile Reactions", duration_guess=60)
    def view_pile_reactions(self, params, **kwargs) -> vkt.TableResult:
        """
        Run the SCIA analysis and list the reaction forces per pile in a table.
        Rows are sorted by pile number.
        Columns: Pile #, X (m), Y (m), Min Rz (kN), Max Rz (kN).
        Min/Max are taken across all individual load cases (LC_SW and LC1).
        """
        plate_diameter     = params.step_geo.sec_plate.slab_diameter
        pile_edge_distance = params.step_geo.sec_piles.pile_edge_distance / 1e3  # mm → m
        num_piles          = params.step_geo.sec_piles.num_piles

        # Pre-compute pile XY positions so we can show them in the table
        positions = _pile_positions(plate_diameter, pile_edge_distance, num_piles)

        reactions = self._run_scia_and_get_reactions(params)

        # Collect all per-load-case Rz lists; fall back gracefully if a key is absent
        # rz_min/rz_max are pre-grouped per unique pile node (one entry per pile),
        # with min/max taken across envelope sub-cases (C1/1, C1/2) during parsing.
        node_names  = reactions["node_names"]
        rz_min_list = reactions.get("rz_min", [])
        rz_max_list = reactions.get("rz_max", [])

        logger.info(f"📊 Total unique nodes from SCIA: {len(node_names)}")
        logger.info(f"📊 First 5 node names: {node_names[:5]}")

        def _strip_prefix(name: str) -> str:
            """Strip the 'Sn:p{i}/' prefix SCIA prepends, returning just 'K:p{i}_b'."""
            return name.split("/")[-1]

        def _is_pile_node(name: str) -> bool:
            n = _strip_prefix(name)
            return (n.startswith("K:p") and n.endswith("_b")) or \
                   (n.startswith("K:p") and n.endswith("_t"))

        def _find_rz_minmax(pile_index: int) -> tuple[float, float]:
            """Return (min_rz, max_rz) for the given pile, matched by node name."""
            candidates = {
                f"K:p{pile_index}_b", f"K:p{pile_index}_t",
                f"p{pile_index}_b",   f"p{pile_index}_t",
                f"K:p{pile_index}",   f"p{pile_index}",
            }
            for name, rz_min, rz_max in zip(node_names, rz_min_list, rz_max_list):
                if _strip_prefix(name) in candidates:
                    return float(rz_min), float(rz_max)
            # Positional fallback
            idx = pile_index - 1
            if idx < len(rz_min_list):
                logger.warning(f"⚠️ Pile {pile_index}: no name match – using positional fallback")
                return float(rz_min_list[idx]), float(rz_max_list[idx])
            return 0.0, 0.0

        rows = []
        for i in range(1, num_piles + 1):
            px, py = positions[i - 1]
            min_rz, max_rz = _find_rz_minmax(i)

            rows.append([
                i,                          # Pile #
                round(px, 3),               # X (m)
                round(py, 3),               # Y (m)
                round(min_rz / 1e3, 2),     # Min Rz (kN)
                round(max_rz / 1e3, 2),     # Max Rz (kN)
            ])

        headers = [
            vkt.TableHeader("Pile #",   align="center"),
            vkt.TableHeader("X [m]",    align="center"),
            vkt.TableHeader("Y [m]",    align="center"),
            vkt.TableHeader("Min Rz [kN]", align="center"),
            vkt.TableHeader("Max Rz [kN]", align="center"),
        ]
        return vkt.TableResult(rows, column_headers=headers)

    @vkt.TableView("2D Internal Forces", duration_guess=60)
    def view_2d_internal_forces(self, params, **kwargs) -> vkt.TableResult:
        """
        Display 6 governing rows — one per force/moment component (m_xD+, m_xD-, m_yD+,
        m_yD-, n_xD, n_yD). Each row shows the element+case that produces the absolute
        maximum for that component, together with all other force values for that same row.
        Removed columns: Node, m_cD+, m_cD-, n_cD. Values converted to kN/kNm per metre.
        """
        data = self._run_scia_and_get_reactions(params)
        forces = data.get("internal_forces_2d", {})

        if not forces:
            logger.warning("⚠️ No 2D internal forces data available to display")
            return vkt.TableResult(
                [["No data available – run the analysis first"]],
                column_headers=[vkt.TableHeader("Status")],
            )

        def _to_float(v):
            """Safely convert a raw value to float; return None on failure."""
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        def _fmt(v, scale=1e-3):
            """Convert N→kN or Nm/m→kNm/m, round to 2 decimals. Return '-' on failure."""
            try:
                return round(float(v) * scale, 2)
            except (TypeError, ValueError):
                return "-"

        # Parse "Element: 1; Node: 17" → element ID string
        def _parse_element(mesh_str: str) -> str:
            """Extract element ID from 'Element: X; Node: Y'."""
            try:
                return mesh_str.split(";")[0].split(":")[1].strip()
            except (IndexError, AttributeError):
                return mesh_str

        # Columns to keep (raw SCIA keys, excluding Node / m_cD+ / m_cD- / n_cD)
        value_keys = ["m_xD+", "m_xD-", "m_yD+", "m_yD-", "n_xD", "n_yD"]

        mesh_col = forces.get("Mesh", [])
        case_col = forces.get("Case", [])
        n_rows   = len(mesh_col)
        logger.info(f"📐 Building governing 2D internal forces table from {n_rows} raw rows")

        # --- Parse all raw rows into a flat list of dicts ---
        # Each entry holds element, case, and all value-column floats for that row.
        parsed_rows = []
        for i in range(n_rows):
            elem = _parse_element(mesh_col[i] if i < len(mesh_col) else "-")
            case = case_col[i] if i < len(case_col) else "-"
            entry = {"elem": elem, "case": case}
            for key in value_keys:
                col = forces.get(key, [])
                entry[key] = _to_float(col[i] if i < len(col) else None)
            parsed_rows.append(entry)

        # --- For each value column, find the single raw row with the abs-max value ---
        # This gives exactly 6 rows: one governing row per force/moment component.
        rows = []
        for key in value_keys:
            # Find the row whose absolute value for this key is the largest
            best = max(
                (r for r in parsed_rows if r[key] is not None),
                key=lambda r, k=key: abs(r[k]),
                default=None,
            )
            if best is None:
                rows.append([key, "-"] + ["-"] * len(value_keys))
                continue

            row = [key, best["elem"], best["case"]]
            for k in value_keys:
                row.append(_fmt(best[k]))
            rows.append(row)

        logger.info(f"📊 Governing table: {len(rows)} rows (1 per force component)")

        headers = [
            vkt.TableHeader("Governing",      align="center"),
            vkt.TableHeader("Element",        align="center"),
            vkt.TableHeader("Case",           align="center"),
            vkt.TableHeader("m_xD+ [kNm/m]", align="right"),
            vkt.TableHeader("m_xD- [kNm/m]", align="right"),
            vkt.TableHeader("m_yD+ [kNm/m]", align="right"),
            vkt.TableHeader("m_yD- [kNm/m]", align="right"),
            vkt.TableHeader("n_xD [kN/m]",   align="right"),
            vkt.TableHeader("n_yD [kN/m]",   align="right"),
        ]
        return vkt.TableResult(rows, column_headers=headers)

    @vkt.PlotlyView("2D Moment Contour Plots", duration_guess=60)
    def view_mxd_plus_plot(self, params, **kwargs) -> vkt.PlotlyResult:
        """
        2×2 subplot grid showing filled mesh/contour plots for m_xD+, m_xD-, m_yD+, m_yD-.
        Scattered element-centre points are interpolated onto a regular grid using
        scipy's linear interpolation, then rendered as a smooth filled contour surface.
        For elements with multiple load cases, the absolute maximum value is used.
        Values are converted from Nm/m → kNm/m.
        """
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        from scipy.interpolate import griddata

        data = self._run_scia_and_get_reactions(params)
        forces = data.get("internal_forces_2d", {})

        if not forces:
            logger.warning("⚠️ No 2D internal forces data available for plot")
            fig = go.Figure()
            fig.update_layout(title="No data available – run the analysis first")
            return vkt.PlotlyResult(fig)

        # ── Raw columns shared across all subplots ───────────────────────────
        mesh_col = forces.get("Mesh", [])
        x_col    = forces.get("x", [])
        y_col    = forces.get("y", [])
        n_rows   = len(mesh_col)
        logger.info(f"📊 Building 2D moment contour surface from {n_rows} rows")

        # ── Helper: parse element id from "Element: X; Node: Y" ─────────────
        def _elem_id(mesh_str: str) -> str:
            try:
                return mesh_str.split(";")[0].split(":")[1].strip()
            except (IndexError, AttributeError):
                return mesh_str

        # ── Helper: aggregate abs-max per element for a given value column ───
        def _aggregate(col_key: str) -> tuple[list, list, list, list]:
            """Return (elems, xs, ys, vals) with one entry per element (abs-max)."""
            raw_col = forces.get(col_key, [])
            elem_data: dict[str, dict] = {}
            for i in range(n_rows):
                elem = _elem_id(mesh_col[i] if i < len(mesh_col) else "")
                try:
                    val = float(raw_col[i]) * 1e-3   # Nm/m → kNm/m
                    x   = float(x_col[i] if i < len(x_col) else 0)
                    y   = float(y_col[i] if i < len(y_col) else 0)
                except (TypeError, ValueError):
                    continue
                if elem not in elem_data or abs(val) > abs(elem_data[elem]["val"]):
                    elem_data[elem] = {"x": x, "y": y, "val": val}

            elems = list(elem_data.keys())
            xs    = [d["x"]   for d in elem_data.values()]
            ys    = [d["y"]   for d in elem_data.values()]
            vals  = [d["val"] for d in elem_data.values()]
            return elems, xs, ys, vals

        # ── Define the 4 subplots (column key, display label, row, col) ──────
        subplots_cfg = [
            ("m_xD+", "m_xD+", 1, 1),
            ("m_xD-", "m_xD-", 1, 2),
            ("m_yD+", "m_yD+", 2, 1),
            ("m_yD-", "m_yD-", 2, 2),
        ]

        # ── Create 2×2 subplot figure ────────────────────────────────────────
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=[cfg[1] + " [kNm/m]" for cfg in subplots_cfg],
            horizontal_spacing=0.22,   # extra room for colorbars between columns
            vertical_spacing=0.18,     # extra room for titles between rows
        )

        # ── Grid resolution for interpolation ────────────────────────────────
        GRID_N = 200  # number of grid points per axis

        # ── Add one filled-contour trace per subplot ──────────────────────────
        for idx, (col_key, label, row, col) in enumerate(subplots_cfg):
            elems, xs, ys, vals = _aggregate(col_key)

            if not vals:
                logger.warning(f"⚠️ No data for column '{col_key}'")
                continue

            logger.info(f"📊 {label}: {len(elems)} elements, "
                        f"range [{min(vals):.2f}, {max(vals):.2f}] kNm/m")

            xs_arr   = np.array(xs)
            ys_arr   = np.array(ys)
            vals_arr = np.array(vals)

            # Build a regular grid that covers the convex hull of the data points
            xi = np.linspace(xs_arr.min(), xs_arr.max(), GRID_N)
            yi = np.linspace(ys_arr.min(), ys_arr.max(), GRID_N)
            xi_grid, yi_grid = np.meshgrid(xi, yi)

            # Interpolate scattered element-centre values onto the regular grid.
            # method='linear' gives a smooth surface; NaN outside the convex hull.
            zi_grid = griddata(
                points=(xs_arr, ys_arr),
                values=vals_arr,
                xi=(xi_grid, yi_grid),
                method="linear",
            )

            logger.info(f"📐 {label}: grid shape {zi_grid.shape}, "
                        f"NaN fraction {np.isnan(zi_grid).mean():.1%}")

            # Colorbar positioning: anchored just outside each subplot's right edge.
            # With horizontal_spacing=0.22 the left subplot domain ends at ~0.39
            # and the right subplot starts at ~0.61, so colorbars sit at 0.41 / 1.02.
            colorbar_x = 0.41 if col == 1 else 1.02
            colorbar_y = 0.78 if row == 1 else 0.22

            fig.add_trace(
                go.Contour(
                    x=xi,
                    y=yi,
                    z=zi_grid,
                    colorscale="Jet",
                    contours=dict(
                        coloring="heatmap",   # filled surface, not just lines
                        showlines=True,
                        showlabels=False,
                    ),
                    line=dict(width=0.5, color="rgba(0,0,0,0.25)"),
                    showscale=True,
                    colorbar=dict(
                        title=dict(text=f"{label}<br>[kNm/m]", side="right"),
                        len=0.42,
                        thickness=12,
                        x=colorbar_x,
                        y=colorbar_y,
                        yanchor="middle",
                    ),
                    name=label,
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{label}</b><br>"
                        "x = %{x:.2f} m<br>"
                        "y = %{y:.2f} m<br>"
                        "value = %{z:.2f} kNm/m"
                        "<extra></extra>"
                    ),
                ),
                row=row, col=col,
            )

            # Overlay the original element-centre points as small markers so the
            # mesh density is visible without cluttering the surface.
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="markers",
                    marker=dict(size=3, color="rgba(0,0,0,0.25)", symbol="circle"),
                    showlegend=False,
                    hoverinfo="skip",
                    name=f"{label} pts",
                ),
                row=row, col=col,
            )

        # ── Equal-aspect axes and shared styling for all 4 subplots ──────────
        # Axis titles are added as figure annotations instead of per-axis titles
        # to avoid overlapping with tick labels and colorbars.
        axis_style = dict(showgrid=False, zeroline=False, showticklabels=True,
                          title=dict(text=""))   # suppress per-axis title
        axis_pairs = [
            ("xaxis",  "yaxis",  "y"),
            ("xaxis2", "yaxis2", "y2"),
            ("xaxis3", "yaxis3", "y3"),
            ("xaxis4", "yaxis4", "y4"),
        ]

        for x_ax, y_ax, y_ref in axis_pairs:
            fig.update_layout(**{
                x_ax: dict(**axis_style, scaleanchor=y_ref, scaleratio=1),
                y_ax: dict(**axis_style),
            })

        fig.update_layout(
            title=dict(
                text="2D Design Moments – Absolute Maximum per Element [kNm/m]",
                font=dict(size=15),
            ),
            plot_bgcolor="white",
            paper_bgcolor="white",
            height=950,
            margin=dict(l=60, r=90, t=90, b=60),
            # Shared axis labels as annotations (one per column/row)
            annotations=list(fig.layout.annotations) + [
                # x-axis label – bottom of each column
                dict(text="x [m]", x=0.19, y=-0.04, xref="paper", yref="paper",
                     showarrow=False, font=dict(size=12)),
                dict(text="x [m]", x=0.81, y=-0.04, xref="paper", yref="paper",
                     showarrow=False, font=dict(size=12)),
                # y-axis label – left of each row
                dict(text="y [m]", x=-0.04, y=0.78, xref="paper", yref="paper",
                     showarrow=False, font=dict(size=12), textangle=-90),
                dict(text="y [m]", x=-0.04, y=0.22, xref="paper", yref="paper",
                     showarrow=False, font=dict(size=12), textangle=-90),
            ],
        )

        return vkt.PlotlyResult(fig)

    # ------------------------------------------------------------------
    # Download buttons
    # ------------------------------------------------------------------

    def download_scia_input_xml(self, params, **kwargs) -> vkt.DownloadResult:
        """Download the generated SCIA XML input file."""
        model = self._build_scia_model(params)
        input_xml, _ = model.generate_xml_input()
        logger.info("📥 Downloading SCIA XML input file")
        return vkt.DownloadResult(input_xml, file_name="round_plate_model.xml")

    def download_scia_input_def(self, params, **kwargs) -> vkt.DownloadResult:
        """Download the SCIA .def definition file."""
        _, input_def = vkt.scia.Model().generate_xml_input()
        logger.info("📥 Downloading SCIA .def file")
        return vkt.DownloadResult(input_def, file_name="viktor.xml.def")
