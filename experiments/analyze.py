"""Aggregate scored results into tables (results/tables.md, CSVs) and figures.

    python -m experiments.analyze
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
FIG = RES / "figures"
MODEL_ORDER = ["haiku", "sonnet", "opus"]
MODEL_LABEL = {"haiku": "Haiku 4.5", "sonnet": "Sonnet 5.5", "opus": "Opus 5.5"}
ARM_LABEL = {"direct": "Direct", "translate": "Translate"}

# Reference palette (dataviz skill, light mode): categorical slots in fixed order.
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
ARM_COLOR = {"direct": "#2a78d6", "translate": "#eb6834"}
OUTCOME_COLOR = {"valid": "#2a78d6", "fabricated": "#eb6834", "miss": "#1baf7a", "no answer": "#eda100"}


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _r(x: float) -> int:
    """Round half up (Python's round() and format() round half to even, which made 82.5% print as 82%)."""
    return int(x + 0.5)


def pct(k, n):
    return f"{_r(100 * k / n)}%" if n else "-"


def pct_ci(k, n):
    if not n:
        return "-"
    lo, hi = wilson(k, n)
    return f"{_r(100 * k / n)}% [{_r(100 * lo)}-{_r(100 * hi)}]"


def load(sub: str) -> pd.DataFrame:
    rows = []
    for p in sorted((RES / sub).glob("*.jsonl")):
        if ".partial" in p.name:
            continue
        for line in p.read_text().splitlines():
            rows.append(json.loads(line))
    return pd.DataFrame(rows)


def mcnemar(a: list[bool], b: list[bool]) -> tuple[int, int, float]:
    """Exact two-sided McNemar test on paired successes."""
    b10 = sum(x and not y for x, y in zip(a, b))
    b01 = sum(y and not x for x, y in zip(a, b))
    n = b10 + b01
    if n == 0:
        return b10, b01, 1.0
    k = min(b10, b01)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return b10, b01, min(1.0, 2 * p)


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


# ---------------------------------------------------------------------------
# SP1
# ---------------------------------------------------------------------------

def sp1_tables(df: pd.DataFrame, out: list[str]):
    inst = json.loads((ROOT / "data" / "sp1" / "instances.json").read_text())["instances"]
    tier = {i["id"]: i["tier"] for i in inst}
    df = df.copy()
    df["tier"] = df["instance"].map(tier)
    out.append("## SP1: one function (CSP / SMT)\n")
    out.append("| model | arm | tier | bugs | valid witness | fabricated | miss | no answer / undecided | controls | false alarm | controls undecided | $/inst | out tok |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    summary = []
    for model in MODEL_ORDER:
        for arm in ("direct", "translate"):
            for t in ("base", "hard", "all"):
                d = df[(df.model == model) & (df.arm == arm)]
                if t != "all":
                    d = d[d.tier == t]
                if d.empty:
                    continue
                bugs, ctrl = d[d.kind == "bug"], d[d.kind == "control"]
                c = Counter(bugs.outcome)
                fa = (ctrl.outcome == "false_alarm").sum()
                ctrl_undecided = ctrl.outcome.isin(["tool_timeout", "tool_undecided"]).sum()
                row = dict(model=model, arm=arm, tier=t, bugs=len(bugs), valid=c["valid_witness"],
                           fabricated=c["invalid_witness"], miss=c["miss"],
                           no_answer=c["no_answer"] + c["harness_error"] + c["tool_timeout"] + c["tool_undecided"],
                           controls=len(ctrl), false_alarm=int(fa), controls_undecided=int(ctrl_undecided), cost=d.llm_cost.mean(), tokens=d.output_tokens.mean())
                summary.append(row)
                out.append(f"| {MODEL_LABEL[model]} | {ARM_LABEL[arm]} | {t} | {len(bugs)} | {pct_ci(row['valid'], len(bugs))} | "
                           f"{pct(row['fabricated'], len(bugs))} | {pct(row['miss'], len(bugs))} | {pct(row['no_answer'], len(bugs))} | "
                           f"{len(ctrl)} | {pct_ci(int(fa), len(ctrl))} | {int(ctrl_undecided)} | {row['cost']:.3f} | {row['tokens']:.0f} |")
    pd.DataFrame(summary).to_csv(RES / "sp1_summary.csv", index=False)

    out.append("\n**Valid-witness rate by trigger rarity (bugs only)**\n")
    buckets = ["common", "uncommon", "rare", "very_rare"]
    out.append("| model | arm | " + " | ".join(buckets) + " |")
    out.append("|---|---|" + "---|" * len(buckets))
    for model in MODEL_ORDER:
        for arm in ("direct", "translate"):
            d = df[(df.model == model) & (df.arm == arm) & (df.kind == "bug")]
            if d.empty:
                continue
            cells = []
            for b in buckets:
                db = d[d.bucket == b]
                cells.append(f"{(db.outcome == 'valid_witness').sum()}/{len(db)}")
            out.append(f"| {MODEL_LABEL[model]} | {ARM_LABEL[arm]} | " + " | ".join(cells) + " |")

    out.append("\n**False alarms on controls: clean reference vs. equivalent mutant**\n")
    out.append("| model | arm | clean | equivalent |")
    out.append("|---|---|---|---|")
    for model in MODEL_ORDER:
        for arm in ("direct", "translate"):
            d = df[(df.model == model) & (df.arm == arm) & (df.kind == "control")]
            if d.empty:
                continue
            cl, eq = d[d.bucket == "clean"], d[d.bucket == "equivalent"]
            out.append(f"| {MODEL_LABEL[model]} | {ARM_LABEL[arm]} | {(cl.outcome == 'false_alarm').sum()}/{len(cl)} | "
                       f"{(eq.outcome == 'false_alarm').sum()}/{len(eq)} |")

    out.append("\n**Direct vs. Translate on the same bug instances (exact McNemar)**\n")
    out.append("| model | tier | only Direct valid | only Translate valid | p |")
    out.append("|---|---|---|---|---|")
    for model in MODEL_ORDER:
        for t in ("base", "hard", "all"):
            d = df[(df.model == model) & (df.kind == "bug")]
            if t != "all":
                d = d[d.tier == t]
            a = d[d.arm == "direct"].set_index("instance").outcome.eq("valid_witness")
            b = d[d.arm == "translate"].set_index("instance").outcome.eq("valid_witness")
            common = a.index.intersection(b.index)
            if len(common) == 0:
                continue
            b10, b01, p = mcnemar(list(a[common]), list(b[common]))
            out.append(f"| {MODEL_LABEL[model]} | {t} | {b10} | {b01} | {p:.3f} |")

    inst_df = pd.DataFrame(inst)
    bugs_i = inst_df[inst_df.kind == "bug"]
    out.append("\n**Alternative: random testing (expected share of bugs caught by N uniform in-domain inputs, from measured rarity)**\n")
    out.append("| tier | bucket | bugs | N=10 | N=100 | N=1000 |")
    out.append("|---|---|---|---|---|---|")
    for t in ("base", "hard"):
        for b in ["common", "uncommon", "rare", "very_rare"]:
            d = bugs_i[(bugs_i.tier == t) & (bugs_i.bucket == b)]
            if d.empty:
                continue
            cells = [f"{100 * (1 - (1 - d.rarity) ** n).mean():.0f}%" for n in (10, 100, 1000)]
            out.append(f"| {t} | {b} | {len(d)} | " + " | ".join(cells) + " |")

    tr = df[df.arm == "translate"]
    if not tr.empty:
        out.append("\n**Translate-arm repair loop (SP1): valid witnesses using only the first specification vs. after up to 2 repairs**\n")
        out.append("| model | first attempt only | with repairs |")
        out.append("|---|---|---|")
        for model in MODEL_ORDER:
            d = tr[(tr.model == model) & (tr.kind == "bug")]
            if d.empty:
                continue
            v = d.outcome == "valid_witness"
            out.append(f"| {MODEL_LABEL[model]} | {(v & (d.attempts == 1)).sum()}/{len(d)} | {v.sum()}/{len(d)} |")
        out.append("\n**SP3 (SP1 translation quality)**\n")
        out.append("| model | specs accepted | first try | sound | unsound specs that hid the bug | mean attempts |")
        out.append("|---|---|---|---|---|---|")
        for model in MODEL_ORDER:
            d = tr[tr.model == model]
            if d.empty:
                continue
            accepted = d.spec_sound.notna().sum()
            sound = (d.spec_sound == True).sum()  # noqa: E712
            hid = ((d.kind == "bug") & (d.outcome == "miss") & (d.spec_sound == False)).sum()  # noqa: E712
            out.append(f"| {MODEL_LABEL[model]} | {accepted}/{len(d)} | {(d.attempts == 1).sum()}/{len(d)} | "
                       f"{sound}/{accepted} | {hid} | {d.attempts.mean():.2f} |")
    return df


def fig_sp1(df: pd.DataFrame):
    """Valid witnesses vs. trigger rarity: both LLM arms (pooled over models) against random testing."""
    buckets = ["common", "uncommon", "rare", "very_rare"]
    labels = ["common\n(>=10%)", "uncommon\n(1-10%)", "rare\n(0.1-1%)", "very rare\n(<0.1%)"]
    inst = pd.DataFrame(json.loads((ROOT / "data" / "sp1" / "instances.json").read_text())["instances"])
    bugs_i = inst[(inst.kind == "bug") & (inst.tier == "base")]
    fig, ax = plt.subplots(figsize=(5.6, 3.0), facecolor=SURFACE)
    style(ax)
    series = []
    for arm in ("direct", "translate"):
        d = df[(df.arm == arm) & (df.kind == "bug") & (df.tier == "base")]
        ys = [100 * (d[d.bucket == b].outcome == "valid_witness").mean() for b in buckets]
        n_models = d.model.nunique()
        series.append((f"LLM {ARM_LABEL[arm]} ({n_models} models pooled)", ys, ARM_COLOR[arm], "-"))
    for n, col in ((100, "#1baf7a"), (1000, "#6250d6")):
        ys = [100 * (1 - (1 - bugs_i[bugs_i.bucket == b].rarity) ** n).mean() for b in buckets]
        series.append((f"random testing, {n} inputs", ys, col, "-"))
    for label, ys, col, ls in series:
        ax.plot(range(4), ys, color=col, linewidth=2, linestyle=ls, marker="o", markersize=5,
                markeredgecolor=SURFACE, markeredgewidth=1.5, label=label)
    ax.set_xticks(range(4), labels, fontsize=7)
    ax.set_ylim(0, 105)
    ax.set_ylabel("bugs with a valid witness (%)", fontsize=8, color=INK2)
    ax.legend(frameon=False, fontsize=7, loc="lower left")
    ax.set_title("SP1 base tier: witness found vs. trigger rarity", fontsize=9, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "sp1_rarity.png", dpi=200, facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------------------
# SP2
# ---------------------------------------------------------------------------

def sp2_tables(df: pd.DataFrame, out: list[str], title: str = "SP2: one design (STRIPS planning)", brief: bool = False):
    out.append(f"\n## {title}\n")
    out.append("| model | arm | violating designs | valid trace | fabricated trace | miss | no answer | fixed designs | false alarm | $/inst |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    rows = []
    for model in MODEL_ORDER:
        for arm in ("direct", "translate"):
            d = df[(df.model == model) & (df.arm == arm)]
            if d.empty:
                continue
            v, f = d[d.violation == True], d[d.violation == False]  # noqa: E712
            c = Counter(v.outcome)
            fa = (f.outcome == "false_alarm").sum()
            rows.append(dict(model=model, arm=arm, valid=c["valid_trace"], n=len(v), fabricated=c["invalid_trace"],
                             miss=c["miss"], false_alarm=int(fa), n_fixed=len(f)))
            out.append(f"| {MODEL_LABEL[model]} | {ARM_LABEL[arm]} | {len(v)} | {pct_ci(c['valid_trace'], len(v))} | "
                       f"{pct(c['invalid_trace'], len(v))} | {pct(c['miss'], len(v))} | {pct(c['no_answer'] + c['harness_error'] + c['tool_limit'], len(v))} | "
                       f"{len(f)} | {pct_ci(int(fa), len(f))} | {d.llm_cost.mean():.3f} |")
    if not brief:
        pd.DataFrame(rows).to_csv(RES / "sp2_summary.csv", index=False)

    out.append("\n**SP2 by variant (valid trace on flawed/subtle; correct 'safe' on fixed)**\n")
    out.append("| model | arm | " + " | ".join(f"{fam}" for fam in ("payments", "inventory", "lock", "queue", "cache")) + " | flawed | subtle | fixed |")
    out.append("|---|---|" + "---|" * 8)
    for model in MODEL_ORDER:
        for arm in ("direct", "translate"):
            d = df[(df.model == model) & (df.arm == arm)]
            if d.empty:
                continue
            good = d.outcome.isin(["valid_trace", "correct_safe"])
            cells = [f"{good[d.family == fam].sum()}/{(d.family == fam).sum()}" for fam in ("payments", "inventory", "lock", "queue", "cache")]
            cells += [f"{good[d.variant == v].sum()}/{(d.variant == v).sum()}" for v in ("flawed", "subtle", "fixed")]
            out.append(f"| {MODEL_LABEL[model]} | {ARM_LABEL[arm]} | " + " | ".join(cells) + " |")

    out.append("\n**Valid traces by shortest violating-trace length (flawed + subtle)**\n")
    lengths = sorted(df[df.violation == True].shortest.dropna().unique())  # noqa: E712
    out.append("| model | arm | " + " | ".join(str(int(x)) for x in lengths) + " |")
    out.append("|---|---|" + "---|" * len(lengths))
    for model in MODEL_ORDER:
        for arm in ("direct", "translate"):
            d = df[(df.model == model) & (df.arm == arm) & (df.violation == True)]  # noqa: E712
            if d.empty:
                continue
            cells = [f"{(d[d.shortest == L].outcome == 'valid_trace').sum()}/{(d.shortest == L).sum()}" for L in lengths]
            out.append(f"| {MODEL_LABEL[model]} | {ARM_LABEL[arm]} | " + " | ".join(cells) + " |")

    out.append("\n**Direct vs. Translate on the same designs (exact McNemar; success = correct verdict with valid trace)**\n")
    out.append("| model | only Direct correct | only Translate correct | p |")
    out.append("|---|---|---|---|")
    for model in MODEL_ORDER:
        d = df[df.model == model]
        ok = d.outcome.isin(["valid_trace", "correct_safe"])
        a = ok[d.arm == "direct"].set_axis(d[d.arm == "direct"].instance)
        b = ok[d.arm == "translate"].set_axis(d[d.arm == "translate"].instance)
        common = a.index.intersection(b.index)
        if len(common) == 0:
            continue
        b10, b01, p = mcnemar(list(a[common]), list(b[common]))
        out.append(f"| {MODEL_LABEL[model]} | {b10} | {b01} | {p:.3f} |")

    tr = df[df.arm == "translate"]
    if not tr.empty:
        out.append("\n**Translate-arm repair loop (SP2): correct outcomes using only the first problem file vs. after repairs**\n")
        out.append("| model | first attempt only | with repairs |")
        out.append("|---|---|---|")
        for model in MODEL_ORDER:
            d = tr[tr.model == model]
            if d.empty:
                continue
            ok = d.outcome.isin(["valid_trace", "correct_safe"])
            out.append(f"| {MODEL_LABEL[model]} | {(ok & (d.attempts == 1)).sum()}/{len(d)} | {ok.sum()}/{len(d)} |")
        out.append("\n**SP3 (SP2 translation quality: model-written initial state vs. gold)**\n")
        out.append("| model | parsed | design facts exact | init exact | init precision | init recall | first try |")
        out.append("|---|---|---|---|---|---|---|")
        for model in MODEL_ORDER:
            d = tr[tr.model == model]
            if d.empty:
                continue
            s = pd.DataFrame([x if isinstance(x, dict) else {} for x in d.sp3])
            parsed = s.get("parsed", pd.Series(dtype=bool)).fillna(False)
            out.append(f"| {MODEL_LABEL[model]} | {int(parsed.sum())}/{len(d)} | {int(s.get('design_exact', pd.Series()).fillna(False).sum())}/{len(d)} | "
                       f"{int(s.get('init_exact', pd.Series()).fillna(False).sum())}/{len(d)} | "
                       f"{s.get('init_precision', pd.Series()).mean():.3f} | {s.get('init_recall', pd.Series()).mean():.3f} | "
                       f"{(d.attempts == 1).sum()}/{len(d)} |")


TIMING = {"clock", "lease-age", "hidden", "hold-age", "next-tick", "timeout-tick", "visibility-timeout",
          "lease-limit", "hold-limit", "first-tick", "zero-tick"}


def classify_failure(family: str, detail: str) -> str:
    import re
    sys.path.insert(0, str(ROOT))
    from premortem.sp2.families import design_predicates
    if "no trace" in detail:
        return "no trace"
    if "unparseable" in detail or "unknown action" in detail or "unknown object" in detail or "expects" in detail \
            or "has type" in detail:
        return "vocabulary / arity"
    if "not reached" in detail:
        return "stops before violation"
    m = re.search(r"precondition \(not \((\S+)|precondition \((\S+)", detail)
    if m:
        head = (m.group(1) or m.group(2)).rstrip(")")
        if head in design_predicates(family) or head.startswith("mode-"):
            return "assumes another design"
        if head in TIMING:
            return "timer / counter"
        return "event order / state"
    return "other"


def sp2_failures(df: pd.DataFrame, out: list[str]):
    d = df[(df.arm == "direct") & df.outcome.isin(["invalid_trace", "false_alarm"])]
    if d.empty:
        return
    d = d.assign(kind=[classify_failure(f, x) for f, x in zip(d.family, d.outcome_detail)])
    kinds = ["assumes another design", "event order / state", "timer / counter", "stops before violation",
             "vocabulary / arity", "no trace", "other"]
    out.append("\n**Why Direct traces fail on the gold model (invalid traces + false alarms)**\n")
    out.append("| model | " + " | ".join(kinds) + " |")
    out.append("|---|" + "---|" * len(kinds))
    for model in MODEL_ORDER:
        dm = d[d.model == model]
        if dm.empty:
            continue
        c = Counter(dm.kind)
        out.append(f"| {MODEL_LABEL[model]} | " + " | ".join(str(c[k]) for k in kinds) + " |")
    out.append("\n**Mean output tokens (incl. thinking) per instance**\n")
    out.append("| model | arm | SP2 flawed | SP2 subtle | SP2 fixed |")
    out.append("|---|---|---|---|---|")
    for model in MODEL_ORDER:
        for arm in ("direct", "translate"):
            dm = df[(df.model == model) & (df.arm == arm)]
            if dm.empty:
                continue
            out.append(f"| {MODEL_LABEL[model]} | {ARM_LABEL[arm]} | " +
                       " | ".join(f"{dm[dm.variant == v].output_tokens.mean():.0f}" for v in ("flawed", "subtle", "fixed")) + " |")


def fig_sp2(df: pd.DataFrame):
    """Valid traces vs. shortest trace length. Only Haiku varies; the others are noted in the plot."""
    bins = [(6, 8), (9, 11), (12, 15), (17, 19), (21, 23), (27, 27)]
    d0 = df[(df.model == "haiku") & (df.violation == True)]  # noqa: E712
    if d0.empty:
        return
    fig, ax = plt.subplots(figsize=(5.6, 2.9), facecolor=SURFACE)
    style(ax)
    for arm in ("direct", "translate"):
        d = d0[d0.arm == arm]
        ys, ns = [], []
        for lo, hi in bins:
            db = d[(d.shortest >= lo) & (d.shortest <= hi)]
            ns.append(len(db))
            ys.append(100 * (db.outcome == "valid_trace").mean() if len(db) else float("nan"))
        ax.plot(range(len(bins)), ys, color=ARM_COLOR[arm], linewidth=2, marker="o", markersize=5,
                markeredgecolor=SURFACE, markeredgewidth=1.5, label=f"Haiku 4.5 {ARM_LABEL[arm]}")
    labels = [(f"{lo}-{hi}" if lo != hi else f"{lo}") + f"\n(n={n})" for (lo, hi), n in zip(bins, ns)]
    ax.set_xticks(range(len(bins)), labels, fontsize=7)
    ax.set_xlabel("shortest violating trace (events)", fontsize=8, color=INK2)
    ax.set_ylim(0, 108)
    ax.set_ylabel("valid failure trace (%)", fontsize=8, color=INK2)
    ax.legend(frameon=False, fontsize=7, loc="lower left")
    others = [MODEL_LABEL[m] for m in ("sonnet", "opus") if (df.model == m).any()]
    if others:
        ax.text(len(bins) - 1, 103, f"{' and '.join(others)}: 100% in both arms at every length",
                ha="right", fontsize=7, color=INK2)
    ax.set_title("SP2: valid traces vs. trace length (flawed + subtle, main + stress)", fontsize=9, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "sp2_length.png", dpi=200, facecolor=SURFACE)
    plt.close(fig)


def fig_outcomes(sp1: pd.DataFrame, sp2: pd.DataFrame):
    """Outcome composition on bug/violating instances, per model x arm, for SP1-hard and SP2."""
    panels = []
    if not sp1.empty:
        panels.append(("SP1 hard tier (bugs)", sp1[(sp1.tier == "hard") & (sp1.kind == "bug")],
                       {"valid": ["valid_witness"], "fabricated": ["invalid_witness"], "miss": ["miss"],
                        "no answer": ["no_answer", "harness_error", "tool_timeout", "tool_undecided"]}))
    if not sp2.empty:
        panels.append(("SP2 (violating designs)", sp2[sp2.violation == True],  # noqa: E712
                       {"valid": ["valid_trace"], "fabricated": ["invalid_trace"], "miss": ["miss"],
                        "no answer": ["no_answer", "harness_error", "tool_limit"]}))
    if not panels:
        return
    fig, axes = plt.subplots(1, len(panels), figsize=(4.6 * len(panels), 2.9), facecolor=SURFACE)
    axes = [axes] if len(panels) == 1 else axes
    for ax, (title, d, cats) in zip(axes, panels):
        style(ax)
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        rows = [(m, a) for m in MODEL_ORDER for a in ("direct", "translate") if ((d.model == m) & (d.arm == a)).any()]
        for i, (m, a) in enumerate(rows):
            dd = d[(d.model == m) & (d.arm == a)]
            left = 0.0
            for cat, outs in cats.items():
                w = 100 * dd.outcome.isin(outs).mean()
                if w > 0:
                    ax.barh(i, w - 0.6 if w > 1 else w, left=left, height=0.6, color=OUTCOME_COLOR[cat], linewidth=0)
                left += w
        ax.set_yticks(range(len(rows)), [f"{MODEL_LABEL[m]} · {ARM_LABEL[a]}" for m, a in rows], fontsize=7)
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.set_xlabel("% of instances", fontsize=8, color=INK2)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, color=OUTCOME_COLOR[c]) for c in OUTCOME_COLOR]
    fig.legend(handles, list(OUTCOME_COLOR), loc="lower center", ncol=4, frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(FIG / "outcomes.png", dpi=200, facecolor=SURFACE)
    plt.close(fig)


def solver_scaling(out: list[str]):
    inst = [i for i in json.loads((ROOT / "data" / "sp2" / "instances.json").read_text())["instances"]
            if i.get("set", "main") != "opaque"]
    out.append("\n## Solver behaviour on the gold SP2 problems\n")
    out.append("| family | variant | size | ground actions | shortest | SATPlan s | GBFS expanded | BFS expanded |")
    out.append("|---|---|---|---|---|---|---|---|")
    for i in inst:
        g = i["gold"]
        sat = f"{g['satplan']['seconds']:.2f}" + ("" if g['satplan']['status'] in ("solved", "no_plan_within_bound") else f" ({g['satplan']['status']})")
        gb = f"{g['gbfs']['expanded']}" + (" (limit)" if g['gbfs']['status'] == "limit" else "")
        bf = f"{g['bfs']['expanded']}" + (" (limit)" if g['bfs']['status'] == "limit" else "")
        out.append(f"| {i['family']} | {i['variant']} | {i['size']} | {g['n_actions']} | {i['shortest'] or '-'} | {sat} | {gb} | {bf} |")
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 2.8), facecolor=SURFACE)
    fams = ["payments", "inventory", "lock", "queue", "cache"]
    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
    for ax in axes:
        style(ax)
    for fam, col in zip(fams, colors):
        d = sorted([i for i in inst if i["family"] == fam and i["variant"] == "fixed"], key=lambda i: i["size"])
        dm = [i for i in d if i.get("set", "main") == "main"]
        axes[0].plot([i["size"] for i in dm], [max(i["gold"]["satplan"]["seconds"], 1e-3) for i in dm], color=col,
                     linewidth=2, marker="o", markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.5, label=fam)
        axes[1].plot([i["size"] for i in d], [max(i["gold"]["gbfs"]["expanded"], 1) for i in d], color=col, linewidth=2,
                     marker="o", markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.5, label=fam)
        for i in d:
            if i["gold"]["gbfs"]["status"] == "limit":
                axes[1].annotate("search limit", (i["size"], i["gold"]["gbfs"]["expanded"]), textcoords="offset points",
                                 xytext=(-30, -14), fontsize=7, color=INK2)
    axes[0].set_yscale("log")
    axes[1].set_yscale("log")
    axes[0].set_title("SATPlan: time to exhaust T <= 40 (s)", fontsize=9, color=INK, loc="left")
    axes[1].set_title("GBFS + h_FF: states expanded to prove safety", fontsize=9, color=INK, loc="left", pad=10)
    axes[0].set_xticks([1, 2, 3, 4])
    axes[1].set_xticks(sorted({i["size"] for i in inst}))
    for ax in axes:
        ax.set_xlabel("design size", fontsize=8, color=INK2)
    axes[1].legend(frameon=False, fontsize=7, loc="upper left")
    fig.suptitle("Certifying the fixed designs", fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(FIG / "solver_scaling.png", dpi=200, facecolor=SURFACE)
    plt.close(fig)


def costs(out: list[str]):
    sys.path.insert(0, str(ROOT))
    from premortem.llm import cache_summary
    out.append("\n## LLM usage (all cached calls, list-price equivalent)\n")
    out.append("| model | calls | input tokens | output tokens | cost (USD) |")
    out.append("|---|---|---|---|---|")
    for m, s in sorted(cache_summary().items()):
        out.append(f"| {m} | {s['calls']} | {s['input_tokens']:,} | {s['output_tokens']:,} | {s['cost_usd']:.2f} |")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    out = ["# Results tables (generated by experiments/analyze.py)\n"]
    sp1 = load("sp1")
    sp2 = load("sp2")
    if not sp1.empty:
        sp1 = sp1_tables(sp1, out)
        fig_sp1(sp1)
    if not sp2.empty:
        inst2 = {i["id"]: i for i in json.loads((ROOT / "data" / "sp2" / "instances.json").read_text())["instances"]}
        sp2 = sp2[sp2.instance.isin(inst2)].copy()
        sp2["set"] = sp2.instance.map(lambda x: inst2[x].get("set", "main"))
        sp2["shortest"] = sp2.instance.map(lambda x: inst2[x]["shortest"])
        main_set = sp2[sp2.set == "main"]
        sp2_tables(main_set, out)
        sp2_failures(main_set, out)
        for name, title in (("stress", "SP2 stress set (sizes 6 and 8: traces of 17-27 events)"),
                            ("opaque", "SP2 opaque-vocabulary ablation (main set, design facts and design-specific events renamed)")):
            d = sp2[sp2.set == name]
            if not d.empty:
                sp2_tables(d, out, title, brief=True)
                if name == "opaque":
                    sp2_failures(d, out)
        fig_sp2(sp2[sp2.set != "opaque"])
        sp2 = main_set
    fig_outcomes(sp1, sp2)
    solver_scaling(out)
    costs(out)
    (RES / "tables.md").write_text("\n".join(out) + "\n")
    print("\n".join(out[:80]))


if __name__ == "__main__":
    main()
