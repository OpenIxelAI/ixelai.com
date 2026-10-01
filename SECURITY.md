# Security

This repository is the IxelAI website: static pages with no server, no forms, no accounts and no cookies.
It never collects anything about the people who visit it.

## Reporting a problem

Please report anything that looks wrong privately: use GitHub's **Report a vulnerability** button on this
repository's **Security** tab, or email **openixel.ai@gmail.com**. Don't open a public issue. For problems
in one of the tools, use that tool's own repository.

## How the site protects visitors

- **No third parties.** Fonts, scripts, styles and videos are all served from this site, so a visit never
  contacts Google, an analytics service or a CDN. There is no tracking and nothing to opt out of.
- **A Content Security Policy** on every page allows scripts, fonts, media and connections only from the
  site itself, and blocks plugins, forms and `<base>` changes. Keep it that way: don't add inline scripts,
  third-party embeds or analytics.
- **No referrer.** Links out of the site don't tell the other site which page the visitor came from.
- **HTTPS only**, with the certificate from GitHub Pages, and the domain verified on GitHub so no one else
  can publish under it.

## What must never be committed here

The repository will be public. Never commit API keys, tokens, `.env` files, private keys, personal email
addresses, phone numbers, home addresses, or screenshots and recordings that show any of them. See
[videos/README.md](videos/README.md) for how to record a demo safely.
