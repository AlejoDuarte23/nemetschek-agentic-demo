import random

import viktor as vkt


class Parametrization(vkt.Parametrization):
    inputs = vkt.Section("Load inputs")
    inputs.intro = vkt.Text(
        """# Reaction Loads
Generate vertical load, shear, and moment reactions from a distributed load.
"""
    )
    inputs.distributed_load = vkt.NumberField(
        "Distributed load",
        default=25.0,
        min=0.0,
        suffix="kN/m2",
        description="Area load used to generate representative reaction magnitudes.",
    )
    inputs.number_of_reactions = vkt.IntegerField(
        "Number of reactions",
        default=6,
        min=1,
        max=100,
        description="Number of reaction rows to generate.",
    )


def generate_reactions(distributed_load: float, number_of_reactions: int) -> list[list[float | str]]:
    seed = f"{distributed_load:.4f}:{number_of_reactions}"
    generator = random.Random(seed)
    rows: list[list[float | str]] = []

    for index in range(1, number_of_reactions + 1):
        tributary_area = generator.uniform(4.0, 18.0)
        vertical_load = distributed_load * tributary_area
        shear_z = vertical_load * generator.uniform(-0.08, 0.08)
        shear_y = vertical_load * generator.uniform(-0.08, 0.08)
        moment_y = vertical_load * generator.uniform(-0.75, 0.75)
        moment_z = vertical_load * generator.uniform(-0.75, 0.75)
        rows.append(
            [
                f"R{index}",
                round(vertical_load, 2),
                round(shear_z, 2),
                round(shear_y, 2),
                round(moment_y, 2),
                round(moment_z, 2),
            ]
        )

    return rows


class Controller(vkt.Controller):
    parametrization = Parametrization

    @vkt.TableView("Reaction loads")
    def get_data_view(self, params, **kwargs):
        distributed_load = params.inputs.distributed_load or 0.0
        number_of_reactions = int(params.inputs.number_of_reactions or 0)

        if distributed_load <= 0:
            raise vkt.UserError("Distributed load must be greater than zero.")
        if number_of_reactions <= 0:
            raise vkt.UserError("Number of reactions must be greater than zero.")

        return vkt.TableResult(
            generate_reactions(distributed_load, number_of_reactions),
            column_headers=[
                "Reaction",
                "P [kN]",
                "Vz [kN]",
                "Vy [kN]",
                "My [kNm]",
                "Mz [kNm]",
            ],
            enable_sorting_and_filtering=True,
        )
