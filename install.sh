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
# (install.sh in the repo). Run it again any time to update.
#
# It needs git, bash and Python 3.10 or newer, and asks before installing any that is missing. On
# Linux that is the distribution's package manager, through sudo when you aren't root. On a Mac it
# is Apple's Command Line Tools (for git), and Homebrew, or else python.org's installer (for
# Python), which is opened only when its SHA-256 matches the one pinned in this file. Nothing is
# installed, and sudo never runs, without a yes. With no terminal to answer on, it prints what to
# run instead.
#
# With `curl | sh`, this script arrives on standard input, so everything is inside main(), which
# runs only once the whole file has been read, and nothing it starts reads standard input:
# questions are asked on the terminal (/dev/tty).

main() {
  # What to install: "" or all for everything (Ixel), mat for Ixel MAT alone, handoff for Handoff alone
  ONLY=""

  # The Python that a Mac without Homebrew is offered: python.org's universal2 installer, which
  # is opened only when its SHA-256 matches the one pinned here. To update, bump the version and the
  # hash together, to a 3.13.x on https://www.python.org/downloads/macos/. The maintainer fills
  # PYTHON_ORG_SHA256 from the file itself (shasum -a 256 python-3.13.X-macos11.pkg) or the release
  # page. While it is empty the installer never downloads or installs the package: it only prints
  # the URL.
  PYTHON_ORG_VERSION="3.13.16"
  PYTHON_ORG_URL="https://www.python.org/ftp/python/$PYTHON_ORG_VERSION/python-$PYTHON_ORG_VERSION-macos11.pkg"
  PYTHON_ORG_SHA256="30666509020b4da0dd8bc2e773255f34d76b7bb80b66960a928d5f6daa0192d7"

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

  # A Python new enough for the tools (each installer checks again and explains), and able to make
  # a virtual environment with pip: Debian and Ubuntu have venv and ensurepip in python3-venv
  have_python() {
    for candidate in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
      command -v "$candidate" >/dev/null 2>&1 || continue
      "$candidate" -c 'import sys, venv, ensurepip; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null && return 0
    done
    return 1
  }

  # Some Python is here, but none of them is 3.10 or newer: installing python3 again won't fix that
  python_too_old() {
    found=no
    for candidate in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
      command -v "$candidate" >/dev/null 2>&1 || continue
      "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null && return 1
      found=yes
    done
    [ "$found" = yes ]
  }

  # Stops, saying why no Python here will do (after have_python has failed)
  stop_python() {
    if python_too_old; then
      stop "$name needs Python 3.10 or newer, and this system's python3 is older than that. Many distributions have a python3.11 or python3.12 package: install one."
    fi
    stop "$name needs Python 3.10 or newer with venv and pip, and no Python here has both. On Debian and Ubuntu they come in the python3-venv package (python3.12-venv for python3.12, and so on)."
  }

  # The package manager of this Linux distribution, printed, from the ID in /etc/os-release and then
  # each word of its ID_LIKE (so Mint, Rocky or Manjaro count as the family they come from). Prints
  # nothing when the distribution isn't one we know, or its package manager isn't here.
  distro_manager() {
    [ -r /etc/os-release ] || return 0
    rest="$(
      # shellcheck source=/dev/null
      . /etc/os-release
      printf '%s %s' "${ID:-}" "${ID_LIKE:-}"
    )" || return 0
    while [ -n "$rest" ]; do
      word="${rest%% *}"
      case "$rest" in *" "*) rest="${rest#* }" ;; *) rest="" ;; esac
      case "$word" in
        debian | ubuntu) want=apt-get ;;
        fedora | rhel | centos)
          want=dnf
          command -v dnf >/dev/null 2>&1 || want=yum ;;
        arch) want=pacman ;;
        opensuse* | suse | sles) want=zypper ;;
        alpine) want=apk ;;
        *) continue ;;
      esac
      if command -v "$want" >/dev/null 2>&1; then
        printf '%s' "$want"
        return 0
      fi
    done
    return 0
  }

  # How to install a package on a Mac with Homebrew (nothing when there is no Homebrew). Linux has
  # installed git and bash, or stopped, before this is used.
  package_hint() {
    if command -v brew >/dev/null 2>&1; then printf 'brew install %s' "$1"; fi
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

  # On Linux, git, bash (Alpine has none to start with) and a Python 3.10 or newer with venv come
  # from the distribution's package manager. Only what is missing, and only after a yes: sudo is
  # never run without one, nor when there is no terminal to ask on.
  if [ "$system" = linux ]; then
    need_git=no need_bash=no need_python=no
    if ! command -v git >/dev/null 2>&1; then need_git=yes; fi
    if ! command -v bash >/dev/null 2>&1; then need_bash=yes; fi
    if ! have_python; then
      if python_too_old; then stop_python; fi
      need_python=yes
    fi

    if [ "$need_git" = yes ] || [ "$need_bash" = yes ] || [ "$need_python" = yes ]; then
      # What is missing, in words: "git", "git and Python 3.10 or newer (with venv)", "git, bash and ..."
      missing="" count=0
      if [ "$need_git" = yes ]; then missing="git"; count=$((count + 1)); fi
      if [ "$need_bash" = yes ]; then missing="${missing:+$missing, }bash"; count=$((count + 1)); fi
      if [ "$need_python" = yes ]; then missing="${missing:+$missing, }Python 3.10 or newer (with venv)"; count=$((count + 1)); fi
      missing="$(printf '%s' "$missing" | sed 's/, \([^,]*\)$/ and \1/')"
      if [ "$count" = 1 ]; then pronoun=it be="isn't"; else pronoun=them be="aren't"; fi

      manager="$(distro_manager)"
      if [ -z "$manager" ]; then
        stop "$missing $be installed, and the installer doesn't know this Linux distribution's package manager. Install $pronoun with your system's package manager."
      fi

      # The package names per manager: Debian and Ubuntu split venv off into python3-venv, and
      # Arch calls Python python
      packages=""
      if [ "$need_git" = yes ]; then packages="git"; fi
      if [ "$need_bash" = yes ]; then packages="${packages:+$packages }bash"; fi
      if [ "$need_python" = yes ]; then
        case "$manager" in
          apt-get) packages="${packages:+$packages }python3 python3-venv" ;;
          pacman) packages="${packages:+$packages }python" ;;
          *) packages="${packages:+$packages }python3" ;;
        esac
      fi

      # The one command that is shown, printed when the answer is no, and run when it is yes. It is
      # made of fixed words, so it is safe to run as written.
      if [ "$(id -u)" = 0 ]; then
        sudo_word="" no_sudo=no
      elif command -v sudo >/dev/null 2>&1; then
        sudo_word="sudo " no_sudo=no
      else
        sudo_word="" no_sudo=yes
      fi
      case "$manager" in
        apt-get) cmd="${sudo_word}apt-get update && ${sudo_word}apt-get install -y $packages" ;;
        pacman) cmd="${sudo_word}pacman -S --needed --noconfirm $packages" ;;
        apk) cmd="${sudo_word}apk add $packages" ;;
        *) cmd="${sudo_word}$manager install -y $packages" ;;
      esac

      if [ "$no_sudo" = yes ]; then
        stop "$missing $be installed, and sudo isn't here to install $pronoun. As root, run:  $cmd"
      fi
      if ask "$name needs $missing. Install $pronoun with:  $cmd"; then
        sh -c "$cmd" </dev/null || stop "couldn't install $missing with $manager (the lines above say why)."
      else
        stop "$missing $be installed. Install $pronoun with:  $cmd"
      fi
    fi

    # What was just installed is the distribution's python3, which can still be older than 3.10
    # (Debian 11, RHEL 8 and 9 and openSUSE Leap 15 are like that)
    if ! have_python; then stop_python; fi
  fi
  need git
  need bash

  # On a Mac, Python comes from Homebrew when it is there, and otherwise from python.org's
  # installer. (Linux has Python, or has stopped, above.)
  if [ "$system" = mac ] && ! have_python; then
    if command -v brew >/dev/null 2>&1; then
      if ask "$name needs Python 3.10 or newer. Install Python 3.13 with Homebrew now?"; then
        brew install python@3.13 </dev/null || stop "Homebrew couldn't install Python 3.13 (the lines above say why)."
      else
        stop "$name needs Python 3.10 or newer. Get it from https://www.python.org/downloads/ or with Homebrew:  brew install python@3.13"
      fi
    # No question while there is no pinned hash: a package that can't be checked is never opened
    elif [ -z "$PYTHON_ORG_SHA256" ] \
        || ! ask "$name needs Python 3.10 or newer. Download Python $PYTHON_ORG_VERSION from python.org and open its installer?"; then
      stop "$name needs Python 3.10 or newer. Download Python $PYTHON_ORG_VERSION from  $PYTHON_ORG_URL  and open it."
    else
      pkg_dir="$(mktemp -d "${TMPDIR:-/tmp}/ixel-python.XXXXXX")" || stop "couldn't make a temporary folder to download Python into."
      pkg="$pkg_dir/python-$PYTHON_ORG_VERSION-macos11.pkg"
      say "Downloading $PYTHON_ORG_URL"
      curl -fsSL --proto '=https' -o "$pkg" "$PYTHON_ORG_URL" </dev/null \
        || stop "couldn't download $PYTHON_ORG_URL (the lines above say why)."
      pkg_sum="$(shasum -a 256 "$pkg" | cut -d ' ' -f 1 | tr '[:upper:]' '[:lower:]')"
      want_sum="$(printf '%s' "$PYTHON_ORG_SHA256" | tr '[:upper:]' '[:lower:]')"
      if [ "$pkg_sum" != "$want_sum" ]; then
        rm -rf "$pkg_dir"
        stop "the download from $PYTHON_ORG_URL didn't match its SHA-256 (expected $want_sum, got ${pkg_sum:-nothing}), so it wasn't opened. Download Python from https://www.python.org/downloads/ instead."
      fi
      # Installer reads the file after open returns, so it stays in its temporary folder
      open "$pkg" </dev/null || stop "couldn't open $pkg. Open it yourself to install Python."
      stop "finish the Python installer (it opened in a window of its own)."
    fi
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
