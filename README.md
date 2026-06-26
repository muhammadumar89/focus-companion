# Focus Companion 🎯

**Get your time back while the AI thinks.**

When you use an AI coding agent (like Claude Code), there are little gaps where it's "thinking." Those gaps are where your hand drifts to YouTube, X, or Instagram — and ten minutes vanish. Focus Companion fills that gap with something *good*: a calm, full-screen page that plays a short, motivating or thought-provoking clip, then gently snaps you back the moment the agent is done.

And it **learns**. You give each clip a 👍 or 👎, and it shows you more of what you like and less of what you don't — building your own little feed of the people and ideas that actually fire you up.

![it opens when the agent works, you rate clips, it learns](https://github.com/muhammadumar89/focus-companion)

---

## What it does

- **Opens automatically** when your agent starts working, and **brings you back** (soft chime) when it finishes.
- **Plays short clips** (YouTube Shorts) from voices like Feynman, Jobs, Naval, Goggins, Deutsch — or whoever you add.
- **Learns your taste** — 👍/👎 reshapes what you see next, instantly. No two-in-a-row repeats.
- **Grows itself** (optional) — a nightly job finds fresh clips in the lanes you like most.
- **Stays private** — your ratings live on your machine, never uploaded.

## Requirements

- **macOS** (uses `launchd`, `open`, and the `say`/chime tools)
- **[Claude Code](https://claude.com/claude-code)** — the auto-open-while-thinking magic is a Claude Code *hook*
- **Python 3** (already on every Mac)
- *(optional)* **yt-dlp** — only needed for the nightly auto-grow; the installer offers to set it up

> No Claude Code? It still works — just open `http://localhost:7654/focus.html` yourself after starting the server. You only lose the auto-open-on-thinking.

## Install

**One line — paste it in your terminal:**

```bash
curl -fsSL https://raw.githubusercontent.com/muhammadumar89/focus-companion/main/install.sh | bash
```

That's the whole thing. It downloads the code, wires the Claude Code hooks, installs `yt-dlp`, and schedules the nightly auto-grow — no questions asked. Send a prompt in Claude Code and the focus page opens.

**Prefer to read the script first?** (recommended if you're security-minded):

```bash
git clone https://github.com/muhammadumar89/focus-companion.git
cd focus-companion
./install.sh
```

Both do exactly the same thing.

## Use it

- A clip **auto-plays muted** the moment it opens — **tap once** for sound.
- **👍 / 👎** (or the **↑ / ↓** keys) teach it your taste.
- **→ / space / n** skips to the next clip.
- **Want more of someone?** Type a name in the box (e.g. *Lex Fridman*, *Dario Amodei*) — the nightly job fetches a batch of their clips and adds them to your deck.
- Switch to **Quotes** mode anytime with the toggle.

## How it learns (the short version)

Every clip is tagged with a *person* and a *vibe* (grit, ideas, vision…). A 👍 lifts that clip **and its whole lane**, so liking three Feynman clips surfaces more Feynman *and* more "ideas" clips. Picks are weighted by your taste, your freshness, and an anti-repeat rule. The nightly job reads those scores and fetches brand-new shorts in your favorite lanes — so the feed becomes more *you* over time.

## Customize

- **Add / remove clips** — edit the `VIDEOS` list at the top of `focus.html` (each entry is a YouTube Shorts id).
- **Change the nightly time** — edit `Hour` in `~/Library/LaunchAgents/com.focuscompanion.autoexpand.plist`.
- **Change the sound / window it returns to** — edit `focus-stop.sh`.

## Remove it

```bash
./uninstall.sh
```

Removes the hooks and the nightly job. Your files stay put — delete the folder to fully remove.

## License

MIT — do whatever you like. See [LICENSE](LICENSE).

---

*Built with Claude Code. If it gives you even one focused hour back, it did its job.*
