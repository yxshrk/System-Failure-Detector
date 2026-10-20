"""Extract structured answers (JSON objects, code blocks) from model text."""

from __future__ import annotations

import ast
import json
import re

_FENCE = re.compile(r"```([a-zA-Z0-9_+-]*)[ \t]*\n(.*?)```", re.S)


def code_blocks(text: str, lang: str | None = None) -> list[str]:
    out = []
    for m in _FENCE.finditer(text):
        tag = m.group(1).lower()
        if lang is None or tag == lang or (lang == "python" and tag in ("py", "python3")):
            out.append(m.group(2))
    return out


def _balanced_objects(text: str) -> list[str]:
    objs, depth, start, in_str, esc = [], 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                objs.append(text[start:i + 1])
    return objs


def _loads(s: str):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    py = re.sub(r"\btrue\b", "True", re.sub(r"\bfalse\b", "False", re.sub(r"\bnull\b", "None", s)))
    try:
        return ast.literal_eval(py)
    except (ValueError, SyntaxError):
        return None


def last_json_object(text: str, required_key: str | None = None):
    """The last JSON object in the text (preferring fenced json blocks) that parses."""
    candidates = []
    for block in code_blocks(text, "json"):
        candidates += _balanced_objects(block) or [block]
    candidates += _balanced_objects(text)
    for cand in reversed(candidates):
        obj = _loads(cand.strip())
        if isinstance(obj, dict) and (required_key is None or required_key in obj):
            return obj
    return None
