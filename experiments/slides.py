"""Presentation figures built from the scored results, drawn at the size of their slot in the deck.

    python -m experiments.slides      -> results/figures/slides/*.png

Separate from analyze.py so the report figures stay untouched. Deck conventions: Arial throughout, no
title baked into a figure (the slide has it), blue only for Direct and orange only for Translate,
models in tier order (strong, mid-tier, weak).
"""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.transforms import blended_transform_factory

from experiments.analyze import (ARM_LABEL, GRID, INK, INK2, MODEL_LABEL, ROOT, SURFACE, WEAK_MODEL,
                                 load)

plt.rcParams["font.family"] = "Arial"
OUT = ROOT / "results" / "figures" / "slides"
DPI = 220
BLUE, ORANGE, GREEN, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#b5b3ad"
ARM_COLOR = {"direct": BLUE, "translate": ORANGE}
BUCKETS = ["common", "uncommon", "rare", "very_rare"]
QWEN = "soc:qwen3.8:27b"
TIERS = [("Strong", ["sonnet", "opus", QWEN]), ("Mid-tier", ["haiku"]), ("Weak", [WEAK_MODEL])]
TIER_ORDER = [m for _, ms in TIERS for m in ms]


def style(ax, grid="y"):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=11, length=0)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=1)
    ax.set_axisbelow(True)


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
# 1. Scoreboard: every model and arm against the five headline numbers (slide 12)
# ---------------------------------------------------------------------------

def scoreboard(sp1: pd.DataFrame, sp2: pd.DataFrame):
    cols = [("Functions:\nbugs found\n(of 115)", "found", 115), ("Functions:\nfalse alarms\n(of 59 correct)", "alarm", 59),
            ("Designs:\nfailure traces found\n(of 40)", "found", 40), ("Designs:\nfalse alarms\n(of 20 correct)", "alarm", 20),
            ("Designs, names hidden:\nfalse alarms\n(of 20 correct)", "alarm", 20)]
    rows, cells = [], []
    for model in TIER_ORDER:
        for arm in ("direct", "translate"):
            a, m = sp1[(sp1.model == model) & (sp1.arm == arm)], sp2[(sp2.model == model) & (sp2.arm == arm)]
            main, opaque = m[m.set == "main"], m[m.set == "opaque"]
            bugs, ctrl = a[a.kind == "bug"], a[a.kind == "control"]
            viol, fixed, ofixed = main[main.violation == True], main[main.violation == False], opaque[opaque.violation == False]  # noqa: E712
            counts = [((bugs.outcome == "valid_witness").sum(), len(bugs)),
                      ((ctrl.outcome == "false_alarm").sum(), len(ctrl)),
                      ((viol.outcome == "valid_trace").sum(), len(viol)),
                      ((fixed.outcome == "false_alarm").sum(), len(fixed)),
                      ((ofixed.outcome == "false_alarm").sum(), len(ofixed)) if len(ofixed) else None]
            rows.append((model, arm))
            cells.append(counts)

    # One neutral ramp for "how wrong" (share of the column that went badly); blue and orange stay for the arms.
    cmap = LinearSegmentedColormap.from_list("bad", ["#f4f3f0", "#d9d8d3", "#8a8985", "#3a3a38"])
    fig = plt.figure(figsize=(9.25, 3.55), facecolor=SURFACE)
    ax = fig.add_axes([0.31, 0.0, 0.675, 0.76])
    ax.set_facecolor(SURFACE)
    gap = {2, 4, 6, 8}  # extra space between models
    ys, y = [], 0.0
    for r in range(len(rows)):
        if r in gap:
            y += 0.18 if r != 6 else 0.45  # wider gap between tiers (strong | mid-tier)
        if r == 8:
            y += 0.27
        ys.append(y)
        y += 1
    for r, counts in enumerate(cells):
        for c, cnt in enumerate(counts):
            y0 = ys[r]
            if cnt is None:
                ax.add_patch(plt.Rectangle((c + 0.04, y0 + 0.06), 0.92, 0.88, color="#ebeae6", linewidth=0))
                ax.text(c + 0.5, y0 + 0.5, "not run", ha="center", va="center", fontsize=9.5, color=INK2)
                continue
            k, n = cnt
            bad = (n - k) / n if cols[c][1] == "found" else k / n
            label = f"{k}" if n == cols[c][2] else f"{k} of {n}"
            ax.add_patch(plt.Rectangle((c + 0.04, y0 + 0.06), 0.92, 0.88, color=cmap(bad), linewidth=0))
            ax.text(c + 0.5, y0 + 0.5, label, ha="center", va="center", fontsize=11,
                    color="white" if bad > 0.45 else INK, weight="bold" if bad > 0.1 else "normal")
    ax.set_xlim(0, len(cols))
    ax.set_ylim(y, 0)
    ax.set_xticks(np.arange(len(cols)) + 0.5, [c[0] for c in cols], fontsize=9, color=INK)
    ax.xaxis.tick_top()
    ax.set_yticks([])
    ax.tick_params(length=0, pad=4)
    for side in ax.spines.values():
        side.set_visible(False)
    # Row labels drawn by hand: tier, model, then the arm in its colour.
    for r, (model, arm) in enumerate(rows):
        yc = ys[r] + 0.5
        ax.text(-0.08, yc, ARM_LABEL[arm], ha="right", va="center", fontsize=10.5, color=ARM_COLOR[arm], weight="bold")
        if arm == "direct":
            ax.text(-0.8, ys[r] + 1.0, MODEL_LABEL[model], ha="right", va="center", fontsize=10.5, color=INK)
    for tier, models in TIERS:
        idx = [r for r, (m, _) in enumerate(rows) if m in models]
        top, bot = ys[idx[0]] + 0.08, ys[idx[-1]] + 0.92
        tr = blended_transform_factory(fig.transFigure, ax.transData)
        ax.text(0.004, (top + bot) / 2, tier, ha="left", va="center", fontsize=10.5, color=INK, weight="bold", transform=tr)
        ax.plot([0.08, 0.08], [top, bot], color=INK2, linewidth=1.2, clip_on=False, transform=tr)
    save(fig, "scoreboard.png")


# ---------------------------------------------------------------------------
# 2. False alarms on the correct designs, Direct vs Translate (slide 14)
# ---------------------------------------------------------------------------

def false_alarms(sp2: pd.DataFrame):
    fig = plt.figure(figsize=(9.25, 3.45), facecolor=SURFACE)
    panels = (("main", "Readable names"), ("opaque", "Names hidden"))
    lines = {"haiku": dict(color=INK, ls="-"), WEAK_MODEL: dict(color=INK2, ls="--")}
    for p, (setname, ptitle) in enumerate(panels):
        ax = fig.add_axes([0.235 + p * 0.465, 0.12, 0.22, 0.74])
        style(ax)
        d = sp2[(sp2.set == setname) & (sp2.violation == False)]  # noqa: E712
        zero_group, ends = [], []
        for model in TIER_ORDER:
            dm = d[d.model == model]
            if dm.empty:
                continue
            ys = [int((dm[dm.arm == arm].outcome == "false_alarm").sum()) for arm in ("direct", "translate")]
            n = [int((dm.arm == arm).sum()) for arm in ("direct", "translate")]
            if model not in lines:
                zero_group.append((MODEL_LABEL[model], ys, n))
                continue
            st = lines[model]
            ax.plot([0, 1], ys, color=st["color"], linewidth=2.6, linestyle=st["ls"], marker="o", markersize=8,
                    markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
            ends.append((MODEL_LABEL[model], ys, n))
        zs = [z for z in zero_group if z[1] == [0, 0]]
        if zs:
            ax.plot([0, 1], [0, 0], color=GREEN, linewidth=2.6, marker="o", markersize=8,
                    markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
            names = ", ".join(n.replace(" 5.5", "").replace(" 3.8 27B", "") for n, _, _ in zs)
            ends.insert(0, (names, [0, 0], zs[0][2]))
        # Labels: model and Direct count on the left, Translate count on the right; nudge apart when close.
        for side in (0, 1):
            pos = sorted(((e[1][side], i) for i, e in enumerate(ends)))
            placed = {}
            for k, (yv, i) in enumerate(pos):
                yl = yv
                if k and yl - placed[pos[k - 1][1]] < 1.7:
                    yl = placed[pos[k - 1][1]] + 1.7
                placed[i] = yl
            for i, (name, ys, n) in enumerate(ends):
                if side == 0:
                    ax.text(-0.07, placed[i], f"{name}   {ys[0]} of {n[0]}", ha="right", va="center", fontsize=10.5, color=INK)
                else:
                    ax.text(1.07, placed[i], f"{ys[1]} of {n[1]}", ha="left", va="center", fontsize=10.5, color=INK, weight="bold")
        ax.set_xlim(-0.05, 1.12)
        ax.set_ylim(-1, 20.5)
        ax.set_xticks([0, 1], ["Direct", "Translate"], fontsize=12)
        for lbl, arm in zip(ax.get_xticklabels(), ("direct", "translate")):
            lbl.set_color(ARM_COLOR[arm])
            lbl.set_weight("bold")
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.grid(False)
        for xv in (0, 1):
            ax.axvline(xv, color=GRID, linewidth=1, zorder=1)
        ax.set_title(ptitle, fontsize=12, color=INK, loc="center", pad=10, weight="bold")
    save(fig, "false_alarms.png")


# ---------------------------------------------------------------------------
# 3. RQ1: valid witnesses vs how hard the failure is to reach (slide 13)
# ---------------------------------------------------------------------------

def hardness(sp1: pd.DataFrame, sp2: pd.DataFrame):
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.25, 3.45), facecolor=SURFACE)
    for ax in (a, b):
        style(ax)
        ax.set_ylim(0, 108)
        ax.set_xlim(-0.35, 3.35)
        ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])

    inst = pd.DataFrame(json.loads((ROOT / "data" / "sp1" / "instances.json").read_text())["instances"])
    bug_inst = inst[(inst.kind == "bug") & inst.bucket.isin(BUCKETS)]
    pooled = sp1[(sp1.kind == "bug") & (sp1.model != WEAK_MODEL)]
    series = [(f"random testing, {n:,} inputs", [100 * (1 - (1 - bug_inst[bug_inst.bucket == k].rarity) ** n).mean() for k in BUCKETS], col)
              for n, col in ((100, MUTED), (1000, INK2))]
    for arm in ("direct", "translate"):
        d = pooled[pooled.arm == arm]
        series.append((f"{ARM_LABEL[arm]}, pooled: Sonnet, Opus, Qwen, Haiku",
                       [100 * (d[d.bucket == k].outcome == "valid_witness").mean() for k in BUCKETS], ARM_COLOR[arm]))
    for label, ys, col in series:
        a.plot(range(4), ys, color=col, linewidth=2.4, marker="o", markersize=7,
               markeredgecolor=SURFACE, markeredgewidth=1.5, label=label)
    a.set_xticks(range(4), ["common", "uncommon", "rare", "very rare"])
    a.set_xlabel("Functions, by how rare the failing input is", fontsize=10, color=INK)
    a.set_ylabel("failures found", fontsize=11, color=INK2)
    a.legend(frameon=False, fontsize=8.5, loc="lower left")

    inst2 = {i["id"]: i for i in json.loads((ROOT / "data" / "sp2" / "instances.json").read_text())["instances"]}
    v = sp2[(sp2.violation == True) & (sp2.set != "opaque")].copy()  # noqa: E712
    v["shortest"] = v.instance.map(lambda x: inst2[x]["shortest"])
    bins = [(6, 10), (11, 15), (17, 27), (30, 51)]
    lines = [("Sonnet 5.5 and Opus 5.5 (both arms)", v[v.model.isin(["sonnet", "opus"])], GREEN),
             ("Haiku 4.5, Direct", v[(v.model == "haiku") & (v.arm == "direct")], BLUE),
             ("Haiku 4.5, Translate", v[(v.model == "haiku") & (v.arm == "translate")], ORANGE)]
    for label, d, col in lines:
        ys = []
        for lo, hi in bins:
            db = d[(d.shortest >= lo) & (d.shortest <= hi)]
            ys.append(100 * (db.outcome == "valid_trace").mean() if len(db) else np.nan)
        b.plot(range(len(bins)), ys, color=col, linewidth=2.4, marker="o", markersize=7,
               markeredgecolor=SURFACE, markeredgewidth=1.5, label=label)
    b.set_xticks(range(len(bins)), [f"{lo}–{hi}" for lo, hi in bins])
    b.set_xlabel("Designs, by the shortest known failure trace (events)", fontsize=10, color=INK)
    b.set_ylabel("failure traces found", fontsize=11, color=INK2)
    b.legend(frameon=False, fontsize=9, loc="lower left")
    b.text(3, 92, "Haiku not run\non 30–51", fontsize=9, color=INK2, ha="center", va="top")
    fig.tight_layout(w_pad=3)
    save(fig, "hardness_panel.png")


# ---------------------------------------------------------------------------
# 4. States expanded to certify the fixed designs, inventory highlighted (slide 15)
# ---------------------------------------------------------------------------

def inventory_panel():
    inst = [i for i in json.loads((ROOT / "data" / "sp2" / "instances.json").read_text())["instances"]
            if i["variant"] == "fixed" and i.get("set", "main") in ("main", "stress")]
    fig, ax = plt.subplots(figsize=(2.875, 2.9), facecolor=SURFACE)
    style(ax)
    ax.tick_params(labelsize=9)
    for fam in ("payments", "lock", "queue", "cache", "inventory"):
        d = sorted([i for i in inst if i["family"] == fam], key=lambda i: i["size"])
        xs, ys = [i["size"] for i in d], [max(i["gold"]["gbfs"]["expanded"], 1) for i in d]
        hot = fam == "inventory"
        if hot:  # solid up to the last proof (size 6); dashed to size 8, where the budget ran out first
            k = xs.index(6) + 1
            ax.plot(xs[:k], ys[:k], color=INK, linewidth=2.4, marker="o", markersize=5,
                    markeredgecolor=SURFACE, markeredgewidth=1.0, zorder=3)
            ax.plot(xs[k - 1:], ys[k - 1:], color=INK, linewidth=1.8, linestyle=(0, (3, 2)), zorder=3)
            continue
        ax.plot(xs, ys, color=MUTED, linewidth=1.4, marker="o", markersize=3.5,
                markeredgecolor=SURFACE, markeredgewidth=1.0, zorder=2)
    ax.annotate("2.7M", (6, 2685810), xytext=(-6, 6), textcoords="offset points", ha="right", fontsize=9, color=INK)
    # Size 8 exceeded the search budget before a proof: open marker, the true count is higher.
    ax.plot([8], [2637989], marker="o", markersize=7, markerfacecolor=SURFACE, markeredgecolor=INK, markeredgewidth=1.8, zorder=4)
    ax.annotate("budget\nexceeded", (8, 2637989), xytext=(0, 7), textcoords="offset points", ha="center", va="bottom", fontsize=8.5, color=INK)
    ax.text(8.2, 30000, "inventory", fontsize=9, color=INK, weight="bold", ha="right")
    ax.text(8.2, 900, "other 4 designs", fontsize=9, color=INK2, ha="right")
    ax.set_yscale("log")
    ax.minorticks_off()
    ax.set_ylim(1, 3e8)
    ax.set_yticks([1, 100, 1e4, 1e6], ["1", "100", "10k", "1M"])
    ax.set_xticks([1, 2, 3, 4, 6, 8])
    ax.set_xlabel("design size", fontsize=9.5, color=INK2)
    ax.set_ylabel("states expanded to prove safe\n(log scale)", fontsize=9, color=INK2)
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
