#!/usr/bin/env python3
"""Records the docs' videos of Ixel at work: the Ask panel, a Board run, the Agent (beta), Machines, and Handoff
and Ixel MAT in a terminal.

    python scripts/docs-videos.py --ixel-mat ../Ixel-MAT --home /tmp/you

Run it with a Python that has Ixel MAT and Handoff installed from their checkouts
(pip install -e ../Ixel-MAT -e ../Handoff-by-IxelAI), plus Playwright, and with ffmpeg on PATH. The terminal
clips need xterm.js: `npm install @xterm/xterm@5.5.0` in a folder, and pass that folder with --xterm.

Everything really runs: the Ixel app, Handoff's board, worker and merge, the Agent's tools, its sandbox and the
tests it runs, and the `handoff` and `ixel` commands. Only the models are stand-ins on this computer, so no
model provider is reached and nothing is billed:

- the panel's answers come from Ixel MAT's own test server (tests/fake_providers.py), scripted as in
  docs-screenshots.py;
- the Agent's model replies with a scripted list of actions (read, edit, run the tests, finish);
- a stand-in Ollama at 127.0.0.1:11434 drives the Board run with Handoff's four file tools, and answers
  Auto crew's question about the job.

Each clip says so in its corner, and the videos page says so too. Port 11434 must be free. The app runs with
a PATH of its own (this Python's folder, a stand-in `ollama`, and the system's folders), so real agents on
this computer aren't found. Everything runs in --home, which must be empty or new; its path shows on the
Board, so pick a plain one. Look at every clip before committing it.

The clips go in videos/ as MP4 (H.264, no sound), each with a JPG poster. Ask, the Board and the Agent have real
recordings with real models in videos/real/ (its README.txt says how they were made), so by default this records
only the clips that still use stand-ins: machines, handoff-terminal and ixel-terminal. `--only ask board agent`
records stand-in versions of the other three as ixel-mat, handoff and agent, which no page shows.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import importlib.util
import json
import os
import pty
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
OUT = SITE / "videos"
VIEWPORT = {"width": 1280, "height": 800}
CLIPS = ("ask", "board", "agent", "machines", "handoff-terminal", "ixel-terminal")
# The clips no real recording replaces yet; the rest are in videos/real/
STAND_INS = ("machines", "handoff-terminal", "ixel-terminal")
CAPTION = "Stand-in models, scripted replies"
# The file each clip is saved as (videos/README.md)
FILES = {"ask": "ixel-mat", "board": "handoff"}
FONT = next((f for f in ("/usr/share/fonts/opentype/inter/Inter-Regular.otf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") if os.path.exists(f)), None)

shots = None  # docs-screenshots.py, loaded in main()

# ── The Agent's stand-in model: one scripted run ─────────────────────────────

AGENT_GOAL = "Fix the cart total's rounding and run the tests"
AGENT_SCRIPT = [
    {"thought": "Read the cart code and its test first.",
     "reads": [{"action": "read_file", "args": {"path": "cart.py"}},
               {"action": "read_file", "args": {"path": "tests/test_cart.py"}}]},
    {"thought": "0.10 can't be held exactly as a float, and totals under $1 skip the rounding. Add whole cents "
                "instead.",
     "action": "edit_file", "args": {
         "path": "cart.py",
         "old": "    total = 0.0\n    for price in prices:\n        total += price\n"
                "    return round(total, 2) if total > 1 else total\n",
         "new": "    cents = sum(round(price * 100) for price in prices)\n    return cents / 100\n"}},
    {"thought": "Run the tests to check the fix.", "action": "run_command",
     "args": {"argv": ["python3", "-m", "pytest", "-q"]}},
    {"thought": "Both tests pass.", "action": "finish", "args": {"answer": (
        "Fixed cart_total in cart.py. It now adds the prices in whole cents, so three dimes total 0.30 instead "
        "of 0.30000000000000004; carts under $1 used to skip the rounding. Both tests pass.")}},
]
agent_calls = {"n": 0}


def models(recorded):
    """The panel's stand-in, and the Agent's (its prompt lists the Agent's actions)."""
    from fake_providers import openai_reply

    text = json.dumps(recorded.body.get("messages", []))
    if "edit_file" in text and "run_command" in text:
        n = agent_calls["n"]
        agent_calls["n"] += 1
        time.sleep(1.5)
        return openai_reply(json.dumps(AGENT_SCRIPT[min(n, len(AGENT_SCRIPT) - 1)]))
    return shots.panel(recorded)


# ── A stand-in Ollama for the Board run and Auto crew ────────────────────────

LOCAL_MODEL = "qwen3:4b-instruct"
API_DOC = ("# Orders API\n\n## GET /api/orders\n\nThe signed-in user's orders, newest first.\n\n"
           "## POST /api/orders\n\nCreates an order from the cart. Returns 400 if the cart is empty or a price "
           "is missing.\n")


def ollama_reply(body: dict) -> dict:
    messages = body.get("messages", [])
    if not body.get("tools"):  # Auto crew asking what kind of job a task is
        return {"content": json.dumps({"job": "coding", "size": "standard"})}
    done = sum(1 for m in messages if m.get("role") == "tool")
    call = [("read_file", {"path": "api/orders.py"}), ("write_file", {"path": "docs/api.md", "content": API_DOC})]
    if done < len(call):
        name, args = call[done]
        return {"content": None, "tool_calls": [{"id": f"call_{done}", "type": "function",
                                                 "function": {"name": name, "arguments": json.dumps(args)}}]}
    return {"content": "Wrote docs/api.md: GET and POST /api/orders, with the 400 for an empty cart."}


class StandInOllama:
    def __enter__(self) -> "StandInOllama":
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def send(self, data: dict, status: int = 200) -> None:
                body = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                if self.path == "/v1/models":
                    self.send({"object": "list", "data": [{"id": LOCAL_MODEL, "object": "model"}]})
                elif self.path == "/api/version":
                    self.send({"version": "0.12.3"})
                elif self.path == "/api/tags":
                    self.send({"models": [{"name": LOCAL_MODEL, "model": LOCAL_MODEL, "size": 2_500_000_000}]})
                else:
                    self.send({"error": "not found"}, 404)

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if not self.path.endswith("/chat/completions"):
                    self.send({"error": "not found"}, 404)
                    return
                time.sleep(2.0 if body.get("tools") else 0.5)
                message = {"role": "assistant", **ollama_reply(body)}
                self.send({"choices": [{"message": message, "finish_reason": "stop"}],
                           "usage": {"prompt_tokens": 1800, "completion_tokens": 140}})

        self.server = ThreadingHTTPServer(("127.0.0.1", 11434), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()


# ── The home folder: the screenshots' one, plus a cart bug and a task for the local model ──

def make_home(home: Path, url: str) -> None:
    from handoff.board import HUMAN, Board

    shots.make_home(home, url)
    shop = home / "code" / "shop"
    (shop / "cart.py").write_text(
        'def cart_total(prices):\n    """The cart\'s total, in dollars."""\n    total = 0.0\n'
        "    for price in prices:\n        total += price\n    return round(total, 2) if total > 1 else total\n",
        encoding="utf-8")
    (shop / "tests").mkdir(exist_ok=True)
    (shop / "tests" / "test_cart.py").write_text(
        "from cart import cart_total\n\n\ndef test_three_dimes():\n    assert cart_total([0.10, 0.10, 0.10]) == 0.30\n"
        "\n\ndef test_empty():\n    assert cart_total([]) == 0\n", encoding="utf-8")
    git = ["git", "-C", str(shop), "-c", "user.name=You", "-c", "user.email=you@example.com",
           "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "Cart"], check=True)
    Board.open(shop).create(HUMAN, "Write the orders API docs", "Describe GET and POST /api/orders in docs/api.md.",
                            ["docs/api.md covers both routes"], assignee="ollama", paths=["docs/api.md"])


# ── Recording ────────────────────────────────────────────────────────────────

CURSOR = """
(() => {
  const add = () => {
    if (document.getElementById('demo-cursor') || !document.body) return;
    const c = document.createElement('div');
    c.id = 'demo-cursor';
    const s = c.style;
    s.position = 'fixed'; s.left = '640px'; s.top = '420px'; s.width = '18px'; s.height = '18px';
    s.marginLeft = '-9px'; s.marginTop = '-9px'; s.borderRadius = '50%'; s.zIndex = '2147483647';
    s.pointerEvents = 'none'; s.background = 'rgba(255,255,255,0.85)'; s.boxShadow = '0 0 0 2px rgba(0,0,0,0.5)';
    s.transition = 'left 0.55s ease, top 0.55s ease, transform 0.15s ease';
    document.body.appendChild(c);
  };
  document.addEventListener('DOMContentLoaded', add); setInterval(add, 300);
})();
"""


class Clip:
    """One page being recorded, with a visible cursor that moves to what it clicks."""

    def __init__(self, page):
        self.page = page

    def wait(self, ms: int) -> None:
        self.page.wait_for_timeout(ms)

    def point(self, locator) -> None:
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        if box:
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            self.page.evaluate(f"(() => {{ const c = document.getElementById('demo-cursor'); if (c) {{ "
                               f"c.style.left = '{x}px'; c.style.top = '{y}px'; }} }})()")
            self.wait(650)

    def click(self, target) -> None:
        locator = self.page.locator(target).first if isinstance(target, str) else target
        self.point(locator)
        self.page.evaluate("(() => { const c = document.getElementById('demo-cursor'); if (c) { "
                           "c.style.transform = 'scale(0.7)'; setTimeout(() => c.style.transform = '', 160); } })()")
        locator.click()

    def type(self, target: str, text: str) -> None:
        self.click(target)
        self.page.locator(target).first.press_sequentially(text, delay=38)

    def until(self, check, timeout: float = 60) -> None:
        deadline = time.monotonic() + timeout
        while not check():
            if time.monotonic() > deadline:
                raise TimeoutError("the page didn't get there")
            self.wait(250)


class Screencast:
    """Chromium's own screencast of a page: a JPEG each time the page changes, with its time. Sharper than
    Playwright's video, and it needs no ffmpeg of Playwright's own."""

    def __init__(self, context, page, folder: Path):
        self.folder = folder
        self.frames: list[tuple[float, Path]] = []
        self.cdp = context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self.frame)
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": VIEWPORT["width"],
                                               "maxHeight": VIEWPORT["height"], "everyNthFrame": 1})

    def frame(self, event: dict) -> None:
        path = self.folder / f"{len(self.frames):05d}.jpg"
        path.write_bytes(base64.b64decode(event["data"]))
        self.frames.append((event["metadata"]["timestamp"], path))
        self.cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})

    def stop(self) -> Path:
        """Stop, and write the concat list ffmpeg reads: each frame shown until the next one came."""
        self.cdp.send("Page.stopScreencast")
        listing = self.folder / "frames.txt"
        lines = []
        for (t, path), nxt in zip(self.frames, self.frames[1:] + [(self.frames[-1][0] + 1.0, None)]):
            lines += [f"file '{path}'", f"duration {max(nxt[0] - t, 0.001):.3f}"]
        lines.append(f"file '{self.frames[-1][1]}'")
        listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return listing


def record_app(url: str, home: Path, names: list[str], out: Path, raw: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = shots.launch(p)
        for name in names:
            context = browser.new_context(viewport=VIEWPORT, color_scheme="dark")
            context.add_init_script(CURSOR)
            page = context.new_page()
            cast = Screencast(context, page, Path(tempfile.mkdtemp(prefix=f"{name}-", dir=raw)))
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url)
            page.wait_for_selector(".model", state="attached")
            clip = Clip(page)
            clip.wait(1200)
            SCENES[name](clip, home)
            clip.wait(2500)
            listing = cast.stop()
            context.close()
            finish(listing, out, name)
            if errors:
                print(f"  {name}: the page reported errors:", *errors, sep="\n    ", file=sys.stderr)
        browser.close()


def scene_ask(clip: Clip, home: Path) -> None:
    page = clip.page
    clip.click('.modes button[data-mode="review"]')
    clip.type("#question", shots.QUESTION)
    clip.wait(400)
    clip.click("#ask")
    done = page.locator(".thread:not([hidden]) .turn:last-child th.step.done")
    clip.until(lambda: done.count() >= 3)
    page.wait_for_selector("table.scores", timeout=60_000)
    clip.wait(1500)
    for selector in (".verdict", "table.scores"):
        page.evaluate(f"document.querySelector('{selector}').scrollIntoView({{block: 'start', behavior: 'smooth'}})")
        clip.wait(3500)


def scene_board(clip: Clip, home: Path) -> None:
    page = clip.page
    clip.click('.rail-item[data-view="board"]')
    clip.wait(1200)
    clip.click(".project-choice")
    page.wait_for_selector(".task-card", timeout=20_000)
    clip.wait(2000)
    clip.click(page.get_by_text("Write the orders API docs").first)
    clip.wait(1500)
    clip.click('[data-key^="action:approve"]')
    clip.wait(1500)
    clip.click('[data-key="needs-run-mode"]')
    page.select_option('[data-key="needs-run-mode"]', "one")
    clip.wait(1500)
    clip.click('[data-key="needs-submit"]')
    clip.until(lambda: page.get_by_text("What it used").count() > 0, timeout=90)
    clip.wait(2500)
    clip.click(page.get_by_role("button", name="Merge into main"))
    clip.wait(1500)
    confirm = page.get_by_role("button", name=re.compile("^Merge"))
    if confirm.count() > 1:  # the drawer asks once more before it merges
        clip.click(confirm.last)
    clip.until(lambda: page.get_by_text("Merged into the checked-out branch").count() > 0, timeout=30)
    clip.wait(3000)


def scene_agent(clip: Clip, home: Path) -> None:
    page = clip.page
    agent_calls["n"] = 0
    clip.click('.rail-item[data-view="agent"]')
    clip.wait(1200)
    clip.click("#agent-chip-folder")
    clip.type("#agent-folder-input", "~/code/shop")
    clip.click(page.get_by_role("button", name="Use this folder"))
    clip.wait(600)
    clip.type("#agent-box", AGENT_GOAL)
    clip.click("#agent-send")
    approvals = 0
    deadline = time.monotonic() + 90
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError(f"the Agent didn't finish its job ({approvals} actions approved)")
        clip.wait(400)
        button = page.locator("button:visible", has_text="Approve")
        if button.count():
            clip.wait(2200)  # time to read what it asks
            clip.click(button.first)
            approvals += 1
        if approvals >= 2 and page.get_by_text("Both tests pass").count():
            break
    clip.wait(2500)
    with contextlib.suppress(Exception):
        clip.click(page.get_by_text(re.compile(r"^Worked for")).first)
        clip.wait(1200)
        clip.click(page.locator(".agent-row-head", has_text="Ran").first)
        clip.wait(3500)


def scene_machines(clip: Clip, home: Path) -> None:
    page = clip.page
    clip.click('.rail-item[data-view="machines"]')
    clip.wait(2500)
    with contextlib.suppress(Exception):
        clip.click(page.locator(".machine", has_text="homelab").get_by_role("button", name="Edit"))
        clip.wait(3000)
        clip.click(page.get_by_role("button", name="Cancel"))
        clip.wait(800)
        clip.click(page.get_by_role("button", name="Run on machines"))
        clip.wait(3000)


SCENES = {"ask": scene_ask, "board": scene_board, "agent": scene_agent, "machines": scene_machines}


# ── The terminal clips: a real run of each command in a pty, played back in xterm.js ──

TERMINALS = {
    "handoff-terminal": ["handoff board", "handoff show T-8"],
    "ixel-terminal": ['ixel review "Is the regex ^(a+)+$ safe to run on text people type in?"'],
}
COLS, ROWS = 104, 34


def pty_run(command: str, cwd: Path, env: dict) -> list:
    """The command's output as [seconds, text] chunks, as a terminal of COLS x ROWS saw it."""
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(cwd)
        os.execvpe("sh", ["sh", "-c", f"stty cols {COLS} rows {ROWS}; exec {command}"], env)
    start, chunks = time.monotonic(), []
    while True:
        ready, _, _ = select.select([fd], [], [], 120)
        if not ready:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
            raise SystemExit(f"`{command}` printed nothing for two minutes, so it wasn't recorded")
        try:
            data = os.read(fd, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append([round(time.monotonic() - start, 3), data.decode("utf-8", "replace")])
    os.close(fd)
    code = os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1])
    if code != 0:
        tail = "".join(text for _, text in chunks)[-800:]
        raise SystemExit(f"`{command}` failed (exit {code}), so it wasn't recorded:\n{tail}")
    return chunks


TERMINAL_PAGE = """<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="xterm.css">
<style>html,body{margin:0;height:100%;background:#0d0e10}
.win{position:absolute;inset:28px 32px;border-radius:10px;background:#16181c;box-shadow:0 10px 40px #0008;
overflow:hidden;border:1px solid #2a2d33}.bar{height:30px;display:flex;align-items:center;gap:8px;padding:0 12px;
background:#1d2025}.bar i{width:12px;height:12px;border-radius:50%;background:#3a3d44;display:block}
#t{padding:12px 14px}</style><div class="win"><div class="bar"><i></i><i></i><i></i></div><div id="t"></div></div>
<script src="xterm.js"></script><script>
const runs = RUNS;
const term = new Terminal({cols: COLS, rows: ROWS, fontSize: 15, fontFamily: 'DejaVu Sans Mono, monospace',
  theme: {background: '#16181c'}, cursorBlink: true});
term.open(document.getElementById('t'));
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  await sleep(800);
  for (const run of runs) {
    term.write('\\x1b[32m~/code/shop\\x1b[0m $ ');
    await sleep(500);
    for (const ch of run.command) { term.write(ch); await sleep(35); }
    await sleep(400); term.write('\\r\\n');
    let last = 0;
    for (const [t, text] of run.chunks) { await sleep(Math.min((t - last) * 1000, 2500)); last = t; term.write(text); }
    await sleep(2500);
  }
  term.write('\\x1b[32m~/code/shop\\x1b[0m $ ');
  await sleep(1500);
  document.title = 'done';
})();
</script>"""


def record_terminals(names: list[str], home: Path, env: dict, xterm: Path, out: Path, raw: Path) -> None:
    from playwright.sync_api import sync_playwright

    page_dir = Path(tempfile.mkdtemp(prefix="ixel-terminal-"))
    shutil.copy(xterm / "node_modules/@xterm/xterm/lib/xterm.js", page_dir)
    shutil.copy(xterm / "node_modules/@xterm/xterm/css/xterm.css", page_dir)
    term_env = {**env, "TERM": "xterm-256color", "COLUMNS": str(COLS), "LINES": str(ROWS), "FORCE_COLOR": "1"}
    with sync_playwright() as p:
        browser = shots.launch(p)
        for name in names:
            runs = [{"command": c, "chunks": pty_run(c, home / "code" / "shop", term_env)} for c in TERMINALS[name]]
            html = (TERMINAL_PAGE.replace("RUNS", json.dumps(runs)).replace("COLS", str(COLS))
                    .replace("ROWS", str(ROWS)))
            (page_dir / f"{name}.html").write_text(html, encoding="utf-8")
            context = browser.new_context(viewport=VIEWPORT)
            page = context.new_page()
            cast = Screencast(context, page, Path(tempfile.mkdtemp(prefix=f"{name}-", dir=raw)))
            page.goto((page_dir / f"{name}.html").as_uri())
            page.wait_for_function("document.title === 'done'", timeout=240_000)
            listing = cast.stop()
            context.close()
            finish(listing, out, name)
        browser.close()


def finish(listing: Path, out: Path, name: str) -> None:
    """The recording as a small MP4 with the stand-in caption, and its last frame as the poster."""
    caption = ""
    if FONT:
        caption = (f",drawtext=fontfile={FONT}:text='{CAPTION}':fontsize=15:fontcolor=white@0.85:"
                   "box=1:boxcolor=black@0.55:boxborderw=7:x=w-tw-16:y=h-th-16")
    name = FILES.get(name, name)
    mp4 = out / f"{name}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-vf", f"fps=25,scale=1280:-2{caption}",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-an", str(mp4)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-1.5", "-i", str(mp4), "-frames:v", "1",
                    "-q:v", "4", str(out / f"{name}.jpg")], check=True)
    print(f"  {name}.mp4  {mp4.stat().st_size / 1e6:.1f} MB")


def main() -> int:
    global shots
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ixel-mat", required=True, type=Path, help="an Ixel MAT checkout (for its tests' stand-in server)")
    parser.add_argument("--home", required=True, type=Path, help="an empty or new home folder to run in; its path shows")
    parser.add_argument("--xterm", type=Path, help="a folder where @xterm/xterm is installed (for the terminal clips)")
    parser.add_argument("--out", type=Path, default=OUT, help=f"where the clips go (default: {OUT})")
    parser.add_argument("--only", nargs="*", choices=CLIPS, help=f"record only these clips (default: {' '.join(STAND_INS)})")
    args = parser.parse_args()

    sys.path.insert(0, str(args.ixel_mat.resolve() / "tests"))
    spec = importlib.util.spec_from_file_location("docs_screenshots", SITE / "scripts" / "docs-screenshots.py")
    shots = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shots)
    from fake_providers import ThreadedFakeProvider  # noqa: E402

    names = list(args.only or STAND_INS)
    terminals = [n for n in names if n in TERMINALS]
    if terminals and not args.xterm:
        print("The terminal clips need --xterm (a folder with @xterm/xterm installed).", file=sys.stderr)
        return 2
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", 11434)) == 0:
            print("Something is listening on 11434 (Ollama's port). Stop it and run this again.", file=sys.stderr)
            return 2
    home = args.home
    if home.exists() and any(home.iterdir()):
        print(f"{home} isn't empty. Give an empty or new folder with --home.", file=sys.stderr)
        return 2
    home.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)

    # The app finds only this Python's commands, a stand-in `ollama` and the system's own
    shim = Path(tempfile.mkdtemp(prefix="ixel-videos-bin-"))
    (shim / "ollama").write_text('#!/bin/sh\necho "ollama version is 0.12.3"\n', encoding="utf-8")
    (shim / "ollama").chmod(0o755)
    os.environ["PATH"] = os.pathsep.join([str(shim), str(Path(sys.executable).parent), "/usr/local/bin", "/usr/bin",
                                          "/bin"])
    raw = Path(tempfile.mkdtemp(prefix="ixel-videos-raw-"))
    with ThreadedFakeProvider(models) as fake, StandInOllama():
        fake.stream_delay = 0.05
        make_home(home, fake.openai_url)
        app = [n for n in names if n in SCENES]
        if app:
            with shots.run_app(home) as url:
                record_app(url, home, app, args.out, raw)
        if terminals:
            env = {**os.environ, "HOME": str(home), "IXEL_DEMO_KEY": "demo", "IXEL_NO_UPDATE_CHECK": "1"}
            for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY"):
                env.pop(key, None)
            record_terminals(terminals, home, env, args.xterm, args.out, raw)
    print(f"Done. The clips are in {args.out}. Watch each one before committing it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
