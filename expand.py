#!/usr/bin/env python3
"""
Focus Companion — nightly auto-expand (deterministic, no LLM).

Reads taste.json -> finds your top positively-rated people (lanes) -> uses yt-dlp
to fetch fresh shorts in those lanes -> dedupes against the deck -> appends a few
new clips to focus.html's VIDEOS array. Disliked lanes are never fetched.

Runs fully locally via launchd. No Claude binary, no network auth, no hooks.
"""
import json, os, re, glob, shutil, subprocess, datetime

DIR  = os.path.expanduser("~/focus-companion")
HTML = os.path.join(DIR, "focus.html")
TASTE = os.path.join(DIR, "taste.json")
LOG  = os.path.join(DIR, "auto-expand.log")

MAX_DECK    = 90        # stop growing past this
ADD_PER_RUN = 6         # new clips per night
SEARCH_N    = 14        # candidates to pull per lane
SKIP_TITLE = re.compile(
    r"\b(compilation|full (video|episode|speech)|1 ?hour|hours?|podcast|ep(isode)?\.? ?\d|"
    r"interview|mix|playlist|live|parody|remix|song|\brap\b|lyrics|cover|tribute|"
    r"ai ?voice|deepfake|reaction|meme|funny|prank|magic|gangsta|edit\b)\b", re.I)


def log(m):
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {m}"
    with open(LOG, "a") as f:
        f.write(line + "\n")
    print(line)


def find_ytdlp():
    for p in glob.glob(os.path.expanduser("~/Library/Python/*/bin/yt-dlp")):
        return p
    return shutil.which("yt-dlp") or "/opt/homebrew/bin/yt-dlp"


def search_shorts(ytdlp, person, n=SEARCH_N):
    # non-flat + duration filter so we only keep true short-form clips (<=90s)
    try:
        out = subprocess.run(
            [ytdlp, "--match-filter", "duration<=90 & duration>0",
             "--print", "%(id)s\t%(title)s", f"ytsearch{n}:{person} shorts"],
            capture_output=True, text=True, timeout=300).stdout
    except Exception as e:
        log(f"  search failed for {person}: {e}")
        return []
    out_rows = []
    for line in out.splitlines():
        if "\t" not in line:
            continue
        vid, title = line.split("\t", 1)
        if SKIP_TITLE.search(title):
            continue
        out_rows.append((vid.strip(), title.strip()))
    return out_rows


def clean_who(person, title):
    t = re.sub(r"#\w+", " ", title)
    t = re.sub(r'["\\\n\r]', " ", t)               # kill anything that breaks a JS string
    t = re.sub(r"\s+", " ", t).strip(" -—–|:")
    t = t[:48].strip(" -—–|:")
    if not t:
        t = "Short"
    return t if person.lower() in t.lower() else f"{person} — {t}"


def main():
    if not (os.path.isfile(TASTE) and os.path.isfile(HTML)):
        log("missing taste.json or focus.html; skipping")
        return
    taste = json.load(open(TASTE))
    html = open(HTML, encoding="utf-8").read()

    ids = set(re.findall(r'\{id:"([^"]+)"', html))
    if len(ids) >= MAX_DECK:
        log(f"deck at {len(ids)} (cap {MAX_DECK}); skipping")
        return

    clip_person = dict(re.findall(r'\{id:"([^"]+)"[^}]*?person:"([^"]*)"', html))
    person_vibe = {}
    for cid, p in clip_person.items():
        m = re.search(r'\{id:"' + re.escape(cid) + r'"[^}]*?vibe:"([^"]*)"', html)
        if p and m:
            person_vibe.setdefault(p, m.group(1))

    net = {}
    for cid, t in taste.items():
        p = clip_person.get(cid, "")
        if p:
            net[p] = net.get(p, 0) + (t.get("up", 0) - t.get("down", 0))
    top = [p for p, n in sorted(net.items(), key=lambda x: -x[1]) if n > 0][:3]
    if not top:
        log("no positively-rated lanes yet; skipping")
        return
    log(f"top lanes: {[(p, net[p]) for p in top]}")

    ytdlp = find_ytdlp()
    new = []
    per_lane = max(2, ADD_PER_RUN // len(top) + 1)
    for p in top:
        vibe = person_vibe.get(p, "")
        got = 0
        for vid, title in search_shorts(ytdlp, p):
            if vid in ids:
                continue
            ids.add(vid)
            new.append((vid, clean_who(p, title), p, vibe))
            got += 1
            if got >= per_lane or len(new) >= ADD_PER_RUN:
                break
        if len(new) >= ADD_PER_RUN:
            break
    new = new[:ADD_PER_RUN]
    if not new:
        log("no fresh clips found; skipping")
        return

    today = datetime.date.today().isoformat()
    entries = []
    for vid, who, p, vibe in new:
        w = ", w:2" if vibe == "ideas" else ""
        entries.append(f'  {{id:"{vid}", who:"{who}", person:"{p}", vibe:"{vibe}"{w}}}')
    insertion = (",\n  /* — auto-expanded " + today +
                 " (top lanes: " + ", ".join(top) + ") — */\n" + ",\n".join(entries))

    start = html.find("let VIDEOS = [")
    end = html.find("\n];", start)
    if start < 0 or end < 0:
        log("couldn't locate VIDEOS array; aborting (no change)")
        return
    new_html = html[:end] + insertion + html[end:]
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(new_html)
    log(f"added {len(new)} clips: " + " | ".join(w for _, w, _, _ in new))


if __name__ == "__main__":
    main()
