# IxelAI

The IxelAI company site: a few static pages, no build step. This repository is its only copy: the
`website/` folder that used to hold it in Handoff-by-IxelAI was removed so the two can't drift apart.

| Path | What it is |
|---|---|
| `index.html` | The home page: the star chart and all three tools |
| `ixel-mat/`, `handoff/`, `ixel-console/` | One page per tool: overview, demo video, who it's for, how it works, and Windows install |
| `about/` | Our mission and what we believe |
| `styles.css`, `site.js` | Styles and the script (starfield, copy buttons, demo videos) every page shares |
| `videos/` | The tool pages' demo recordings; see [videos/README.md](videos/README.md) |
| `fonts/` | The site's fonts, self-hosted so visitors never contact Google, with their licenses |
| `favicon.svg` | Browser tab icon (the crescent and gold star) |
| `ixel-logo.svg`, `ixel-logo.png` | The Ixel mark, same as in the product repos. The PNG is the link preview image |

To look at it, open `index.html` in a browser. Links between pages end in a folder (`ixel-mat/`), which
GitHub Pages serves but a double-clicked file doesn't, so to click around locally run
`python -m http.server` in this folder and open `http://localhost:8000`. To change it, edit it here and
push to `main`.

Every page has the same header and footer. When you change one, change it in all five.

The site makes no requests to anyone else: fonts are in `fonts/` (SIL Open Font License, licenses
alongside), and every page has a Content Security Policy that allows only this site's own files. Don't add
analytics, embeds, CDN links or inline scripts; see [SECURITY.md](SECURITY.md).

## Turning on GitHub Pages

Pages is not on yet (the API token used to create this repository cannot change Pages settings).

1. This repository is private, and GitHub Pages only serves private repositories on a paid plan (GitHub
   Pro or Team). Either make the repository public in **Settings → General → Danger Zone** (it holds
   nothing but the public page), or upgrade.
2. Go to **Settings → Pages**, choose **Deploy from a branch**, `main`, `/ (root)`, and save.

The `CNAME` file sets the custom domain to `ixelai.com`, so Pages picks it up as soon as it is on.

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
- Product copy comes from each project's README and SECURITY.md. When a README changes, update the matching section here.
