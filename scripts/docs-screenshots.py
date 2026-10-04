#!/usr/bin/env python3
"""Takes the docs' pictures of the Ixel app: runs it here with example models, a demo project and demo
machines, and captures each screen in Chromium.

    python scripts/docs-screenshots.py --ixel-mat ../ixel-mat

Run it with a Python that has Ixel MAT and Handoff installed from their checkouts
(pip install -e ../ixel-mat -e ../Handoff-by-IxelAI), plus Playwright and Pillow.

Nothing reaches a model provider: the panel's answers come from a stand-in server on this computer (Ixel
MAT's own tests/fake_providers.py) and are scripted for the pictures, which the docs say under each one.
Everything runs in a home folder of its own (--home; a new temporary folder by default), so no real
paths, keys, names or machines appear. Look at every picture before committing it.

The pictures go in docs/images/ as WebP. Run it again after the app changes, and commit what changed.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
OUT = SITE / "docs" / "images"
URL_RE = re.compile(r"http://127\.0\.0\.1:\d+/#token=[A-Za-z0-9_-]+")
VIEWPORT = {"width": 1280, "height": 800}

QUESTION = "Is the regex ^(a+)+$ safe to run on text people type in?"
ANSWERS = {
    "claude-opus-5-5": (
        "No. `(a+)+` puts one quantifier inside another, so when a match fails (try `aaaaaaaaaaaaaaaaaaaaaaaa!`) "
        "the engine tries every way of splitting the a's between the two loops before it gives up. That's "
        "exponential time, a classic ReDoS.\n\n`^a+$` matches exactly the same strings in linear time."),
    "gpt-6-astra": (
        "Not safe. It's the textbook catastrophic-backtracking pattern: nested quantifiers over the same "
        "characters. A 30-character input that almost matches can hang the thread for minutes.\n\n"
        "Use `^a+$`, or an engine that never backtracks (RE2, Go's regexp, Rust's regex)."),
    "gemini-3.8-flash": (
        "Yes, it's safe: the anchors `^` and `$` pin the match to the whole string, so the engine has "
        "nothing to backtrack into."),
    "qwen3.8:27b": (
        "No. Nested quantifiers like `(a+)+` backtrack exponentially when the match fails. Rewrite it as "
        "`^a+$`, and put a length limit on the input."),
}
VERDICT = (
    "**No, it isn't safe** on text people type in.\n\n"
    "The inner `a+` and the outer `+` can split a run of a's in exponentially many ways. When the input "
    "almost matches (`aaaaaaaaaaaaaaaaaaaaaaaaaaaa!`), the engine tries all of them before it fails, which "
    "can hang the thread for minutes: a regular-expression denial of service (ReDoS).\n\n"
    "**Fix it:**\n\n"
    "- Write `^a+$`. It matches exactly the same strings, in linear time.\n"
    "- Or use an engine that never backtracks: RE2, Go's `regexp`, Rust's `regex`.\n"
    "- Either way, limit how long the input can be.")
AGENTS = [  # name, model the stand-in answers as, label, billing
    ("claude", "claude-opus-5-5", "Claude", "api"),
    ("gpt", "gpt-6-astra", "GPT", "api"),
    ("gemini", "gemini-3.8-flash", "Gemini Flash", "api"),
    ("qwen", "qwen3.8:27b", "Qwen 27B (local)", "local"),
]
MACHINES = [
    {"id": "m1", "name": "homelab", "host": "homelab", "user": "you", "agent": "openclaw",
     "command": "openclaw tui", "group": "Home", "notes": "The Mac mini in the closet"},
    {"id": "m2", "name": "vps-1", "host": "203.0.113.10", "user": "deploy", "agent": "hermes",
     "command": "hermes", "group": "Cloud"},
    {"id": "m3", "name": "gpu-box", "host": "gpu-box", "user": "you", "port": 2222, "agent": "custom",
     "command": "./serve.sh", "group": "Home"},
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ixel-mat", required=True, type=Path, help="an Ixel MAT checkout (for its tests' stand-in server)")
    parser.add_argument("--home", type=Path, help="the home folder to run in (default: a new temporary folder)")
    parser.add_argument("--out", type=Path, default=OUT, help=f"where the pictures go (default: {OUT})")
    parser.add_argument("--only", nargs="*", help="take only these pictures (their names, without .webp)")
    args = parser.parse_args()

    sys.path.insert(0, str(args.ixel_mat.resolve() / "tests"))
    from fake_providers import ThreadedFakeProvider  # noqa: E402

    home = args.home or Path(tempfile.mkdtemp(prefix="ixel-docs-"))
    if home.exists() and any(home.iterdir()):
        print(f"{home} isn't empty. Give an empty or new folder with --home.", file=sys.stderr)
        return 2
    home.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)

    with ThreadedFakeProvider(panel) as fake:
        fake.stream_delay = 0.05
        make_home(home, fake.openai_url)
        with run_app(home) as url:
            shoot(url, home, args.out, set(args.only or ()))
    print(f"Done. The pictures are in {args.out}. Look at each one before committing it.")
    return 0


# ── The stand-in models ─────────────────────────────────────────────────────

def panel(recorded):
    from fake_providers import FENCED_ANSWER, openai_reply, prompt_kind, verdict_reply

    prompt = recorded.body["messages"][0]["content"]
    if isinstance(prompt, list):
        prompt = "".join(p.get("text", "") for p in prompt if isinstance(p, dict))
    kind = prompt_kind(prompt)
    model = recorded.body["model"]
    if kind == "answer":
        time.sleep({"qwen3.8:27b": 1.2, "gemini-3.8-flash": 0.6}.get(model, 0.3))
        return openai_reply(ANSWERS[model])
    if kind == "review":
        reviews, best = [], None
        for _, label, text in FENCED_ANSWER.findall(prompt):
            right = not text.startswith("Yes")
            reviews.append({"answer": label, "verdict": "correct" if right else "incorrect",
                            "errors": [] if right else ["The anchors don't stop backtracking inside the group: "
                                                        "(a+)+ is still exponential on a near-match."],
                            "strengths": ["Gives a linear-time rewrite."] if right and "^a+$" in text else []})
            if right and best is None:
                best = label
        return openai_reply(json.dumps({"reviews": reviews, "best": best, "summary": "Checked each claim."}))
    if kind == "verify":
        good = [label for _, label, text in FENCED_ANSWER.findall(prompt) if not text.startswith("Yes")]
        return openai_reply(json.dumps({"status": "confirmed", "use": good[0]}))
    return openai_reply(verdict_reply(prompt, VERDICT, confidence="high",
                                      corrections=["One answer said the anchors prevent backtracking. They "
                                                   "don't: the group inside them still backtracks."]))


# ── The home folder: settings, machines and a project with a board ──────────────

def make_home(home: Path, url: str) -> None:
    cfg = home / ".config" / "ixel-mat"
    cfg.mkdir(parents=True)
    agents = "".join(
        f'[agents.{name}]\ntype = "http"\nurl = "{url}"\ntoken_env = "IXEL_DEMO_KEY"\nmodel = "{model}"\n'
        f'label = "{label}"\nbilling = "{billing}"\n\n' for name, model, label, billing in AGENTS)
    (cfg / "config.toml").write_text(
        "# Example settings for the docs' pictures\n\n" + agents
        + '[review]\nmode = "review"\nmoderator = "claude"\n\n'
        + '[saver]\nverifier = "claude"\nescalate = "disagreement"\n\n'
        + '[triage]\nenabled = true\nagent = "gemini"\n\n'
        + '[updates]\ncheck = false\n', encoding="utf-8")
    (cfg / "machines.json").write_text(json.dumps({"version": 1, "machines": MACHINES}, indent=2), encoding="utf-8")

    shop = home / "code" / "shop"
    (shop / "api").mkdir(parents=True)
    (shop / "api" / "orders.py").write_text("def list_orders():\n    return []\n", encoding="utf-8")
    (shop / "README.md").write_text("# Shop\n", encoding="utf-8")
    git = ["git", "-C", str(shop), "-c", "user.name=You", "-c", "user.email=you@example.com",
           "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(shop)], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "Start the shop"], check=True)
    make_board(shop)


def make_board(project: Path) -> None:
    from handoff.board import HUMAN, Board

    board = Board.open(project)
    t1, _ = board.create("claude", "Add /api/orders", "List and create orders.",
                         ["GET returns the user's orders", "POST validates the cart"], assignee="claude",
                         paths=["api/orders.py"])
    board.note("claude", t1.id, "The endpoint and its validation are done; wiring up the database next.")
    t2, _ = board.create("claude", "Tests for /api/orders", "Cover both routes.",
                         ["tests/test_orders.py covers GET and POST", "pytest runs without network"],
                         assignee="codex")
    board.claim("codex", t2.id, ["tests/test_orders.py"])
    board.pass_task("codex", t2.id, "claude", done="Tests written in tests/test_orders.py",
                    left="2 fail until the endpoint lands", verify="pytest tests/test_orders.py",
                    files=["tests/test_orders.py"])
    board.create(HUMAN, "Update the API docs", "Describe /api/orders in docs/api.md.", assignee="codex")
    t4, _ = board.create("claude", "Take payments at checkout", "Charge the cart total.", assignee="claude")
    board.set_status("claude", t4.id, "blocked", reason="Which payment provider: Stripe or Paddle?",
                     waiting_on=HUMAN)
    t5, _ = board.create("codex", "Fix the cart total's rounding", "Totals were off by a cent on some carts.",
                         ["A cart of 3 × $0.10 totals $0.30"], assignee="codex")
    board.note("codex", t5.id, "Money is kept in cents now, so nothing is rounded twice.")
    board.request_review("codex", t5.id, HUMAN, "Check the rounding fix in cart.py")
    t6, _ = board.create("claude", "Set up the linter", "Ruff, with the project's line length.", assignee="claude")
    board.set_status("claude", t6.id, "done", reason="Nothing to review: config only.")
    board.create(HUMAN, "Make a logo for the shop", "Something simple, in the shop's green.")


@contextlib.contextmanager
def run_app(home: Path):
    """`ixel gui` with `home` as its home folder; yields the address it prints."""
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "PYTHONIOENCODING": "utf-8",
           "PYTHONUNBUFFERED": "1", "IXEL_DEMO_KEY": "demo", "IXEL_NO_UPDATE_CHECK": "1"}
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY",
                "GROQ_API_KEY", "TYPESAFE_API_KEY"):
        env.pop(key, None)
    proc = subprocess.Popen([sys.executable, "-m", "ixel_mat", "gui", "--no-browser"], env=env, cwd=home,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    found = {}

    def read():
        for line in proc.stdout:
            match = URL_RE.search(line)
            if match and "url" not in found:
                found["url"] = match.group(0)

    threading.Thread(target=read, daemon=True).start()
    deadline = time.monotonic() + 30
    while "url" not in found and time.monotonic() < deadline and proc.poll() is None:
        time.sleep(0.1)
    try:
        if "url" not in found:
            raise SystemExit("ixel gui didn't print its address")
        yield found["url"]
    finally:
        proc.terminate()
        proc.wait(10)


# ── The pictures ──────────────────────────────────────────────────────────

def shoot(url: str, home: Path, out: Path, only: set[str]) -> None:
    from playwright.sync_api import sync_playwright

    def save(page, name: str, **options) -> None:
        if only and name not in only:
            return
        png = page.screenshot(**options)
        webp(png, out / f"{name}.webp")
        print(f"  {name}.webp")

    with sync_playwright() as p:
        browser = launch(p)
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=2, color_scheme="dark")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector(".model", state="attached")
        page.wait_for_timeout(500)
        save(page, "app-ask")

        page.fill("#question", QUESTION)
        page.click('.modes button[data-mode="review"]')
        page.click("#ask")
        page.wait_for_selector(".thread:not([hidden]) .turn:last-child th.step.active", timeout=30_000)
        page.wait_for_timeout(700)
        save(page, "app-ask-working")
        done = page.locator(".thread:not([hidden]) .turn:last-child th.step.done")
        deadline = time.monotonic() + 60  # (the page's CSP refuses wait_for_function's eval)
        while done.count() < 3 and time.monotonic() < deadline:
            page.wait_for_timeout(250)
        page.wait_for_selector("table.scores", timeout=60_000)
        page.wait_for_timeout(800)
        page.evaluate("document.querySelector('.verdict').scrollIntoView({block: 'start'})")
        page.wait_for_timeout(300)
        save(page, "app-ask-verdict")
        page.evaluate("document.querySelector('table.scores').scrollIntoView({block: 'center'})")
        page.wait_for_timeout(300)
        save(page, "app-ask-scores")

        page.set_viewport_size({"width": 1480, "height": 800})
        page.click('.rail-item[data-view="board"]')
        page.fill("#board-project-input", str(home / "code" / "shop"))
        page.press("#board-project-input", "Enter")
        page.wait_for_selector(".columns", timeout=20_000)
        page.locator("#board-title").click()
        page.wait_for_timeout(1000)
        save(page, "app-board")
        with contextlib.suppress(Exception):
            page.get_by_text("Tests for /api/orders").first.click()
            page.wait_for_timeout(1000)
            save(page, "app-board-task")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)

        page.set_viewport_size(VIEWPORT)
        page.click('.rail-item[data-view="machines"]')
        page.wait_for_timeout(1000)
        save(page, "app-machines")

        page.click('.rail-item[data-view="health"]')
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Check now").click()
        page.set_viewport_size({"width": 1280, "height": 1640})  # the page scrolls inside the window
        page.wait_for_timeout(4000)
        save(page, "app-health")
        page.set_viewport_size(VIEWPORT)

        page.click('.rail-item[data-view="settings"]')
        page.wait_for_selector(".set-group", timeout=20_000)
        page.wait_for_timeout(1500)
        save(page, "app-settings")
        with contextlib.suppress(Exception):
            page.locator("#set-h-saver").scroll_into_view_if_needed()
            page.evaluate("document.querySelector('#set-h-review').scrollIntoView({block: 'start'})")
            page.wait_for_timeout(500)
            page.set_viewport_size({"width": 1280, "height": 1180})
            page.wait_for_timeout(500)
            save(page, "app-settings-roles")
        if errors:
            print("The page reported errors:", *errors, sep="\n  ", file=sys.stderr)
        browser.close()


def launch(p):
    try:
        return p.chromium.launch()
    except Exception:  # noqa: BLE001 - a Playwright without its own Chromium: use one that's installed
        for path in (os.environ.get("CHROMIUM"), "/opt/pw-browsers/chromium", shutil.which("chromium"),
                     shutil.which("chromium-browser"), shutil.which("google-chrome")):
            if path and os.path.exists(path):
                return p.chromium.launch(executable_path=path)
        raise


def webp(png: bytes, path: Path) -> None:
    from PIL import Image

    with Image.open(io.BytesIO(png)) as image:
        image.convert("RGB").save(path, "WEBP", quality=82, method=6)


if __name__ == "__main__":
    sys.exit(main())
