# Working on the site

To look at it, open `index.html` in a browser. Links between pages end in a folder (`ixel-mat/`), which GitHub
Pages serves but a double-clicked file doesn't, so to click around run `python -m http.server` in this folder
and open `http://localhost:8000`. To change it, edit it here and push to `main`.

- **Every page has the same header and footer.** When you change one, change it on every page. The docs pages
  get theirs from `scripts/make-docs.py`.
- **Nothing from anyone else.** Fonts are in `fonts/` (SIL Open Font License, licenses alongside), and every
  page has a Content Security Policy that allows only this site's own files. Don't add analytics, embeds, CDN
  links or inline scripts; see [SECURITY.md](SECURITY.md).
- **Keep `.nojekyll`.** It's empty, and it stops GitHub Pages from running Jekyll, which would turn the
  Markdown files here into themed pages that load a script from a CDN.
- **Nothing private.** This repository is public: no keys, real IP addresses, hostnames, usernames or home
  folders, in files or in pictures. [videos/README.md](videos/README.md) says how to record a demo safely.

## The installers

| Installs | Windows (PowerShell) | macOS and Linux |
|---|---|---|
| Ixel: Ixel MAT, Handoff and the Ixel app | `irm https://ixelai.com/install.ps1 \| iex` | `curl -fsSL https://ixelai.com/install.sh \| sh` |
| Ixel MAT and the Ixel app | `irm https://ixelai.com/ixel-mat/install.ps1 \| iex` | `curl -fsSL https://ixelai.com/ixel-mat/install.sh \| sh` |
| Handoff | `irm https://ixelai.com/handoff/install.ps1 \| iex` | `curl -fsSL https://ixelai.com/handoff/install.sh \| sh` |

Each gets the tools with git and runs each tool's own installer. `install.sh` also takes the choice as an
argument: `sh -s -- mat`, `sh -s -- handoff`, or `sh -s -- all`.

Change only `install.ps1` and `install.sh` at the root. The copies in `ixel-mat/` and `handoff/` differ in two
lines (the choice, `$Only` or `ONLY`, and the usage line), and `python scripts/make-installers.py` makes them;
commit them together. `--check` changes nothing and fails if a copy is out of date. Keep the PowerShell files
ASCII (the script checks): Windows PowerShell reads a file without a byte order mark in the computer's ANSI
code page. The [Ixel repository](https://github.com/OpenIxelAI/Ixel) carries the same two root files, byte for
byte. With a checkout of it beside this one (`../Ixel`), the script writes and checks those too (`--ixel PATH`
names another place); commit them there as well. Without one, it says it didn't check them.

## The docs

`docs/` holds one folder per page, each an `index.html`, plus `docs.css`, `docs.js` (the tabs for each system
and the phone menu; it stores nothing) and `images/`. Write a page's content by hand. The first two scripts
fill in the rest, between `<!-- name -->` and `<!-- /name -->` markers, and take `--check`; the third retakes
the pictures:

- **`python scripts/make-docs.py`** writes every docs page's header, menu, "On this page" list, previous and
  next links, and footer, from the list of pages at the top of the script. It fails on a link to a heading
  that isn't there.
- **`python scripts/make-models.py`** writes the model picks on `docs/models/` and `docs/local-models/` from
  `docs/models/data.json`, by the rules in its `pick()`. The data is
  [Artificial Analysis](https://artificialanalysis.ai/)'s, credited on the pages. `--fetch` reads their free
  API first, with a free key: `AA_API_KEY=... python scripts/make-models.py --fetch`. It replaces every score
  and cost, keeps the hand-kept `open`, `params` and `active`, lists new models that may be open, and changes
  nothing if the API refuses or sends too little.
- **`python scripts/docs-screenshots.py --ixel-mat ../ixel-mat --home /home/you`** retakes the app pictures in
  `docs/images/` from the real app, with stand-in models, an example board and example machines, in a home
  folder of its own (`--home /home/you`, so the pictures show that path instead of a temporary one). It needs Ixel MAT, Handoff, Playwright's Chromium and Pillow. The pictures of local models need the model
  servers' usual ports free (11434, 1234, 8000 and a few more, so stop `python -m http.server` first); it skips
  them and says so otherwise. Look at every picture before committing it.

### The weekly refresh

`.github/workflows/model-picks.yml` runs `make-models.py --fetch` every Monday, pushes the new picks to `main`
and asks GitHub Pages to publish them. It needs the repository secret `AA_API_KEY` (**Settings → Secrets and
variables → Actions**); without it, the job stops with a warning and changes nothing. To run it now: **Actions
→ Refresh model picks → Run workflow**. The key is sent only to Artificial Analysis.
