# Demo videos

Each tool page shows its recording from this folder as soon as the file is here. Until then, it shows the
example screen.

| File | Shown on |
|---|---|
| `ixel-mat.mp4` | ixelai.com/ixel-mat/ |
| `handoff.mp4` | ixelai.com/handoff/ |
| `machines.mp4` | ixelai.com/machines/ |

## Making one on Windows

1. Open **Snipping Tool**, switch it to **Record** (the video camera), click **New**, and drag a box around the
   window. Or press **Win + Alt + R** to record the window you're in with the Xbox Game Bar.
2. Show one real task from start to finish. Under a minute is plenty; no sound needed.
3. Save it as an `.mp4` with the name from the table above.

## Before you record: keep it private

Anything on screen is public once it's uploaded, and a screen recording can't be edited after the fact
on GitHub. Before you press record:

- **Record only the app's window**, not the whole screen, so the taskbar, notifications and other windows
  stay out of it.
- **Use a clean terminal prompt.** A PowerShell prompt shows your Windows user folder
  (`C:\Users\<your name>`). Run `function prompt { "PS> " }` first, so it shows `PS>` only.
- **No keys or tokens on screen.** Don't open `.env` files, settings with API keys, or `ixel setup`'s key
  steps while recording. Use placeholder names for servers and profiles (`homelab`, `vps-1`), never real
  IP addresses, hostnames or usernames.
- **Turn off notifications** (Windows: **Focus** or **Do not disturb**) so a message preview doesn't
  appear mid-recording.
- **Watch it back** before uploading, start to finish.

## Adding it

On GitHub, open this `videos` folder, choose **Add file → Upload files**, drop the `.mp4` in, and commit.
GitHub's upload limit is 25 MB per file, which fits about a minute of screen recording. The page picks it up
the next time GitHub Pages publishes the site, usually within a minute or two.
