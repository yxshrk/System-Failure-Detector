"""Opaque-vocabulary ablation for SP2.

The main domains name design facts and design-specific events descriptively
(``(dedup-racy)``, ``accept-new-atomic``), which may let a model map the design
text to the right mechanism by matching words rather than by understanding
the mechanism. This ablation renames every design fact to ``mode-N`` and every
action whose precondition mentions a design fact to ``<verb>-N``, and drops the
comments on the design-fact declarations. Semantics (preconditions and
effects) are unchanged, so gold traces carry over under the renaming.
"""

from __future__ import annotations

import random
import re

from ..planning import parse_domain
from .families import FAMILIES, design_predicates


def _sub(text: str, old: str, new: str) -> str:
    return re.sub(rf"(?<![\w-]){re.escape(old)}(?![\w-])", new, text)


def renaming(family: str) -> dict[str, str]:
    fam = FAMILIES[family]
    dom = parse_domain(fam.domain)
    rng = random.Random(f"opaque:{family}")
    preds = sorted(design_predicates(family))
    rng.shuffle(preds)
    ren = {p: f"mode-{k + 1}" for k, p in enumerate(preds)}
    guarded = [name for name, a in dom.actions.items()
               if any(atom.predicate in ren for atom in a.pre_pos)]
    by_verb: dict[str, list[str]] = {}
    for name in sorted(guarded):
        by_verb.setdefault(name.split("-")[0], []).append(name)
    for verb, names in by_verb.items():
        rng.shuffle(names)
        for k, name in enumerate(names):
            ren[name] = f"{verb}-{k + 1}"
    return ren


def opaque_domain(family: str) -> str:
    ren = renaming(family)
    out = []
    in_design = False
    for line in FAMILIES[family].domain.splitlines():
        s = line.strip()
        if s.startswith(";; --- design facts"):
            in_design = True
            out.append(line.split(";;")[0] + ";; --- design facts (which of these hold depends on the design) ---")
            continue
        if s.startswith(";; ---"):
            in_design = False
        if in_design and ";" in line:
            line = line.split(";")[0].rstrip()
        out.append(line)
    text = "\n".join(out) + "\n"
    for old, new in sorted(ren.items(), key=lambda kv: -len(kv[0])):
        text = _sub(text, old, new)
    return text


def opaque_text(family: str, text: str) -> str:
    for old, new in sorted(renaming(family).items(), key=lambda kv: -len(kv[0])):
        text = _sub(text, old, new)
    return text
