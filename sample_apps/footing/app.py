import math

import viktor as vkt


ALLOWABLE_SOIL_PRESSURE = 150.0
CONCRETE_UNIT_WEIGHT = 24.0
DIMENSION_STEP = 0.10
MIN_DIMENSION = 0.80
MAX_DIMENSION = 30.0


class Parametrization(vkt.Parametrization):
    inputs = vkt.Section("Footing input")
    inputs.intro = vkt.Text(
        """# Pad Footing
Enter reaction rows from a support or column base. The footing is sized so all reactions stay inside the middle kern and the maximum bearing pressure stays below 150 kPa.
"""
    )
    inputs.reactions = vkt.Table(
        "Reaction table",
        default=[
            {"p": 850.0, "my": 65.0, "mz": 40.0},
            {"p": 1120.0, "my": 80.0, "mz": 95.0},
            {"p": 760.0, "my": 35.0, "mz": 55.0},
        ],
        description="Use P, My, and Mz from the governing load combinations.",
    )
    inputs.reactions.p = vkt.NumberField("P [kN]")
    inputs.reactions.my = vkt.NumberField("My [kNm]")
    inputs.reactions.mz = vkt.NumberField("Mz [kNm]")
    inputs.pad_thickness = vkt.NumberField(
        "Pad thickness",
        default=0.60,
        min=0.10,
        suffix="m",
        description="Used to include footing self-weight in the bearing check.",
    )


def get_reaction_rows(params) -> list[dict[str, float]]:
    rows = []
    for index, row in enumerate(params.inputs.reactions or [], start=1):
        vertical_load = float(row.get("p") or 0.0)
        moment_y = float(row.get("my") or 0.0)
        moment_z = float(row.get("mz") or 0.0)

        if vertical_load <= 0:
            raise vkt.UserError(f"Row {index}: P must be greater than zero.")

        rows.append(
            {
                "index": index,
                "p": vertical_load,
                "my": moment_y,
                "mz": moment_z,
            }
        )

    if not rows:
        raise vkt.UserError("Add at least one reaction row.")

    return rows


def evaluate_reaction(row: dict[str, float], width: float, length: float, thickness: float) -> dict[str, float | str]:
    self_weight = width * length * thickness * CONCRETE_UNIT_WEIGHT
    total_vertical_load = row["p"] + self_weight
    eccentricity_x = abs(row["mz"]) / total_vertical_load
    eccentricity_y = abs(row["my"]) / total_vertical_load
    kern_ratio = 6.0 * (eccentricity_x / width + eccentricity_y / length)
    average_pressure = total_vertical_load / (width * length)
    maximum_pressure = average_pressure * (1.0 + kern_ratio)
    minimum_pressure = average_pressure * (1.0 - kern_ratio)
    bearing_utilization = maximum_pressure / ALLOWABLE_SOIL_PRESSURE
    utilization = max(kern_ratio, bearing_utilization)
    controlling_check = "middle kern" if kern_ratio >= bearing_utilization else "bearing"

    return {
        "reaction": f"Row {int(row['index'])}",
        "p": row["p"],
        "my": row["my"],
        "mz": row["mz"],
        "self_weight": self_weight,
        "total_vertical_load": total_vertical_load,
        "eccentricity_x": eccentricity_x,
        "eccentricity_y": eccentricity_y,
        "kern_ratio": kern_ratio,
        "average_pressure": average_pressure,
        "maximum_pressure": maximum_pressure,
        "minimum_pressure": minimum_pressure,
        "bearing_utilization": bearing_utilization,
        "utilization": utilization,
        "controlling_check": controlling_check,
    }


def evaluate_footing(rows: list[dict[str, float]], width: float, length: float, thickness: float) -> tuple[bool, dict[str, float | str]]:
    evaluations = [evaluate_reaction(row, width, length, thickness) for row in rows]
    critical = max(evaluations, key=lambda item: float(item["utilization"]))
    passes = (
        float(critical["kern_ratio"]) <= 1.0
        and float(critical["maximum_pressure"]) <= ALLOWABLE_SOIL_PRESSURE
        and float(critical["minimum_pressure"]) >= 0.0
    )
    return passes, critical


def dimension_range(max_dimension: float):
    steps = int(round((max_dimension - MIN_DIMENSION) / DIMENSION_STEP))
    for step in range(steps + 1):
        yield round(MIN_DIMENSION + step * DIMENSION_STEP, 2)


def find_footing_dimensions(rows: list[dict[str, float]], thickness: float) -> dict[str, float | str]:
    if thickness <= 0:
        raise vkt.UserError("Pad thickness must be greater than zero.")

    if thickness * CONCRETE_UNIT_WEIGHT >= ALLOWABLE_SOIL_PRESSURE:
        raise vkt.UserError("Pad self-weight pressure exceeds the allowable soil pressure.")

    best_result: dict[str, float | str] | None = None
    best_area = math.inf

    for width in dimension_range(MAX_DIMENSION):
        for length in dimension_range(MAX_DIMENSION):
            area = width * length
            if area > best_area:
                continue
            passes, critical = evaluate_footing(rows, width, length, thickness)
            if not passes:
                continue

            balance_penalty = abs(width - length)
            if area < best_area or (
                math.isclose(area, best_area, rel_tol=0.0, abs_tol=1e-9)
                and best_result is not None
                and balance_penalty < abs(float(best_result["width"]) - float(best_result["length"]))
            ):
                best_area = area
                best_result = {
                    "width": width,
                    "length": length,
                    "area": area,
                    **critical,
                }

    if best_result is None:
        raise vkt.UserError("No footing dimensions found up to 30 m x 30 m.")

    return best_result


def make_data_result(result: dict[str, float | str], thickness: float) -> vkt.DataResult:
    kern_status = (
        vkt.DataStatus.SUCCESS
        if float(result["kern_ratio"]) <= 1.0
        else vkt.DataStatus.ERROR
    )
    bearing_status = (
        vkt.DataStatus.SUCCESS
        if float(result["maximum_pressure"]) <= ALLOWABLE_SOIL_PRESSURE
        else vkt.DataStatus.ERROR
    )

    data = vkt.DataGroup(
        dimensions=vkt.DataItem(
            "Footing dimensions",
            "",
            subgroup=vkt.DataGroup(
                width=vkt.DataItem("B", result["width"], suffix=" m", number_of_decimals=2),
                length=vkt.DataItem("L", result["length"], suffix=" m", number_of_decimals=2),
                thickness=vkt.DataItem("Thickness", thickness, suffix=" m", number_of_decimals=2),
                area=vkt.DataItem("Area", result["area"], suffix=" m2", number_of_decimals=2),
            ),
            status=vkt.DataStatus.SUCCESS,
        ),
        bearing=vkt.DataItem(
            "Bearing check",
            "",
            subgroup=vkt.DataGroup(
                allowable=vkt.DataItem("Allowable pressure", ALLOWABLE_SOIL_PRESSURE, suffix=" kPa", number_of_decimals=0),
                maximum=vkt.DataItem("Maximum pressure", result["maximum_pressure"], suffix=" kPa", number_of_decimals=1),
                minimum=vkt.DataItem("Minimum pressure", result["minimum_pressure"], suffix=" kPa", number_of_decimals=1),
                utilization=vkt.DataItem("Bearing utilization", result["bearing_utilization"], number_of_decimals=2),
            ),
            status=bearing_status,
        ),
        kern=vkt.DataItem(
            "Middle kern check",
            "",
            subgroup=vkt.DataGroup(
                eccentricity_x=vkt.DataItem("ex = |Mz| / N", result["eccentricity_x"], suffix=" m", number_of_decimals=3),
                eccentricity_y=vkt.DataItem("ey = |My| / N", result["eccentricity_y"], suffix=" m", number_of_decimals=3),
                ratio=vkt.DataItem("6(ex/B + ey/L)", result["kern_ratio"], number_of_decimals=2),
            ),
            status=kern_status,
        ),
        critical=vkt.DataItem(
            "Critical reaction",
            "",
            subgroup=vkt.DataGroup(
                reaction=vkt.DataItem("Row", result["reaction"]),
                p=vkt.DataItem("P", result["p"], suffix=" kN", number_of_decimals=1),
                my=vkt.DataItem("My", result["my"], suffix=" kNm", number_of_decimals=1),
                mz=vkt.DataItem("Mz", result["mz"], suffix=" kNm", number_of_decimals=1),
                controlling_check=vkt.DataItem("Controlling check", result["controlling_check"]),
            ),
            status=vkt.DataStatus.INFO,
        ),
    )
    return vkt.DataResult(data)


class Controller(vkt.Controller):
    parametrization = Parametrization

    @vkt.DataView("Footing dimensions")
    def get_data_view(self, params, **kwargs):
        rows = get_reaction_rows(params)
        thickness = float(params.inputs.pad_thickness or 0.0)
        result = find_footing_dimensions(rows, thickness)
        return make_data_result(result, thickness)
