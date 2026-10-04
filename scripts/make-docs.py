#!/usr/bin/env python3
"""Puts the shared parts into every docs page: the site's header, the docs menu, "On this page", the
previous and next page links, and the footer.

    python scripts/make-docs.py           # update the pages
    python scripts/make-docs.py --check   # change nothing; fail if a page is out of date

Each page in docs/ is a whole HTML file you edit by hand. Only what's between its
<!-- docs:NAME --> and <!-- /docs:NAME --> markers is made here, so change the menu in PAGES below, not
in the pages. "On this page" lists the page's <h2 id="..."> headings, in order. After adding a page
or a heading, run this and commit the pages with it.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent

# The menu: (group, [(folder under docs/, title in the menu)]). The order is the reading order, which the
# previous and next links follow.
PAGES = [
    ("Get started", [
        ("", "Overview"),
        ("install", "Install"),
        ("setup", "Set up your models"),
    ]),
    ("Use Ixel", [
        ("app", "The Ixel app"),
        ("terminal", "In the terminal"),
        ("handoff", "Handoff: agents as a team"),
    ]),
    ("Models", [
        ("models", "Which model for each job"),
        ("local-models", "Local models"),
    ]),
    ("Your data", [
        ("privacy", "Privacy"),
    ]),
]

MARK = re.compile(r"(<!-- docs:(\w+) -->)(.*?)(<!-- /docs:\2 -->)", re.DOTALL)
H2 = re.compile(r'<h2 id="([\w-]+)">(.*?)</h2>', re.DOTALL)
TAG = re.compile(r"<[^>]+>")


def order() -> list[tuple[str, str]]:
    return [page for _, pages in PAGES for page in pages]


def root(folder: str) -> str:
    """The way from a page back up to the site's root."""
    return "../" if not folder else "../../"


def link(here: str, there: str) -> str:
    """A link from the page in docs/<here>/ to docs/<there>/."""
    up = "" if not here else "../"
    return up + (there + "/" if there else "") or "./"


def header(folder: str) -> str:
    r = root(folder)
    return f"""
  <header class="wrap top">
    <a class="brand" href="{r}" aria-label="IxelAI home">
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <circle cx="29" cy="36" r="19" fill="#c8d8e8"/>
        <circle cx="36" cy="32" r="17" fill="#070b14"/>
        <polygon points="47,7 49.2,13.6 56,13.6 50.5,17.7 52.6,24.3 47,20.2 41.4,24.3 43.5,17.7 38,13.6 44.8,13.6" fill="#d4af37"/>
      </svg>
      <span class="wordmark">Ixe<span>l</span></span>
    </a>
    <nav class="nav" aria-label="Main">
      <a href="{r}ixel-mat/">Ixel MAT</a>
      <a href="{r}handoff/">Handoff</a>
      <a href="{r}machines/">Machines</a>
      <a href="{r}docs/" aria-current="page">Docs</a>
      <a href="{r}about/">About</a>
      <a href="https://github.com/OpenIxelAI">GitHub</a>
    </nav>
  </header>
  """


def menu(folder: str) -> str:
    parts = ['\n      <details open>\n        <summary>Docs menu</summary>\n        <div class="docs-nav-body">']
    for group, pages in PAGES:
        parts.append(f"\n          <h2>{html.escape(group)}</h2>\n          <ul>")
        for there, title in pages:
            current = ' aria-current="page"' if there == folder else ""
            parts.append(f'\n            <li><a href="{link(folder, there)}"{current}>{html.escape(title)}</a></li>')
        parts.append("\n          </ul>")
    parts.append("\n        </div>\n      </details>\n      ")
    return "".join(parts)


def toc(text: str) -> str:
    headings = H2.findall(text)
    if not headings:
        return "\n      "
    items = "".join(f'\n        <li><a href="#{anchor}">{TAG.sub("", title).strip()}</a></li>'
                    for anchor, title in headings)
    return f'\n      <h2>On this page</h2>\n      <ul>{items}\n      </ul>\n      '


def pager(folder: str) -> str:
    pages = order()
    at = [p[0] for p in pages].index(folder)
    parts = []
    if at > 0:
        there, title = pages[at - 1]
        parts.append(f'\n        <a class="prev" href="{link(folder, there)}"><span>Previous</span>{html.escape(title)}</a>')
    if at < len(pages) - 1:
        there, title = pages[at + 1]
        parts.append(f'\n        <a class="next" href="{link(folder, there)}"><span>Next</span>{html.escape(title)}</a>')
    return "".join(parts) + "\n        "


def footer(folder: str) -> str:
    r = root(folder)
    return f"""
  <footer>
    <div class="wrap foot">
      <div class="sign">
        <span class="wordmark">Ixel</span>
        <span class="tag-line">To shine</span>
      </div>
      <span>© <span id="year">2026</span> IxelAI · All three tools are MIT-licensed</span>
      <nav class="foot-nav" aria-label="Footer">
        <a href="{r}docs/">Docs</a>
        <a href="{r}docs/privacy/">Privacy</a>
        <a href="{r}about/#contact">Contact</a>
        <a href="https://github.com/OpenIxelAI">GitHub</a>
      </nav>
    </div>
  </footer>
  """


def render(folder: str, text: str) -> str:
    makers = {"header": header, "nav": menu, "pager": pager, "footer": footer}
    found = set()

    def fill(match: re.Match) -> str:
        name = match.group(2)
        found.add(name)
        body = toc(text) if name == "toc" else makers[name](folder) if name in makers else match.group(3)
        return match.group(1) + body + match.group(4)

    out = MARK.sub(fill, text)
    missing = {"header", "nav", "toc", "pager", "footer"} - found
    if missing:
        raise SystemExit(f"docs/{folder}: no markers for {', '.join(sorted(missing))}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="change nothing; fail if a page is out of date")
    args = parser.parse_args()
    stale = []
    for folder, _ in order():
        path = SITE / "docs" / folder / "index.html"
        if not path.exists():
            raise SystemExit(f"{path.relative_to(SITE)} is in the menu but doesn't exist")
        text = path.read_text(encoding="utf-8")
        new = render(folder, text)
        for anchor in re.findall(r'href="#([\w-]+)"', new):
            if f'id="{anchor}"' not in new:
                raise SystemExit(f"{path.relative_to(SITE)}: #{anchor} points at nothing on the page")
        if new != text:
            stale.append(path.relative_to(SITE))
            if not args.check:
                path.write_text(new, encoding="utf-8")
    if args.check and stale:
        print("Out of date (run python scripts/make-docs.py):", *stale, sep="\n  ")
        return 1
    print("Up to date." if not stale else f"Updated {len(stale)} page(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
