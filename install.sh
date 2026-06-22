#!/bin/bash
# Focus Companion — one-command installer (macOS).
#
# Run it either way:
#   curl -fsSL https://raw.githubusercontent.com/muhammadumar89/focus-companion/main/install.sh | bash
#   …or from a clone:  ./install.sh
#
# It downloads the code (if needed), wires the Claude Code hooks, installs yt-dlp,
# and schedules the nightly auto-grow — no questions asked. Safe to re-run.
set -e
REPO="https://github.com/muhammadumar89/focus-companion.git"
DEST="$HOME/focus-companion"

echo ""
echo "  Focus Companion — installing…"

# 1) Find the code. If we're inside a clone (focus.html is next to us), use it.
#    Otherwise (curl | bash) clone/update into ~/focus-companion.
SELF_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || true)"
if [ -n "$SELF_DIR" ] && [ -f "$SELF_DIR/focus.html" ]; then
  DIR="$SELF_DIR"
else
  if ! command -v git >/dev/null 2>&1; then
    echo "  ✗ git is required. Install Xcode command line tools first: xcode-select --install"
    exit 1
  fi
  if [ -d "$DEST/.git" ]; then
    echo "  updating existing copy at $DEST"
    git -C "$DEST" pull --quiet || true
  elif [ -e "$DEST" ] && [ -f "$DEST/focus.html" ]; then
    echo "  using existing copy at $DEST"
  else
    echo "  downloading to $DEST"
    git clone --quiet "$REPO" "$DEST"
  fi
  DIR="$DEST"
fi

# 2) make the scripts runnable
chmod +x "$DIR"/*.sh "$DIR"/*.py 2>/dev/null || true

# 3) wire the Claude Code hooks into ~/.claude/settings.json (merge, don't clobber)
python3 - "$DIR" <<'PY'
import json, os, sys
DIR = sys.argv[1]
path = os.path.expanduser("~/.claude/settings.json")
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    s = json.load(open(path))
except Exception:
    s = {}
hooks = s.setdefault("hooks", {})
def add(event, script):
    cmd = f"bash '{DIR}/{script}'"
    arr = hooks.setdefault(event, [])
    for group in arr:
        for h in group.get("hooks", []):
            if h.get("command") == cmd:
                return
    arr.append({"hooks": [{"type": "command", "command": cmd}]})
add("UserPromptSubmit", "focus-start.sh")
add("Stop", "focus-stop.sh")
json.dump(s, open(path, "w"), indent=2)
print("  ✓ hooks wired (opens on prompt, brings you back when done)")
PY

# 4) install yt-dlp (best-effort) and, if present, schedule the nightly auto-grow
if pip3 install --user --quiet yt-dlp >/dev/null 2>&1; then
  echo "  ✓ yt-dlp installed"
  PLIST="$HOME/Library/LaunchAgents/com.focuscompanion.autoexpand.plist"
  mkdir -p "$HOME/Library/LaunchAgents"
  sed "s|__DIR__|$DIR|g" "$DIR/com.focuscompanion.autoexpand.plist.template" > "$PLIST"
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load -w "$PLIST" 2>/dev/null || true
  echo "  ✓ nightly auto-grow scheduled (3:00 AM)"
else
  echo "  ! couldn't install yt-dlp — the app still works; nightly auto-grow is off."
fi

echo ""
echo "  ✅ Done. Send a prompt in Claude Code and the focus page opens."
echo "     Rate clips with 👍 / 👎 (or ↑ / ↓). To remove: $DIR/uninstall.sh"
echo ""
