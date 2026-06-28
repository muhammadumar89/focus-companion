#!/usr/bin/env python3
"""
Focus Companion — local bridge server.

Replaces `python3 -m http.server`. Three jobs:
  1. Serve focus.html and friends with no-cache headers (always fresh, no stale tab).
  2. Accept POST /rate  -> append the rating to ratings.jsonl (the file the agent reads).
  3. Answer GET /__ping -> "focus-bridge" so the start script knows the bridge is up.

Everything stays on 127.0.0.1 — nothing is exposed to the network.
"""
import http.server, socketserver, json, os, datetime, glob, shutil, tempfile, re, subprocess
import urllib.request, urllib.parse, urllib.error

DIR = os.path.dirname(os.path.abspath(__file__))   # this script's own folder
PORT = 7654
RATINGS = os.path.join(DIR, "ratings.jsonl")
POST_MODEL = "claude-sonnet-4-6"


def _ytdlp():
    for p in glob.glob(os.path.expanduser("~/Library/Python/*/bin/yt-dlp")):
        return p
    return shutil.which("yt-dlp") or "/opt/homebrew/bin/yt-dlp"


def _api_key():
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


def _vtt_to_text(vtt):
    out = []
    for ln in vtt.splitlines():
        ln = ln.strip()
        if (not ln or "-->" in ln or ln.isdigit() or ln.startswith("WEBVTT")
                or ln.startswith("Kind:") or ln.startswith("Language:")):
            continue
        ln = re.sub(r"<[^>]+>", "", ln).strip()      # strip caption timing tags
        if ln and (not out or out[-1] != ln):        # drop consecutive repeats
            out.append(ln)
    return " ".join(out)


def _transcript(vid):
    ytdlp, url, tmp = _ytdlp(), "https://www.youtube.com/watch?v=" + vid, tempfile.mkdtemp()
    try:
        subprocess.run([ytdlp, "--skip-download", "--write-auto-subs", "--sub-langs", "en.*",
                        "--sub-format", "vtt", "-o", os.path.join(tmp, "s"), url],
                       capture_output=True, timeout=70)
        vtts = glob.glob(os.path.join(tmp, "*.vtt"))
        text = _vtt_to_text(open(vtts[0], encoding="utf-8").read()) if vtts else ""
        if len(text) < 40:   # no captions -> fall back to title + description
            text = subprocess.run([ytdlp, "--skip-download", "--print",
                                   "%(title)s. %(description).600s", url],
                                  capture_output=True, text=True, timeout=40).stdout.strip()
        return text[:4000]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _write_post(vid, title):
    key = _api_key()
    if not key:
        return {"error": "no Anthropic API key (set ANTHROPIC_API_KEY or add it to ~/focus-companion/.env)"}
    try:
        transcript = _transcript(vid)
    except Exception:
        transcript = ""
    src = "Title: %s\n\nWhat the clip says:\n%s" % (title, transcript or "(no transcript available)")
    body = {
        "model": POST_MODEL,
        "max_tokens": 400,
        "system": ("You write sharp, substantive LinkedIn posts. From the given short video, extract its "
                   "single most important insight and write a ready-to-share post of 3 to 5 short lines "
                   "(one or two sentences each). Open with a strong hook line, then the idea and why it "
                   "matters, then a closing thought. Confident, plain, first-person thought-leadership "
                   "voice — as if the reader is sharing the insight themselves. NO hashtags, NO emojis, "
                   "no 'in this video', no preamble. Return only the post text."),
        "messages": [{"role": "user", "content": src + "\n\nWrite the LinkedIn post."}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            data = json.loads(r.read())
        post = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        return {"post": post} if post else {"error": "empty response"}
    except urllib.error.HTTPError as e:
        return {"error": "API error %s" % e.code}
    except Exception as e:
        return {"error": str(e)[:200]}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DIR, **k)

    # always-fresh: kill caching so edits show up on a plain reload
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def do_GET(self):
        if self.path.rstrip("/") == "/__ping":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"focus-bridge")
            return
        if self.path.rstrip("/") == "/requests":
            # let the page show what's queued / recently done
            try:
                data = open(os.path.join(DIR, "requests.json"), "rb").read()
            except Exception:
                data = b"[]"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.split("?", 1)[0].rstrip("/") == "/post":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            vid = (q.get("id", [""])[0]).strip()
            title = (q.get("title", [""])[0]).strip()
            out = _write_post(vid, title) if vid else {"error": "no id"}
            payload = json.dumps(out).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def do_POST(self):
        if self.path.rstrip("/") == "/rate":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                row = json.loads(raw)
            except Exception:
                row = {"raw": raw.decode("utf-8", "ignore")}
            row["at"] = datetime.datetime.now().isoformat(timespec="seconds")
            with open(RATINGS, "a") as f:
                f.write(json.dumps(row) + "\n")
            self.send_response(204)
            self.end_headers()
            return
        if self.path.rstrip("/") == "/sync":
            # full snapshot of the browser's taste memory -> taste.json (overwrite)
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                obj = json.loads(raw)
            except Exception:
                obj = None
            if isinstance(obj, dict):
                with open(os.path.join(DIR, "taste.json"), "w") as f:
                    json.dump(obj, f, indent=2, ensure_ascii=False)
            self.send_response(204)
            self.end_headers()
            return
        if self.path.rstrip("/") == "/request":
            # queue "fetch N clips of <name>" for the nightly job to fulfill
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                req = json.loads(raw)
            except Exception:
                req = {}
            name = (req.get("name") or "").strip()[:80]
            if name:
                rf = os.path.join(DIR, "requests.json")
                try:
                    reqs = json.load(open(rf))
                except Exception:
                    reqs = []
                try:
                    count = max(1, min(25, int(req.get("count", 20))))
                except Exception:
                    count = 20
                reqs.append({"name": name, "count": count, "status": "pending",
                             "at": datetime.datetime.now().isoformat(timespec="seconds")})
                with open(rf, "w") as f:
                    json.dump(reqs, f, indent=2, ensure_ascii=False)
            self.send_response(204)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *a):   # stay quiet
        pass


if __name__ == "__main__":
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    httpd.serve_forever()
