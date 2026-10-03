#!/bin/sh
# Installs Ixel MAT and Handoff on a Mac or Linux, and adds Ixel to your apps
# (Applications on a Mac, the app menu on Linux).
#
#   curl -fsSL https://ixelai.com/install.sh | sh
#
# For each tool it gets the source with git, into the folder that tool's own installer uses
# (~/.local/share/ixel-mat/repo and ~/.local/share/handoff/repo), then runs that installer
# (install.sh in the repo). Nothing here needs sudo. Run it again any time to update both.
#
# With `curl | sh`, this script arrives on standard input, so everything is inside main(), which
# runs only once the whole file has been read, and nothing it starts reads standard input:
# questions are asked on the terminal (/dev/tty).

main() {
  set -eu

  say() { printf '%s\n' "$*"; }
  stop() {
    printf '\nInstall stopped: %s\n' "$*" >&2
    printf 'Once that is fixed, run the same command again.\n' >&2
    exit 1
  }
  # ask "question" succeeds on yes (the default); no terminal to ask on counts as no
  ask() {
    (: </dev/tty) 2>/dev/null || return 1
    printf '%s [Y/n] ' "$1" >/dev/tty
    read -r answer </dev/tty || return 1
    case "$answer" in [nN]*) return 1 ;; esac
    return 0
  }

  # A Python new enough for both tools (each installer checks again and explains)
  have_python() {
    for candidate in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
      command -v "$candidate" >/dev/null 2>&1 || continue
      "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null && return 0
    done
    return 1
  }

  get_source() {  # get_source <url> <branch> <repo folder>
    if [ -d "$3/.git" ]; then
      git -C "$3" fetch --quiet origin "$2"
      git -C "$3" checkout --quiet "$2"
      git -C "$3" pull --quiet --ff-only origin "$2"
    else
      rm -rf "$3"
      mkdir -p "$(dirname "$3")"
      git clone --quiet --branch "$2" "$1" "$3"
    fi
  }

  install_tool() {  # install_tool <name> <url> <branch> <install root>
    repo="$4/repo"
    say ""
    say "== $1"
    say "Getting the source into $repo"
    get_source "$2" "$3" "$repo" || stop "couldn't get $1's source with git (the lines above say why)."
    bash "$repo/install.sh" </dev/null || stop "$1's installer failed (the lines above say why)."
  }

  case "$(uname -s)" in
    Darwin) system=mac ;;
    Linux) system=linux ;;
    *) say "This installer is for macOS and Linux. On Windows, run this in PowerShell:"
       say "  irm https://ixelai.com/install.ps1 | iex"
       exit 1 ;;
  esac

  say "Installing Ixel MAT and Handoff."

  # On a Mac, git and the compiler that builds Ixel's app come with Apple's Command Line Tools.
  # Without them, /usr/bin/git only offers to install them.
  if [ "$system" = mac ] && ! xcode-select -p >/dev/null 2>&1; then
    say ""
    say "Apple's Command Line Tools are needed: they bring git, and build Ixel's app."
    if ask "Open Apple's installer for them now?"; then
      xcode-select --install >/dev/null 2>&1 || true
      stop "finish Apple's Command Line Tools installer (it opened in a window of its own)."
    fi
    stop "install Apple's Command Line Tools with:  xcode-select --install"
  fi
  command -v git >/dev/null 2>&1 || stop "git isn't installed. Install it with your package manager (for example:  sudo apt install git)."
  command -v bash >/dev/null 2>&1 || stop "bash isn't installed. Install it with your package manager."

  if ! have_python; then
    if [ "$system" = mac ] && command -v brew >/dev/null 2>&1 \
        && ask "Ixel needs Python 3.10 or newer. Install Python 3.13 with Homebrew now?"; then
      brew install python@3.13 </dev/null || stop "Homebrew couldn't install Python 3.13 (the lines above say why)."
    elif [ "$system" = mac ]; then
      stop "Ixel needs Python 3.10 or newer. Get it from https://www.python.org/downloads/ or with Homebrew:  brew install python@3.13"
    fi
    # On Linux, the installer that runs next names the package for your distribution
  fi

  # The same settings each tool's own installer reads, so both agree on where things go
  install_tool "Ixel MAT" "${IXEL_REPO_URL:-https://github.com/OpenIxelAI/ixel-mat.git}" \
    "${IXEL_BRANCH:-main}" "${IXEL_INSTALL_ROOT:-$HOME/.local/share/ixel-mat}"
  install_tool "Handoff" "${HANDOFF_REPO_URL:-https://github.com/OpenIxelAI/Handoff-by-IxelAI.git}" \
    "${HANDOFF_BRANCH:-main}" "${HANDOFF_INSTALL_ROOT:-$HOME/.local/share/handoff}"

  say ""
  say "Ixel MAT and Handoff are installed."
  if [ "$system" = mac ] && [ -d "$HOME/Applications/Ixel.app" ]; then
    say "Open Ixel from Applications (in your home folder), or with Spotlight."
  elif [ "$system" = linux ] && [ -f "${XDG_DATA_HOME:-$HOME/.local/share}/applications/ixel.desktop" ]; then
    say "Open Ixel from your app menu."
  fi
  say "Open a new terminal window first, so it finds the new commands. Then:"
  say "  ixel setup               add your models and keys"
  say "  handoff setup --write    in a project folder: connect Claude Code, Codex and Claude Desktop"
  say "To update both later, run the same install command again."
}

main "$@"
