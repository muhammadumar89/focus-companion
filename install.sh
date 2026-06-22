#!/bin/bash
# Focus Companion — one-command installer (macOS).
# Wires the Claude Code hooks so the focus page opens whenever the agent works,
# and optionally sets up the nightly auto-expand. Safe to re-run.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  Focus Companion — installing from:"
echo "  $DIR"
echo ""

# 1) make the scripts runnable
chmod +x "$DIR"/*.sh "$DIR"/*.py 2>/dev/null || true

# 2) wire the Claude Code hooks into ~/.claude/settings.json (merge, don't clobber)
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
                return  # already installed
    arr.append({"hooks": [{"type": "command", "command": cmd}]})

add("UserPromptSubmit", "focus-start.sh")   # open the focus page when you send a prompt
add("Stop", "focus-stop.sh")                 # chime + bring the window back when done
json.dump(s, open(path, "w"), indent=2)
print("  ✓ Claude Code hooks wired into ~/.claude/settings.json")
PY

# 3) optional: nightly auto-expand (needs yt-dlp + a launchd timer)
echo ""
printf "  Set up the nightly auto-grow (downloads yt-dlp, schedules a 3 AM job)? [y/N] "
read -r yn
if [[ "$yn" =~ ^[Yy] ]]; then
  echo "  installing yt-dlp ..."
  pip3 install --user --quiet yt-dlp && echo "  ✓ yt-dlp installed"
  PLIST="$HOME/Library/LaunchAgents/com.focuscompanion.autoexpand.plist"
  mkdir -p "$HOME/Library/LaunchAgents"
  sed "s|__DIR__|$DIR|g" "$DIR/com.focuscompanion.autoexpand.plist.template" > "$PLIST"
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load -w "$PLIST"
  echo "  ✓ nightly auto-grow scheduled for 3:00 AM"
fi

echo ""
echo "  ✅ Installed. Send a prompt in Claude Code and the focus page will open."
echo "     Rate clips with 👍 / 👎 (or the ↑ / ↓ keys) and it learns what you like."
echo "     To remove everything later: ./uninstall.sh"
echo ""
