<div align="center">

# Drive → SSD

**Your Google Drive, copied to a disk you actually own.**

![platform](https://img.shields.io/badge/platform-macOS-7e9bc4?style=flat-square)
![scope](https://img.shields.io/badge/access-read--only-8ea876?style=flat-square)
![status](https://img.shields.io/badge/status-not%20signed-c17c62?style=flat-square)

[Download](#download) · [How it works](#how-it-works) · [Privacy](#privacy) · [FAQ](#faq)

</div>

---

Drive → SSD is a small desktop app for macOS that lets you browse your Google
Drive and pull files straight down to a local folder or external drive — no
re-uploading to another cloud service, no subscription, no server in between.

```
  GOOGLE DRIVE  ─ ─ ─ ─ ─ ─●─ ─ ─ ─ ─ ─  YOUR DISK
```

## How it works

**01 · Sign in with your Google account**
A standard Google sign-in window opens. The app only ever asks for read-only
access to your Drive — it can list and download files, nothing else.

**02 · Pick a destination folder**
Choose anywhere on your machine — an external SSD, a Desktop folder, wherever
you want the copy to live.

**03 · Select files and download**
Browse your Drive in the app, select what you need, and download it directly.
Files go straight from Google's servers to your disk.

<details>
<summary><strong>What it looks like</strong></summary>

```
┌─────────────────────┬──────────────────────────────┐
│ ● Not signed in      │                                │
│                       │  Sign in with Google to       │
│ DESTINATION           │  browse your Drive.           │
│ /Users/you/Desktop    │                                │
│                       │                                │
│ [ Browse... ]         │                                │
└─────────────────────┴──────────────────────────────┘
```

</details>

## Why it's built this way

- **Read-only, always** — the app requests the Drive read-only scope. It can
  see and download your files — it can never edit, delete, or upload
  anything back to your Drive.
- **Nothing leaves your machine** — there's no backend server. Files travel
  directly from Google's API to your local disk.
- **Your sign-in stays local** — after you sign in, your access token is
  stored in your user Library folder on your own Mac, not synced anywhere.
- **Open source** — the full source is right here. Read every line before
  you sign in, if you want.

## Download

Grab the latest build from the [Releases](../../releases) page.

> **On unsigned builds:** this app isn't notarized by Apple, so macOS will
> warn you the first time you open it ("Apple cannot check it for malicious
> software"). Right-click the app → **Open** → confirm in the dialog to run
> it. If that doesn't clear it, strip the quarantine flag manually:
> ```bash
> xattr -cr /Applications/DriveToSSD.app
> ```

## Privacy

Full policy: [`privacy.html`](./privacy.html)

Short version — the app requests a single scope, `drive.readonly`. It can
list and download your files and cannot modify, delete, or upload anything.
No analytics, no third-party sharing, no server collecting your data. Your
access token lives only in `~/Library/Application Support/DriveToSSD/` on
your own machine, and you can revoke access anytime from
[Google Account permissions](https://myaccount.google.com/permissions).

## FAQ

**Is this affiliated with Google?**
No — independent, personal project.

**Can it write to or delete anything in my Drive?**
No. The `drive.readonly` scope is view-and-download only.

**Where does my sign-in token go?**
Nowhere but your own Mac. See [Privacy](#privacy) for details.

---

<div align="center">

[Privacy policy](./privacy.html) · [Report an issue](../../issues) · [Contact](mailto:you@example.com)

</div>
