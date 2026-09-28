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

Pages is not on yet (the API token used to create this repository cannot change Pages settings). Go to **Settings → Pages**, choose **Deploy from a branch**, `main`, `/ (root)`, and save. The site is then `https://openixelai.github.io/ixelai.com/`.

## Adding your domain

After you buy the domain, at your registrar's DNS settings add:

| Type | Name | Value |
|---|---|---|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `openixelai.github.io` |

Then in **Settings → Pages**, type the domain under **Custom domain**, save, and tick **Enforce HTTPS** once it's offered. If you also own the other extension (`.org` or `.com`), use your registrar's forwarding to send it to the main one.

## Before the products are public

- The three tool links on the page go to [github.com/OpenIxelAI](https://github.com/OpenIxelAI), not to the private product repositories, so visitors don't hit a 404. Point each link at its repo when that repo is public.
- The link-preview image (`og:image` in `index.html`) points at `https://openixelai.github.io/ixelai.com/ixel-logo.png`. Once your own domain is live, change it to `https://<your domain>/ixel-logo.png`.
- Product copy comes from each project's README and SECURITY.md. When a README changes, update the matching section here.
