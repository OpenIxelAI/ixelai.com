#!/usr/bin/env python3
"""Writes the docs' model picks from benchmark data: who writes the verdict, the big model that verifies,
the models that draft, the model that decides (Triage), and which open models run on how much memory.

    python scripts/make-models.py           # update docs/models/ and docs/local-models/ from data.json
    python scripts/make-models.py --check   # change nothing; fail if a page is out of date
    AA_API_KEY=... python scripts/make-models.py --fetch   # read Artificial Analysis's API first

The data is docs/models/data.json: Artificial Analysis's Intelligence Index for each model and setting,
what one task costs at that setting, and, for open-weights models, their size. The picks follow the
rules in pick() below, which the models page states in words, so the pages say why each one won. Only
what's between the <!-- models:NAME --> markers in the two pages is written here.

--fetch reads https://artificialanalysis.ai/api/v2/data/llms/models with the free API key in
AA_API_KEY (made at artificialanalysis.ai; they ask that the data be credited to them, which the pages
do). Its prices are per million tokens, not per task, and it doesn't say which models are open or how
big they are, so models already in data.json keep those, and a new model counts as open only when its
name has its size in it (27B, 36B A4B) and comes from a maker already in the data with open models.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
DATA = SITE / "docs" / "models" / "data.json"
MODELS_PAGE = SITE / "docs" / "models" / "index.html"
LOCAL_PAGE = SITE / "docs" / "local-models" / "index.html"
API = "https://artificialanalysis.ai/api/v2/data/llms/models"
MARK = re.compile(r"(<!-- models:(\w+) -->)(.*?)(<!-- /models:\2 -->)", re.DOTALL)

# How each maker's models get onto your panel: (what you add, the page that explains it)
ADD = {
    "Anthropic": ("An Anthropic key, or Claude Code", "setup/#api-keys"),
    "OpenAI": ("An OpenAI key, or Codex", "setup/#api-keys"),
    "Google": ("A Gemini key, or Gemini CLI", "setup/#api-keys"),
    "SpaceXAI": ("An xAI key", "setup/#api-keys"),
    "xAI": ("An xAI key", "setup/#api-keys"),
}
OTHER = ("OpenCode, or its maker's OpenAI-compatible API", "setup/#other-models")
MEMORY_TIERS = [8, 16, 24, 32, 64, 128, 256, 512]  # GB of memory a computer or graphics card might have


def gb_needed(model: dict) -> int:
    """About how much memory a 4-bit download of the model takes to run, with room for the conversation."""
    return round(model["params"] * 0.6 + 2)


def variant(m: dict) -> str:
    return f'{m["name"]} ({m["effort"]})' if m.get("effort") else m["name"]


def best_per(models: list[dict], key) -> list[dict]:
    """The highest-scoring model for each value of key(model), best first (cheaper first on a tie)."""
    best: dict = {}
    for m in sorted(models, key=lambda m: (-m["score"], m.get("cost") if m.get("cost") is not None else 1e9)):
        best.setdefault(key(m), m)
    return list(best.values())


def known(cost) -> bool:
    """A cost to compare by. A price of 0 or none means the benchmark didn't say, not that it's free."""
    return isinstance(cost, (int, float)) and cost > 0


def usable(m: dict) -> bool:
    """Whether Ixel can run the model at this setting. Ixel sends xhigh and max as high through the
    OpenAI-style API it uses for every maker but Anthropic (and for model servers on your computer), so
    those settings only count for Claude."""
    return m["creator"] == "Anthropic" or (m.get("effort") or "").lower() not in ("xhigh", "max")


def pick(all_models: list[dict]) -> dict:
    """The picks, by the rules the models page states."""
    models = [m for m in all_models if usable(m)]
    priced = [m for m in models if known(m.get("cost"))]
    if not priced:
        raise SystemExit("No model in data.json has a cost, so there's nothing to pick by")
    # The top pick needs a cost: the other picks are measured against it
    top = max(priced, key=lambda m: (m["score"], -m["cost"]))
    family = [m for m in priced if m["name"] == top["name"]]
    # The same model at a setting that costs a third as much or less, if one scores within 5
    cheaper = [m for m in family if m["cost"] <= top["cost"] / 3 and m["score"] >= top["score"] - 5]
    cheaper = max(cheaper, key=lambda m: m["score"]) if cheaper else None
    others = [m for m in best_per(models, lambda m: m["creator"]) if m["creator"] != top["creator"]][:3]
    # Drafters: a tenth of the top model's cost per task or less, not the top model itself, one per maker
    budget = top["cost"] / 10
    drafters = best_per([m for m in priced if m["cost"] <= budget and m["name"] != top["name"]],
                        lambda m: m["name"])
    drafters = best_per(drafters, lambda m: m["creator"])[:4]
    # Triage: at least half the top score, and the cheapest of those, one per maker
    able = sorted([m for m in priced if m["score"] >= top["score"] / 2], key=lambda m: (m["cost"], -m["score"]))
    deciders, seen = [], set()
    for m in able:
        if m["creator"] not in seen:
            seen.add(m["creator"])
            deciders.append(m)
    # Local: for each amount of memory, the best open models that fit. Amounts with the same picks are
    # one row ("32 to 128 GB").
    local = []
    open_models = best_per([m for m in models if m.get("open") and m.get("params")], lambda m: m["name"])
    for tier in MEMORY_TIERS:
        fits = sorted([m for m in open_models if gb_needed(m) <= tier], key=lambda m: (-m["score"], m["params"]))[:3]
        if not fits:
            continue
        if local and [m["name"] for m in local[-1][2]] == [m["name"] for m in fits]:
            local[-1] = (local[-1][0], tier, fits)
        else:
            local.append((tier, tier, fits))
    return {"top": top, "cheaper": cheaper, "others": others, "budget": budget, "drafters": drafters,
            "deciders": deciders[:3], "local": local, "biggest": sorted(open_models, key=lambda m: -m["score"])[:3]}


# ── HTML ────────────────────────────────────────────────────────────────

def e(text) -> str:
    return html.escape(str(text))


def money(cost) -> str:
    return "not shown" if not known(cost) else f"${cost:,.3f}" if cost < 0.1 else f"${cost:,.2f}"


def how(m: dict, up: str) -> str:
    what, where = ADD.get(m["creator"], OTHER)
    text = f'<a href="{up}{where}">{e(what)}</a>'
    if m.get("open"):
        text += f', or <a href="{up}local-models/">run it yourself</a>'
    return text


def row(role: str, m: dict, why: str, up: str, also: str = "") -> str:
    return (f'\n          <tr>\n            <td>{role}</td>\n            <td><b>{e(variant(m))}</b>'
            f'<small>{e(m["creator"])}</small></td>\n            <td class="num">{m["score"]}</td>\n'
            f'            <td class="num">{money(m.get("cost"))}</td>\n            <td>{why}{also}<small>{how(m, up)}</small></td>\n          </tr>')


def picks_html(data: dict, p: dict) -> str:
    up = "../"
    top, cheaper = p["top"], p["cheaper"]
    others = ", ".join(f'{e(variant(m))} ({m["score"]})' for m in p["others"])
    cheap_note = (f' At <b>{e(cheaper["effort"])}</b> effort it scores {cheaper["score"]} for '
                  f'{money(cheaper["cost"])} a task.' if cheaper else "")
    rows = [row("Writes the verdict", top, "The highest score, so the final answer is the best it can be."
                + cheap_note, up, f'<small>From other makers: {others}.</small>' if others else "")]
    rows.append(row("Big model that verifies", top, "The same top model. In Saver it reads the drafts and "
                    "replies in a few words, so it costs far less here than writing answers.", up))
    for i, m in enumerate(p["drafters"]):
        rows.append(row("Models that draft" if i == 0 else "", m,
                        "The best score at a tenth of the top model's cost or less." if i == 0 else
                        "Another maker, so the drafts don't share blind spots." if i == 1 else "Also good.", up))
    for i, m in enumerate(p["deciders"]):
        rows.append(row("Decides, in Triage" if i == 0 else "", m,
                        "The cheapest model that scores at least half the top score: Triage asks it short "
                        "questions between rounds." if i == 0 else "The cheapest from another maker.", up))
    head = ('\n      <div class="table picks">\n        <table>\n          <thead><tr><th>Job</th><th>Pick</th>'
            f'<th>Score</th><th>Cost</th><th>Why, and how to add it</th></tr></thead>\n          <tbody>'
            + "".join(rows) + '\n          </tbody>\n        </table>\n      </div>\n      ')
    return head


def fresh_html(data: dict) -> str:
    day = dt.date.fromisoformat(data["read_on"])
    when = f"{day.day} {day:%B %Y}"  # (%-d isn't on Windows)
    return (f'\n      <p class="fresh"><span>Picks from <a href="{e(data["source_url"])}">{e(data["source"])}</a>, '
            f'read {e(when)}</span></p>\n      ')


def method_html(data: dict, p: dict) -> str:
    return (f'\n      <p>Score is {e(data["source"])}\'s <b>{e(data["score"])}</b>, which combines its tests of '
            f'reasoning, knowledge, math and coding into one number. Cost is {e(data["cost"])}: '
            f'{e(data["cost_note"])} The picks come from {e(data["read_from"])}, read on {e(data["read_on"])}.</p>\n      ')


def local_html(data: dict, p: dict) -> str:
    up = "../"
    rows = []
    for low, high, models in p["local"]:
        tier = f"{low} GB" if low == high else f"{low} to {high} GB"
        first, rest = models[0], models[1:]
        also = "; ".join(f'{e(variant(m))} ({m["score"]})' for m in rest)
        size = f'{first["params"]:g}B' + (f', {first["active"]:g}B active' if first.get("active") else "")
        rows.append(f'\n          <tr>\n            <td>{tier}</td>\n            <td><b>{e(variant(first))}</b>'
                    f'<small>{e(first["creator"])} · {size}</small></td>\n            <td class="num">{first["score"]}</td>\n'
                    f'            <td class="num">about {gb_needed(first)} GB</td>\n'
                    f'            <td>{("Also: " + also) if also else ""}</td>\n          </tr>')
    biggest = ", ".join(f'{e(variant(m))} ({m["score"]}, {m["params"]:g}B, about {gb_needed(m)} GB)'
                        for m in p["biggest"])
    return ('\n      <div class="table picks">\n        <table>\n          <thead><tr><th>Memory</th><th>Best open model'
            '</th><th>Score</th><th>Needs</th><th>Next best</th></tr></thead>\n          <tbody>' + "".join(rows)
            + '\n          </tbody>\n        </table>\n      </div>\n      <p>The best open models overall: '
            + biggest + '. Those need a server, or a Mac with a lot of memory.</p>\n      ')


# ── Reading Artificial Analysis ───────────────────────────────────────────

EFFORT = re.compile(r"^(.*?)\s*\(([^()\d]*)\)\s*$")  # "(high)", "(max)"; not a date like "(Sep '25)"
SIZE = re.compile(r"(\d+(?:\.\d+)?)B(?:\s*A(\d+(?:\.\d+)?)B)?\b", re.IGNORECASE)


def fetch(data: dict) -> dict:
    key = os.environ.get("AA_API_KEY")
    if not key:
        raise SystemExit("--fetch needs your Artificial Analysis API key in AA_API_KEY")
    request = urllib.request.Request(API, headers={"x-api-key": key, "User-Agent": "ixelai.com docs"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - a fixed https address
        rows = json.load(response).get("data", [])
    before = {(m["name"], m.get("effort")): m for m in data["models"]}
    open_makers = {m["creator"] for m in data["models"] if m.get("open")}
    models = []
    for r in rows:
        score = (r.get("evaluations") or {}).get("artificial_analysis_intelligence_index")
        if score is None:
            continue
        full = r.get("name") or ""
        match = EFFORT.match(full)
        name, effort = (match.group(1), match.group(2)) if match else (full, None)
        creator = (r.get("model_creator") or {}).get("name") or ""
        price = (r.get("pricing") or {}).get("price_1m_blended_3_to_1")
        price = price if known(price) else None
        m = {"name": name, "creator": creator, "effort": effort, "score": round(score), "cost": price}
        old = before.get((name, effort)) or next((k for (n, _), k in before.items() if n == name), None)
        if old and old.get("open"):
            m.update({k: old[k] for k in ("open", "params", "active") if k in old})
        elif creator in open_makers and (size := SIZE.search(name)):
            m.update({"open": True, "params": float(size.group(1))})
            if size.group(2):
                m["active"] = float(size.group(2))
        models.append(m)
    if not models:
        raise SystemExit("Artificial Analysis sent no models with a score; data.json is left as it was")
    return {**data, "read_on": dt.date.today().isoformat(), "read_from": "its API",
            "source_url": "https://artificialanalysis.ai/", "cost": "price per million tokens",
            "cost_note": "The price of a million tokens, three parts reading to one part writing, in US dollars.",
            "models": models}


# ── Writing the pages ───────────────────────────────────────────────────

def fill(text: str, parts: dict[str, str], page: Path) -> str:
    found = set()

    def one(match: re.Match) -> str:
        found.add(match.group(2))
        return match.group(1) + parts.get(match.group(2), match.group(3)) + match.group(4)

    out = MARK.sub(one, text)
    if missing := set(parts) - found:
        raise SystemExit(f"{page.relative_to(SITE)}: no markers for {', '.join(sorted(missing))}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="change nothing; fail if a page is out of date")
    parser.add_argument("--fetch", action="store_true", help="read Artificial Analysis's API into data.json first")
    args = parser.parse_args()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if args.fetch:
        data = fetch(data)
    p = pick(data["models"])  # before data.json changes: data the picks can't be made from isn't kept
    if args.fetch:
        DATA.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    pages = {
        MODELS_PAGE: {"fresh": fresh_html(data), "picks": picks_html(data, p), "method": method_html(data, p)},
        LOCAL_PAGE: {"fresh": fresh_html(data), "local": local_html(data, p)},
    }
    stale = []
    for page, parts in pages.items():
        text = page.read_text(encoding="utf-8")
        new = fill(text, parts, page)
        if new != text:
            stale.append(page.relative_to(SITE))
            if not args.check:
                page.write_text(new, encoding="utf-8")
    if args.check and stale:
        print("Out of date (run python scripts/make-models.py):", *stale, sep="\n  ")
        return 1
    print("Up to date." if not stale else f"Updated {', '.join(map(str, stale))}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
