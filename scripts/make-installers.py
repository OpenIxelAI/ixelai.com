"""
Makes the one-tool installers from the ones at the site's root, so there is one source to change.

    ixel-mat/install.ps1, ixel-mat/install.sh    Ixel MAT alone
    handoff/install.ps1, handoff/install.sh      Handoff alone

Each copy is its root file with two lines changed: the one that picks what to install ($Only in
install.ps1, ONLY in install.sh) and the usage line in the header comment. The Ixel repository
(github.com/OpenIxelAI/Ixel) carries the two root files byte for byte; with a checkout of it beside
this one (../Ixel or ../ixel), or named with --ixel, those copies are written and checked too.
Change the root files, then run this:

    python scripts/make-installers.py            writes the copies
    python scripts/make-installers.py --check    writes nothing, and fails if a copy is out of date

It uses Python's standard library only, so it runs the same on Windows, macOS and Linux.
"""
from __future__ import annotations

import argparse
import os
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


def inside_site(folder: Path) -> bool:
    """Whether `folder` is this repository or a folder in it (samefile, so case and symlinks don't fool it)."""
    return any(p.exists() and p.samefile(SITE) for p in (folder, *folder.parents))


def is_ixel(folder: Path) -> bool:
    """Whether `folder` is a checkout of the Ixel repository: outside this one, holding at least one of the two
    installers, and each one it holds is the all-in-one installer (its usage line names no site folder)."""
    if not folder.is_dir() or inside_site(folder):
        return False
    present = [(folder / name, usage.format(page="")) for name, _, usage in INSTALLERS if (folder / name).is_file()]
    return bool(present) and all(
        line in path.read_text(encoding="utf-8", errors="replace").splitlines() for path, line in present)


def find_ixel(given: str | None) -> tuple[Path | None, Path | None]:
    """The Ixel checkout (the one named with --ixel, else one beside this repository), and a folder beside
    this one that has an Ixel name but isn't a checkout of it, to say so."""
    if given:
        ixel = Path(given).expanduser().resolve()
        if not is_ixel(ixel):
            raise Problem(f"{ixel} isn't a checkout of the Ixel repository: that needs the all-in-one install.ps1 "
                          "or install.sh (whose usage line names no folder of the site), outside this repository.")
        return ixel, None
    odd = None
    for name in IXEL_NAMES:
        folder = SITE.parent / name
        if is_ixel(folder):
            return folder.resolve(), None
        if folder.is_dir() and odd is None:
            odd = folder
    return None, odd


def out_of_date(target: Path, source: Path, data: bytes) -> bool:
    """Whether `target` differs from what it should hold, its executable bit included (not on Windows)."""
    if not target.is_file() or target.read_bytes() != data:
        return True
    return os.name != "nt" and (target.stat().st_mode & 0o111) != (source.stat().st_mode & 0o111)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Make ixel-mat/ and handoff/ installers from the root ones.")
    parser.add_argument("--check", action="store_true", help="write nothing; fail if a copy is out of date")
    parser.add_argument("--ixel", metavar="PATH",
                        help="a checkout of the Ixel repository, whose two installers are copies of the root ones "
                             "(default: ../Ixel or ../ixel, when it's there)")
    args = parser.parse_args(argv)

    try:
        ixel, odd = find_ixel(args.ixel)
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
        return target.relative_to(SITE).as_posix() if SITE in target.parents else str(target)

    stale = []
    for target, (source, data) in wanted.items():
        if not out_of_date(target, SITE / source, data):
            continue
        if args.check:
            stale.append(shown(target))
            continue
        target.write_bytes(data)
        shutil.copymode(SITE / source, target)  # install.sh's copies stay executable
        print(f"wrote {shown(target)}" + ("  (commit it in the Ixel repository too)" if ixel and target.parent == ixel else ""))

    if stale:
        print("Out of date: " + ", ".join(stale), file=sys.stderr)
        print("Run:  python scripts/make-installers.py" + (f' --ixel "{ixel}"' if args.ixel else ""), file=sys.stderr)
        return 1
    if args.check:
        print(f"All {len(wanted)} copies match the root installers.")
    if odd:
        print(f"The Ixel repository's copies weren't written or checked: {odd} isn't a checkout of it (its installers "
              "aren't the all-in-one ones). Name the right one with --ixel PATH.")
    elif not ixel:
        print("The Ixel repository's copies weren't written or checked: there's no checkout of it beside this one "
              "(../Ixel or ../ixel). Name one with --ixel PATH.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
