# IxelAI

The IxelAI company site: a few static pages, no build step. This repository is its only copy: the
`website/` folder that used to hold it in Handoff-by-IxelAI was removed so the two can't drift apart.

| Path | What it is |
|---|---|
| `index.html` | The home page: the star chart, all three tools, and the one-line install (Ixel, or one tool alone) |
| `ixel-mat/`, `handoff/`, `machines/` | One page per tool: overview, demo video, who it's for, how it works, and install. `ixel-mat/` and `handoff/` also hold that tool's own installers |
| `ixel-console/` | Ixel Console's old address: it says Ixel Console is now Machines, and how to bring your machines over |
| `install.ps1`, `install.sh` | The one-line installers; see [The installers](#the-installers). Keep them ASCII |
| `scripts/make-installers.py` | Makes the one-tool installers in `ixel-mat/` and `handoff/` from the root ones |
| `about/` | Our mission and what we believe |
| `docs/` | The docs: install, setup, the app, the terminal, Handoff, model picks, local models and privacy. See [The docs](#the-docs) |
| `scripts/make-docs.py`, `scripts/make-models.py`, `scripts/docs-screenshots.py` | Keep the docs' menus, model picks and app pictures up to date |
| `.github/workflows/model-picks.yml` | Refreshes the model picks every week; see [The weekly refresh](#the-weekly-refresh) |
| `styles.css`, `site.js` | Styles and the script (starfield, copy buttons, demo videos) every page shares |
| `videos/` | The tool pages' demo recordings; see [videos/README.md](videos/README.md) |
| `fonts/` | The site's fonts, self-hosted so visitors never contact Google, with their licenses |
| `favicon.svg` | Browser tab icon (the crescent and gold star) |
| `.nojekyll` | Empty. Tells GitHub Pages to serve the files as they are, with no Jekyll build; keep it |
| `ixel-logo.svg`, `ixel-logo.png` | The Ixel mark, same as in the product repos. The PNG is the link preview image |

To look at it, open `index.html` in a browser. Links between pages end in a folder (`ixel-mat/`), which
GitHub Pages serves but a double-clicked file doesn't, so to click around locally run
`python -m http.server` in this folder and open `http://localhost:8000`. To change it, edit it here and
push to `main`.

Every page has the same header and footer. When you change one, change it on every page (the docs pages
get theirs from `scripts/make-docs.py`).

The site makes no requests to anyone else: fonts are in `fonts/` (SIL Open Font License, licenses
alongside), and every page has a Content Security Policy that allows only this site's own files. Don't add
analytics, embeds, CDN links or inline scripts; see [SECURITY.md](SECURITY.md).

## The installers

Ixel is the all-in-one: one command installs Ixel MAT, Handoff and the Ixel app. Each tool also installs
on its own, for people who want just that one:

| Installs | Windows (PowerShell) | macOS and Linux |
|---|---|---|
| Ixel: Ixel MAT, Handoff and the Ixel app | `irm https://ixelai.com/install.ps1 \| iex` | `curl -fsSL https://ixelai.com/install.sh \| sh` |
| Ixel MAT and the Ixel app | `irm https://ixelai.com/ixel-mat/install.ps1 \| iex` | `curl -fsSL https://ixelai.com/ixel-mat/install.sh \| sh` |
| Handoff | `irm https://ixelai.com/handoff/install.ps1 \| iex` | `curl -fsSL https://ixelai.com/handoff/install.sh \| sh` |

Each one gets the tools with git, into the folders their own installers use, and runs those installers
(`install.ps1` or `install.sh` in each tool's repository). Ixel MAT's installer is the one that adds the Ixel
app. Running a command again updates what it installed. `install.sh` also takes the choice as an argument:
`sh -s -- mat`, `sh -s -- handoff`, or `sh -s -- all` for everything.

There is one source to change: `install.ps1` and `install.sh` at the root. The copies in `ixel-mat/` and
`handoff/` are the same files with two lines changed, the choice (`$Only` or `ONLY`) and the usage line in
the header. After changing a root installer, run

```
python scripts/make-installers.py
```

to update the copies, and commit them together. `python scripts/make-installers.py --check` changes nothing and
fails if a copy is out of date. The PowerShell ones must stay ASCII (the script checks): Windows PowerShell
reads a file without a byte order mark in the computer's ANSI code page.

GitHub Pages serves all six as they are. The empty `.nojekyll` file at the root turns Jekyll off, so
nothing is built from the repository's files. Without it, Jekyll turns `README.md`, `SECURITY.md` and
`videos/README.md` into themed pages that load a script from a CDN, which this site promises never to do.
Keep it.

## The docs

`docs/` holds one folder per page, each an `index.html`, plus `docs.css`, `docs.js` (the tabs for each
system, and the menu on a phone; it stores nothing) and `images/`. Write a page's content by hand. Two
scripts fill in the rest, between `<!-- name -->` and `<!-- /name -->` markers, and each takes `--check`
to change nothing and fail if a page is out of date; a third retakes the pictures:

- **`python scripts/make-docs.py`** writes every docs page's header, menu, "On this page" list, previous
  and next links, and footer, from the list of pages at the top of the script. Add a page there, then run
  it. It also fails on a link to a heading that isn't there.
- **`python scripts/make-models.py`** writes the model picks on `docs/models/` and `docs/local-models/`
  from `docs/models/data.json`, by the rules in its `pick()`, which the models page states in words. The
  data is [Artificial Analysis](https://artificialanalysis.ai/)'s; they ask to be credited, which the
  pages do. `--fetch` reads [their free API](https://artificialanalysis.ai/data-api/docs) first, with a
  free key from artificialanalysis.ai: `AA_API_KEY=... python scripts/make-models.py --fetch`. It replaces
  every model's score and cost, so hand edits to those don't last; whether a model is open and its size
  (`open`, `params`, `active`) do, since their free API doesn't say. It lists each new model that may be
  open, to add those by hand. It changes nothing when the API refuses, sends under half as many models as
  `data.json` has, or gives no costs. Each page shows the date the numbers were read.
- **`python scripts/docs-screenshots.py --ixel-mat ../ixel-mat`** retakes the app pictures in
  `docs/images/`. It runs the real app from an Ixel MAT checkout, with stand-in models that give scripted
  answers, an example project board and example machines, in a home folder of its own, so nothing of
  yours shows. It needs Ixel MAT, Handoff, Playwright's Chromium and Pillow. The pictures of models on your
  computers and Private use a stand-in Ollama at port 11434, so they need that port and the other model
  servers' ports free; the script skips them and says so otherwise. Look at every picture before
  committing it, and run it again whenever the app's pages change.

### The weekly refresh

`.github/workflows/model-picks.yml` runs `make-models.py --fetch` every Monday, pushes the new picks to
`main` and asks GitHub Pages to publish them (a push made with a workflow's own token doesn't start a
Pages build by itself). It needs the key saved as a repository secret: **Settings → Secrets and
variables → Actions → New repository secret**, named `AA_API_KEY`. Without it, the job stops with a
warning and changes nothing. To refresh now, open **Actions → Refresh model picks → Run workflow**. The
summary of the run that first sees a new model that may be open lists it, to add by hand. The key is
sent only to Artificial Analysis. GitHub Actions is free for public repositories like this one.

## GitHub Pages

The site is live: GitHub Pages serves `main` from the root of this public repository, and the `CNAME`
file sets the custom domain to `ixelai.com`. A push to `main` updates it.

## The domains

IxelAI owns `ixelai.com` and `ixelai.org`. `ixelai.com` is the site; `ixelai.org` forwards to it.

Both domains are registered with Cloudflare, so their DNS is in the Cloudflare dashboard.

**`ixelai.com`**: under **ixelai.com → DNS → Records**, remove any existing records for `@` and `www`, then
add these with **Proxy status** set to **DNS only** (grey cloud). Cloudflare's proxy stops GitHub from issuing
the site's HTTPS certificate.

| Type | Name | Value |
|---|---|---|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `openixelai.github.io` |

Then in **Settings → Pages**, check that **Custom domain** shows `ixelai.com`, and tick **Enforce HTTPS** once
it's offered (DNS and the certificate can take up to a day). `www.ixelai.com` redirects to `ixelai.com`
on its own.

**`ixelai.org`**: Cloudflare forwards it with a redirect rule, which needs proxied records to act on:

1. Under **ixelai.org → DNS → Records**, add an `A` record `@` → `192.0.2.1` and a `CNAME` record `www` → `ixelai.org`,
   both **Proxied** (orange cloud). `192.0.2.1` is a placeholder address; Cloudflare answers before it is used.
2. Under **ixelai.org → Rules → Redirect Rules**, create a rule for **All incoming requests** that redirects to
   `https://ixelai.com` with status code **301**.

## Before the products are public

- The three tool links on the page go to [github.com/OpenIxelAI](https://github.com/OpenIxelAI), not to the private product repositories, so visitors don't hit a 404. Point each link at its repo when that repo is public.
- The installers clone each tool from its GitHub repository, so they work for everyone only once that repository is public.
- Product copy comes from each project's README and SECURITY.md. When a README changes, update the matching section here.
