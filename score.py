#!/usr/bin/env python3
"""
Focus Companion — purpose scorer.

Scores each clip 0..10 on how much watching it moves you toward your MISSION
(not whether you'd 'like' it), and writes a `const PURPOSE = {...}` map into
focus.html. The dial's left side ("what I should watch") reads these scores.

Edit PROFILE below to change what the feed steers you toward. Only un-scored
clips are sent to the model, so re-runs are cheap.
"""
import os, re, json, urllib.request, urllib.error

DIR = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(DIR, "focus.html")
MODEL = "claude-sonnet-4-6"

PROFILE = (
    "You are scoring short videos for Umar — a founder building an open-source, "
    "sovereign-AI company in the spirit of 'technology of freedom'. He is maximizing "
    "toward: open source, entrepreneurship, building a great frontier-AI company, "
    "first-principles thinking, decentralization and freedom, and becoming a sharper, "
    "wiser, more original founder. Score how much WATCHING each clip would move him "
    "toward that mission and the person he is trying to become — NOT whether it is "
    "entertaining or whether he would personally 'like' it. "
    "10 = directly sharpens a founder building open-source frontier AI, or a deep truth "
    "he should internalize. 5 = generally useful. 0 = irrelevant to his growth."
)


def api_key():
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:
        return k
    for p in ("~/focus-companion/.env", "~/leadloop/.env"):
        p = os.path.expanduser(p)
        if os.path.isfile(p):
            for ln in open(p):
                if ln.strip().startswith("ANTHROPIC_API_KEY"):
                    return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def call(items, key):
    listing = "\n".join(f"{cid}\t{who}" for cid, who in items)
    body = {
        "model": MODEL, "max_tokens": 2000,
        "system": (PROFILE + " Return ONLY a JSON object mapping each clip id to an "
                   "integer 0-10. No prose, no markdown."),
        "messages": [{"role": "user", "content": "Clips (id<TAB>title):\n" + listing}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read())
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def main():
    html = open(HTML, encoding="utf-8").read()
    clips = re.findall(r'\{id:"([^"]+)", who:"([^"]+)"', html)
    m = re.search(r"const PURPOSE = (\{.*?\});", html, re.S)
    have = {}
    if m:
        try:
            have = json.loads(m.group(1))
        except Exception:
            have = {}
    todo = [(cid, who) for cid, who in clips if cid not in have]
    if not todo:
        print("all clips already scored")
        return
    key = api_key()
    if not key:
        print("no ANTHROPIC_API_KEY — skipping purpose scoring")
        return
    scores = {}
    for i in range(0, len(todo), 60):          # batch to keep prompts modest
        scores.update(call(todo[i:i + 60], key))
    merged = {**have, **{k: int(v) for k, v in scores.items()}}
    new_html = re.sub(r"const PURPOSE = \{.*?\};",
                      "const PURPOSE = " + json.dumps(merged) + ";", html, count=1, flags=re.S)
    open(HTML, "w", encoding="utf-8").write(new_html)
    print(f"scored {len(scores)} new clips (total {len(merged)})")


if __name__ == "__main__":
    main()
