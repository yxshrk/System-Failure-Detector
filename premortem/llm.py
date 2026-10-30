"""LLM access with an on-disk cache.

The default backend drives the Claude Code CLI in headless mode
(``claude -p``), which the course guidelines allow ("If you have subscription
to frontier AI agents such as Claude Code ... you should be able to use them").
Every call runs with all tools disabled (``--tools ""``), so in the Direct arm
the model can only read and reason about the code; it cannot execute it. The
system prompt is replaced entirely, so no coding-agent instructions leak in.

Responses are cached by a hash of (backend, model, system prompt, prompt), which
makes every experiment re-runnable for free and exactly reproducible from the
cache directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parents[1] / "results" / "llm_cache"

MODELS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5-5",
    "opus": "claude-opus-5-5",
}


class LLMAuthError(RuntimeError):
    """The CLI is logged out: every further call would fail, so a run must stop rather than record no-answers."""


@dataclass
class Completion:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cost_usd: float = 0.0
    seconds: float = 0.0
    cached: bool = False
    error: str | None = None


class ClaudeCLI:
    def __init__(self, model: str, cache_dir: Path = CACHE_DIR, timeout: int = 900, effort: str | None = None):
        self.alias = model
        self.model = MODELS.get(model, model)
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.effort = effort
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, system: str, prompt: str) -> str:
        blob = json.dumps({"backend": "claude-cli", "model": self.model, "effort": self.effort,
                           "system": system, "prompt": prompt}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    def complete(self, system: str, prompt: str, tag: str = "") -> Completion:
        key = self._key(system, prompt)
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            rec = json.loads(path.read_text())
            c = Completion(**rec["completion"])
            c.cached = True
            return c
        if os.environ.get("PREMORTEM_CACHE_ONLY"):
            return Completion(text="", model=self.model, error="cache miss in cache-only mode")
        c = self._call(system, prompt)
        if c.error is None:
            path.write_text(json.dumps({"tag": tag, "model": self.model, "system": system, "prompt": prompt,
                                        "completion": asdict(c)}, indent=1))
        return c

    def _call(self, system: str, prompt: str, retries: int = 3) -> Completion:
        cmd = ["claude", "-p", "--model", self.model, "--output-format", "json", "--tools", "",
               "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config",
               "--system-prompt", system]
        if self.effort:
            cmd += ["--effort", self.effort]
        last = ""
        for attempt in range(retries):
            t0 = time.perf_counter()
            try:
                with tempfile.TemporaryDirectory() as cwd:  # neutral working directory: no project files visible
                    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                                          timeout=self.timeout, cwd=cwd, env=_clean_env())
            except subprocess.TimeoutExpired:
                last = f"timeout after {self.timeout}s"
                continue
            secs = time.perf_counter() - t0
            try:
                d = json.loads(proc.stdout)
            except json.JSONDecodeError:
                last = f"exit {proc.returncode}: {proc.stderr[-500:] or proc.stdout[-500:]}"
                time.sleep(5 * (attempt + 1))
                continue
            if d.get("is_error") and "authenticat" in str(d.get("result", "")).lower():
                raise LLMAuthError(f"Claude CLI: {d.get('result')}")
            if d.get("is_error") or d.get("subtype") != "success":
                last = f"api error: {str(d.get('result'))[:300]} {d.get('api_error_status')}"
                time.sleep(10 * (attempt + 1))
                continue
            usage = d.get("usage", {})
            models = list(d.get("modelUsage", {}).keys())
            return Completion(
                text=d.get("result", ""),
                model=models[0] if models else self.model,
                input_tokens=usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
                + usage.get("cache_read_input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                thinking_tokens=usage.get("output_tokens_details", {}).get("thinking_tokens", 0),
                cost_usd=d.get("total_cost_usd", 0.0),
                seconds=secs,
            )
        return Completion(text="", model=self.model, error=last)


def _clean_env() -> dict:
    env = dict(os.environ)
    for k in ("CLAUDE_CODE_MESSAGING_TOKEN",):
        env.pop(k, None)
    return env


def get_llm(name: str) -> ClaudeCLI:
    return ClaudeCLI(name)


def cache_summary(cache_dir: Path = CACHE_DIR) -> dict:
    out: dict = {}
    for p in cache_dir.glob("*.json"):
        rec = json.loads(p.read_text())
        c = rec["completion"]
        m = out.setdefault(c["model"], {"calls": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0})
        m["calls"] += 1
        m["cost_usd"] += c["cost_usd"]
        m["input_tokens"] += c["input_tokens"]
        m["output_tokens"] += c["output_tokens"]
    return out
