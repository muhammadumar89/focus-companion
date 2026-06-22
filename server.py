#!/usr/bin/env python3
"""
Focus Companion — local bridge server.

Replaces `python3 -m http.server`. Three jobs:
  1. Serve focus.html and friends with no-cache headers (always fresh, no stale tab).
  2. Accept POST /rate  -> append the rating to ratings.jsonl (the file the agent reads).
  3. Answer GET /__ping -> "focus-bridge" so the start script knows the bridge is up.

Everything stays on 127.0.0.1 — nothing is exposed to the network.
"""
import http.server, socketserver, json, os, datetime

DIR = os.path.expanduser("~/focus-companion")
PORT = 7654
RATINGS = os.path.join(DIR, "ratings.jsonl")


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
        self.send_response(404)
        self.end_headers()

    def log_message(self, *a):   # stay quiet
        pass


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()
