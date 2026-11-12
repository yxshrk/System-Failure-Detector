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
# Each panel is <svg id="NAME" viewBox="x y w h">, written to NAME.png at 2x.
NAMES = ["two_tasks", "method", "coldcard_timeline", "sp1_formulation", "sp2_trace"]
SCALE = 2
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome", default=CHROME, help="path to a Chrome or Chromium binary")
    args = ap.parse_args()
    html = (SLIDES / "diagrams.html").read_text()
    head = html.split("<body>")[0]
    svgs = re.findall(r'<svg id="(\w+)" viewBox="[-\d.]+ [-\d.]+ (\d+) (\d+)".*?</svg>', html, flags=re.S)
    assert [s[0] for s in svgs] == NAMES, f"expected panels {NAMES}, found {[s[0] for s in svgs]}"
    with tempfile.TemporaryDirectory() as tmp:
        for name, w, h in svgs:
            svg = re.search(rf'<svg id="{name}".*?</svg>', html, flags=re.S).group(0)
            page = Path(tmp) / f"{name}.html"
            page.write_text(f"{head}<body style='margin:0;background:#fcfcfb'>"
                            f"<div style='width:{w}px;height:{h}px'>{svg}</div></body></html>")
            out = SLIDES / f"{name}.png"
            subprocess.run([args.chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
                            f"--force-device-scale-factor={SCALE}", "--virtual-time-budget=3000",
                            f"--screenshot={out}", f"--window-size={w},{h}", page.as_uri()],
                           check=True, capture_output=True)
            print("wrote", out)


if __name__ == "__main__":
    main()
