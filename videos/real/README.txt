Real recordings of Ixel at work
===============================

These clips are real runs with real models on a Mac, not stand-ins. Each one
records only Ixel's own page in a browser (Chromium, 1280x800, dark), from a
throwaway copy of Ixel with its own home folder (/tmp/ixel-demo-home) that holds
no one's real history, projects or settings. The demo project (cart.py rounds
wrong; tests/test_cart.py has one failing test) is at /tmp/ixel-demo/shop for
the Board and a copy at ~/shop (/tmp/ixel-demo-home/shop) for the Agent.
Long waits are sped up, and nothing that happened is cut. H.264, no audio.

Versions: Ixel MAT v0.4.0 (ixel-mat fd46a26), Handoff v0.6.0 (Handoff 89c4a26),
Claude Code 2.1.306, Grok Build 1.0.52, Ollama 0.40.3.

ask.mp4 / ask.jpg (about 59 s)
  Ask in Review mode: "Is the regex ^(a+)+$ safe to run on user input?"
  Panel: Claude Code (Sonnet, on a subscription; moderator), Grok Build
  (Grok's own model, on a subscription) and Qwen3 4B Instruct (Ollama,
  on the Mac), all at their default effort. The three answer, grade each other
  anonymously (Claude and Grok score 1.00, Qwen 0.00 for calling the regex
  safe), and Claude writes the verdict: not safe (ReDoS). 7 calls, 69 s.

board.mp4 / board.jpg (about 41 s)
  The Board on /tmp/ixel-demo/shop with three tasks. T-1 "Write docs/api.md
  for /api/orders" runs on Ollama qwen3:4b-instruct with no thinking effort.
  The clip shows it running, the handback, the What it used table (4.1k read,
  405 written, $0) and Merge into main. The Board's Claude and Grok workers
  couldn't sign in from the throwaway setup, so this clip uses the local model
  (and shows no Auto switch, which appears only for Claude).

agent.mp4 / agent.jpg (about 61 s)
  The Agent (beta) on ~/shop with Grok Build (default effort): "Fix the cart
  total's rounding and run the tests". It reads the folder, asks to edit
  cart.py (int(total * 100) / 100 becomes round(total, 2)) and to run the
  tests. Five approvals in all: pytest wasn't installed in its sandbox and pip
  had no network, so it ran the tests with python3 instead. Both pass. 8 model
  calls, about $0.04 at API prices.
