# IxelAI

The IxelAI company site: one static page, no build step. This repository is its only copy: the
`website/` folder that used to hold it in Handoff-by-IxelAI was removed so the two can't drift apart.

| File | What it is |
|---|---|
| `index.html` | The whole site: page, styles and the starfield script |
| `favicon.svg` | Browser tab icon (the crescent and gold star) |
| `ixel-logo.svg`, `ixel-logo.png` | The Ixel mark, same as in the product repos. The PNG is the link preview image |

To look at it, open `index.html` in a browser. To change it, edit it here and push to `main`.

## Turning on GitHub Pages

Pages is not on yet (the API token used to create this repository cannot change Pages settings).

1. This repository is private, and GitHub Pages only serves private repositories on a paid plan (GitHub
   Pro or Team). Either make the repository public in **Settings → General → Danger Zone** (it holds
   nothing but the public page), or upgrade.
2. Go to **Settings → Pages**, choose **Deploy from a branch**, `main`, `/ (root)`, and save.

The `CNAME` file sets the custom domain to `ixelai.com`, so Pages picks it up as soon as it is on.

## The domains

IxelAI owns `ixelai.com` and `ixelai.org`. `ixelai.com` is the site; `ixelai.org` forwards to it.

**`ixelai.com`**: at the registrar's DNS settings, remove any existing parking records for `@` and `www`,
then add:

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

**`ixelai.org`**: use the registrar's URL forwarding (sometimes called a redirect) to send `ixelai.org` and
`www.ixelai.org` to `https://ixelai.com`, as a permanent (301) redirect.

## Before the products are public

- The three tool links on the page go to [github.com/OpenIxelAI](https://github.com/OpenIxelAI), not to the private product repositories, so visitors don't hit a 404. Point each link at its repo when that repo is public.
- Product copy comes from each project's README and SECURITY.md. When a README changes, update the matching section here.
