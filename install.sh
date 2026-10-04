#!/bin/sh
# Installs Ixel, or one of its tools alone, on a Mac or Linux. ONLY below, or the first argument,
# picks which: all (or an empty ONLY) for everything (Ixel MAT, Handoff, and the Ixel app, in
# Applications on a Mac or the app menu on Linux), mat for Ixel MAT and its app, or handoff for
# Handoff, as in  curl -fsSL https://ixelai.com/install.sh | sh -s -- handoff
#
#   curl -fsSL https://ixelai.com/install.sh | sh
#
# The site has three copies of this file, made from the one at its root by scripts/make-installers.py:
# install.sh (everything), ixel-mat/install.sh and handoff/install.sh. Only ONLY and the line above
# differ, so change the root one and run that script.
#
# For each tool it gets the source with git, into the folder that tool's own installer uses
# (~/.local/share/ixel-mat/repo and ~/.local/share/handoff/repo), then runs that installer
# (install.sh in the repo). Nothing here needs sudo. Run it again any time to update.
#
# With `curl | sh`, this script arrives on standard input, so everything is inside main(), which
# runs only once the whole file has been read, and nothing it starts reads standard input:
# questions are asked on the terminal (/dev/tty).

main() {
  # What to install: "" or all for everything (Ixel), mat for Ixel MAT alone, handoff for Handoff alone
  ONLY=""

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

  # A Python new enough for the tools (each installer checks again and explains)
  have_python() {
    for candidate in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
      command -v "$candidate" >/dev/null 2>&1 || continue
      "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null && return 0
    done
    return 1
  }

  # How to install a package with this system's package manager (nothing when it's none we know)
  package_hint() {
    if command -v apt-get >/dev/null 2>&1; then printf 'sudo apt install %s' "$1"
    elif command -v dnf >/dev/null 2>&1; then printf 'sudo dnf install %s' "$1"
    elif command -v yum >/dev/null 2>&1; then printf 'sudo yum install %s' "$1"
    elif command -v pacman >/dev/null 2>&1; then printf 'sudo pacman -S %s' "$1"
    elif command -v zypper >/dev/null 2>&1; then printf 'sudo zypper install %s' "$1"
    elif command -v apk >/dev/null 2>&1; then printf 'sudo apk add %s' "$1"
    elif command -v brew >/dev/null 2>&1; then printf 'brew install %s' "$1"
    fi
  }
  need() {  # need <program>: stop, saying how to get it, when it's missing
    command -v "$1" >/dev/null 2>&1 && return 0
    how="$(package_hint "$1")"
    if [ -n "$how" ]; then
      stop "$1 isn't installed. Install it with:  $how"
    fi
    stop "$1 isn't installed. Install it with your system's package manager."
  }

  # A git URL without a trailing slash or .git, so two spellings of one repository match
  plain_url() { printf '%s' "$1" | sed -e 's#/*$##' -e 's#[.]git$##' -e 's#/*$##'; }

  # Work of yours in a tool's folder that cloning it again would delete: changed or new files,
  # commits that aren't on its remote, or a stash
  own_work() {
    [ -n "$(git -C "$1" status --porcelain 2>/dev/null)" ] && return 0
    [ -n "$(git -C "$1" log --oneline --branches --not --remotes 2>/dev/null)" ] && return 0
    [ -n "$(git -C "$1" stash list 2>/dev/null)" ] && return 0
    return 1
  }

  get_source() {  # get_source <url> <branch> <repo folder>
    origin="$(git -C "$3" remote get-url origin 2>/dev/null || true)"
    if [ -d "$3/.git" ] && [ "$(plain_url "$origin")" = "$(plain_url "$1")" ]; then
      git -C "$3" fetch --quiet origin "$2"
      git -C "$3" checkout --quiet "$2"
      git -C "$3" pull --quiet --ff-only origin "$2"
    else
      # A folder that came from another URL (a fork, say) is cloned again, so what's installed is
      # what was asked for. Not over work of yours, though: that's for you to move first.
      if [ -d "$3/.git" ] && own_work "$3"; then
        stop "$3 has changes of yours, and it came from ${origin:-another place}, not $1. Move what you want to keep out of it, then delete that folder."
      fi
      rm -rf "$3"
      mkdir -p "$(dirname "$3")"
      git clone --quiet --branch "$2" "$1" "$3"
    fi
  }

  # The tools' own installers add their command folder to PATH in bash's, zsh's or fish's startup
  # file. With another shell (or with that turned off), say which line to add, and where.
  path_note() {
    shell_name="$(basename "${SHELL:-sh}")"
    case "$shell_name" in bash | zsh | fish) known=yes ;; *) known=no ;; esac
    mat_bin="${IXEL_BIN_DIR:-$HOME/.local/bin}"
    handoff_bin="${HANDOFF_BIN_DIR:-$HOME/.local/bin}"
    new_window=no add_mat=no add_handoff=no
    if [ "$with_mat" = yes ] && ! on_path "$mat_bin"; then
      if [ "$known" = yes ] && [ "${IXEL_SKIP_PATH_UPDATE:-0}" != 1 ]; then new_window=yes; else add_mat=yes; fi
    fi
    if [ "$with_handoff" = yes ] && ! on_path "$handoff_bin"; then
      if [ "$known" = yes ] && [ "${HANDOFF_SKIP_PATH_UPDATE:-0}" != 1 ]; then new_window=yes; else add_handoff=yes; fi
    fi
    if [ "$add_mat" = yes ] && [ "$add_handoff" = yes ] && [ "$mat_bin" = "$handoff_bin" ]; then
      add_handoff=no  # one folder, one line
    fi
    if [ "$add_mat" = no ] && [ "$add_handoff" = no ]; then
      if [ "$new_window" = yes ]; then
        say "Open a new terminal window first, so it finds the new commands. Then:"
      else
        say "Then:"
      fi
      return 0
    fi
    case "$shell_name" in
      csh | tcsh)
        say "Your shell ($shell_name) won't find the new commands until you add this to ~/.cshrc and open a new"
        say "terminal window:"
        if [ "$add_mat" = yes ]; then say "  setenv PATH \"$mat_bin:\$PATH\""; fi
        if [ "$add_handoff" = yes ]; then say "  setenv PATH \"$handoff_bin:\$PATH\""; fi ;;
      *)
        say "Your shell ($shell_name) won't find the new commands until you add this to ~/.profile (or your"
        say "shell's own startup file), then log out and back in:"
        if [ "$add_mat" = yes ]; then say "  export PATH=\"$mat_bin:\$PATH\""; fi
        if [ "$add_handoff" = yes ]; then say "  export PATH=\"$handoff_bin:\$PATH\""; fi ;;
    esac
    say "Then:"
  }
  on_path() { case ":$PATH:" in *":$1:"*) return 0 ;; esac; return 1; }

  install_tool() {  # install_tool <name> <url> <branch> <install root>
    repo="$4/repo"
    say ""
    say "== $1"
    say "Getting the source into $repo"
    get_source "$2" "$3" "$repo" || stop "couldn't get $1's source with git (the lines above say why)."
    bash "$repo/install.sh" </dev/null || stop "$1's installer failed (the lines above say why)."
  }

  # An argument picks instead of ONLY. What's being installed, the same with what's in it, the folder
  # of this file's copy on the site, and which tools.
  choice="$(printf '%s' "${*:-$ONLY}" | tr '[:upper:]' '[:lower:]')"
  case "$choice" in
    "" | all)
      name="Ixel" parts="Ixel: Ixel MAT and Handoff" page="" with_mat=yes with_handoff=yes ;;
    mat | ixel-mat)
      name="Ixel MAT" parts="Ixel MAT" page="ixel-mat/" with_mat=yes with_handoff=no ;;
    handoff)
      name="Handoff" parts="Handoff" page="handoff/" with_mat=no with_handoff=yes ;;
    *)
      say "The installer can't install \"$choice\". Pick one of these:" >&2
      say "  all        everything: Ixel MAT, Handoff and the Ixel app" >&2
      say "  mat        Ixel MAT and the Ixel app" >&2
      say "  handoff    Handoff" >&2
      say "For example:  curl -fsSL https://ixelai.com/install.sh | sh -s -- handoff" >&2
      exit 1 ;;
  esac

  case "$(uname -s)" in
    Darwin) system=mac ;;
    Linux) system=linux ;;
    *) say "This installer is for macOS and Linux. On Windows, run this in PowerShell:"
       say "  irm https://ixelai.com/${page}install.ps1 | iex"
       exit 1 ;;
  esac

  say "Installing $parts."

  # On a Mac, git and the compiler that builds Ixel's app come with Apple's Command Line Tools.
  # Without them, /usr/bin/git only offers to install them.
  if [ "$system" = mac ] && ! xcode-select -p >/dev/null 2>&1; then
    say ""
    if [ "$with_mat" = yes ]; then
      say "Apple's Command Line Tools are needed: they bring git, and build Ixel's app."
    else
      say "Apple's Command Line Tools are needed: they bring git."
    fi
    if ask "Open Apple's installer for them now?"; then
      xcode-select --install >/dev/null 2>&1 || true
      stop "finish Apple's Command Line Tools installer (it opened in a window of its own)."
    fi
    stop "install Apple's Command Line Tools with:  xcode-select --install"
  fi
  need git
  need bash

  if ! have_python; then
    if [ "$system" = mac ] && command -v brew >/dev/null 2>&1 \
        && ask "$name needs Python 3.10 or newer. Install Python 3.13 with Homebrew now?"; then
      brew install python@3.13 </dev/null || stop "Homebrew couldn't install Python 3.13 (the lines above say why)."
    elif [ "$system" = mac ]; then
      stop "$name needs Python 3.10 or newer. Get it from https://www.python.org/downloads/ or with Homebrew:  brew install python@3.13"
    fi
    # On Linux, the installer that runs next names the package for your distribution
  fi

  # The same settings each tool's own installer reads, so both agree on where things go
  if [ "$with_mat" = yes ]; then
    install_tool "Ixel MAT" "${IXEL_REPO_URL:-https://github.com/OpenIxelAI/ixel-mat.git}" \
      "${IXEL_BRANCH:-main}" "${IXEL_INSTALL_ROOT:-$HOME/.local/share/ixel-mat}"
  fi
  if [ "$with_handoff" = yes ]; then
    install_tool "Handoff" "${HANDOFF_REPO_URL:-https://github.com/OpenIxelAI/Handoff-by-IxelAI.git}" \
      "${HANDOFF_BRANCH:-main}" "${HANDOFF_INSTALL_ROOT:-$HOME/.local/share/handoff}"
  fi

  say ""
  say "$name is installed."
  if [ "$with_mat" = yes ]; then
    if [ "$system" = mac ] && [ -d "$HOME/Applications/Ixel.app" ]; then
      say "Open Ixel from Applications (in your home folder), or with Spotlight."
    elif [ "$system" = linux ] && [ -f "${XDG_DATA_HOME:-$HOME/.local/share}/applications/ixel.desktop" ]; then
      say "Open Ixel from your app menu."
    fi
  fi
  path_note
  if [ "$with_mat" = yes ]; then
    say "  ixel setup               add your models and keys"
  fi
  if [ "$with_handoff" = yes ]; then
    say "  handoff setup --write    in a project folder: connect Claude Code, Codex and Claude Desktop"
  fi
  say "To update $name later, run the same install command again."
}

main "$@"
