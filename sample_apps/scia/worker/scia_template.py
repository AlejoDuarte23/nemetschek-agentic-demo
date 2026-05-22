from pathlib import Path

import viktor as vkt


DEFAULT_ESA_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "base_model.esa"


def get_esa_template_path() -> Path:
    """Return the bundled ESA template path used for memoized SCIA analysis."""
    if not DEFAULT_ESA_TEMPLATE_PATH.exists():
        raise vkt.UserError(
            f"Bundled SCIA .esa template was not found at {DEFAULT_ESA_TEMPLATE_PATH}."
        )
    return DEFAULT_ESA_TEMPLATE_PATH


def get_esa_template_file() -> vkt.File:
    """Return the bundled sample ESA template as a VIKTOR file."""
    return vkt.File.from_path(get_esa_template_path())
