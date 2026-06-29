#!/usr/bin/env python3
"""
Focus Companion — nightly auto-expand (deterministic, no LLM).

Reads taste.json -> finds your top positively-rated people (lanes) -> uses yt-dlp
to fetch fresh shorts in those lanes -> dedupes against the deck -> appends a few
new clips to focus.html's VIDEOS array. Disliked lanes are never fetched.

Runs fully locally via launchd. No Claude binary, no network auth, no hooks.
"""
import json, os, re, glob, shutil, subprocess, datetime

DIR  = os.path.dirname(os.path.abspath(__file__))   # this script's own folder
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

# Channels always pulled in — every short on these is added & kept fresh nightly.
# Empty for now. Add {"person":..., "vibe":..., "url":...} dicts to pin a channel.
PINNED = []


def log(m):
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {m}"
    with open(LOG, "a") as f:
        f.write(line + "\n")
    print(line)


def find_ytdlp():
    for p in glob.glob(os.path.expanduser("~/Library/Python/*/bin/yt-dlp")):
        return p
    return shutil.which("yt-dlp") or "/opt/homebrew/bin/yt-dlp"


def search_shorts(ytdlp, person, n=SEARCH_N, max_dur=90):
    # non-flat + duration filter. Default <=90s for the tight nightly grow; requests
    # pass a bigger cap so podcast/interview folks (Lex, Dario…) actually return clips.
    try:
        out = subprocess.run(
            [ytdlp, "--match-filter", f"duration<={max_dur} & duration>0",
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


def list_channel(ytdlp, url):
    # every short on a channel (fast, flat). Their own content -> no junk filter.
    try:
        out = subprocess.run([ytdlp, "--flat-playlist", "--print", "%(id)s\t%(title)s", url],
                             capture_output=True, text=True, timeout=180).stdout
    except Exception as e:
        log(f"  channel fetch failed {url}: {e}")
        return []
    rows = []
    for line in out.splitlines():
        if "\t" in line:
            vid, title = line.split("\t", 1)
            rows.append((vid.strip(), title.strip()))
    return rows


def clean_who(person, title):
    t = re.sub(r"#\w+", " ", title)
    t = re.sub(r'["\\\n\r]', " ", t)               # kill anything that breaks a JS string
    t = re.sub(r"\s+", " ", t).strip(" -—–|:")
    t = t[:48].strip(" -—–|:")
    if not t:
        t = "Short"
    return t if person.lower() in t.lower() else f"{person} — {t}"


_FILLER = re.compile(r"\b(at ?least|atleast|please|some|a ?few|the|of|for|me|i|want|wanna|add|show|find|"
                     r"get|give|with|to|and|on|about|shorts?|videos?|clips?|reels?)\b", re.I)
def clean_request_name(raw):
    """Turn a typed request into a clean search name: 'David Dutch, atleast 20
    shorts of David Dutch' -> 'David Dutch'. Drops commas-tail, numbers, filler."""
    s = (raw or "").split(",")[0]
    s = re.sub(r"\d+", " ", s)
    s = _FILLER.sub(" ", s)
    s = re.sub(r"[^A-Za-z .&\-']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = " ".join(s.split()[:4])               # cap to ~4 words
    return s or (raw or "").strip()[:40]


def main():
    if not os.path.isfile(HTML):
        log("missing focus.html; skipping")
        return
    taste = json.load(open(TASTE)) if os.path.isfile(TASTE) else {}
    html = open(HTML, encoding="utf-8").read()
    ids = set(re.findall(r'\{id:"([^"]+)"', html))
    drop = {cid for cid, t in taste.items() if (t.get("up", 0) - t.get("down", 0)) <= -1}  # 👎'd
    ids |= drop                      # never re-add a clip you've disliked
    ytdlp = find_ytdlp()

    new = []          # (vid, who, person, vibe)
    sources = []      # human note of what we grew

    # 0) Pinned channels — always add every fresh short (CodeNinja vision travels along).
    for ch in PINNED:
        got = 0
        for vid, title in list_channel(ytdlp, ch["url"]):
            if vid in ids:
                continue
            ids.add(vid)
            new.append((vid, clean_who(ch["person"], title), ch["person"], ch["vibe"]))
            got += 1
        if got:
            sources.append(f"{ch['person']} +{got}")
            log(f"pinned {ch['person']}: +{got}")

    # 1) Fulfill any requests typed into the focus page (uncapped per request).
    reqf = os.path.join(DIR, "requests.json")
    reqs, reqs_changed = [], False
    if os.path.isfile(reqf):
        try:
            reqs = json.load(open(reqf))
        except Exception:
            reqs = []
    for r in reqs:
        if r.get("status") != "pending":
            continue
        name = clean_request_name(r.get("name") or "")
        if not name:
            r["status"] = "skipped"; reqs_changed = True; continue
        want = max(1, min(25, int(r.get("count", 20))))
        log(f"request: up to {want} clips of '{name}'")
        got = 0
        for vid, title in search_shorts(ytdlp, name, n=max(want * 2, 30), max_dur=600):
            if vid in ids:
                continue
            ids.add(vid)
            new.append((vid, clean_who(name, title), name, "ideas"))
            got += 1
            if got >= want:
                break
        r["status"] = "done"; r["added"] = got; r["done"] = datetime.date.today().isoformat()
        reqs_changed = True
        sources.append(f"requested {got}× {name}")
    if reqs_changed:
        with open(reqf, "w") as f:
            json.dump(reqs, f, indent=2, ensure_ascii=False)

    # 2) Grow your top positively-rated lanes (capped), if there's room.
    if len(ids) < MAX_DECK:
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
        if top:
            log(f"top lanes: {[(p, net[p]) for p in top]}")
            lane_new, per_lane = [], max(2, ADD_PER_RUN // len(top) + 1)
            for p in top:
                vibe, got = person_vibe.get(p, ""), 0
                for vid, title in search_shorts(ytdlp, p):
                    if vid in ids:
                        continue
                    ids.add(vid)
                    lane_new.append((vid, clean_who(p, title), p, vibe))
                    got += 1
                    if got >= per_lane or len(lane_new) >= ADD_PER_RUN:
                        break
                if len(lane_new) >= ADD_PER_RUN:
                    break
            new.extend(lane_new[:ADD_PER_RUN])
            if lane_new:
                sources.append("lanes: " + ", ".join(top))

    # 3) Rebuild the VIDEOS array: drop disliked clips, keep the rest, append new ones.
    start = html.find("let VIDEOS = [")
    obr = html.find("[", start)
    end = html.find("\n];", start)
    if obr < 0 or end < 0:
        log("couldn't locate VIDEOS array; aborting (no change)")
        return
    kept, pruned = [], 0
    for m in re.finditer(r'\{id:"([^"]+)"[^}]*\}', html[obr + 1:end]):
        if m.group(1) in drop:
            pruned += 1
        else:
            kept.append(m.group(0))
    for vid, who, p, vibe in new:
        w = ", w:2" if vibe == "ideas" else ""
        kept.append(f'{{id:"{vid}", who:"{who}", person:"{p}", vibe:"{vibe}"{w}}}')
    if not new and not pruned:
        log("nothing to add or prune")
        return
    body = "\n  " + ",\n  ".join(kept)
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html[:obr + 1] + body + html[end:])
    note = "; ".join(sources) if sources else "auto"
    log(f"deck rebuilt: +{len(new)} added, -{pruned} disliked  (now {len(kept)}) ({note})")


if __name__ == "__main__":
    main()
