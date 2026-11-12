"""Render each <svg> panel in results/figures/slides/diagrams.html to its own PNG with headless Chrome.

    python -m experiments.render_diagrams [--chrome PATH]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLIDES = ROOT / "results" / "figures" / "slides"
# Panel order in diagrams.html -> output name.
NAMES = ["method", "worked_example", "coldcard_timeline", "sp1_formulation", "sp2_formulation"]
# Wide 16:9 panels are scaled to 2000 px wide; the narrower deck-slot panels are rendered at 2x.
SCALE = {"method": 1.25, "worked_example": 1.25}
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome", default=CHROME, help="path to a Chrome or Chromium binary")
    args = ap.parse_args()
    html = (SLIDES / "diagrams.html").read_text()
    head = html.split("<body>")[0]
    svgs = re.findall(r"<svg.*?</svg>", html, flags=re.S)
    assert len(svgs) == len(NAMES), f"expected {len(NAMES)} panels, found {len(svgs)}"
    with tempfile.TemporaryDirectory() as tmp:
        for name, svg in zip(NAMES, svgs):
            w, h = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups()
            page = Path(tmp) / f"{name}.html"
            page.write_text(f"{head}<body style='margin:0;background:#fcfcfb'>"
                            f"<div style='width:{w}px;height:{h}px'>{svg}</div></body></html>")
            out = SLIDES / f"{name}.png"
            subprocess.run([args.chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
                            f"--force-device-scale-factor={SCALE.get(name, 2)}", "--virtual-time-budget=3000",
                            f"--screenshot={out}", f"--window-size={w},{h}", page.as_uri()],
                           check=True, capture_output=True)
            print("wrote", out)


if __name__ == "__main__":
    main()
