#!/bin/bash
# Focus Companion — remove the hooks and the nightly job. Leaves your code files
# (and your taste.json) in place; delete the folder yourself to fully remove.
DIR="$(cd "$(dirname "$0")" && pwd)"

# 1) remove our hooks from ~/.claude/settings.json (leave any others untouched)
python3 - "$DIR" <<'PY'
import json, os, sys
DIR = sys.argv[1]
path = os.path.expanduser("~/.claude/settings.json")
try:
    s = json.load(open(path))
except Exception:
    s = {}
hooks = s.get("hooks", {})
ours = {f"bash '{DIR}/focus-start.sh'", f"bash '{DIR}/focus-stop.sh'"}
for ev in ("UserPromptSubmit", "Stop"):
    arr = hooks.get(ev, [])
    kept = [g for g in arr if not any(h.get("command") in ours for h in g.get("hooks", []))]
    if kept:
        hooks[ev] = kept
    else:
        hooks.pop(ev, None)
json.dump(s, open(path, "w"), indent=2)
print("  ✓ hooks removed")
PY

# 2) stop & remove the nightly job
PLIST="$HOME/Library/LaunchAgents/com.focuscompanion.autoexpand.plist"
if [ -f "$PLIST" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "  ✓ nightly job removed"
fi

# 3) stop the local server if running
lsof -ti tcp:7654 2>/dev/null | xargs kill 2>/dev/null || true
echo "  ✅ uninstalled. Your files are untouched — delete this folder to fully remove."
