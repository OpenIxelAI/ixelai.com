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

--fetch reads Artificial Analysis's free API (https://artificialanalysis.ai/api/v2/language/models/free,
documented at https://artificialanalysis.ai/data-api/docs) with the free API key in AA_API_KEY. They ask
that the data be credited to them, which the pages do. It gives each model's score and cost per task, the
same numbers as their pages, and replaces every model's in data.json. It doesn't say which models are
open or how big they are (their paid tiers do, and are used when the key is one), so a model already
marked open in data.json keeps that and its size, matched by name. A new model counts as open only when
its name has its size in it (27B, 36B A4B) and its maker's models here are all open; other new models
from makers with open models are listed once, on the run that first sees them, to add by hand. --fetch
changes nothing when the API refuses or redirects, sends under half as many models as data.json has,
gives no costs, or would leave under half of the open models.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
DATA = SITE / "docs" / "models" / "data.json"
MODELS_PAGE = SITE / "docs" / "models" / "index.html"
LOCAL_PAGE = SITE / "docs" / "local-models" / "index.html"
API = "https://artificialanalysis.ai/api/v2/language/models/free"
MAX_PAGES = 10  # their free tier allows 100 requests a day; a page holds 200 models
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


LEVELS = ["minimal", "low", "medium", "high", "xhigh", "max"]
# The highest thinking level Ixel sends each maker's current models (ixel_mat/effort.py in Ixel MAT): a
# higher one is sent as this. Other makers' APIs and model servers on your own computer take up to high.
TOP_LEVEL = {"Anthropic": "max", "OpenAI": "max", "SpaceXAI": "xhigh", "xAI": "xhigh", "Google": "high"}


def usable(m: dict, local: bool = False) -> bool:
    """Whether Ixel can run the model at this setting: a setting above what Ixel sends that maker (or, run
    on your own computer, above high) would be sent as a lower one, so its score wouldn't be what you get."""
    found = levels_in(m.get("effort") or "")
    if not found:  # no setting, or one that isn't a thinking level ("Reasoning")
        return True
    top = "high" if local else TOP_LEVEL.get(m["creator"], "high")
    return LEVELS.index(max(found, key=LEVELS.index)) <= LEVELS.index(top)


def pick(all_models: list[dict]) -> dict:
    """The picks, by the rules the models page states."""
    models = [m for m in all_models if usable(m)]
    priced = [m for m in models if known(m.get("cost"))]
    if not priced:
        raise SystemExit("No model in data.json has a cost, so there's nothing to pick by")
    # The top pick needs a cost: the other picks are measured against it
    top = max(priced, key=lambda m: (m["score"], -m["cost"]))
    family = [m for m in priced if m["name"] == top["name"] and m.get("effort") in LEVELS]
    # The same model at a setting that costs a third as much or less, if one scores within 5
    cheaper = [m for m in family if m["cost"] <= top["cost"] / 3 and m["score"] >= top["score"] - 5]
    cheaper = max(cheaper, key=lambda m: m["score"]) if cheaper else None
    others = [m for m in best_per(priced, lambda m: m["creator"]) if m["creator"] != top["creator"]][:3]
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
    open_models = best_per([m for m in all_models if m.get("open") and m.get("params") and usable(m, local=True)],
                           lambda m: m["name"])
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
# A size standing on its own in a name: "27B", "36B A4B", "235B-A22B"; not "8x22B" or "Flash-8B"'s guess
SIZE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)B(?:[\s-]*A(\d+(?:\.\d+)?)B)?\b", re.IGNORECASE)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is refused, not followed, so the key never goes anywhere but Artificial Analysis."""

    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


def levels_in(setting: str) -> list[str]:
    """The thinking levels a setting names, however it's written: "Max Effort", "Reasoning, Extra High"."""
    text = re.sub(r"\b(?:x|extra)[\s-]*high\b", "xhigh", setting.lower())
    return [w for w in re.findall(r"[a-z]+", text) if w in LEVELS]


def level(setting: str) -> str:
    """A thinking setting as Ixel names it ("Reasoning, Max Effort" is max), or as it's written when it
    names no level ("Reasoning") or has thinking off ("Non-reasoning, Low Effort"), so that one is never
    shown as the thinking setting of the same name."""
    found = levels_in(setting)
    if not found or re.search(r"\bnon[\s-]*reasoning\b", setting, re.IGNORECASE):
        return setting
    return max(found, key=LEVELS.index)


def same(name: str) -> str:
    """A model's name for matching, so "gpt-oss-120B" and "gpt-oss-120b" are one model."""
    return re.sub(r"[^a-z0-9.]", "", name.lower())


def notes(title: str, lines: list[str]) -> None:
    """Things for a person to look at. In a GitHub Actions run they go on the run's summary page, with one
    warning that says how many, since a run's page shows only the first ten warnings."""
    if not lines:
        return
    print(f"{title}:", *lines, sep="\n  ")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as out:
            out.write(f"### {title}\n\n" + "".join(f"- {line}\n" for line in lines) + "\n")
        print(f"::warning::{title}: {len(lines)}. They're listed on this run's summary.")


def read_api(key: str) -> list[dict]:
    """Every model on Artificial Analysis's free API, page by page."""
    rows: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        request = urllib.request.Request(f"{API}?page={page}", headers={"User-Agent": "ixelai.com docs"})
        request.add_unredirected_header("x-api-key", key)
        try:
            with OPENER.open(request, timeout=60) as response:
                body = json.load(response)
        except urllib.error.HTTPError as error:
            why = {401: "the key is missing or wrong", 429: "today's requests are used up"}.get(error.code, error.reason)
            if 300 <= error.code < 400:
                why = "it sent the request somewhere else, which isn't followed"
            raise SystemExit(f"Artificial Analysis answered {error.code} ({why}); data.json is left as it was")
        rows += body.get("data") or []
        if not (body.get("pagination") or {}).get("has_more"):
            return rows
    raise SystemExit(f"Artificial Analysis has more than {MAX_PAGES} pages of models; data.json is left as it was")


def fetch(data: dict) -> dict:
    key = os.environ.get("AA_API_KEY")
    if not key:
        raise SystemExit("--fetch needs your Artificial Analysis API key in AA_API_KEY")
    rows = read_api(key)
    before = {(same(m["name"]), m.get("effort")): m for m in data["models"]}
    by_name = {same(m["name"]): m for m in data["models"]}
    makers = {m["creator"] for m in data["models"]}
    some_open = {m["creator"] for m in data["models"] if m.get("open")}
    # Makers whose every model here is open, so a new one with its size in its name is open too. A maker
    # with closed models as well (Google's Gemini beside Gemma) could have a closed "Flash-8B".
    open_makers = {c for c in some_open if all(m.get("open") for m in data["models"] if m["creator"] == c)}
    models, maybe_open = [], {}
    for r in rows:
        score = (r.get("evaluations") or {}).get("artificial_analysis_intelligence_index")
        if not isinstance(score, (int, float)) or score < 0:
            continue
        full = r.get("name") or ""
        match = EFFORT.match(full)
        name, effort = (match.group(1), level(match.group(2))) if match else (full, None)
        creator = (r.get("model_creator") or {}).get("name") or ""
        cost = ((r.get("artificial_analysis_intelligence_index_cost") or {}).get("cost_per_task") or {}).get("total_cost")
        m = {"name": name, "creator": creator, "effort": effort, "score": math.floor(score + 0.5),  # as they show it
             "cost": cost if known(cost) else None}
        size = r.get("parameters") or {}
        old = before.get((same(name), effort)) or by_name.get(same(name))
        if (r.get("licensing") or {}).get("is_open_weights") and known(size.get("total")):  # paid tiers say
            m.update({"open": True, "params": float(size["total"])})
            if known(size.get("active")) and size["active"] < size["total"]:
                m["active"] = float(size["active"])
        elif old and old.get("open"):
            m.update({k: old[k] for k in ("open", "params", "active") if k in old})
        elif (creator in open_makers and (found := SIZE.search(name))
              and not re.search(r"\d+x\d+(?:\.\d+)?B", name, re.IGNORECASE)):
            m.update({"open": True, "params": float(found.group(1))})
            if found.group(2):
                m["active"] = float(found.group(2))
        elif not old and "licensing" not in r and (creator in some_open or creator not in makers):
            best = maybe_open.get(same(name))
            if not best or m["score"] > best["score"]:
                maybe_open[same(name)] = m
        models.append(m)
    if len(models) < len(data["models"]) / 2:
        raise SystemExit(f"Artificial Analysis sent {len(models)} models with a score, under half the "
                         f"{len(data['models'])} in data.json, so it looks incomplete; data.json is left as it was")
    was_open = {same(m["name"]) for m in data["models"] if m.get("open")}
    still_open = {same(m["name"]) for m in models if m.get("open")}
    if len(was_open & still_open) < len(was_open) / 2:
        raise SystemExit(f"Only {len(was_open & still_open)} of the {len(was_open)} open models in data.json "
                         "came back, so the Local models page would lose most of its picks; data.json is left as it was")
    notes("Open models no longer in Artificial Analysis's list",
          [by_name[gone]["name"] for gone in sorted(was_open - still_open)])
    notes('New models that may be open (if one is, add "open" and "params" for it in docs/models/data.json '
          "so the Local models page can list it)",
          [f'{m["name"]}, from {m["creator"]}, scores {m["score"]}'
           for m in sorted(maybe_open.values(), key=lambda m: -m["score"])])
    return {**data, "read_on": dt.date.today().isoformat(), "read_from": "its API",
            "source_url": "https://artificialanalysis.ai/leaderboards/models", "models": models}


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
