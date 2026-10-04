# Security

This repository is the IxelAI website: static pages with no server of our own, no forms, no accounts and
no cookies. It runs no tracking. GitHub Pages, which hosts it, logs visitors' IP addresses for security;
that's GitHub's, not ours.

## Reporting a problem

Please report anything that looks wrong privately: email **openixel.ai@proton.me**, or use GitHub's
**Report a vulnerability** button on this repository's **Security** tab if it's there. Don't open a public
issue. For a problem in one of the tools, email the same address. Once a tool's repository is public, you
can also use its own Security tab.

## How the site protects visitors

- **No third parties.** Fonts, scripts, styles and videos are all served from this site, so a visit never
  contacts Google, an analytics service or a CDN. There is no tracking and nothing to opt out of.
- **A Content Security Policy** on every page allows scripts, fonts, media and connections only from the
  site itself, and blocks plugins, forms and `<base>` changes. Keep it that way: don't add inline scripts,
  third-party embeds or analytics.
- **No Jekyll.** The empty `.nojekyll` file keeps GitHub Pages from building themed pages out of the
  Markdown files here, which would load a script from a CDN.
- **No referrer.** Links out of the site don't tell the other site which page the visitor came from.
- **HTTPS only**, with the certificate from GitHub Pages, and the domain verified on GitHub so no one else
  can publish under it.

## What must never be committed here

This repository is public. Never commit API keys, tokens, `.env` files, private keys, personal email
addresses, phone numbers, home addresses, or screenshots and recordings that show any of them. See
[videos/README.md](videos/README.md) for how to record a demo safely.
