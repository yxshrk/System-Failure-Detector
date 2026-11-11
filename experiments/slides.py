"""Presentation figures (16:9, large type) built from the scored results.

    python -m experiments.slides      -> results/figures/slides/*.png

Separate from analyze.py so the report figures stay untouched.
"""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from experiments.analyze import (ARM_LABEL, GRID, INK, INK2, MODEL_LABEL, MODEL_ORDER, ROOT, SURFACE, WEAK_MODEL,
                                 load)

OUT = ROOT / "results" / "figures" / "slides"
SIZE = (13.33, 7.5)  # 16:9 at 150 dpi -> 2000 x 1125
DPI = 150
BLUE, ORANGE, GREEN, PURPLE, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#b5b3ad"
BUCKETS = ["common", "uncommon", "rare", "very_rare"]
BUCKET_LABEL = ["common\n(≥10% of inputs)", "uncommon\n(1–10%)", "rare\n(0.1–1%)", "very rare\n(<0.1%)"]


def style(ax, grid="y"):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=15, length=0)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=1)
    ax.set_axisbelow(True)


def title(fig, head, sub=None):
    fig.text(0.04, 0.93, head, fontsize=28, color=INK, weight="bold", ha="left", va="top")
    if sub:
        fig.text(0.04, 0.855, sub, fontsize=17, color=INK2, ha="left", va="top")


def save(fig, name):
    fig.savefig(OUT / name, dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", OUT / name)


def sp2_frame() -> pd.DataFrame:
    inst = {i["id"]: i for i in json.loads((ROOT / "data" / "sp2" / "instances.json").read_text())["instances"]}
    d = load("sp2")
    d = d[d.instance.isin(inst)].copy()
    d["set"] = d.instance.map(lambda x: inst[x].get("set", "main"))
    return d


# ---------------------------------------------------------------------------
# 1. Scoreboard: every model x arm against the four headline numbers
# ---------------------------------------------------------------------------

def scoreboard(sp1: pd.DataFrame, sp2: pd.DataFrame):
    cols = [("SP1 bugs\nfound", "found"), ("SP1 false\nalarms", "alarm"),
            ("SP2 traces\nfound", "found"), ("SP2 false\nalarms", "alarm"), ("SP2 false alarms\n(names hidden)", "alarm")]
    rows, cells = [], []
    for model in MODEL_ORDER:
        for arm in ("direct", "translate"):
            a, m, o = sp1[(sp1.model == model) & (sp1.arm == arm)], sp2[(sp2.model == model) & (sp2.arm == arm)], None
            main, opaque = m[m.set == "main"], m[m.set == "opaque"]
            bugs, ctrl = a[a.kind == "bug"], a[a.kind == "control"]
            viol, fixed, ofixed = main[main.violation == True], main[main.violation == False], opaque[opaque.violation == False]  # noqa: E712
            counts = [((bugs.outcome == "valid_witness").sum(), len(bugs)),
                      ((ctrl.outcome == "false_alarm").sum(), len(ctrl)),
                      ((viol.outcome == "valid_trace").sum(), len(viol)),
                      ((fixed.outcome == "false_alarm").sum(), len(fixed)),
                      ((ofixed.outcome == "false_alarm").sum(), len(ofixed)) if len(ofixed) else o]
            rows.append(f"{MODEL_LABEL[model]} · {ARM_LABEL[arm]}")
            cells.append(counts)

    # One sequential hue for "how wrong": share of the column that went badly (missed bugs or false alarms).
    cmap = LinearSegmentedColormap.from_list("bad", ["#f4f3f0", "#f8c9b3", ORANGE, "#a53d12"])
    fig = plt.figure(figsize=SIZE, facecolor=SURFACE)
    title(fig, "Sonnet, Opus, Qwen near-perfect; Haiku, Llama are not",
          "Darker = more wrong: bugs missed, or false alarms raised on correct code")
    ax = fig.add_axes([0.25, 0.03, 0.72, 0.66])
    ax.set_facecolor(SURFACE)
    for r, counts in enumerate(cells):
        for c, cnt in enumerate(counts):
            if cnt is None:
                ax.add_patch(plt.Rectangle((c + 0.04, r + 0.06), 0.92, 0.88, color="#ebeae6", linewidth=0))
                ax.text(c + 0.5, r + 0.5, "not run", ha="center", va="center", fontsize=14, color=INK2)
                continue
            k, n = cnt
            bad = (n - k) / n if cols[c][1] == "found" else k / n
            ax.add_patch(plt.Rectangle((c + 0.04, r + 0.06), 0.92, 0.88, color=cmap(bad), linewidth=0))
            ax.text(c + 0.5, r + 0.5, f"{k}/{n}", ha="center", va="center", fontsize=17,
                    color="white" if bad > 0.45 else INK, weight="bold" if bad > 0.1 else "normal")
    ax.set_xlim(0, len(cols))
    ax.set_ylim(len(rows), 0)
    ax.set_xticks(np.arange(len(cols)) + 0.5, [c[0] for c in cols], fontsize=15, color=INK)
    ax.xaxis.tick_top()
    ax.set_yticks(np.arange(len(rows)) + 0.5, rows, fontsize=15)
    for lbl, row in zip(ax.get_yticklabels(), rows):
        lbl.set_color(INK if row.startswith(MODEL_LABEL[WEAK_MODEL]) else INK2)
        if row.startswith(MODEL_LABEL[WEAK_MODEL]):
            lbl.set_weight("bold")
    ax.tick_params(length=0, pad=8)
    for side in ax.spines.values():
        side.set_visible(False)
    for y in range(2, len(rows), 2):
        ax.axhline(y, color=SURFACE, linewidth=5)
    save(fig, "scoreboard.png")


# ---------------------------------------------------------------------------
# 2. False alarms: Direct vs Translate on correct designs
# ---------------------------------------------------------------------------

def false_alarms(sp2: pd.DataFrame):
    fig = plt.figure(figsize=SIZE, facecolor=SURFACE)
    title(fig, "Translating to a formal model cuts false alarms",
          "False alarms on the 20 correct (fixed) designs, Direct vs. Translate")
    panels = (("main", "Readable names"), ("opaque", "Mechanism names hidden"))
    colors = {"haiku": BLUE, WEAK_MODEL: ORANGE}
    for p, (setname, ptitle) in enumerate(panels):
        ax = fig.add_axes([0.17 + p * 0.47, 0.11, 0.30, 0.62])
        style(ax)
        d = sp2[(sp2.set == setname) & (sp2.violation == False)]  # noqa: E712
        zero_group = []
        for model in MODEL_ORDER:
            dm = d[d.model == model]
            if dm.empty:
                continue
            ys = [int((dm[dm.arm == arm].outcome == "false_alarm").sum()) for arm in ("direct", "translate")]
            if model not in colors:
                zero_group.append((MODEL_LABEL[model], ys))
                continue
            col = colors[model]
            ls = "--" if model == WEAK_MODEL else "-"
            ax.plot([0, 1], ys, color=col, linewidth=3, linestyle=ls, marker="o", markersize=12,
                    markeredgecolor=SURFACE, markeredgewidth=2.5, zorder=3)
            name = MODEL_LABEL[model]
            ax.text(-0.06, ys[0], f"{name}  {ys[0]}", ha="right", va="center", fontsize=15, color=INK)
            ax.text(1.06, ys[1], f"{ys[1]}", ha="left", va="center", fontsize=15, color=INK, weight="bold")
        zs = [z for z in zero_group if z[1] == [0, 0]]
        if zs:
            ax.plot([0, 1], [0, 0], color=GREEN, linewidth=3, marker="o", markersize=12,
                    markeredgecolor=SURFACE, markeredgewidth=2.5, zorder=3)
            names = ", ".join(n.replace(" 5.5", "").replace(" 3.8 27B", "") for n, _ in zs)
            ax.text(0.5, 0.7, f"{names}: 0 → 0", ha="center", va="bottom", fontsize=15, color=INK)
        ax.set_xlim(-0.05, 1.12)
        ax.set_ylim(-1, 20.5)
        ax.set_xticks([0, 1], ["Direct", "Translate"], fontsize=17, color=INK)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.grid(False)
        for xv in (0, 1):
            ax.axvline(xv, color=GRID, linewidth=1, zorder=1)
        ax.set_title(ptitle, fontsize=18, color=INK, loc="center", pad=14)
    fig.text(0.04, 0.025, "Dashed: Llama's drop is mostly because its problem files left out facts, "
             "so the planner found no violation, not because it reasoned better.", fontsize=13, color=INK2, style="italic")
    save(fig, "false_alarms.png")


# ---------------------------------------------------------------------------
# Deck-sized panels: drawn at the exact size of their slot in the deck, no title (the slide has it)
# ---------------------------------------------------------------------------

def panel_style(ax):
    style(ax)
    ax.tick_params(labelsize=11)


def hardness(sp1: pd.DataFrame, sp2: pd.DataFrame):
    """Slide 9: SP1 valid witnesses vs trigger rarity, SP2 valid traces vs shortest trace length."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.25, 3.4), facecolor=SURFACE)
    for ax in (a, b):
        panel_style(ax)
        ax.set_ylim(0, 108)
        ax.set_xlim(-0.35, 3.35)
        ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])

    inst = pd.DataFrame(json.loads((ROOT / "data" / "sp1" / "instances.json").read_text())["instances"])
    bug_inst = inst[(inst.kind == "bug") & inst.bucket.isin(BUCKETS)]
    strong = sp1[(sp1.kind == "bug") & (sp1.model != WEAK_MODEL)]
    series = [(f"random, {n:,} inputs", [100 * (1 - (1 - bug_inst[bug_inst.bucket == k].rarity) ** n).mean() for k in BUCKETS], col, "-")
              for n, col in ((100, MUTED), (1000, INK2))]
    for arm, col in (("direct", BLUE), ("translate", ORANGE)):
        d = strong[strong.arm == arm]
        series.append((f"LLM {ARM_LABEL[arm]} (4 models pooled)", [100 * (d[d.bucket == k].outcome == "valid_witness").mean() for k in BUCKETS], col, "-"))
    for label, ys, col, ls in series:
        a.plot(range(4), ys, color=col, linewidth=2.4, linestyle=ls, marker="o", markersize=7,
               markeredgecolor=SURFACE, markeredgewidth=1.5, label=label)
    a.set_xticks(range(4), ["common", "uncommon", "rare", "very rare"], fontsize=11)
    a.set_xlabel("SP1: how rare the failing inputs are", fontsize=11, color=INK2)
    a.set_ylabel("failures found", fontsize=11, color=INK2)
    a.legend(frameon=False, fontsize=10, loc="lower left")

    inst2 = {i["id"]: i for i in json.loads((ROOT / "data" / "sp2" / "instances.json").read_text())["instances"]}
    v = sp2[(sp2.violation == True) & (sp2.set != "opaque")].copy()  # noqa: E712
    v["shortest"] = v.instance.map(lambda x: inst2[x]["shortest"])
    bins = [(6, 10), (11, 15), (17, 27), (30, 51)]
    lines = [("Sonnet 5.5, Opus 5.5 (both arms)", v[v.model.isin(["sonnet", "opus"])], GREEN),
             ("Haiku 4.5 Direct", v[(v.model == "haiku") & (v.arm == "direct")], BLUE),
             ("Haiku 4.5 Translate", v[(v.model == "haiku") & (v.arm == "translate")], ORANGE)]
    for label, d, col in lines:
        ys = []
        for lo, hi in bins:
            db = d[(d.shortest >= lo) & (d.shortest <= hi)]
            ys.append(100 * (db.outcome == "valid_trace").mean() if len(db) else np.nan)
        b.plot(range(len(bins)), ys, color=col, linewidth=2.4, marker="o", markersize=7,
               markeredgecolor=SURFACE, markeredgewidth=1.5, label=label)
    b.set_xticks(range(len(bins)), [f"{lo}–{hi}" for lo, hi in bins], fontsize=11)
    b.set_xlabel("SP2: shortest known failure trace (events)", fontsize=11, color=INK2)
    b.legend(frameon=False, fontsize=10, loc="lower left")
    b.text(3, 92, "Haiku not run\non 30–51", fontsize=9, color=INK2, ha="center", va="top")
    fig.tight_layout(w_pad=3)
    save(fig, "hardness_panel.png")


def inventory_panel():
    """Slide 11: states expanded to certify the fixed designs, inventory highlighted."""
    inst = [i for i in json.loads((ROOT / "data" / "sp2" / "instances.json").read_text())["instances"]
            if i["variant"] == "fixed" and i.get("set", "main") in ("main", "stress")]
    fig, ax = plt.subplots(figsize=(4.375, 3.18), facecolor=SURFACE)
    panel_style(ax)
    for fam in ("payments", "lock", "queue", "cache", "inventory"):
        d = sorted([i for i in inst if i["family"] == fam], key=lambda i: i["size"])
        xs, ys = [i["size"] for i in d], [max(i["gold"]["gbfs"]["expanded"], 1) for i in d]
        hot = fam == "inventory"
        ax.plot(xs, ys, color=ORANGE if hot else MUTED, linewidth=2.6 if hot else 1.5, marker="o",
                markersize=6 if hot else 4, markeredgecolor=SURFACE, markeredgewidth=1.2, zorder=3 if hot else 2)
    ax.annotate("2.7M", (6, 2685810), xytext=(-6, 8), textcoords="offset points", ha="right", fontsize=10, color=INK)
    # Size 8 hit the search cap before a proof: open marker, the true count is higher.
    ax.plot([8], [2637989], marker="o", markersize=8, markerfacecolor=SURFACE, markeredgecolor=ORANGE, markeredgewidth=2, zorder=4)
    ax.annotate("capped", (8, 2637989), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=10, color=INK)
    ax.text(8.2, 9026 * 0 + 30000, "inventory", fontsize=10, color=ORANGE, weight="bold", ha="right")
    ax.text(8.2, 900, "other 4 designs", fontsize=10, color=INK2, ha="right")
    ax.set_yscale("log")
    ax.minorticks_off()
    ax.set_ylim(1, 3e7)
    ax.set_yticks([1, 100, 1e4, 1e6], ["1", "100", "10k", "1M"])
    ax.set_xticks([1, 2, 3, 4, 6, 8])
    ax.set_xlabel("design size", fontsize=11, color=INK2)
    ax.set_ylabel("states expanded to prove safe", fontsize=10, color=INK2)
    fig.tight_layout()
    save(fig, "inventory_panel.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sp1, sp2 = load("sp1"), sp2_frame()
    scoreboard(sp1, sp2)
    false_alarms(sp2)
    hardness(sp1, sp2)
    inventory_panel()


if __name__ == "__main__":
    main()
