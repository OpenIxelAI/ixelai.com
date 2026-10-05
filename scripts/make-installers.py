"""
Makes the one-tool installers from the ones at the site's root, so there is one source to change.

    ixel-mat/install.ps1, ixel-mat/install.sh    Ixel MAT alone
    handoff/install.ps1, handoff/install.sh      Handoff alone

Each copy is its root file with two lines changed: the one that picks what to install ($Only in
install.ps1, ONLY in install.sh) and the usage line in the header comment. The Ixel repository
(github.com/OpenIxelAI/Ixel) carries the two root files byte for byte; with a checkout of it beside
this one (../Ixel), or named with --ixel, those copies are written and checked too. Change the root
files, then run this:

    python scripts/make-installers.py            writes the copies
    python scripts/make-installers.py --check    writes nothing, and fails if a copy is out of date

It uses Python's standard library only, so it runs the same on Windows, macOS and Linux.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent

# Each root installer, with the line that picks what to install and its usage line. {only} is the
# choice, {page} the copy's folder on the site; both are empty in the root file.
INSTALLERS = [
    ("install.ps1", "    $Only = '{only}'", "#   irm https://ixelai.com/{page}install.ps1 | iex"),
    ("install.sh", '  ONLY="{only}"', "#   curl -fsSL https://ixelai.com/{page}install.sh | sh"),
]

# The site folder each copy goes in, and the choice it makes
COPIES = {"ixel-mat": "mat", "handoff": "handoff"}

# Where a checkout of the Ixel repository usually is: beside this one
IXEL_NAMES = ("Ixel", "ixel")


class Problem(Exception):
    """Something to fix in a root installer; nothing was written."""


def swap_line(lines: list[str], old: str, new: str, name: str) -> None:
    """Replace the one line that is exactly `old` (its line ending aside) with `new`, keeping the ending."""
    found = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == old]
    if len(found) != 1:
        raise Problem(f"{name} should have exactly one line that reads: {old.strip()}  (found {len(found)})")
    i = found[0]
    lines[i] = new + lines[i][len(old):]


def make_copy(name: str, text: str, choose: str, usage: str, folder: str, only: str) -> str:
    lines = text.splitlines(keepends=True)
    for template in (choose, usage):
        swap_line(lines, template.format(only="", page=""), template.format(only=only, page=folder + "/"), name)
    return "".join(lines)


def read_root(name: str) -> str:
    data = (SITE / name).read_bytes()
    try:
        # PowerShell scripts stay ASCII: Windows PowerShell reads a file without a BOM in the ANSI code page
        return data.decode("ascii" if name.endswith(".ps1") else "utf-8")
    except UnicodeDecodeError as exc:
        raise Problem(f"{name} has a character that isn't ASCII, at byte {exc.start}. Keep it ASCII.") from None


def find_ixel(given: str | None) -> Path | None:
    """The Ixel checkout: the one named with --ixel, else one beside this repository, else None."""
    if given:
        ixel = Path(given).expanduser().resolve()
        if not all((ixel / name).is_file() for name, _, _ in INSTALLERS):
            raise Problem(f"{ixel} isn't a checkout of the Ixel repository: it has no install.ps1 and install.sh.")
        return ixel
    for name in IXEL_NAMES:
        ixel = SITE.parent / name
        if all((ixel / file).is_file() for file, _, _ in INSTALLERS):
            return ixel
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Make ixel-mat/ and handoff/ installers from the root ones.")
    parser.add_argument("--check", action="store_true", help="write nothing; fail if a copy is out of date")
    parser.add_argument("--ixel", metavar="PATH",
                        help="a checkout of the Ixel repository, whose two installers are copies of the root ones "
                             "(default: ../Ixel, when it's there)")
    args = parser.parse_args(argv)

    try:
        ixel = find_ixel(args.ixel)
        wanted = {}
        for name, choose, usage in INSTALLERS:
            text = read_root(name)
            for folder, only in COPIES.items():
                copy = make_copy(name, text, choose, usage, folder, only)
                wanted[SITE / folder / name] = (name, copy.encode("ascii" if name.endswith(".ps1") else "utf-8"))
            if ixel:
                wanted[ixel / name] = (name, (SITE / name).read_bytes())
    except Problem as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    def shown(target: Path) -> str:
        return target.relative_to(SITE).as_posix() if target.is_relative_to(SITE) else str(target)

    stale = []
    for target, (source, data) in wanted.items():
        if target.is_file() and target.read_bytes() == data:
            continue
        if args.check:
            stale.append(shown(target))
            continue
        target.write_bytes(data)
        shutil.copymode(SITE / source, target)  # install.sh's copies stay executable
        print(f"wrote {shown(target)}" + ("  (commit it in the Ixel repository too)" if ixel and target.parent == ixel else ""))

    if stale:
        print("Out of date: " + ", ".join(stale), file=sys.stderr)
        print("Run:  python scripts/make-installers.py" + (f" --ixel {args.ixel}" if args.ixel else ""), file=sys.stderr)
        return 1
    if args.check:
        print(f"All {len(wanted)} copies match the root installers.")
    if not ixel:
        print("The Ixel repository's copies weren't checked: there's no ../Ixel. Name a checkout of it with --ixel PATH.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
