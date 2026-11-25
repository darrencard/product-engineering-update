#!/usr/bin/env python3
"""Ablation eval: does the skill, alone or used by Claude, make a better update than Claude alone?

Usage:
  python3 evals/ablation/ablation.py all --out evals/ablation/results/latest
  python3 evals/ablation/ablation.py generate|judge|check|report --out DIR [options]

Steps (each skips work already on disk, so a stopped run resumes):
  generate  Condition A, Claude alone: headless `claude -p` reading project settings only, in an
            empty folder, given the task prompt and the fixture's files. Condition B: the skill's
            pipeline, scripts/run.py, on the same files. Condition C: as A, with the skill
            installed through --plugin-dir. --runs times per fixture.
  judge     A blind judge (`claude -p`, no tools) sees the data and two decks as X and Y, and picks
            per criterion and overall. Each pair in --matchups is judged in both orders. Self and
            within-condition pairs measure the judge's noise.
  check     Mechanical checks with no judge: figures in each deck that no one-step derivation
            from the data produces, and printed metrics that disagree with truth.py.
  report    Totals, win rates with a 95% Wilson interval, the noise band, the check counts and
            the token cost, written to summary.json.

It calls the model and costs money, so it is not part of the unit tests or CI. See README.md.
Standard library only.
"""

from __future__ import annotations

import argparse
import bisect
import concurrent.futures as cf
import hashlib
import itertools
import json
import math
import os
import re
import shutil
import subprocess  # noqa: S404  (the eval drives the claude CLI and the skill's scripts)
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SKILL = ROOT / "skills" / "product-engineering-update"
FIXTURES = ROOT / "evals" / "fixtures"
PROMPTS = HERE / "prompts"
sys.path.insert(0, str(HERE))

from decktext import deck_text, split_samples  # noqa: E402
from truth import recompute  # noqa: E402

Json = dict[str, Any]
CRITERIA = ["figures_correct", "no_invented_numbers", "speed_with_quality", "gaps_shown", "board_cut_usable"]
# A role from the intake, as a user would give. A label such as "eval" would itself print on the board cut.
SIGNED_OFF = "the CEO"
LOCK = threading.Lock()
# Element ids dropped from condition B's decks before judging. Empty for the real eval; set by
# --b-drop-sections only for a labelled counterfactual (for example the template's appendices).
B_DROP: frozenset[str] = frozenset()

# Variables the parent Claude Code session sets; a nested `claude -p` must not inherit them.
NESTED_ENV = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SIMPLE")

VERDICT = {"type": "string", "enum": ["X", "Y", "tie"]}
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "object",
            "properties": {
                c: {"type": "object", "properties": {"winner": VERDICT, "reason": {"type": "string"}}, "required": ["winner", "reason"]} for c in CRITERIA
            },
            "required": CRITERIA,
        },
        "overall": {"type": "object", "properties": {"winner": VERDICT, "reason": {"type": "string"}}, "required": ["winner", "reason"]},
    },
    "required": ["criteria", "overall"],
}
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"metric": {"type": "string"}, "which": {"type": "string", "enum": ["current", "prior"]}, "printed": {"type": "string"}},
                "required": ["metric", "which", "printed"],
            },
        }
    },
    "required": ["items"],
}


# ---------- the claude CLI ----------


def claude_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in NESTED_ENV}
    if os.environ.get("ABLATION_DROP_API_KEY"):
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_BASE_URL", None)
    return env


def claude(
    prompt: str,
    cwd: Path,
    model: str,
    tools: str,
    schema: Json | None = None,
    stream_to: Path | None = None,
    budget: float = 10.0,
    worker: bool = False,
    plugin_dir: Path | None = None,
) -> Json:
    """Run one headless Claude Code call. Returns the final result event.

    A judge or extraction call runs with --safe-mode and no skills, as in the first measured run.
    A worker call (conditions A and C) reads project settings only, so no user setting, output
    style, plugin, hook or CLAUDE.md reaches it; --safe-mode cannot be used there because it also
    blocks a skill loaded with --plugin-dir. Condition C adds the skill with plugin_dir.
    """
    args = ["claude", "-p"]
    args += ["--setting-sources", "project"] if worker else ["--safe-mode", "--disable-slash-commands"]
    if plugin_dir:
        args += ["--plugin-dir", str(plugin_dir)]
    args += ["--strict-mcp-config", "--no-session-persistence", "--model", model, "--tools", tools, "--max-budget-usd", str(budget)]
    if tools:
        args += ["--permission-mode", "bypassPermissions"]
    if schema:
        args += ["--json-schema", json.dumps(schema)]
    args += ["--output-format", "stream-json", "--verbose"] if stream_to else ["--output-format", "json"]
    done = subprocess.run(args, input=prompt, cwd=cwd, env=claude_env(), capture_output=True, text=True, check=False, timeout=3600)  # noqa: S603
    if stream_to:
        stream_to.write_text(done.stdout, encoding="utf-8")
        events = [json.loads(line) for line in done.stdout.splitlines() if line.strip().startswith("{")]
        final = next((e for e in reversed(events) if e.get("type") == "result"), {})
    else:
        try:
            final = json.loads(done.stdout)
        except json.JSONDecodeError:
            final = {}
    if not final or final.get("is_error"):
        raise RuntimeError(f"claude failed ({done.returncode}): {(final.get('result') if final else done.stderr or done.stdout)[:500]}")
    return final


def structured(final: Json) -> Json:
    if isinstance(final.get("structured_output"), dict):
        return final["structured_output"]
    text = final.get("result") or ""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError(f"no JSON in the reply: {text[:300]}")
    return json.loads(m.group(0))


def usage_of(final: Json) -> Json:
    u = final.get("usage") or {}
    return {
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "cache_read_input_tokens": u.get("cache_read_input_tokens", 0),
        "cache_creation_input_tokens": u.get("cache_creation_input_tokens", 0),
        "cost_usd": final.get("total_cost_usd", 0.0),
        "num_turns": final.get("num_turns"),
        "duration_ms": final.get("duration_ms"),
    }


# ---------- generate ----------


def stage_input(fixture: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("intake.json", "systems.json"):
        shutil.copy(fixture / name, dest / name)
    shutil.copytree(fixture / "csv", dest / "csv", dirs_exist_ok=True)


SKILL_NAME = "product-engineering-update"
SKILL_SCRIPTS = re.compile(r"\b(run|collect|compute_metrics|draft|validate|render|review|intake|summary|convert)\.py\b")
WORKER_TOOLS = "Read,Write,Edit,Bash,Glob,Grep,Skill"


def tool_calls(transcript: str) -> list[Json]:
    calls = []
    for line in transcript.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        for block in (e.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                calls.append(block)
    return calls


def init_skills(transcript: str) -> list[str]:
    for line in transcript.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            return list(e.get("skills") or [])
    return []


def skill_use(transcript: str) -> Json:
    """How a run used the skill: Skill tool calls that loaded it, and Bash calls that ran its scripts."""
    loaded, scripts = [], []
    for block in tool_calls(transcript):
        text = json.dumps(block.get("input"))
        if block.get("name") == "Skill" and SKILL_NAME in text:
            loaded.append(text[:200])
        elif block.get("name") == "Bash" and SKILL_SCRIPTS.search(text) and ("pegskill-" in text or SKILL_NAME in text or "scripts/" in text):
            scripts.append(SKILL_SCRIPTS.search(text).group(0))  # type: ignore[union-attr]
    return {"skill_available": any(SKILL_NAME in s for s in init_skills(transcript)), "skill_loaded": len(loaded), "script_calls": scripts}


def leaks_in(transcript: str) -> list[str]:
    """Any sign condition A reached the skill: the skill available at start, or a tool call that loaded it or touched its files."""
    found = [f"skill available: {s}" for s in init_skills(transcript) if SKILL_NAME in s]
    for block in tool_calls(transcript):
        text = json.dumps(block.get("input"))
        if any(w in text for w in (SKILL_NAME, "plugins/cache", "pegskill-", "compute_metrics")):
            found.append(f"{block.get('name')}: {text[:200]}")
    return found


def plugin_copy() -> Path:
    """The skill as a user installs it (plugin manifest and skills), in a folder outside the repository.

    Outside the repository so Claude cannot read the eval, its fixtures or this report through the path.
    """
    dest = Path(tempfile.mkdtemp(prefix="pegskill-"))
    shutil.copytree(ROOT / ".claude-plugin", dest / ".claude-plugin")
    shutil.copytree(ROOT / "skills", dest / "skills")
    return dest


def gen_claude(out: Path, cond: str, fx: str, i: int, model: str) -> str:
    """Condition A (Claude alone) or C (Claude with the skill installed): same prompt, files and settings."""
    run = out / "runs" / cond / fx / str(i)
    if (run / "meta.json").exists():
        return f"{cond} {fx} {i}: done before"
    if run.exists():
        shutil.rmtree(run)
    # A neutral folder outside the repository, so nothing in the path points at the skill or the eval.
    work = Path(tempfile.mkdtemp(prefix="update-"))
    plugin = plugin_copy() if cond == "C" else None
    try:
        stage_input(FIXTURES / fx, work / "input")
        (work / "out").mkdir()
        transcript = work.parent / f"{work.name}.jsonl"
        prompt = (PROMPTS / "task.md").read_text(encoding="utf-8")
        final = claude(prompt, work, model, WORKER_TOOLS, stream_to=transcript, budget=15.0, worker=True, plugin_dir=plugin)
        run.mkdir(parents=True)
        shutil.copytree(work / "out", run / "out")
        shutil.move(str(transcript), run / "transcript.jsonl")
    finally:
        shutil.rmtree(work, ignore_errors=True)
        if plugin:
            shutil.rmtree(plugin, ignore_errors=True)
    text = (run / "transcript.jsonl").read_text(encoding="utf-8")
    decks = sorted(p.name for p in (run / "out").glob("*") if p.suffix.lower() in {".html", ".htm", ".md"})
    meta: Json = {"condition": cond, "fixture": fx, "run": i, "model": model, "usage": usage_of(final), "decks": decks}
    if cond == "A":
        meta["skill_leaks"] = leaks_in(text)
        note = f" LEAK {meta['skill_leaks']}" if meta["skill_leaks"] else ""
    else:
        meta["skill_use"] = skill_use(text)
        note = f" skill loaded {meta['skill_use']['skill_loaded']}x, {len(meta['skill_use']['script_calls'])} script calls"
    (run / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return f"{cond} {fx} {i}: {decks} ${meta['usage']['cost_usd']:.2f}{note}"


def gen_b(out: Path, fx: str, i: int) -> str:
    run = out / "runs" / "B" / fx / str(i)
    if (run / "meta.json").exists():
        return f"B {fx} {i}: done before"
    if run.exists():
        shutil.rmtree(run)
    fixture = FIXTURES / fx
    stage_input(fixture, run / "input")
    work = run / "out"
    work.mkdir()
    shutil.copy(fixture / "intake.json", work / "intake.json")
    systems = json.loads((fixture / "systems.json").read_text(encoding="utf-8"))
    args = [sys.executable, "-I", str(SKILL / "scripts" / "run.py"), "--run", str(work), "--no-ask", "--retrieved-at", "2026-09-30"]
    for p in sorted((fixture / "csv").glob("*.csv")):
        args += [f"--csv={p.stem}={p}", f"--system={p.stem}={systems.get(p.stem, 'CSV export')}"]
    args += ["--board", "--signed-off-by", SIGNED_OFF]
    done = subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603
    (run / "run.log").write_text(done.stdout + done.stderr, encoding="utf-8")
    deck = work / "deck.json"
    digest = hashlib.sha256(re.sub(r'"\d{4}-\d{2}-\d{2}T[\d:]+Z"', '""', deck.read_text(encoding="utf-8")).encode()).hexdigest() if deck.exists() else None
    decks = [n for n in ("update.html", "board.html") if (work / n).exists()]
    meta = {"condition": "B", "fixture": fx, "run": i, "returncode": done.returncode, "decks": decks, "deck_sha256": digest, "usage": {"cost_usd": 0.0}}
    (run / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return f"B {fx} {i}: exit {done.returncode} {decks}"


def generate(out: Path, fixtures: list[str], runs: int, model: str, jobs: int, conds: str = "ABC") -> None:
    if "B" in conds:
        for fx in fixtures:
            for i in range(1, runs + 1):
                print(gen_b(out, fx, i), flush=True)
    with cf.ThreadPoolExecutor(jobs) as pool:
        futures = [pool.submit(gen_claude, out, c, fx, i, model) for i in range(1, runs + 1) for fx in fixtures for c in "CA" if c in conds]
        for f in cf.as_completed(futures):
            try:
                print(f.result(), flush=True)
            except Exception as e:  # noqa: BLE001  (one failed run should not stop the rest)
                print(f"generate failed: {e}", flush=True)


# ---------- deck text ----------


def full_text(run: Path) -> str | None:
    """The update and its board cut as one text, or None if the run made no update."""
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    files = {name: run / "out" / name for name in meta.get("decks", [])}
    main = files.get("update.html") or next((p for n, p in files.items() if "board" not in n), None)
    if not main:
        return None
    board = files.get("board.html") or next((p for n, p in files.items() if "board" in n), None)
    drop = B_DROP if meta["condition"] == "B" else frozenset()
    text = "=== FULL UPDATE ===\n" + deck_text(main, drop)
    text += "\n\n=== BOARD CUT ===\n" + (deck_text(board, drop) if board else "(no separate board cut was produced)")
    return text


def data_block(fx: str) -> str:
    fixture = FIXTURES / fx
    parts = [f"### intake.json\n```json\n{(fixture / 'intake.json').read_text(encoding='utf-8')}\n```"]
    parts.append(f"### systems.json\n```json\n{(fixture / 'systems.json').read_text(encoding='utf-8')}\n```")
    for p in sorted((fixture / "csv").glob("*.csv")):
        parts.append(f"### csv/{p.name}\n```csv\n{p.read_text(encoding='utf-8')}```")
    return "\n\n".join(parts)


def runs_of(out: Path, cond: str, fx: str) -> list[Path]:
    base = out / "runs" / cond / fx
    return sorted((p for p in base.glob("*") if (p / "meta.json").exists()), key=lambda p: int(p.name)) if base.exists() else []


# ---------- judge ----------


def parse_matchups(spec: str, runs: int) -> list[tuple[str, int]]:
    """'CA,CB:2,BA' -> [('CA', runs), ('CB', 2), ('BA', runs)]. The first letter is the condition tested."""
    out = []
    for part in (p for p in spec.split(",") if p):
        m, _, n = part.partition(":")
        out.append((m, int(n) if n else runs))
    return out


def judge_jobs(out: Path, fixtures: list[str], matchups: list[tuple[str, int]], noise: str, self_n: int, pairs_only: bool = False) -> list[Json]:
    """Pairs for each matchup in both orders, then the noise runs.

    Noise, for each condition in `noise`: up to self_n runs judged against themselves (a consistent
    judge says tie), and runs 1 and 2 judged against each other in both orders (how far the verdict
    moves between runs of one condition and with position). B's decks are the same on every run, so
    B gets only the self test.
    """
    jobs = []
    for fx in fixtures:
        for m, n in matchups:
            first, second = runs_of(out, m[0], fx), runs_of(out, m[1], fx)
            for p, q in list(zip(first, second))[:n]:
                for order in ("12", "21"):
                    x, y = (p, q) if order == "12" else (q, p)
                    jobs.append({"id": f"pair-{m}-{fx}-{p.name}-{order}", "fixture": fx, "kind": "pair", "matchup": m, "x": x, "y": y})
        if pairs_only:
            continue
        for c in noise:
            rs = runs_of(out, c, fx)
            for r in rs[:self_n]:
                jobs.append({"id": f"self-{fx}-{c}{r.name}", "fixture": fx, "kind": f"self_{c}", "x": r, "y": r})
            if c != "B" and len(rs) >= 2:
                for order, (x, y) in (("12", (rs[0], rs[1])), ("21", (rs[1], rs[0]))):
                    jobs.append({"id": f"within-{fx}-{c}-{order}", "fixture": fx, "kind": f"within_{c}", "x": x, "y": y})
    return jobs


def run_judge(out: Path, job: Json, model: str) -> str:
    dest = out / "judgments" / f"{job['id']}.json"
    if dest.exists():
        return f"{job['id']}: done before"
    x, y = full_text(job["x"]), full_text(job["y"])
    if x is None or y is None:
        dest.write_text(json.dumps({**strip(job), "skipped": "a run made no update"}, indent=1), encoding="utf-8")
        return f"{job['id']}: skipped, no update"
    prompt = (PROMPTS / "judge.md").read_text(encoding="utf-8").format(data=data_block(job["fixture"]), deck_x=x, deck_y=y)
    scratch = out / "scratch"
    scratch.mkdir(exist_ok=True)
    final = claude(prompt, scratch, model, "", schema=JUDGE_SCHEMA, budget=5.0)
    verdict = structured(final)
    record = {**strip(job), "model": model, "verdict": verdict, "usage": usage_of(final)}
    dest.write_text(json.dumps(record, indent=1), encoding="utf-8")
    return f"{job['id']}: {verdict['overall']['winner']}"


def strip(job: Json) -> Json:
    return {**job, "x": str(job["x"].relative_to(job["x"].parents[3])), "y": str(job["y"].relative_to(job["y"].parents[3]))}


def judge(out: Path, fixtures: list[str], model: str, jobs: int, matchups: list[tuple[str, int]], noise: str, self_n: int, pairs_only: bool = False) -> None:
    (out / "judgments").mkdir(parents=True, exist_ok=True)
    todo = judge_jobs(out, fixtures, matchups, noise, self_n, pairs_only)
    with cf.ThreadPoolExecutor(jobs) as pool:
        for f in cf.as_completed([pool.submit(run_judge, out, j, model) for j in todo]):
            try:
                print(f.result(), flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"judge failed: {e}", flush=True)


# ---------- mechanical checks ----------

SCALE = {"k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6, "million": 1e6, "bn": 1e9, "B": 1e9, "billion": 1e9}
MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
NOT_FIGURES = [
    r"\bv?\d+\.\d+\.\d+\b",  # version numbers
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?Z?)?",
    r"\d{4}-\d{2}",
    r"\d{4}\s*-?\s*Q[1-4]",
    r"\bQ[1-4]\s*\d{4}",
    rf"\b\d{{1,2}}\s+{MONTHS}\s+\d{{4}}",
    rf"\b{MONTHS}\s+\d{{1,2}},?\s+\d{{4}}",
    rf"\b{MONTHS}\s+\d{{1,2}}\b",
    rf"\b\d{{1,2}}\s+{MONTHS}",
    rf"\b{MONTHS}\s+\d{{4}}",
    r"\b(?:19|20)\d{2}\b",
    r"\b\d{1,2}:\d{2}\b",
    r"\b[A-Za-z]+-?\d+[A-Za-z]*\b",  # IDs and versions: L09, v14, Sev-2, H1, P0
    r"\b[Ss]lides?\s+\d+[a-z]?(?:\s*(?:to|and|-|,)\s*\d+[a-z]?)*",
]
FIGURE_UNITS = r"%|pp|percentage points|[kKmMB]\b|bn\b|million\b|billion\b|h\b|hrs?\b|hours?\b|min\b|mins\b|minutes?\b|m\b|days?\b|d\b|x\b"
FIGURE = re.compile(rf"(?<![\w.])(-|−|\+)?(\$)?(\d{{1,3}}(?:,\d{{3}})+|\d+)(\.\d+)?\s?({FIGURE_UNITS})?")
TIME = {
    "h": 1.0,
    "hr": 1.0,
    "hrs": 1.0,
    "hour": 1.0,
    "hours": 1.0,
    "min": 1 / 60,
    "mins": 1 / 60,
    "minute": 1 / 60,
    "minutes": 1 / 60,
    "day": 24.0,
    "days": 24.0,
    "d": 24.0,
}


def figures(text: str) -> list[Json]:
    """Every figure in a text, as printed, with its value and the rounding its printing implies."""
    for pattern in NOT_FIGURES:
        text = re.sub(pattern, " ", text)
    found = []
    for m in FIGURE.finditer(text):
        sign, dollar, whole, frac, unit = m.groups()
        value = float(whole.replace(",", "") + (frac or ""))
        if sign in ("-", "−"):
            value = -value
        unit = unit or ""
        scale = SCALE.get(unit, 1.0) if unit not in ("m",) or dollar else 1.0
        if unit == "m" and dollar:
            scale = 1e6
        decimals = len(frac) - 1 if frac else 0
        bare = not dollar and not unit and not frac
        if bare and abs(value) <= 20:
            continue  # small bare counts: slide numbers, list sizes, "3 wins"
        found.append(
            {
                "printed": m.group(0).strip(),
                "value": value * scale,
                "tol": 0.5 * 10 ** (-decimals) * scale,
                "unit": unit,
                "percent": unit in ("%", "pp", "percentage points"),
                "time": unit in TIME and not dollar,
                "money": bool(dollar),
            }
        )
    return found


def numbers_in(obj: Any) -> list[float]:
    """Every number in a JSON value or a string, raw."""
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, str):
        out = []
        for f in figures(obj) + [{"value": float(x.replace(",", ""))} for x in re.findall(r"(?<![\w.])\d[\d,]*\.?\d*", obj)]:
            out.append(f["value"])
        return out
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in numbers_in(v)]
    if isinstance(obj, list):
        return [n for v in obj for n in numbers_in(v)]
    return []


MONEY_COLUMNS = {"arr", "cost", "plan", "actual", "cost_per_task"}
KINDS = ("pct", "money", "time", "count")


def kind_of_unit(unit: str) -> str:
    return {"%": "pct", "$": "money", "h": "time", "m": "time"}.get(unit, "count")


def pool_for(fx: str) -> dict[str, list[float]]:
    """Every figure the data states or one named step produces, by kind (percent, money, time,
    count): raw cells of the small tables and the intake; counts, sums and shares by group in the
    large tables; within-row steps (plan against actual); the recomputed metrics with their priors
    and changes; and each metric against the intake's own targets. A printed figure must match a
    figure of its own kind, so a made-up percentage cannot match a dollar amount by chance."""
    import csv

    fixture = FIXTURES / fx
    intake = json.loads((fixture / "intake.json").read_text(encoding="utf-8"))
    targets = set(numbers_in(intake))
    pool: dict[str, set[float]] = {k: set(targets) for k in KINDS}
    for p in sorted((fixture / "csv").glob("*.csv")):
        with p.open(encoding="utf-8", newline="") as f:
            table = list(csv.DictReader(f))
        cols = list(table[0].keys()) if table else []

        def is_num(x: str | None) -> bool:
            return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", x or ""))

        numeric = [c for c in cols if any(is_num(r[c]) for r in table)]
        grouping = [c for c in cols if c not in numeric and 1 < len({r[c] for r in table}) <= 15]
        pool["count"].add(float(len(table)))
        if len(table) <= 12:
            for r in table:
                vals = [float(r[c]) for c in numeric if is_num(r[c])]
                raw = vals + numbers_in([r[c] for c in cols if c not in numeric])
                for k in ("pct", "money", "count"):
                    pool[k].update(raw)
                for a, b in itertools.permutations(vals, 2):
                    pool["money"].add(a - b)
                    pool["count"].add(a - b)
                    pool["pct"].add(a - b)
                    if b:
                        pool["pct"].update({100 * a / b, 100 * (a - b) / b})
        for c in grouping:
            for val in sorted({r[c] for r in table}):
                sel = [r for r in table if r[c] == val]
                pool["count"].add(float(len(sel)))
                pool["pct"].add(100.0 * len(sel) / len(table))
                for col in numeric:
                    total = sum(float(r[col]) for r in table if is_num(r[col]))
                    part = sum(float(r[col]) for r in sel if is_num(r[col]))
                    pool["money" if col in MONEY_COLUMNS else "count"].add(part)
                    if total:
                        pool["pct"].add(100.0 * part / total)
    for t in recompute(fixture).values():
        k = kind_of_unit(t["unit"])
        vals = t["values"] + t.get("prior", [])
        pool[k].update(vals)
        for v, p in itertools.product(t["values"], t.get("prior", [])):
            pool[k].update({v - p, p - v})
            if p:
                pool["pct"].add(100.0 * (v - p) / p)
        for v, g in itertools.product(t["values"], targets_for(intake, t["label"])):
            if g:
                pool[k].update({g - v, v - g})
                pool["pct"].add(100.0 * v / g)
    for name, plan in (intake.get("investment_plan") or {}).items():
        mix = recompute(fixture).get(f"mix:{name}")
        for v in mix["values"] if mix else []:
            pool["pct"].update({v - plan, plan - v})
    return {k: sorted(v) for k, v in pool.items()}


def targets_for(intake: Json, label: str) -> list[float]:
    """The intake's own targets and healthy ranges for one metric, matched by name."""
    name = label.split(" (")[0].lower()
    found: list[float] = []
    for item in [intake.get("north_star") or {}, *(intake.get("inputs") or [])]:
        if item.get("metric") and item["metric"].lower() == name and isinstance(item.get("target"), (int, float)):
            found.append(float(item["target"]))
    for metric, rng in (intake.get("delivery_ranges") or {}).items():
        if metric.lower() == name:
            found += numbers_in(rng)
    return found


def kinds_for(f: Json) -> tuple[str, ...]:
    if f["percent"]:
        return ("pct",)
    if f["money"]:
        return ("money",)
    if f["time"]:
        return ("time",)
    if f["unit"] in ("k", "K", "m", "M", "B", "bn", "million", "billion"):
        return ("money", "count")
    return ("count", "money", "time")


def matches(f: Json, pools: dict[str, list[float]]) -> bool:
    candidates = [f["value"]]
    if f["time"]:
        hours = f["value"] * TIME[f["unit"]]
        candidates = [hours, hours * 60, f["value"]]
    for kind in kinds_for(f):
        pool = pools[kind]
        for v in candidates:
            tol = max(f["tol"] * (abs(v / f["value"]) if f["value"] else 1), abs(v) * 0.005, 1e-9)
            i = bisect.bisect_left(pool, v - tol)
            if i < len(pool) and pool[i] <= v + tol:
                return True
    return False


SHAPES = {
    "whole percent, 21 to 99": lambda r: f"{r.randint(21, 99)}%",
    "percent to 1 decimal": lambda r: f"{r.uniform(0, 100):.1f}%",
    "dollars in millions to 1 decimal": lambda r: f"${r.uniform(1, 60):.1f}M",
    "dollars in thousands": lambda r: f"${r.randint(100, 999)}K",
    "whole hours, 21 to 99": lambda r: f"{r.randint(21, 99)}h",
    "4-digit count": lambda r: f"{r.randint(1000, 9999):,}",
}


def chance_rates(pools: dict[str, list[float]], n: int = 2000, seed: int = 1) -> dict[str, float]:
    """How often a random figure of each shape matches the pool by chance: the check's blind spot."""
    import random

    r = random.Random(seed)  # noqa: S311
    return {name: sum(matches(figures(make(r))[0], pools) for _ in range(n)) / n for name, make in SHAPES.items()}


def parse_printed(s: str) -> Json | None:
    got = figures(s.replace("−", "-"))
    if not got:
        m = re.search(r"-?\d[\d,]*\.?\d*", s)
        if not m:
            return None
        whole = m.group(0).replace(",", "")
        decimals = len(whole.split(".")[1]) if "." in whole else 0
        return {"value": float(whole), "tol": 0.5 * 10**-decimals, "unit": "", "time": False, "money": False, "percent": False}
    return got[0]


def arithmetic(fx: str, items: list[Json], truth: dict[str, Json]) -> list[Json]:
    """Each printed metric against the recomputed value. Returns one row per item with ok or not."""
    rows = []
    for it in items:
        t = truth.get(it.get("metric", ""))
        f = parse_printed(it.get("printed", ""))
        if not t or not f:
            continue
        values = t["values"] if it.get("which") == "current" else t.get("prior", [])
        if not values:
            continue
        v = f["value"]
        if f["time"] and t["unit"] in ("h", "m"):
            v = v * TIME[f["unit"]] * (60 if t["unit"] == "m" else 1)
            tol = f["tol"] * TIME[f["unit"]] * (60 if t["unit"] == "m" else 1)
        else:
            tol = f["tol"]
        ok = any(abs(abs(v) - abs(x)) <= max(tol, abs(x) * 0.005) + 1e-9 for x in values)
        rows.append({"metric": it["metric"], "which": it.get("which"), "printed": it["printed"], "expected": values, "ok": ok})
    return rows


def extract(out: Path, run: Path, fx: str, model: str) -> str:
    dest = run / "extract.json"
    if dest.exists():
        return f"extract {run}: done before"
    text = full_text(run)
    if text is None:
        dest.write_text(json.dumps({"items": [], "skipped": "no update"}), encoding="utf-8")
        return f"extract {run}: no update"
    truth = recompute(FIXTURES / fx)
    metrics = "\n".join(f"- {k}: {v['label']} ({v['unit'] or 'value'})" for k, v in truth.items() if not k.startswith("finance_plan:"))
    body, _ = split_samples(text)
    prompt = (PROMPTS / "extract.md").read_text(encoding="utf-8").format(metrics=metrics, deck=body)
    scratch = out / "scratch"
    scratch.mkdir(exist_ok=True)
    final = claude(prompt, scratch, model, "", schema=EXTRACT_SCHEMA, budget=3.0)
    got = structured(final)
    dest.write_text(json.dumps({"items": got.get("items", []), "model": model, "usage": usage_of(final)}, indent=1), encoding="utf-8")
    return f"extract {run.parent.parent.name} {fx} {run.name}: {len(got.get('items', []))} items"


def check(out: Path, fixtures: list[str], model: str, jobs: int) -> None:
    runs = [(r, fx) for fx in fixtures for cond in "ABC" for r in runs_of(out, cond, fx)]
    with cf.ThreadPoolExecutor(jobs) as pool:
        for f in cf.as_completed([pool.submit(extract, out, r, fx, model) for r, fx in runs]):
            try:
                print(f.result(), flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"extract failed: {e}", flush=True)
    pools = {fx: pool_for(fx) for fx in fixtures}
    calibration = {fx: chance_rates(p) for fx, p in pools.items()}
    (out / "calibration.json").write_text(json.dumps(calibration, indent=1), encoding="utf-8")
    for r, fx in runs:
        text = full_text(r)
        record: Json = {"fixture": fx, "run": str(r.relative_to(out))}
        if text is None:
            record["skipped"] = "no update"
        else:
            body, samples = split_samples(text)
            figs = figures(body)
            unmatched = [f["printed"] for f in figs if not matches(f, pools[fx])]
            ex = json.loads((r / "extract.json").read_text(encoding="utf-8")) if (r / "extract.json").exists() else {"items": []}
            arith = arithmetic(fx, ex.get("items", []), recompute(FIXTURES / fx))
            record |= {
                "figures": len(figs),
                "unmatched": unmatched,
                "sample_figures": len(figures(samples)),
                "arithmetic_checked": len(arith),
                "arithmetic_errors": [a for a in arith if not a["ok"]],
            }
        (r / "check.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
        if "skipped" not in record:
            errors = len(record["arithmetic_errors"])
            print(f"check {record['run']}: {record['figures']} figures, {len(record['unmatched'])} unmatched, {errors} arithmetic errors")


# ---------- report ----------


def wilson(k: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def condition_of(path: str) -> str:
    return path.split("/")[1]


def matchup_of(j: Json) -> str:
    # The first measured run judged only A against B and stored no matchup.
    return j.get("matchup") or "BA"


def tally_pairs(pairs: list[Json], m: str) -> Json:
    """Win counts for one matchup. m[0] is the condition tested, m[1] the one it is tested against."""
    t, base = m[0], m[1]

    def winner_cond(j: Json, w: str) -> str:
        return "tie" if w == "tie" else condition_of(j["x"] if w == "X" else j["y"])

    res: Json = {"tested": t, "against": base, "per_judgment": {}}
    for scope in ["overall", *CRITERIA]:
        counts = {t: 0, base: 0, "tie": 0}
        for j in pairs:
            w = j["verdict"]["overall"]["winner"] if scope == "overall" else j["verdict"]["criteria"][scope]["winner"]
            counts[winner_cond(j, w)] += 1
        n = sum(counts.values())
        decisive = counts[t] + counts[base]
        res["per_judgment"][scope] = {
            **counts,
            "n": n,
            "tested_share_with_ties_half": (counts[t] + 0.5 * counts["tie"]) / n if n else None,
            "tested_share_of_decisive": counts[t] / decisive if decisive else None,
            "tested_share_of_decisive_ci95": wilson(counts[t], decisive) if decisive else None,
        }
    # A pair counts once: a win only if both orders agree, otherwise a split.
    by_pair: dict[str, list[Json]] = {}
    for j in pairs:
        by_pair.setdefault(j["id"].rsplit("-", 1)[0], []).append(j)
    pc = {t: 0, base: 0, "split": 0}
    position = {"X": 0, "Y": 0, "tie": 0}
    for group in by_pair.values():
        ws = {winner_cond(j, j["verdict"]["overall"]["winner"]) for j in group}
        for j in group:
            position[j["verdict"]["overall"]["winner"]] += 1
        pc[next(iter(ws)) if len(ws) == 1 and len(group) == 2 and "tie" not in ws else "split"] += 1
    n_pairs = sum(pc.values())
    res["per_pair"] = {**pc, "n": n_pairs, "tested_wins_ci95": wilson(pc[t], n_pairs) if n_pairs else None}
    res["position"] = position
    per_fx: Json = {}
    for j in pairs:
        d = per_fx.setdefault(j["fixture"], {t: 0, base: 0, "tie": 0})
        d[winner_cond(j, j["verdict"]["overall"]["winner"])] += 1
    res["per_fixture"] = per_fx
    return res


def report(out: Path) -> Json:
    js = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((out / "judgments").glob("*.json"))] if (out / "judgments").exists() else []
    js = [j for j in js if "verdict" in j]
    summary: Json = {"judgments": len(js)}
    pairs = [j for j in js if j["kind"] == "pair"]
    summary["matchups"] = {m: tally_pairs([j for j in pairs if matchup_of(j) == m], m) for m in sorted({matchup_of(j) for j in pairs})}
    noise: Json = {}
    for kind in sorted({j["kind"] for j in js if j["kind"] != "pair"}):
        sel = [j for j in js if j["kind"] == kind]
        d: Json = {
            "n": len(sel),
            "overall_not_tie": sum(j["verdict"]["overall"]["winner"] != "tie" for j in sel),
            "criteria_not_tie": sum(j["verdict"]["criteria"][c]["winner"] != "tie" for j in sel for c in CRITERIA),
            "criteria_n": len(sel) * len(CRITERIA),
        }
        if kind.startswith("within_"):
            # Both orders of one pair should name the same run; a flip means the verdict follows position.
            d["order_flips"] = sum(
                1
                for fx in {j["fixture"] for j in sel}
                for pair in [[j for j in sel if j["fixture"] == fx]]
                if len(pair) == 2
                and len({(j["x"] if j["verdict"]["overall"]["winner"] == "X" else j["y"]) for j in pair if j["verdict"]["overall"]["winner"] != "tie"}) > 1
            )
        noise[kind] = d
    summary["noise"] = noise

    checks: Json = {}
    for p in sorted((out / "runs").glob("*/*/*/check.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        cond = condition_of(c["run"])
        d = checks.setdefault(
            cond, {"decks": 0, "no_update": 0, "figures": 0, "unmatched": 0, "arithmetic_checked": 0, "arithmetic_errors": 0, "sample_figures": 0}
        )
        if "skipped" in c:
            d["no_update"] += 1
            continue
        d["decks"] += 1
        for k in ("figures", "sample_figures", "arithmetic_checked"):
            d[k] += c[k]
        d["unmatched"] += len(c["unmatched"])
        d["arithmetic_errors"] += len(c["arithmetic_errors"])
    summary["checks"] = checks
    if (out / "calibration.json").exists():
        summary["chance_match_rates"] = json.loads((out / "calibration.json").read_text(encoding="utf-8"))

    cost: Json = {}

    def tally(stage: str, u: Json) -> None:
        d = cost.setdefault(
            stage, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "cost_usd": 0.0}
        )
        d["calls"] += 1
        for k in d:
            if k != "calls":
                d[k] += u.get(k) or 0

    for cond in "AC":
        for p in sorted((out / "runs" / cond).glob("*/*/meta.json")):
            tally(f"generate_{cond}", json.loads(p.read_text(encoding="utf-8"))["usage"])
    for j in js:
        tally("judge", j["usage"])
    for p in sorted((out / "runs").glob("*/*/*/extract.json")):
        e = json.loads(p.read_text(encoding="utf-8"))
        if "usage" in e:
            tally("extract", e["usage"])
    summary["cost"] = cost
    leaks = [
        str(p.parent.relative_to(out))
        for p in sorted((out / "runs" / "A").glob("*/*/meta.json"))
        if json.loads(p.read_text(encoding="utf-8")).get("skill_leaks")
    ]
    summary["skill_leaks_in_A"] = leaks
    use: Json = {}
    for p in sorted((out / "runs" / "C").glob("*/*/meta.json")):
        u = json.loads(p.read_text(encoding="utf-8"))["skill_use"]
        use[str(p.parent.relative_to(out))] = {"skill_loaded": u["skill_loaded"], "script_calls": len(u["script_calls"])}
    summary["skill_use_in_C"] = {
        "runs": len(use),
        "loaded_the_skill": sum(v["skill_loaded"] > 0 for v in use.values()),
        "ran_its_scripts": sum(v["script_calls"] > 0 for v in use.values()),
        "per_run": use,
    }
    hashes: Json = {}
    for p in sorted((out / "runs" / "B").glob("*/*/meta.json")):
        m = json.loads(p.read_text(encoding="utf-8"))
        hashes.setdefault(m["fixture"], set()).add(m["deck_sha256"])
    summary["b_distinct_decks_per_fixture"] = {k: len(v) for k, v in hashes.items()}
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["generate", "judge", "check", "report", "all"])
    ap.add_argument("--out", type=Path, default=HERE / "results" / "latest")
    ap.add_argument("--fixtures", default=",".join(sorted(p.name for p in FIXTURES.iterdir() if (p / "intake.json").exists())))
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--model", default="claude-opus-5-5", help="the model for conditions A and C")
    ap.add_argument("--conditions", default="ABC", help="which conditions to generate: A Claude alone, B the pipeline, C Claude with the skill")
    ap.add_argument("--matchups", default="CA,CB,BA", help="pairs to judge, the tested condition first; CB:2 judges 2 runs per fixture")
    ap.add_argument("--noise", default="AC", help="conditions that get self and within-condition noise runs")
    ap.add_argument("--judge-model", default="claude-opus-5-5")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--self-n", type=int, default=1, help="how many runs per fixture and noise condition to judge against themselves")
    ap.add_argument("--pairs-only", action="store_true", help="judge only the pairs, with no noise runs")
    ap.add_argument("--b-drop-sections", default="", help="counterfactual only: element ids to drop from B decks before judging, comma separated")
    args = ap.parse_args()
    fixtures = [f for f in args.fixtures.split(",") if f]
    global B_DROP
    B_DROP = frozenset(x for x in args.b_drop_sections.split(",") if x)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.step in ("generate", "all"):
        generate(args.out, fixtures, args.runs, args.model, args.jobs, args.conditions)
    if args.step in ("judge", "all"):
        judge(args.out, fixtures, args.judge_model, args.jobs, parse_matchups(args.matchups, args.runs), args.noise, args.self_n, args.pairs_only)
    if args.step in ("check", "all"):
        check(args.out, fixtures, args.judge_model, args.jobs)
    if args.step in ("report", "all"):
        report(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
