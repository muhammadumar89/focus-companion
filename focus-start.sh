#!/bin/bash
# Focus Companion — runs when you submit a prompt (the agent starts working).
# Opens the focus screen so your eyes have somewhere good to land.
#
# Serves the page over http://localhost via the bridge server (server.py) so that:
#   - YouTube clips can embed (they refuse file:// URLs, Error 150/153)
#   - the page never goes stale (no-cache headers)
#   - your 👍/👎 ratings get saved to ratings.jsonl for the agent to learn from
# The bridge is started once in the background and reused after that.

DIR="$(cd "$(dirname "$0")" && pwd)"   # this script's own folder
PORT=7654
URL="http://localhost:$PORT/focus.html"

if command -v python3 >/dev/null 2>&1; then
  # Is OUR bridge already up? (a plain http.server would answer files but not /__ping)
  if [ "$(curl -s "http://localhost:$PORT/__ping" 2>/dev/null)" != "focus-bridge" ]; then
    # free the port (in case the old static server is holding it) then start the bridge
    lsof -ti tcp:"$PORT" 2>/dev/null | xargs kill 2>/dev/null
    (cd "$DIR" && nohup python3 "$DIR/server.py" >/dev/null 2>&1 &)
    sleep 0.6
  fi
  open "$URL"
else
  # no python3 — fall back to the file (clips may not play, but the page opens)
  open "file://$DIR/focus.html"
fi

exit 0
