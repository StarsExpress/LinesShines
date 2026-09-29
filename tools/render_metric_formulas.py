"""Pre-render metric-definition formulas to static SVGs for the frontend's
axis-select info popovers.

Dev-only, build-time tool — never imported by `main.py` or anything Railway
runs. Uses matplotlib's built-in mathtext (no system LaTeX/dvipng install
needed; that's only required for `usetex=True`, which this script doesn't
use) to typeset each formula, then saves it as a transparent-background SVG
with text converted to vector paths (`svg.fonttype='path'`, matplotlib's
default) so the browser needs no font of its own to render it correctly.

Formulas rarely change, so this is a manual regeneration step, same
convention as `npm run vendor:plotly`/`vendor:html2canvas` — re-run by hand
and commit the output whenever a formula is added or edited.

Usage (from repo root):
    pip install matplotlib   # dev-only; see requirements-dev.txt
    python -m tools.render_metric_formulas
"""

from __future__ import annotations
from pathlib import Path
import matplotlib

matplotlib.use("svg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "images" / "metric_formulas"

# Text color matches `--chalk` (#f1ecdd), the popover's body-text color
# against its `--turf-800` background (see style.css's .info-popover-text).
TEXT_COLOR = "#f1ecdd"
FONT_SIZE = 18

# One entry per metric *family* — the TPS variant of a metric shares its
# base metric's formula (same math, restricted to true-pass-set rows), same
# convention as config.py's HAVOC_RATE_NOTE/ALLOWED_HAVOC_RATE_NOTE already
# being reused verbatim for both a metric and its "TPS " counterpart.
FORMULAS: dict[str, str] = {
    "havoc_rate": r"$\mathrm{Havoc\ Rate} = \dfrac{\mathrm{Sacks} + \mathrm{QB\ Hits}}{\mathrm{Pass\ Rush\ Opportunities}}$",
    "allowed_havoc_rate": r"$\mathrm{Allowed\ Havoc\ Rate} = \dfrac{\mathrm{Sacks} + \mathrm{QB\ Hits}}{\mathrm{Non\ Spike\ Pass\ Block\ Snaps}}$",
    "prp": r"$\mathrm{PRP} = \dfrac{\mathrm{Sacks} + 0.75\,(\mathrm{QB\ Hits} + \mathrm{Hurries})}{\mathrm{Pass\ Rush\ Snaps}} \times 100$",
    "pbe": r"$\mathrm{PBE} = 100 - \dfrac{\mathrm{Sacks} + 0.75\,(\mathrm{QB\ Hits} + \mathrm{Hurries})}{\mathrm{Pass\ Block\ Snaps}}$",
}


def render_all() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, formula in FORMULAS.items():
        fig = plt.figure(figsize=(0.1, 0.1))
        fig.patch.set_alpha(0.0)
        fig.text(0, 0, formula, fontsize=FONT_SIZE, color=TEXT_COLOR)
        out_path = OUTPUT_DIR / f"{name}.svg"
        fig.savefig(out_path, format="svg", bbox_inches="tight", pad_inches=0.08, transparent=True)
        plt.close(fig)
        print(f"Wrote {out_path.relative_to(OUTPUT_DIR.parent.parent.parent)}")


if __name__ == "__main__":
    render_all()
